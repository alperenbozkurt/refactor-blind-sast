"""Combine the web dynamic check (results/dynamic/<cwe>_web.json) with the SAST results.

Usage: python -I src/dynamic_check/analyze_web.py --cwe 89

For every refactoring of a vulnerable program whose original is exploitable (marker reaches the SQL
text) and whose fixed version is not:
  * exploitable  the marker still reaches the SQL text of the refactoring;
  * same         the normal input produces the same status and the same set of SQL statements
                 (with the marker and integer/quoted literals masked) as the original.
A SAST detection that disappears on an exploitable refactoring is a real miss ("blinded"); one that
disappears on a non-exploitable refactoring means the LLM changed the query (parameterised/removed it).
"""
import json
import re
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[2]
TOOLS = ["bandit", "semgrep-bandit", "semgrep-registry"]


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def sig(run):
    stmts = run.get("statements") or []
    masked = sorted(re.sub(r"'[^']*'|\b\d+\b|ZZINJ", "?", s["sql"]).split() and
                    " ".join(re.sub(r"'[^']*'|\b\d+\b|ZZINJ", "?", s["sql"]).split()) for s in stmts)
    return (run.get("status"), tuple(masked))


def main():
    cwe = arg("--cwe")
    dyn = {(r["id"], r["kind"], r["variant"]): r for r in json.loads((EXP / "results" / "dynamic" / f"{cwe}_web.json").read_text())}
    sast_b = {(r["id"], r["kind"], r["tool"]): r["detected"] for r in json.loads((EXP / "results" / "base_detections.json").read_text())}
    sast_v = {(r["id"], r["kind"], r["variant"], r["tool"]): r["detected"] for r in json.loads((EXP / "results" / "variant_detections.json").read_text())}

    ids = sorted({i for (i, k, v) in dyn if v == "ORIG"})
    ok = [i for i in ids if dyn[(i, "vuln", "ORIG")]["exploitable"] and not dyn[(i, "safe", "ORIG")]["exploitable"]]
    skipped = [i for i in ids if i not in ok]
    print(f"CWE {cwe} (web): marker reaches SQL in {len(ok)} vulnerable originals and no fixed original")
    if skipped:
        print("  not usable as ground truth (vuln not reachable or fixed still flags):", ", ".join(skipped))

    variants = sorted({v for (_, _, v) in dyn if v != "ORIG"})
    vul = {(i, v): dyn[(i, "vuln", v)] for i in ok for v in variants if (i, "vuln", v) in dyn}
    print("\nRefactorings of the vulnerable programs:")
    print(f"{'variant':<11} {'n':>3} {'still injectable':>17} {'same behaviour':>15}")
    for v in variants:
        rs = [r for (i, vv), r in vul.items() if vv == v]
        same = sum(sig(r["normal"]) == sig(dyn[(r["id"], "vuln", "ORIG")]["normal"]) for r in rs)
        print(f"{v:<11} {len(rs):>3} {sum(r['exploitable'] for r in rs):>17} {same:>15}")

    print("\nSAST on refactorings whose original the tool detected:")
    print(f"{'tool':<17} {'kept':>5} {'blinded (lost, injectable)':>27} {'lost, not injectable':>21}")
    for t in TOOLS:
        rs = [(i, v, r) for (i, v), r in vul.items() if sast_b.get((i, "vuln", t))]
        kept = sum(bool(sast_v.get((i, "vuln", v, t))) for i, v, r in rs)
        blind = [(i, v) for i, v, r in rs if not sast_v.get((i, "vuln", v, t)) and r["exploitable"]]
        gone = [(i, v) for i, v, r in rs if not sast_v.get((i, "vuln", v, t)) and not r["exploitable"]]
        print(f"{t:<17} {kept:>5} {len(blind):>27} {len(gone):>21}")
        if blind:
            print("    blinded:", ", ".join(f"{i}/{v}" for i, v in blind))


if __name__ == "__main__":
    main()
