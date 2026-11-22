"""Analyses requested in review. Reads existing results only; no scanning and no API calls.

Usage: python -I src/review_analyses.py [--json results/review_analyses.json]

  1. dispatch prevalence   Refactorings containing a resolvable dispatch-table call, by the same AST
                           transformation used in the controlled experiment.
  2. CodeQL line check     Whether CWE-77 alarms sit on a call that goes through a shell, and CWE-77
                           blinding when only such alarms count.
  3. detector combinations A combination keeps a flaw if any member flags the refactoring.
"""
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare_variants import EXP, LLM, cluster_bootstrap, detections, exploitable, ground_truth, wilson  # noqa: E402
from dispatch_experiment import devirtualize  # noqa: E402
from scan_base import ACCEPT, counts  # noqa: E402
from shell_sinks import shell_sink_lines  # noqa: E402

DATA = EXP / "data" / "pysastbench"
VARIANTS = EXP / "data" / "llm_variants"
PATTERN = ["bandit", "semgrep-bandit", "semgrep-registry"]
CODEQL = "codeql"
COMBOS = {
    "Bandit": ["bandit"],
    "Semgrep (both)": ["semgrep-bandit", "semgrep-registry"],
    "Pattern tools (3)": PATTERN,
    "CodeQL": [CODEQL],
    "Bandit + CodeQL": ["bandit", CODEQL],
    "Semgrep + CodeQL": ["semgrep-bandit", "semgrep-registry", CODEQL],
    "All SAST (4)": PATTERN + [CODEQL],
    "Kimi K3": ["kimi"],
    "Sonnet 5.5": ["sonnet"],
    "All SAST + Kimi": PATTERN + [CODEQL, "kimi"],
}


def path_of(i, kind, variant):
    return DATA / i / f"{kind}.py" if variant == "ORIG" else VARIANTS / i / kind / variant / "main.py"


