"""Do the refactorings counted as 'closed' (attack no longer fires) still work, or did they just break?

Usage: python -I src/closed_check.py [--json results/closed_check.json]
Reads existing dynamic results only; no new runs.

For every refactoring of a verified vulnerable program, compares its two runs with the original's:
  normal run   same coarse signal (exit code / HTTP status) as the original, new error or not,
               same observable output (stdout or response body, masked as in extra_analyses.py)
  attack run   errored or not, and whether the original's attack run errored
A 'closed' refactoring counts as working if its normal run gives the same coarse signal as the original
without a new error, and its attack run does not error where the original's did not. The same numbers
are given for the refactorings on which the attack still fires, for comparison.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare_variants import EXP, exploitable, ground_truth  # noqa: E402
from extra_analyses import dynamic_rows, errored, outcome  # noqa: E402


def check(rows, ex, truth):
    groups = collections.defaultdict(collections.Counter)
    cases = []
    for (i, kind, v), fired in sorted(ex.items()):
        if kind != "vuln" or v == "ORIG" or i not in truth:
            continue
        r, base = rows.get((i, kind, v)), rows.get((i, kind, "ORIG"))
        model = v.split("_")[0]
        group = "fires" if fired else "closed"
        for key in (group, f"{group}/{model}"):
            g = groups[key]
            g["n"] += 1
            if not (r and base and isinstance(r.get("normal"), dict) and isinstance(base.get("normal"), dict)):
                g["no_data"] += 1
                continue
            c1, f1 = outcome(base["normal"])
            c2, f2 = outcome(r["normal"])
            new_normal_error = errored(r["normal"]) and not errored(base["normal"])
            new_attack_error = errored(r.get("attack") or {}) and not errored(base.get("attack") or {})
            same_coarse = c1 == c2
            same_output = f1[0] == f2[0]
            works = same_coarse and not new_normal_error and not new_attack_error
            g["same_coarse"] += same_coarse
            g["same_output"] += same_output
            g["new_normal_error"] += new_normal_error
            g["new_attack_error"] += new_attack_error
            g["works"] += works
            att, batt = r.get("attack") or {}, base.get("attack") or {}
            if errored(att):
                g["attack_error_any"] += 1
                g["attack_error_also_in_original"] += errored(batt)
            # did the attack run still reach the dangerous call (SQL executed / command run)?
            if "statements" in att or "commands" in att:
                g["sink_observable"] += 1
                g["sink_reached"] += bool(att.get("statements") or att.get("commands"))
            if group == "closed" and key == group and not works:
                err = (r.get("attack") or {}).get("error") or (r.get("attack") or {}).get("stderr_tail") or \
                      (r.get("normal") or {}).get("error") or (r.get("normal") or {}).get("stderr_tail") or ""
                cases.append(dict(id=i, variant=v, base_normal=c1, refactored_normal=c2,
                                  new_normal_error=new_normal_error, new_attack_error=new_attack_error,
                                  last_error_line=(err.strip().splitlines() or [""])[-1][:160]))
    return {k: dict(v) for k, v in sorted(groups.items())}, cases


def evidence(rows, ex, truth):
    """How each closed refactoring handled the attack input, per CWE.

    sql_parameterized   CWE-89: the marker reached the query, but as a bound parameter, not in the SQL text
    marker_as_argument  CWE-77: a command ran with the marker inside an argument instead of as its own command
    no_command          CWE-77: no command ran on the attack input
    rejected            the attack run ended with an error that the original's attack run did not raise
    other               anything else (listed with the last error/output line)"""
    out = collections.defaultdict(collections.Counter)
    other = []
    for (i, kind, v), fired in sorted(ex.items()):
        if kind != "vuln" or v == "ORIG" or i not in truth or fired:
            continue
        cwe = i.split("_")[0]
        att = (rows.get((i, kind, v)) or {}).get("attack") or {}
        batt = (rows.get((i, kind, "ORIG")) or {}).get("attack") or {}
        cmds = att.get("commands")
        if att.get("in_params") and not att.get("in_sql"):
            cat = "sql_parameterized"
        elif cmds is not None and cwe == "77":
            cat = "marker_as_argument" if any("canary" in c for c in cmds) else "no_command"
        elif errored(att) and not errored(batt):
            cat = "rejected"
        else:
            cat = "other"
        out[cwe][cat] += 1
        if cat in ("no_command", "rejected", "other"):
            msg = att.get("error") or att.get("stderr_tail") or att.get("stdout") or att.get("body") or ""
            other.append(dict(id=i, variant=v, category=cat, last_line=(str(msg).strip().splitlines() or [""])[-1][:140]))
    return {k: dict(v) for k, v in sorted(out.items())}, other


DANGER = {  # the call that carries the flaw in each CWE, and the usual guards a fix adds
    "502": (r"\b(pickle|cPickle|dill|marshal|shelve|joblib)\.(loads?|Unpickler)\b|yaml\.(load|unsafe_load)\(|\bjsonpickle\.decode",
            r"yaml\.safe_load|json\.loads?|SafeLoader|find_class|RestrictedUnpickler|hmac"),
    "94": (r"\b(eval|exec)\(", r"ast\.literal_eval|operator\.|ALLOWED|allowed|whitelist|re\.fullmatch|re\.match"),
    "22": (r"open\(|send_file|send_from_directory|FileResponse", r"realpath|abspath|commonpath|is_relative_to|secure_filename|normpath|\.\."),
    "79": (r"", r"escape|markupsafe|html\.escape|autoescape"),
    "77": (r"shell\s*=\s*True|os\.system\(|os\.popen\(", r"shlex\.quote"),
}


def static_evidence(other):
    """For closed refactorings without a runtime signal: does the dangerous call remain, and is a guard added?"""
    import re
    rows = []
    for o in other:
        cwe = o["id"].split("_")[0]
        if cwe not in DANGER:
            continue
        danger, guard = DANGER[cwe]
        orig = (EXP / "data" / "pysastbench" / o["id"] / "vuln.py").read_text()
        ref = (EXP / "data" / "llm_variants" / o["id"] / "vuln" / o["variant"] / "main.py").read_text()
        n = lambda pat, s: len(re.findall(pat, s)) if pat else 0  # noqa: E731
        r = dict(id=o["id"], variant=o["variant"], danger_orig=n(danger, orig), danger_ref=n(danger, ref),
                 guard_orig=n(guard, orig), guard_ref=n(guard, ref))
        r["fix_visible"] = r["danger_ref"] < r["danger_orig"] or r["guard_ref"] > r["guard_orig"]
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(EXP / "results" / "closed_check.json"))
    a = ap.parse_args()
    ex = exploitable()
    truth = set(ground_truth(ex))
    groups, cases = check(dynamic_rows(), ex, truth)
    for k, g in groups.items():
        print(f"{k:<14} " + "  ".join(f"{m}={g.get(m, 0)}" for m in
                                       ("n", "works", "same_coarse", "same_output", "new_normal_error", "new_attack_error",
                                        "attack_error_any", "attack_error_also_in_original", "sink_observable",
                                        "sink_reached", "no_data")))
    print("closed and not working:")
    for c in cases:
        print("  ", c)
    ev, other = evidence(dynamic_rows(), ex, truth)
    print("evidence per CWE:", json.dumps(ev))
    for o in other:
        print("  ", o)
    st = static_evidence(other)
    print("static evidence (dangerous call / guard counts, original -> refactoring):")
    for s in st:
        print("  ", s)
    print("fix visible in code:", sum(s["fix_visible"] for s in st), "of", len(st))
    Path(a.json).write_text(json.dumps(dict(groups=groups, closed_not_working=cases, evidence=ev, evidence_cases=other,
                                            static_evidence=st), indent=1))
    print("saved", Path(a.json).relative_to(EXP))


if __name__ == "__main__":
    main()
