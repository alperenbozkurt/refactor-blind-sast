"""Controlled test: which change to a SQL-building expression makes each analyzer lose the finding?

Usage: .venv/bin/python -I src/sql_literal_experiment.py prepare --work DIR
       .venv/bin/python -I src/sql_literal_experiment.py scan --work DIR [--jobs N]

Each CWE-89 original is rewritten by AST transformation, only at string expressions that build SQL
from dynamic values (f-string, ``%`` or ``+`` concatenation, or ``"...".format``):

  roundtrip    parsed and re-emitted only (control)
  inline       the template stays in the expression: "...{v0}...".format(v0=x)
  local        the template moves to a local variable in the same statement block
  constant     the template moves to a module-level constant
  helper       the unchanged expression moves to a module-level function that returns the query

Every arm is run through the same attack as the dynamic oracle, so a lost finding can be checked
against a flaw that still fires. Generated sources stay in DIR because they derive from the dataset.
Results go to results/codeql/sql_literal_experiment.json.
"""
import argparse
import ast
import builtins
import concurrent.futures as cf
import copy
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "dynamic_check"))
from scan_codeql import OUT, PACK, scan  # noqa: E402
from scan_base import ACCEPT, DATA, EXP, SEMGREP_CONFIGS, counts, import_lines, run_bandit, run_semgrep  # noqa: E402

KEYWORDS = ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "WHERE ", " WHERE", " LIKE", "VALUES", "ORDER BY")
ARMS = ("roundtrip", "inline", "local", "constant", "helper")


def is_sql(text):
    return any(k in text.upper() for k in KEYWORDS)


def esc(text):
    return text.replace("{", "{{").replace("}", "}}")


def from_fstring(node):
    """(template, [(name, expr)]) or None if a format spec is dynamic."""
    parts, args = [], []
    for v in node.values:
        if isinstance(v, ast.Constant):
            parts.append(esc(v.value))
            continue
        name = f"v{len(args)}"
        conv = {115: "!s", 114: "!r", 97: "!a", -1: ""}[v.conversion]
        spec = ""
        if v.format_spec is not None:
            if not all(isinstance(x, ast.Constant) for x in v.format_spec.values):
                return None
            spec = ":" + "".join(x.value for x in v.format_spec.values)
        parts.append("{" + name + conv + spec + "}")
        args.append((name, v.value))
    return "".join(parts), args


def flatten_add(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return flatten_add(node.left) + flatten_add(node.right)
    return [node]


def from_concat(node):
    items = flatten_add(node)
    if not any(isinstance(i, ast.Constant) and isinstance(i.value, str) and is_sql(i.value) for i in items):
        return None
    parts, args = [], []
    for it in items:
        if isinstance(it, ast.Constant) and isinstance(it.value, str):
            parts.append(esc(it.value))
        elif isinstance(it, ast.JoinedStr):
            r = from_fstring(it)
            if r is None:
                return None
            tpl, sub = r
            for old, expr in sub:
                new = f"v{len(args)}"
                tpl = tpl.replace("{" + old + "}", "{" + new + "}").replace("{" + old + "!", "{" + new + "!") \
                         .replace("{" + old + ":", "{" + new + ":")
                args.append((new, expr))
            parts.append(tpl)
        else:
            name = f"v{len(args)}"
            parts.append("{" + name + "}")
            args.append((name, it))
    return "".join(parts), args


def extract(node):
    """(template, keyword args as [(name, expr)], positional [expr]) when node builds SQL."""
    if isinstance(node, ast.JoinedStr):
        text = "".join(v.value for v in node.values if isinstance(v, ast.Constant))
        if is_sql(text) and any(isinstance(v, ast.FormattedValue) for v in node.values):
            r = from_fstring(node)
            return (r[0], r[1], []) if r else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        r = from_concat(node)
        return (r[0], r[1], []) if r and r[1] else None
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format"
            and isinstance(node.func.value, ast.Constant) and isinstance(node.func.value.value, str)
            and is_sql(node.func.value.value)):
        return node.func.value.value, [(k.arg, k.value) for k in node.keywords if k.arg], list(node.args)
    return None


def format_call(receiver, args, pos):
    return ast.Call(ast.Attribute(receiver, "format", ast.Load()), [copy.deepcopy(p) for p in pos],
                    [ast.keyword(n, copy.deepcopy(e)) for n, e in args])