def findings():
    out = {}
    for line in (EXP / "results" / "codeql" / "findings.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["ok"]:
            out[tuple(r["key"])] = r["findings"]
    return out


def dispatch_prevalence(det, ex, truth):
    tally = {"lost": [0, 0], "kept": [0, 0]}
    variants = sorted({v for (_, _, _, v) in det if v != "ORIG"})
    for i in truth:
        if not i.startswith("77_") or not det.get((CODEQL, i, "vuln", "ORIG")):
            continue
        for v in variants:
            k = (CODEQL, i, "vuln", v)
            if k not in det or not ex.get((i, "vuln", v)):
                continue
            has = devirtualize(path_of(i, "vuln", v).read_text())[1] > 0
            group = "kept" if det[k] else "lost"
            tally[group][0] += has
            tally[group][1] += 1
    return tally


def line_check(ex, truth):
    fs = findings()
    accept = ACCEPT[77]
    report = {"orig_vuln": [], "orig_safe": []}
    strict, loose = {}, {}
    for (i, kind, v), found in fs.items():
        if not i.startswith("77_"):
            continue
        p = path_of(i, kind, v)
        sinks = shell_sink_lines(p)
        hits = [f for f in found if counts(f, accept)]
        loose[(i, kind, v)] = bool(hits)
        strict[(i, kind, v)] = any(f["line"] in sinks for f in hits)
        if v == "ORIG":
            report["orig_vuln" if kind == "vuln" else "orig_safe"].append(
                dict(id=i, alarms=len(hits), at_shell_sink=sum(f["line"] in sinks for f in hits)))
    summary = {}
    for label, group in (("orig_vuln", report["orig_vuln"]), ("orig_safe", report["orig_safe"])):
        summary[label] = dict(programs_with_alarm=sum(g["alarms"] > 0 for g in group),
                              programs_with_alarm_at_shell_sink=sum(g["at_shell_sink"] > 0 for g in group),
                              alarms=sum(g["alarms"] for g in group), at_shell_sink=sum(g["at_shell_sink"] for g in group))
    variants = sorted({v for (_, _, v) in strict if v != "ORIG"})
    for label, source in (("any_alarm", loose), ("shell_sink_only", strict)):
        kept = blinded = 0
        for i in truth:
            if not i.startswith("77_") or not source.get((i, "vuln", "ORIG")):
                continue
            for v in variants:
                k = (i, "vuln", v)
                if k in source and ex.get(k):
                    blinded += not source[k]
                    kept += source[k]
        summary[label] = dict(kept=kept, blinded=blinded, rate=round(100 * blinded / (kept + blinded), 1))
    kept_only_elsewhere = sum(1 for k, v in loose.items() if k[1] == "vuln" and k[2] != "ORIG" and ex.get(k) and v and not strict[k])
    summary["refactorings_flagged_only_away_from_shell_sink"] = kept_only_elsewhere
    return summary


def combos(det, ex, truth):
    variants = sorted({v for (_, _, _, v) in det if v != "ORIG"})
    rows = {}
    for name, members in COMBOS.items():
        pr = []
        for i in truth:
            if not any(det.get((m, i, "vuln", "ORIG")) for m in members):
                continue
            for v in variants:
                if ex.get((i, "vuln", v)) and all((m, i, "vuln", v) in det for m in members):
                    pr.append((i, not any(det[(m, i, "vuln", v)] for m in members)))
        b, n = sum(x for _, x in pr), len(pr)
        fixed = sum(any(det.get((m, i, "safe", "ORIG")) for m in members) for i in {k[1] for k in det if k[2] == "safe"})
        rows[name] = dict(flagged_programs=len({i for i, _ in pr}), blinded=b, still_vulnerable=n,
                          rate=round(100 * b / n, 2) if n else None, wilson95=[round(100 * x, 2) for x in wilson(b, n)],
                          bootstrap95=[round(100 * x, 2) for x in cluster_bootstrap(pr)], alarms_on_fixed=fixed)
    # refactorings lost by at least one SAST tool that had flagged the original
    sast = PATTERN + [CODEQL]
    lost = rescued_sast = rescued_llm = none = 0
    for i in truth:
        for v in variants:
            if not ex.get((i, "vuln", v)) or not all((m, i, "vuln", v) in det for m in sast):
                continue
            lose = [m for m in sast if det.get((m, i, "vuln", "ORIG")) and not det[(m, i, "vuln", v)]]
            if not lose:
                continue
            lost += 1
            other = any(det[(m, i, "vuln", v)] for m in sast if m not in lose)
            rescued_sast += other
            llm = any(det.get((m, i, "vuln", v)) for m in LLM)
            rescued_llm += llm
            none += not other and not llm
    return rows, dict(refactorings_with_a_sast_loss=lost, another_sast_tool_still_flags=rescued_sast,
                      an_llm_still_flags=rescued_llm, no_detector_flags=none)


def silent_repairs(ex, truth):
    """Vulnerable refactorings of ground-truth programs on which the attack no longer fires."""
    out = {}
    for (i, kind, v), fired in ex.items():
        if kind != "vuln" or v == "ORIG" or i not in truth:
            continue
        model, prompt = v.split("_")
        for key in (model, v, f"{model}/CWE-{i.split('_')[0]}"):
            c = out.setdefault(key, [0, 0])
            c[0] += not fired
            c[1] += 1
    return dict(sorted(out.items()))


def llm_baseline():
    """Majority-of-three located detections per CWE on the 120 vulnerable originals."""
    from extra_analyses import llm_majority
    maj = llm_majority()
    out = {}
    for m in LLM:
        per = {c: sum(maj.get((m, f"{c}_DS-{n}", "vuln"), (False, False))[1] for n in range(1, 21))
               for c in (22, 77, 79, 89, 94, 502)}
        out[m] = dict(per_cwe=per, total=sum(per.values()))
    return out


def paired(det, ex, truth):
    """Losses of CodeQL and each pattern tool on the same refactorings of programs both flagged."""
    variants = sorted({v for (_, _, _, v) in det if v != "ORIG"})
    out = {}
    for cwe in ("77", "89"):
        for t in PATTERN:
            n = c = s = 0
            for i in truth:
                if not i.startswith(cwe + "_") or not det.get((CODEQL, i, "vuln", "ORIG")) or not det.get((t, i, "vuln", "ORIG")):
                    continue
                for v in variants:
                    if ex.get((i, "vuln", v)) and (CODEQL, i, "vuln", v) in det and (t, i, "vuln", v) in det:
                        n += 1
                        c += not det[(CODEQL, i, "vuln", v)]
                        s += not det[(t, i, "vuln", v)]
            out[f"CWE-{cwe}/{t}"] = dict(common=n, codeql_blinded=c, tool_blinded=s)
    return out


def codeql_by_prompt(det, ex, truth):
    """CodeQL blinded/still-vulnerable on CWE-77, per refactoring."""
    variants = sorted({v for (_, _, _, v) in det if v != "ORIG"})
    out = {}
    for v in variants:
        b = n = 0
        for i in truth:
            k = (CODEQL, i, "vuln", v)
            if i.startswith("77_") and det.get((CODEQL, i, "vuln", "ORIG")) and k in det and ex.get((i, "vuln", v)):
                n += 1
                b += not det[k]
        out[v] = [b, n]
    return out


def fixed_run_errors(truth):
    """Ground-truth programs whose FIXED original never really ran under the attack (crash or error),
    so that 'attack did not fire on the fix' was not an observation."""
    from extra_analyses import dynamic_rows
    rows = dynamic_rows()
    out = []
    for i in truth:
        r = rows.get((i, "safe", "ORIG"))
        if not r:
            out.append(dict(id=i, why="no dynamic row"))
            continue
        a = r.get("attack") or {}
        if "exit" in a:   # command-line programs
            err = a.get("stderr_tail") or ""
            if a.get("exit") not in (0, None) and ("Traceback" in err or "Error" in err):
                # main() is called at module level, so '<module>' appears in every traceback; the program
                # ran if it printed output (these end with EOFError once the scripted input runs out)
                out.append(dict(id=i, why=err.strip().splitlines()[-1][:160] if err.strip() else f"exit {a.get('exit')}",
                                at_import=not (a.get("stdout") or "").strip(), cli=True,
                                commands_run=len(a.get("commands", [])), stdout_chars=len(a.get("stdout") or "")))
        elif a.get("error"):
            err = a["error"]
            out.append(dict(id=i, why=err.strip().splitlines()[-1][:160],
                            at_import='in <module>' in err and 'main.py' in err, cli=False,
                            sql_statements=len(a.get("statements") or [])))
    return out


def equivalence_still_vulnerable(ex, truth):
    """Normal-input equivalence restricted to refactorings on which the attack still fires."""
    from extra_analyses import dynamic_rows, equivalence
    _, differ = equivalence(dynamic_rows(), set(truth))
    diff = {(d["id"], d["variant"]) for d in differ}
    n = same = 0
    for (i, kind, v), fired in ex.items():
        if kind == "vuln" and v != "ORIG" and i in truth and fired:
            n += 1
            same += (i, v) not in diff
    return dict(same=same, n=n, pct=round(100 * same / n, 1))


def ground_truth_sensitivity(det, ex, truth, drop):
    """Blinding when programs whose fixed version did not run cleanly are left out of the ground truth."""
    from compare_variants import DETECTORS, classify
    variants = sorted({v for (_, _, _, v) in det if v != "ORIG"})
    out = {}
    for label, ids in drop.items():
        kept_truth = [i for i in truth if i not in ids]
        out[label] = {"programs": len(kept_truth)}
        for t in DETECTORS:
            _, c = classify(det, ex, kept_truth, variants, t)
            n = c["kept"] + c["blinded"]
            out[label][t] = dict(blinded=c["blinded"], still_vulnerable=n, rate=round(100 * c["blinded"] / n, 2) if n else None)
    return out


def main():
    ex = exploitable()
    truth = ground_truth(ex)
    det = detections("flagged")
    report = {}
    report["dispatch_prevalence"] = dispatch_prevalence(det, ex, truth)
    print("dispatch tables (lost, kept):", report["dispatch_prevalence"])
    report["codeql_line_check"] = line_check(ex, truth)
    print(json.dumps(report["codeql_line_check"], indent=1))
    rows, rescue = combos(det, ex, truth)
    report["combinations"], report["rescue"] = rows, rescue
    for k, r in rows.items():
        print(f"{k:<20} F={r['flagged_programs']:<4} {r['blinded']:>3}/{r['still_vulnerable']:<4} {r['rate']:>5}%  "
              f"W{r['wilson95']} B{r['bootstrap95']}  alarms_on_fixed={r['alarms_on_fixed']}")
    print(rescue)
    report["silent_repairs"] = silent_repairs(ex, truth)
    report["llm_baseline_located"] = llm_baseline()
    report["paired"] = paired(det, ex, truth)
    report["codeql_cwe77_by_prompt"] = codeql_by_prompt(det, ex, truth)
    report["equivalence_still_vulnerable"] = equivalence_still_vulnerable(ex, truth)
    print("equivalence_still_vulnerable", report["equivalence_still_vulnerable"])
    report["fixed_run_errors"] = fixed_run_errors(truth)
    errs = report["fixed_run_errors"]
    report["ground_truth_sensitivity"] = ground_truth_sensitivity(det, ex, truth, {
        "all programs": set(),
        "drop fixed versions that failed at import": {e["id"] for e in errs if e["at_import"]},
        "drop every fixed version that ended in an error": {e["id"] for e in errs}})
    for k in ("silent_repairs", "llm_baseline_located", "paired", "codeql_cwe77_by_prompt", "fixed_run_errors",
              "ground_truth_sensitivity"):
        print(k, json.dumps(report[k]))
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps(report, indent=1))
        print("saved", out)


if __name__ == "__main__":
    main()
