"""Scan every LLM refactoring with Bandit and both Semgrep configurations.

Usage: python -I src/scan_variants.py
Writes results/variant_detections.json (one row per variant x tool) with the same matching rules as
src/scan_base.py. ``in_function`` is only defined when the refactoring kept the vulnerable function's
name (``span_found``); refactorings often move or rename it, so ``detected`` (file level) is the
primary measure for variants. Retention is computed later, after the behaviour check, against the
base program's detection by the same tool.
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scan_base import ACCEPT, DATA, EXP, SEMGREP_CONFIGS, TOOLS, counts, function_lines, import_lines, run_bandit, run_semgrep  # noqa: E402

VARIANTS = EXP / "data" / "llm_variants"


def main():
    _, findings, tb = run_bandit(VARIANTS)
    timing = {"bandit": tb}
    for name in SEMGREP_CONFIGS:
        _, fs, ts = run_semgrep(VARIANTS, name)
        findings += fs
        timing[name] = ts
    by_file = collections.defaultdict(list)
    for f in findings:
        by_file[str(Path(f["file"]).resolve())].append(f)
    metas = {d.name: json.loads((d / "meta.json").read_text()) for d in DATA.iterdir()}
    rows = []
    for p in sorted(VARIANTS.glob("*/*/*/main.py")):
        i, kind, variant = p.parts[-4], p.parts[-3], p.parts[-2]
        meta = metas[i]
        try:
            span = function_lines(p, meta["vul_position"])
        except SyntaxError:
            span = None
        imp = import_lines(p)
        for tool in TOOLS:
            fs = [f for f in by_file[str(p.resolve())] if f["tool"] == tool and f["line"] not in imp]
            match = [f for f in fs if counts(f, ACCEPT[meta["cwe"]])]
            rows.append(dict(id=i, cwe=meta["cwe"], kind=kind, variant=variant, tool=tool, detected=bool(match),
                             in_function=bool(span and any(span[0] <= f["line"] <= span[1] for f in match)),
                             span_found=bool(span), rules=sorted({f["rule"] for f in match})))
    out = EXP / "results" / "variant_detections.json"
    out.write_text(json.dumps(rows, indent=1))
    print(f"{len(rows) // len(TOOLS)} variants scanned in {', '.join(f'{k} {v:.0f}s' for k, v in timing.items())}")
    print(f"saved {out.relative_to(EXP)}")


if __name__ == "__main__":
    main()
