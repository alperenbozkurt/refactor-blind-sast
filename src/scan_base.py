"""Scan the neutralised PySASTBench base programs and report what each tool detects.

Usage: python -I src/scan_base.py
Writes results/base_detections.json and prints a per-CWE summary.

Uses the Bandit/Semgrep wrappers in src/sast.py. A finding counts only if
  * one of its CWE ids is in the accepted set of the pair's CWE,
  * it is not on an import line, and
  * its severity is at least MEDIUM (Bandit) / WARNING (Semgrep). Low-severity audit checks such as
    Bandit B603/B607 fire on *every* subprocess call, including the fixed programs, so they say
    nothing about the vulnerability.
``detected`` is file level; ``in_function`` additionally requires the finding to lie inside the
vulnerable function named in the dataset (``vul_position``), located in each file separately.
"""
import ast
import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from sast import SEMGREP_CONFIGS, TOOLS, import_lines, run_bandit, run_semgrep  # noqa: E402

DATA = EXP / "data" / "pysastbench"
ACCEPT = {
    22: {22, 23, 36, 73},
    77: {77, 78},
    79: {79, 80, 116},
    89: {89},
    94: {78, 94, 95},
    502: {20, 502},
}


LOW = {"LOW", "INFO"}


def counts(f, accept):
    return accept & set(f["cwes"]) and str(f.get("severity") or "").upper() not in LOW


def function_lines(path, position):
    """Line range of ``Class.method`` or ``function`` in the file, or None."""
    tree = ast.parse(path.read_text())
    parts = position.split(".")
    scope = tree.body
    node = None
    for p in parts:
        node = next((n for n in scope if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == p), None)
        if node is None:
            return None
        scope = node.body
    return node.lineno, node.end_lineno


def main():
    raw_b, findings, _ = run_bandit(DATA)
    for name in SEMGREP_CONFIGS:
        findings += run_semgrep(DATA, name)[1]
    by_file = collections.defaultdict(list)
    for f in findings:
        by_file[str(Path(f["file"]).resolve())].append(f)
    rows = []
    for d in sorted(DATA.iterdir()):
        meta = json.loads((d / "meta.json").read_text())
        accept = ACCEPT[meta["cwe"]]
        for kind in ("vuln", "safe"):
            p = (d / f"{kind}.py").resolve()
            span = function_lines(p, meta["vul_position"])
            imp = import_lines(p)
            for tool in TOOLS:
                fs = [f for f in by_file[str(p)] if f["tool"] == tool and f["line"] not in imp]
                match = [f for f in fs if counts(f, accept)]
                in_fn = [f for f in match if span and span[0] <= f["line"] <= span[1]]
                rows.append(dict(id=meta["id"], cwe=meta["cwe"], kind=kind, tool=tool, detected=bool(match),
                                 in_function=bool(in_fn), rules=sorted({f["rule"] for f in match}),
                                 other_rules=sorted({f["rule"] for f in fs if f not in match}), span_found=bool(span)))
    (EXP / "results").mkdir(exist_ok=True)
    (EXP / "results" / "base_detections.json").write_text(json.dumps(rows, indent=1))

    for k in ("vuln", "safe"):
        print(f"vulnerable function located in {k}:", sum(r["span_found"] for r in rows if r["kind"] == k and r["tool"] == "bandit"), "/ 120")
    cwes = sorted({r["cwe"] for r in rows})
    head = "CWE".ljust(6) + "".join(f"{t:>34}" for t in TOOLS)
    print("\nvulnerable: detected/20 (in function)  |  safe: flagged (in function)")
    print(head)
    for c in cwes + ["all"]:
        line = f"{c!s:<6}"
        for t in TOOLS:
            sel = [r for r in rows if r["tool"] == t and (c == "all" or r["cwe"] == c)]
            v = [r for r in sel if r["kind"] == "vuln"]
            s = [r for r in sel if r["kind"] == "safe"]
            line += (f"{sum(r['detected'] for r in v):>5}/{len(v)} ({sum(r['in_function'] for r in v):>3})"
                     f" | FP {sum(r['detected'] for r in s):>2} ({sum(r['in_function'] for r in s):>2})")
        print(line)


if __name__ == "__main__":
    main()
