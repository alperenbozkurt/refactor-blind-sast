"""Do behaviour-preserving refactorings blind the detectors? SAST tools and LLM reviewers side by
side, with the dynamic check deciding whether a lost detection is a real miss or a real fix.

Usage: python -I src/compare_variants.py [--json results/blinding.json]

Metrics:
  located  SAST: a matching finding inside the vulnerable function; LLM: a matching CWE naming the
           vulnerable function or a line inside it. (primary SAST measure)
  flagged  SAST: a matching finding anywhere in the file; LLM: any matching CWE. (file level)
A refactoring routinely moves the vulnerable code into a helper, so "located" drops even when the
tool still reports the flaw elsewhere; "flagged" is therefore the fair measure of true blinding.

Ground truth = programs whose attack input fires on the original vulnerable version and NOT on the
fixed version (results/dynamic/*.json). For each refactoring of such a program that a detector found
in the original:
  kept     still found
  blinded  no longer found AND the attack still fires on the refactoring  (real miss)
  fixed    no longer found AND the attack no longer fires                 (refactoring removed it)

LLM answers use the first answer only (rep 0) so original and refactoring are compared like-for-like;
the repeat-to-repeat disagreement on the originals is reported as the single-answer noise floor.
"""
import collections
import glob
import json
import math
import random
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
SAST = ["bandit", "semgrep-bandit", "semgrep-registry"]
LLM = ["kimi", "sonnet"]
CODEQL = "codeql"  # reported on its own; not pooled with the three pattern-rule configurations
DETECTORS = SAST + [CODEQL] + LLM
CWES = [22, 77, 79, 89, 94, 502]


def jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def detections(metric):
    """(detector, id, kind, variant) -> bool detected, for every detector/program/variant."""
    field = "in_function" if metric == "located" else "detected"
    llm_field = "located" if metric == "located" else "flagged"
    det = {}
    for r in json.load(open(EXP / "results" / "base_detections.json")):
        det[(r["tool"], r["id"], r["kind"], "ORIG")] = bool(r[field])
    for r in json.load(open(EXP / "results" / "variant_detections.json")):
        det[(r["tool"], r["id"], r["kind"], r["variant"])] = bool(r[field])
    for r in json.load(open(EXP / "results" / "codeql_detections.json")):
        det[(r["tool"], r["id"], r["kind"], r["variant"])] = bool(r[field])
    for m in LLM:
        for r in jsonl(EXP / "results" / "llm_scan" / f"{m}__base.jsonl"):
            if r["parse_ok"] and r.get("rep", 0) == 0:
                det[(m, r["id"], r["kind"], "ORIG")] = bool(r[llm_field])
        for r in jsonl(EXP / "results" / "llm_scan" / f"{m}__variants.jsonl"):
            if r["parse_ok"]:
                det[(m, r["id"], r["kind"], r["variant"])] = bool(r[llm_field])
    return det


def exploitable():
    """(id, kind, variant) -> attack fired. Merge every dynamic result file."""
    ex = {}
    for f in glob.glob(str(EXP / "results" / "dynamic" / "*.json")):
        for r in json.load(open(f)):
            ex[(r["id"], r["kind"], r["variant"])] = bool(r.get("exploitable", r.get("attack", {}).get("exploited")))
    return ex


def ground_truth(ex):
    return sorted({i for (i, k, v) in ex if k == "vuln" and v == "ORIG"
                   and ex[(i, "vuln", "ORIG")] and not ex.get((i, "safe", "ORIG"), True)})


def classify(det, ex, truth, variants, detector, ids=None):
    """kept/blinded/fixed counts over refactorings of ground-truth programs the detector found originally."""
    ids = truth if ids is None else [i for i in truth if i in ids]
    c = collections.Counter()
    base = 0
    for i in ids:
        if not det.get((detector, i, "vuln", "ORIG")):
            continue
        base += 1
        for v in variants:
            dk = (detector, i, "vuln", v)
            ek = (i, "vuln", v)
            if dk not in det or ek not in ex:
                continue
            if not ex[ek]:
                c["fixed"] += 1        # the refactoring removed the flaw (whatever the detector says)
            elif det[dk]:
                c["kept"] += 1
            else:
                c["blinded"] += 1
    return base, c


def pairs(det, ex, truth, variants, detector):
    """(program, blinded) for every still-vulnerable refactoring of an original the detector found."""
    out = []
    for i in truth:
        if not det.get((detector, i, "vuln", "ORIG")):
            continue
        for v in variants:
            dk, ek = (detector, i, "vuln", v), (i, "vuln", v)
            if dk in det and ek in ex and ex[ek]:
                out.append((i, not det[dk]))
    return out


