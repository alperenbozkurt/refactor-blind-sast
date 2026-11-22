"""Controlled test: does table-based dispatch explain CodeQL's lost command-injection detections?

Usage: python -I src/dispatch_experiment.py prepare --work DIR
       python -I src/dispatch_experiment.py scan --work DIR [--jobs N]

Two directions, on CWE-77 only:

  devirtualize  Refactorings CodeQL lost although the attack still fires. Each call through a
                dispatch table is replaced by an if/elif chain of direct calls to the table's entries;
                the original dynamic call stays in the final else, so behaviour is unchanged.
  introduce     Original vulnerable programs. The branches of the largest ``if x == <constant>`` chain
                are moved to helper functions and then
                  roundtrip  left untouched (only parsed and unparsed; control for formatting),
                  direct     called directly from the chain (control for the extraction),
                  table      called through a module-level dictionary.

Only the table arm differs from the direct arm in how the helper is reached. Generated sources stay
in DIR because they derive from the dataset. Results go to results/codeql/dispatch_experiment.json.
"""
import argparse
import collections
import concurrent.futures as cf
import copy
import json
import sys
from pathlib import Path
import ast

sys.path.insert(0, str(Path(__file__).parent))
from scan_codeql import DATA, EXP, OUT, PACK, VARIANTS, scan  # noqa: E402
from scan_base import ACCEPT, counts  # noqa: E402
from compare_variants import exploitable  # noqa: E402
from shell_sinks import shell_sink_lines  # noqa: E402


def last_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def tables_of(tree):
    """Last component of a name -> [(key expr, callee expr)] for dicts whose values are callables."""
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            targets, value = n.targets, n.value
        elif isinstance(n, ast.AnnAssign) and n.value is not None:
            targets, value = [n.target], n.value
        else:
            continue
        if not isinstance(value, ast.Dict) or not value.keys:
            continue
        if not all(isinstance(k, (ast.Constant, ast.Name, ast.Attribute)) for k in value.keys):
            continue
        if not all(isinstance(v, (ast.Name, ast.Attribute, ast.Lambda)) for v in value.values):
            continue
        for t in targets:
            if last_name(t):
                out[last_name(t)] = list(zip(value.keys, value.values))
    return out


def lookup(expr):
    """(table name, key expr) when expr is T[key] or T.get(key, ...)."""
    if isinstance(expr, ast.Subscript) and last_name(expr.value):
        return last_name(expr.value), expr.slice
    if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "get"
            and last_name(expr.func.value) and expr.args):
        return last_name(expr.func.value), expr.args[0]
    return None


def side_effect_free(expr):
    return not any(isinstance(n, (ast.Call, ast.Await, ast.Yield, ast.NamedExpr)) for n in ast.walk(expr))


class SwapCallee(ast.NodeTransformer):
    def __init__(self, pos, callee):
        self.pos, self.callee = pos, callee

    def visit_Call(self, node):
        self.generic_visit(node)
        if (node.lineno, node.col_offset) == self.pos:
            node.func = copy.deepcopy(self.callee)
        return node


class Devirtualize(ast.NodeTransformer):
    def __init__(self, tables):
        self.tables = tables
        self.bind = {}
        self.done = 0

    def _function(self, node):
        saved = self.bind
        self.bind = dict(saved)
        for n in ast.walk(node):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                found = lookup(n.value)
                if found and found[0] in self.tables:
                    self.bind[n.targets[0].id] = found
        self.generic_visit(node)
        self.bind = saved
        return node

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function

    def _resolve(self, call):
        found = None
        if isinstance(call.func, ast.Name) and call.func.id in self.bind:
            found = self.bind[call.func.id]
        elif isinstance(call.func, ast.Subscript):
            found = lookup(call.func)
        if found and found[0] in self.tables and side_effect_free(found[1]):
            return found
        return None

    def _statement(self, node):
        for call in ast.walk(node):
            if isinstance(call, ast.Call):
                found = self._resolve(call)
                if found:
                    return self._expand(node, call, *found)
        return node

    visit_Expr = _statement
    visit_Assign = _statement
    visit_AnnAssign = _statement
    visit_Return = _statement

    def _expand(self, stmt, call, table, key):
        pos = (call.lineno, call.col_offset)
        chain = [copy.deepcopy(stmt)]
        for k, callee in reversed(self.tables[table]):
            body = SwapCallee(pos, callee).visit(copy.deepcopy(stmt))
            test = ast.Compare(copy.deepcopy(key), [ast.Eq()], [copy.deepcopy(k)])
            chain = [ast.If(test, [body], chain)]
        self.done += 1
        return chain[0]


