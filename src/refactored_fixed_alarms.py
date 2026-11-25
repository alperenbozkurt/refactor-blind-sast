"""False alarms on the refactorings of the FIXED programs, per detector (file level).

Usage: python -I src/refactored_fixed_alarms.py [--json results/refactored_fixed_alarms.json]
Reads existing results only. A detector that flags everything would show 0% detection loss; this
measures how often each detector flags a fixed program, before and after refactoring, on the verified
programs (attack fires on the vulnerable original, not on the fixed one). Refactorings of fixed programs
on which the attack fires are reported separately and left out of the rate.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare_variants import DETECTORS, EXP, detections, exploitable, ground_truth, wilson  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(EXP / "results" / "refactored_fixed_alarms.json"))
    a = ap.parse_args()
    det = detections("flagged")
    ex = exploitable()
    truth = set(ground_truth(ex))
    out = {}
    for d in DETECTORS:
        orig_n = orig_f = ref_n = ref_f = attack_fires = 0
        for (tool, i, kind, v), flagged in det.items():
            if tool != d or kind != "safe" or i not in truth:
                continue
            if v == "ORIG":
                orig_n += 1
                orig_f += flagged
            elif ex.get((i, "safe", v)):
                attack_fires += 1
            else:
                ref_n += 1
                ref_f += flagged
        lo, hi = wilson(ref_f, ref_n)
        out[d] = dict(fixed_originals=[orig_f, orig_n], refactored_fixed=[ref_f, ref_n],
                      refactored_fixed_pct=round(100 * ref_f / ref_n, 1) if ref_n else None,
                      wilson95=[round(100 * lo, 1), round(100 * hi, 1)],
                      refactored_fixed_where_attack_fires=attack_fires)
        print(f"{d:<18} fixed originals {orig_f}/{orig_n}   refactored fixed {ref_f}/{ref_n} "
              f"({out[d]['refactored_fixed_pct']}%)   attack fires on {attack_fires}")
    Path(a.json).write_text(json.dumps(out, indent=1))
    print("saved", Path(a.json).relative_to(EXP))


if __name__ == "__main__":
    main()