def wilson(k, n, z=1.959964):
    """Wilson score 95% interval for a binomial proportion."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def cluster_bootstrap(pr, reps=5000, seed=2026):
    """95% interval resampling programs, since refactorings of one program are not independent."""
    by = collections.defaultdict(list)
    for i, b in pr:
        by[i].append(b)
    progs = sorted(by)
    if not progs:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    vals = []
    for _ in range(reps):
        s = [rng.choice(progs) for _ in progs]
        n = sum(len(by[p]) for p in s)
        vals.append(sum(sum(by[p]) for p in s) / n)
    vals.sort()
    return (vals[int(0.025 * reps)], vals[int(0.975 * reps) - 1])


def noise_floor():
    """On originals the LLM flagged in rep 0, how often do the other repeats disagree?"""
    out = {}
    for m in LLM:
        reps = collections.defaultdict(dict)
        for r in jsonl(EXP / "results" / "llm_scan" / f"{m}__base.jsonl"):
            if r["parse_ok"]:
                reps[(r["id"], r["kind"])][r.get("rep", 0)] = (bool(r["flagged"]), bool(r["located"]))
        n = collections.Counter()
        flip = collections.Counter()
        for (i, k), d in reps.items():
            if k != "vuln" or 0 not in d:
                continue
            for rr in (1, 2):
                if rr not in d:
                    continue
                for mi, lab in ((0, "flagged"), (1, "located")):
                    if d[0][mi]:
                        n[lab] += 1
                        flip[lab] += not d[rr][mi]
        out[m] = {lab: (flip[lab], n[lab]) for lab in ("flagged", "located")}
    return out


def pct(c):
    still = c["kept"] + c["blinded"]
    return 100 * c["blinded"] / still if still else 0.0


def main():
    ex = exploitable()
    truth = ground_truth(ex)
    report = {"ground_truth_programs": len(truth)}
    print(f"Ground-truth programs (attack fires on original, not on fix): {len(truth)}/120\n")

    for metric in ("located", "flagged"):
        det = detections(metric)
        variants = sorted({v for (_, _, _, v) in det if v != "ORIG"})
        print(f"===== metric = {metric} =====")
        print(f"{'detector':<17}{'found_orig':>11}{'kept':>6}{'blinded':>8}{'fixed':>6}{'blind%':>8}"
              f"{'Wilson 95%':>17}{'cluster boot 95%':>19}")
        report[metric] = {}
        for t in DETECTORS:
            base, c = classify(det, ex, truth, variants, t)
            pr = pairs(det, ex, truth, variants, t)
            w = wilson(c["blinded"], c["kept"] + c["blinded"])
            bt = cluster_bootstrap(pr)
            report[metric][t] = dict(found_orig=base, **c, blind_pct=round(pct(c), 2),
                                     wilson95=[round(100 * x, 2) for x in w],
                                     cluster_boot95=[round(100 * x, 2) for x in bt])
            print(f"{t:<17}{base:>11}{c['kept']:>6}{c['blinded']:>8}{c['fixed']:>6}{pct(c):>7.2f}%"
                  f"   [{100*w[0]:5.2f},{100*w[1]:6.2f}]   [{100*bt[0]:5.2f},{100*bt[1]:6.2f}]")
        print()

    # per-CWE blinding, flagged metric (the fair one)
    det = detections("flagged")
    variants = sorted({v for (_, _, _, v) in det if v != "ORIG"})
    bycwe = {c: [i for i in truth if int(i.split("_")[0]) == c] for c in CWES}
    print("===== blinded refactorings per CWE (flagged metric) =====")
    print(f"{'detector':<17}" + "".join(f"{c:>8}" for c in CWES))
    report["per_cwe_flagged"] = {}
    for t in DETECTORS:
        line = f"{t:<17}"
        report["per_cwe_flagged"][t] = {}
        for c in CWES:
            base, cc = classify(det, ex, truth, variants, t, set(bycwe[c]))
            line += f"{cc['blinded']:>4}/{base * len(variants) if base else 0:<3}"
            report["per_cwe_flagged"][t][c] = dict(base=base, blinded=cc["blinded"], kept=cc["kept"], fixed=cc["fixed"])
        print(line)
    print("  (blinded / refactoring-instances-from-detected-originals)\n")

    # which prompt blinds most (flagged, SAST only, aggregated)
    print("===== SAST blinding by refactor prompt (flagged metric, 3 SAST tools pooled) =====")
    per = collections.Counter()
    tot = collections.Counter()
    for t in SAST:
        for i in truth:
            if not det.get((t, i, "vuln", "ORIG")):
                continue
            for v in variants:
                dk, ek = (t, i, "vuln", v), (i, "vuln", v)
                if dk not in det or ek not in ex or not ex[ek]:
                    continue  # only refactorings where the flaw still fires
                tot[v] += 1
                per[v] += not det[dk]
    for v in variants:
        print(f"  {v:<12} blinded {per[v]:>3} / {tot[v]:<3}  ({100*per[v]/tot[v] if tot[v] else 0:.1f}%)")
    report["per_prompt_sast_flagged"] = {v: dict(blinded=per[v], total=tot[v]) for v in variants}

    print("\n===== LLM single-answer noise floor (disagreement vs rep0 on originals) =====")
    nf = noise_floor()
    for m, d in nf.items():
        print(f"  {m}: flagged {d['flagged'][0]}/{d['flagged'][1]} = {100*d['flagged'][0]/d['flagged'][1] if d['flagged'][1] else 0:.1f}%"
              f"   located {d['located'][0]}/{d['located'][1]} = {100*d['located'][0]/d['located'][1] if d['located'][1] else 0:.1f}%")
    report["llm_noise_floor"] = {m: {k: list(v) for k, v in d.items()} for m, d in nf.items()}

    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps(report, indent=1))
        print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