def devirtualize(source):
    tree = ast.parse(source)
    tr = Devirtualize(tables_of(tree))
    tree = tr.visit(tree)
    return ast.unparse(tree), tr.done


def chain_of(node):
    """Branches [(constant, body)], rest-of-chain for ``if x == c: ... elif x == c2: ...``."""
    subject = None
    branches = []
    cur = node
    while True:
        t = cur.test
        ok = isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.ops[0], ast.Eq) \
            and isinstance(t.comparators[0], ast.Constant) and isinstance(t.left, (ast.Name, ast.Attribute))
        if not ok or (subject is not None and ast.dump(t.left) != ast.dump(subject)):
            return None
        subject = t.left
        branches.append((t.comparators[0], cur.body))
        if len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
            cur = cur.orelse[0]
            continue
        return subject, branches, cur.orelse


def names(nodes, kind):
    return {n.id for s in nodes for n in ast.walk(s) if isinstance(n, ast.Name) and isinstance(n.ctx, kind)}


def jumps(body):
    return any(isinstance(n, (ast.Return, ast.Break, ast.Continue, ast.Yield, ast.YieldFrom, ast.Await))
               for s in body for n in ast.walk(s))


def find_chain(tree):
    """(function, parent body, index, chain) of the longest constant-comparison chain."""
    best = None
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for parent in ast.walk(fn):
            body = getattr(parent, "body", None)
            if not isinstance(body, list):
                continue
            for i, st in enumerate(body):
                if isinstance(st, ast.If):
                    c = chain_of(st)
                    if c and len(c[1]) >= 2 and (best is None or len(c[1]) > len(best[3][1])):
                        best = (fn, body, i, c)
    return best


def introduce(source, target_name):
    """Returns {arm: source}, or None when no usable chain exists."""
    tree = ast.parse(source)
    found = find_chain(tree)
    if not found:
        return None
    fn, parent, idx, (subject, branches, tail) = found
    inside = {id(n) for n in ast.walk(parent[idx])}
    later = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in inside}
    bound = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.lineno < parent[idx].lineno:
            bound.add(n.id)
    moved = [(k, b) for k, b in branches if not jumps(b) and not (names(b, ast.Store) & later)]
    if len(moved) < 2:
        return None
    caps = sorted({n for _, b in moved for n in names(b, ast.Load) - names(b, ast.Store) if n in bound})
    keep = [(k, b) for k, b in branches if not any(b is m for _, m in moved)]
    sink_moved = any(isinstance(n, ast.Call) and last_name(n.func) == target_name for _, b in moved for s in b
                     for n in ast.walk(s))

    def helper(n, body):
        return ast.FunctionDef(f"_branch_{n}", ast.arguments([], [ast.arg(c) for c in caps], None, [], [], None, []),
                               copy.deepcopy(body), [], None, None)

    def call(func):
        return ast.Expr(ast.Call(func, [ast.Name(c, ast.Load()) for c in caps], []))

    def rest():
        out = copy.deepcopy(tail)
        for k, b in reversed(keep):
            test = ast.Compare(copy.deepcopy(subject), [ast.Eq()], [copy.deepcopy(k)])
            out = [ast.If(test, copy.deepcopy(b), out)]
        return out

    def build(arm):
        mod = copy.deepcopy(tree)
        f2 = find_chain(mod)
        fn2, parent2, idx2, _ = f2
        defs = [helper(n, b) for n, (_, b) in enumerate(moved)]
        if arm == "direct":
            out = rest()
            for n, (k, _) in reversed(list(enumerate(moved))):
                test = ast.Compare(copy.deepcopy(subject), [ast.Eq()], [copy.deepcopy(k)])
                out = [ast.If(test, [call(ast.Name(f"_branch_{n}", ast.Load()))], out)]
            parent2[idx2:idx2 + 1] = out
        else:
            table = ast.Assign([ast.Name("_BRANCHES", ast.Store())],
                               ast.Dict([copy.deepcopy(k) for k, _ in moved],
                                        [ast.Name(f"_branch_{n}", ast.Load()) for n in range(len(moved))]))
            defs.append(table)
            lookup_ = ast.Call(ast.Attribute(ast.Name("_BRANCHES", ast.Load()), "get", ast.Load()),
                               [copy.deepcopy(subject)], [])
            assign = ast.Assign([ast.Name("_handler", ast.Store())], lookup_)
            test = ast.Compare(ast.Name("_handler", ast.Load()), [ast.IsNot()], [ast.Constant(None)])
            parent2[idx2:idx2 + 1] = [assign, ast.If(test, [call(ast.Name("_handler", ast.Load()))], rest())]
        pos = next(i for i, s in enumerate(mod.body) if any(n is fn2 for n in ast.walk(s)))
        mod.body[pos:pos] = defs
        return ast.unparse(ast.fix_missing_locations(mod))

    return dict(roundtrip=ast.unparse(tree), direct=build("direct"), table=build("table"),
                _info=dict(moved=len(moved), total=len(branches), sink_moved=sink_moved))