class Rewrite(ast.NodeTransformer):
    def __init__(self, arm, module_names=frozenset()):
        self.arm = arm
        self.module_names = module_names
        self.sites = 0
        self.constants = []
        self.pending = []

    def helper(self, node):
        """Move the expression to a module-level function taking the local names it reads."""
        stored = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        params = sorted({n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
                        - stored - self.module_names - set(dir(builtins)))
        name = f"build_sql_{self.sites}"
        self.sites += 1
        self.constants.append(ast.FunctionDef(name, ast.arguments([], [ast.arg(p) for p in params], None, [], [], None, []),
                                              [ast.Return(copy.deepcopy(node))], [], None, None))
        return ast.Call(ast.Name(name, ast.Load()), [ast.Name(p, ast.Load()) for p in params], [])

    def visit(self, node):
        if isinstance(node, ast.expr):
            found = extract(node)
            if found:
                return self.helper(node) if self.arm == "helper" else self.replace(*found)
        if isinstance(node, ast.stmt):
            saved, self.pending = self.pending, []
            res = super().visit(node)
            pre, self.pending = self.pending, saved
            return pre + [res] if pre else res
        return super().visit(node)

    def replace(self, template, args, pos):
        n = self.sites
        self.sites += 1
        if self.arm == "inline":
            return format_call(ast.Constant(template), args, pos)
        if self.arm == "local":
            name = f"sql_template_{n}"
            self.pending.append(ast.Assign([ast.Name(name, ast.Store())], ast.Constant(template)))
        else:
            name = f"SQL_TEMPLATE_{n}"
            self.constants.append(ast.Assign([ast.Name(name, ast.Store())], ast.Constant(template)))
        return format_call(ast.Name(name, ast.Load()), args, pos)


def build(source, arm):
    tree = ast.parse(source)
    if arm == "roundtrip":
        return ast.unparse(tree), sum(1 for n in ast.walk(tree) if isinstance(n, ast.expr) and extract(n))
    module_names = set()
    for st in tree.body:
        if isinstance(st, (ast.Import, ast.ImportFrom)):
            module_names.update((a.asname or a.name).split(".")[0] for a in st.names)
        elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_names.add(st.name)
        else:
            module_names.update(n.id for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
    tr = Rewrite(arm, frozenset(module_names))
    tree = tr.visit(tree)
    idx = 0
    for i, st in enumerate(tree.body):
        if isinstance(st, (ast.Import, ast.ImportFrom)) or (i == 0 and isinstance(st, ast.Expr)):
            idx = i + 1
    tree.body[idx:idx] = tr.constants
    return ast.unparse(ast.fix_missing_locations(tree)), tr.sites


def prepare(work):
    src = work / "src"
    shutil.rmtree(src, ignore_errors=True)
    manifest = []
    for d in sorted(DATA.glob("89_*")):
        code = (d / "vuln.py").read_text()
        for arm in ARMS:
            out, sites = build(code, arm)
            compile(out, "main.py", "exec")
            p = src / d.name / arm / "main.py"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(out)
            manifest.append(dict(id=d.name, arm=arm, sites=sites, path=str(p)))
    (work / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(len(manifest), "targets; programs without a rewritable site:",
          sorted({m["id"] for m in manifest if m["sites"] == 0}))


def attack_runner():
    """Run the oracle's attack input on one file using the isolated dynamic environment."""
    from run_web import run_case
    specs = json.loads((EXP / "src" / "dynamic_check" / "specs" / "89_web.json").read_text())
    specs = {s["id"]: s for s in specs} if isinstance(specs, list) else specs

    def attack(pid, path):
        spec = specs[pid]
        return bool(run_case(Path(path), spec, "attack", spec.get("extra", {})).get("in_sql"))
    return attack


def run(work, jobs):
    version = json.loads((OUT / "versions.json").read_text())
    pack_ref = f"{PACK}@{version['pack']}"
    manifest = [m for m in json.loads((work / "manifest.json").read_text()) if m["sites"] > 0]
    accept = ACCEPT[89]
    by_path = {str(Path(m["path"]).resolve()): m for m in manifest}
    for m in manifest:
        m["detected"] = {}

    src = work / "src"
    findings = run_bandit(src)[1]
    for name in SEMGREP_CONFIGS:
        findings += run_semgrep(src, name)[1]
    hits = {}
    for f in findings:
        m = by_path.get(str(Path(f["file"]).resolve()))
        if m and f["line"] not in import_lines(m["path"]) and counts(f, accept):
            hits.setdefault((m["id"], m["arm"]), set()).add(f["tool"])
    for m in manifest:
        for tool in ("bandit", *SEMGREP_CONFIGS):
            m["detected"][tool] = tool in hits.get((m["id"], m["arm"]), set())

    scratch = work / "db"
    scratch.mkdir(exist_ok=True)
    with cf.ThreadPoolExecutor(jobs) as ex:
        futs = {ex.submit(scan, (m["id"], m["arm"], "sql"), Path(m["path"]), scratch, pack_ref): m for m in manifest}
        for fut in cf.as_completed(futs):
            r = fut.result()
            m = futs[fut]
            m["codeql_ok"] = r["ok"]
            m["detected"]["codeql"] = any(counts(f, accept) for f in r["findings"])

    attack = attack_runner()
    with cf.ThreadPoolExecutor(jobs) as ex:
        for m, fired in zip(manifest, ex.map(lambda m: attack(m["id"], m["path"]), manifest)):
            m["attack_fires"] = fired
    for m in manifest:
        m.pop("path")
    (OUT / "sql_literal_experiment.json").write_text(json.dumps(manifest, indent=1))
    print("codeql failed:", [(m["id"], m["arm"]) for m in manifest if not m["codeql_ok"]])
    ids = sorted({m["id"] for m in manifest})
    get = {(m["id"], m["arm"]): m for m in manifest}
    for arm in ARMS:
        fired = sum(get[(i, arm)]["attack_fires"] for i in ids)
        print(f"{arm:<10} attack fires {fired}/{len(ids)}  " + "  ".join(
            f"{t}: {sum(get[(i, arm)]['detected'][t] for i in ids)}" for t in ("bandit", *SEMGREP_CONFIGS, "codeql")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["prepare", "scan"])
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    (prepare if a.step == "prepare" else lambda w: run(w, a.jobs))(a.work)


if __name__ == "__main__":
    main()
