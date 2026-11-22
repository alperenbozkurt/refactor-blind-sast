"""Compare SAST tools and LLM reviewers on the base programs.

Usage: python -I src/compare_detectors.py [--trial] [--claude-dir DIR]
Reads results/base_detections.json (SAST), results/llm_scan/<model>__base.jsonl (src/llm_scan.py),
with --trial the local Qwen trial run, and, if given, the isolated Claude trial reviews (DIR/batch*/results.json, keyed by the anonymous ids in
results/llm_scan/anon_key.json). Claude reviews are scored with the same rules as llm_scan.py and
saved to results/llm_scan/claude.jsonl. Prints one table per detector and CWE.
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from llm_scan import majority, parse, score  # noqa: E402
from scan_base import EXP  # noqa: E402

RES = EXP / "results"


def load_claude(claude_dir):
    key = {k["anon"]: k for k in json.loads((RES / "llm_scan" / "anon_key.json").read_text())}
    rows = []
    for f in sorted(Path(claude_dir).glob("batch*/results.json")):
        for anon, ans in json.loads(f.read_text()).items():
            s = key[anon]
            p = parse(json.dumps(ans))
            rows.append(dict(s, model="claude-opus-5-5 (isolated session)", raw=ans, parse_ok=p is not None,
                             **(score(s, p) if p else dict(flagged=None, located=None, any_finding=None))))
    (RES / "llm_scan" / "claude.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return rows


def main():
    detectors = collections.OrderedDict()
    sast = json.loads((RES / "base_detections.json").read_text())
    for tool in ("bandit", "semgrep-bandit", "semgrep-registry"):
        detectors[tool] = [dict(id=r["id"], cwe=r["cwe"], kind=r["kind"], flagged=r["detected"], located=r["in_function"])
                           for r in sast if r["tool"] == tool]
    for f in sorted((RES / "llm_scan").glob("*__base.jsonl")):
        rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        detectors[f.stem.split("__")[0]] = majority(rows)  # one row per program (majority over repeats)
    if "--trial" in sys.argv:  # first trial run (28 Oct): local Qwen, before the API setup
        f = RES / "llm_scan" / "qwen2.5-coder_14b.jsonl"
        if f.exists():
            detectors["qwen (trial)"] = [r for r in map(json.loads, f.read_text().splitlines()) if r["parse_ok"]]
    if "--claude-dir" in sys.argv:
        detectors["claude (trial)"] = [r for r in load_claude(sys.argv[sys.argv.index("--claude-dir") + 1]) if r["parse_ok"]]

    cwes = sorted({r["cwe"] for r in sast})
    print("vulnerable: found in the right function / n   |   fixed: false alarms / n")
    print(f"{'detector':<22}" + "".join(f"{c:>14}" for c in cwes) + f"{'all':>16}{'FP':>12}")
    for name, rows in detectors.items():
        line = f"{name:<22}"
        for c in cwes + ["all"]:
            v = [r for r in rows if r["kind"] == "vuln" and (c == "all" or r["cwe"] == c)]
            line += f"{sum(bool(r['located']) for r in v):>{11 if c != 'all' else 13}}/{len(v):<3}"
        s = [r for r in rows if r["kind"] == "safe"]
        line += f"{sum(bool(r['flagged']) for r in s):>8}/{len(s):<3}"
        print(line)


if __name__ == "__main__":
    main()