def blinded_refactorings():
    rows = json.load(open(EXP / "results" / "codeql_detections.json"))
    det = {(r["id"], r["kind"], r["variant"]): r["detected"] for r in rows}
    ex = exploitable()
    out = []
    for (i, kind, v), d in sorted(det.items()):
        if i.startswith("77_") and kind == "vuln" and v != "ORIG" and not d and ex.get((i, kind, v)) \
                and det.get((i, "vuln", "ORIG")):
            out.append((i, v))
    return out


def prepare(work):
    src = work / "src"
    manifest = []
    for i, v in blinded_refactorings():
        code, n = devirtualize((VARIANTS / i / "vuln" / v / "main.py").read_text())
        if n == 0:
            manifest.append(dict(id=i, variant=v, arm="devirtualize", usable=False))
            continue
        compile(code, "main.py", "exec")
        p = src / "devirtualize" / i / v / "main.py"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(code)
        manifest.append(dict(id=i, variant=v, arm="devirtualize", usable=True, sites=n, path=str(p)))
    for d in sorted(DATA.glob("77_*")):
        meta = json.loads((d / "meta.json").read_text())
        res = introduce((d / "vuln.py").read_text(), meta["vul_position"].split(".")[-1])
        if res is None:
            manifest.append(dict(id=d.name, variant="ORIG", arm="introduce", usable=False))
            continue
        info = res.pop("_info")
        for arm, code in res.items():
            compile(code, "main.py", "exec")
            p = src / "introduce" / d.name / arm / "main.py"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(code)
            manifest.append(dict(id=d.name, variant=arm, arm="introduce", usable=True, path=str(p), **info))
    (work / "manifest.json").write_text(json.dumps(manifest, indent=1))
    c = collections.Counter((m["arm"], m["usable"]) for m in manifest)
    print(dict(c))
    print("unusable:", [(m["id"], m["variant"]) for m in manifest if not m["usable"]])
    print("sink not in a moved branch:", sorted({m["id"] for m in manifest if m.get("sink_moved") is False}))


def run(work, jobs):
    version = json.loads((OUT / "versions.json").read_text())
    pack_ref = f"{PACK}@{version['pack']}"
    manifest = [m for m in json.loads((work / "manifest.json").read_text()) if m["usable"]]
    scratch = work / "db"
    scratch.mkdir(exist_ok=True)
    accept = ACCEPT[77]
    with cf.ThreadPoolExecutor(jobs) as ex:
        futs = {ex.submit(scan, (m["arm"], m["id"], m["variant"]), Path(m["path"]), scratch, pack_ref): m for m in manifest}
        for fut in cf.as_completed(futs):
            r = fut.result()
            m = futs[fut]
            m["ok"] = r["ok"]
            m["error"] = r.get("error", "")[:300]
            m["detected"] = any(counts(f, accept) for f in r["findings"])
            m["rules"] = sorted({f["rule"] for f in r["findings"] if counts(f, accept)})
            sinks = shell_sink_lines(m["path"])
            m["detected_at_shell_sink"] = any(counts(f, accept) and f["line"] in sinks for f in r["findings"])
    for m in manifest:
        m.pop("path", None)
    (OUT / "dispatch_experiment.json").write_text(json.dumps(manifest, indent=1))
    print("failed:", [(m["id"], m["variant"]) for m in manifest if not m["ok"]])
    dev = [m for m in manifest if m["arm"] == "devirtualize"]
    print(f"devirtualize: detection restored {sum(m['detected'] for m in dev)}/{len(dev)}")
    intro = [m for m in manifest if m["arm"] == "introduce" and m["sink_moved"]]
    for arm in ("roundtrip", "direct", "table"):
        sel = [m for m in intro if m["variant"] == arm]
        print(f"introduce/{arm}: detected {sum(m['detected'] for m in sel)}/{len(sel)} (sink branch moved)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["prepare", "scan"])
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    if a.step == "prepare":
        prepare(a.work)
    else:
        run(a.work, a.jobs)


if __name__ == "__main__":
    main()
