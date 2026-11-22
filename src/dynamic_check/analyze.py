"""Combine the dynamic check with the SAST results.

Usage: python -I src/dynamic_check/analyze.py --cwe 77 [--cwe 89 ...] [--show-diff]
Reads results/dynamic/<cwe>.json, results/base_detections.json and results/variant_detections.json.

For each refactoring of a vulnerable program whose original is exploitable:
  * ``exploitable``  the attack input still succeeds on the refactoring;
  * ``same``         with the normal input it prints the same output and runs the same external
                     commands as the original (after masking paths, timestamps and ids).
A SAST detection that disappears on an exploitable refactoring is a real miss ("blinded"); one that
disappears on a non-exploitable refactoring means the LLM changed (usually fixed) the code.
"""
import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[2]
TOOLS = ["bandit", "semgrep-bandit", "semgrep-registry"]


def args(name):
    return [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == name]


def observable(run):
    return run["stdout"], tuple(run["commands"]), run["exit"]


def load(cwes):
    dyn = [r for c in cwes for r in json.loads((EXP / "results" / "dynamic" / f"{c}.json").read_text())]
    base = {(r["id"], r["kind"]): r for r in dyn if r["variant"] == "ORIG"}
    sast_b = {(r["id"], r["kind"], r["tool"]): r["detected"] for r in json.loads((EXP / "results" / "base_detections.json").read_text())}
    sast_v = {(r["id"], r["kind"], r["variant"], r["tool"]): r["detected"]
              for r in json.loads((EXP / "results" / "variant_detections.json").read_text())}
    rows = []
    for r in dyn:
        if r["variant"] == "ORIG":
            continue
        b = base[(r["id"], r["kind"])]
        row = dict(id=r["id"], kind=r["kind"], variant=r["variant"], model=r["variant"].split("_")[0],
                   prompt=r["variant"].split("_")[1], base_exploitable=b["attack"]["exploited"],
                   exploitable=r["attack"]["exploited"], same=observable(r["normal"]) == observable(b["normal"]))
        for t in TOOLS:
            row[t + "_base"] = sast_b[(r["id"], r["kind"], t)]
            row[t] = sast_v.get((r["id"], r["kind"], r["variant"], t))
        rows.append(row)
    return base, rows


def main():
    cwes = args("--cwe")
    base, rows = load(cwes)
    ok_ids = sorted({i for (i, k), b in base.items() if k == "vuln" and b["attack"]["exploited"]
                     and not base[(i, "safe")]["attack"]["exploited"]})
    print(f"CWE {','.join(cwes)}: attack works on {len(ok_ids)} original programs and on none of their fixed versions")
    bad_fix = sorted(i for (i, k), b in base.items() if k == "safe" and b["attack"]["exploited"])
    if bad_fix:
        print("  fixed version still exploitable:", ", ".join(bad_fix))
    vul = [r for r in rows if r["kind"] == "vuln" and r["id"] in ok_ids]

    print("\nRefactorings of the vulnerable programs:")
    print(f"{'variant':<11} {'n':>3} {'still exploitable':>18} {'same behaviour':>15} {'both':>5}")
    for v in sorted({r["variant"] for r in vul}):
        rs = [r for r in vul if r["variant"] == v]
        print(f"{v:<11} {len(rs):>3} {sum(r['exploitable'] for r in rs):>18} {sum(r['same'] for r in rs):>15}"
              f" {sum(r['exploitable'] and r['same'] for r in rs):>5}")

    print("\nSAST on refactorings whose original the tool detected:")
    print(f"{'tool':<17} {'kept':>5} {'lost, still exploitable (blinded)':>34} {'lost, not exploitable':>22}")
    for t in TOOLS:
        rs = [r for r in vul if r[t + "_base"]]
        kept = sum(bool(r[t]) for r in rs)
        blind = [r for r in rs if not r[t] and r["exploitable"]]
        gone = [r for r in rs if not r[t] and not r["exploitable"]]
        print(f"{t:<17} {kept:>5} {len(blind):>34} {len(gone):>22}")
        if blind:
            print("    blinded:", ", ".join(f"{r['id']}/{r['variant']}" for r in blind))

    print("\nSafe programs: refactorings of fixed versions that became exploitable:",
          sum(r["exploitable"] for r in rows if r["kind"] == "safe"), "/", sum(r["kind"] == "safe" for r in rows))
    if "--show-diff" in sys.argv:
        print("\nNon-exploitable refactorings of vulnerable programs:")
        for r in vul:
            if not r["exploitable"]:
                print(f"  {r['id']}/{r['variant']}  same-normal-behaviour={r['same']}")


if __name__ == "__main__":
    main()
