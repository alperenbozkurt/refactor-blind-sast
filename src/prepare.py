"""Turn the PySASTBench synthetic set into neutral base programs.

Usage: python -I src/prepare.py
Reads  data/PySASTBench_raw/SyntheticDataset/<cwe>/<id>_{vul,fix}.py and SyntheticDataset.csv
Writes data/pysastbench/<id>/{vuln,safe}.py, data/pysastbench/<id>/meta.json, data/prepare_log.json

The raw programs announce their vulnerability ("# Vulnerable function ...", vulnerable_render(),
"<!-- XSS vulnerability here -->"). An LLM asked to refactor such code may fix or flag it, so both
versions of every pair are neutralised the same way:
  * comments and docstrings are dropped (ast.unparse also normalises formatting);
  * functions/classes defined in the file whose name starts with vulnerable_/unsafe_/insecure_
    (or Vulnerable/Unsafe/Insecure) lose that prefix; in the fixed version the matching safe_/Safe
    name is renamed to the same neutral name, so the pair stays aligned;
  * HTML (<!-- -->) and JS (//) comments inside template strings are dropped when they contain a
    hint word, and hint words inside short string literals are replaced by neutral words.
Library names such as werkzeug's secure_filename or yaml.safe_load are never touched.
"""
import ast
import builtins
import csv
import difflib
import json
import re
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
RAW = EXP / "data" / "PySASTBench_raw"
OUT = EXP / "data" / "pysastbench"

HINT_PREFIX = re.compile(r"^(vulnerable|unsafe|insecure)_(.+)$|^(Vulnerable|Unsafe|Insecure)([A-Z]\w*)$")
SAFE_PREFIX = re.compile(r"^(safe|secure)_(.+)$|^(Safe|Secure)([A-Z]\w*)$")
HINT_WORDS = re.compile(r"\b(xss )?vulnerab\w*( here)?|\binsecure\b|\bunsafe\b|\binjection\b", re.I)
HINT_SCAN = re.compile(r"vulnerab|insecure|unsafe|exploit|inject|malicious|untrusted|\bcwe\b|\bxss\b", re.I)


def strip_docstrings(tree):
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = n.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) and isinstance(b[0].value.value, str):
                n.body = b[1:] or [ast.Pass()]


def defined_names(tree):
    return {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def neutral(name):
    m = HINT_PREFIX.match(name)
    if not m:
        return None
    return m.group(2) if m.group(2) else m.group(4)


def safe_core(name):
    m = SAFE_PREFIX.match(name)
    if not m:
        return None
    return m.group(2) if m.group(2) else m.group(4)


class Renamer(ast.NodeTransformer):
    def __init__(self, mapping):
        self.m = mapping

    def visit_Name(self, n):
        n.id = self.m.get(n.id, n.id)
        return n

    def visit_Attribute(self, n):
        self.generic_visit(n)
        n.attr = self.m.get(n.attr, n.attr)
        return n

    def _def(self, n):
        self.generic_visit(n)
        n.name = self.m.get(n.name, n.name)
        return n

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _def

    def visit_Constant(self, n):
        if isinstance(n.value, str):
            v = self.m.get(n.value, n.value)  # e.g. url_for("vulnerable_render")
            # comments inside embedded HTML/JS templates
            v = re.sub(r"[ \t]*<!--(?:(?!-->).)*-->", lambda mm: "" if HINT_SCAN.search(mm.group(0)) else mm.group(0), v, flags=re.S)
            v = re.sub(r"[ \t]*//[^\n]*", lambda mm: "" if HINT_SCAN.search(mm.group(0)) else mm.group(0), v)
            if len(v) < 300:
                v = HINT_WORDS.sub(lambda mm: "issue" if mm.group(0)[:1].islower() else "Issue", v)
            n.value = v
        return n


def used_names(tree):
    names = defined_names(tree)
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            names.add(n.attr)
        elif isinstance(n, ast.alias):
            names.add((n.asname or n.name).split(".")[0])
        elif isinstance(n, ast.arg):
            names.add(n.arg)
    return names


def build_mapping(vul_tree, fix_tree):
    taken = used_names(vul_tree) | used_names(fix_tree) | set(dir(builtins))
    vmap, cores = {}, {}
    for name in defined_names(vul_tree):
        core = neutral(name)
        if core:
            new = core if core not in taken else core + "_impl"
            vmap[name], cores[core] = new, new
    fmap = {}
    for name in defined_names(fix_tree):
        core = neutral(name) or safe_core(name)
        if core and core in cores:
            fmap[name] = cores[core]
        elif neutral(name):
            fmap[name] = vmap.get(name, neutral(name))
    return vmap, fmap


def clean(src, mapping):
    tree = ast.parse(src)
    strip_docstrings(tree)
    tree = Renamer(mapping).visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def qualified_names(tree):
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(n.name)
        elif isinstance(n, ast.ClassDef):
            out += [f"{n.name}.{m.name}" for m in n.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return out


def leftover_hints(src):
    return sorted({m.group(0).lower() for m in HINT_SCAN.finditer(src)})


def main():
    rows = {r["TestCase"]: r for r in csv.DictReader(open(RAW / "SyntheticDataset.csv", encoding="utf-8-sig"))}
    log = []
    for vul in sorted((RAW / "SyntheticDataset").glob("*/*_vul.py")):
        case = vul.name[: -len("_vul.py")]
        fix = vul.with_name(case + "_fix.py")
        cwe = int(vul.parent.name)
        vsrc, fsrc = vul.read_text(), fix.read_text()
        vmap, fmap = build_mapping(ast.parse(vsrc), ast.parse(fsrc))
        vclean, fclean = clean(vsrc, vmap), clean(fsrc, fmap)
        pos = rows[case]["Vul Position"].strip()
        pos_clean = ".".join(vmap.get(p, p) for p in pos.split("."))
        paths = qualified_names(ast.parse(vclean))
        if pos_clean not in paths:  # typos in the dataset, e.g. run_diagnotstic
            close = difflib.get_close_matches(pos_clean, paths, n=1, cutoff=0.8)
            log_fix = (pos_clean, close[0] if close else None)
            pos_clean = close[0] if close else pos_clean
        else:
            log_fix = None
        d = OUT / case
        d.mkdir(parents=True, exist_ok=True)
        (d / "vuln.py").write_text(vclean)
        (d / "safe.py").write_text(fclean)
        meta = dict(id=case, cwe=cwe, vul_position=pos_clean, vul_position_raw=pos,
                    renamed_vuln=vmap, renamed_safe=fmap, source="PySASTBench SyntheticDataset @3ad04b7")
        (d / "meta.json").write_text(json.dumps(meta, indent=1))
        log.append(dict(id=case, cwe=cwe, renamed_vuln=vmap, renamed_safe=fmap, position_corrected=log_fix,
                        hints_left_vuln=leftover_hints(vclean), hints_left_safe=leftover_hints(fclean),
                        lines_vuln=vclean.count("\n"), lines_safe=fclean.count("\n")))
    (EXP / "data" / "prepare_log.json").write_text(json.dumps(log, indent=1))
    print(f"{len(log)} pairs written to {OUT.relative_to(EXP)}")
    print("renamed (vuln):", sum(bool(r["renamed_vuln"]) for r in log), "pairs")
    print("vul_position corrected:", [(r["id"], r["position_corrected"]) for r in log if r["position_corrected"]])
    left = [(r["id"], r["hints_left_vuln"]) for r in log if r["hints_left_vuln"]]
    print("hint words still present in vuln:", len(left))
    for i, h in left:
        print("  ", i, h)


if __name__ == "__main__":
    main()
