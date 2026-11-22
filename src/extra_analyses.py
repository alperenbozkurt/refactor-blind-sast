"""Supplementary analyses for the paper. Reads existing results only; no scanning and no API calls.

Usage: python -I src/extra_analyses.py [--json results/extra_analyses.json]

  1. false alarms   Which fixed programs does each detector flag, and does the attack fire on them?
  2. equivalence    Does each refactoring behave like its original on the normal input?
  3. cross          Blinding per detector, split by the model that wrote the refactoring.
  4. examples       Detector and attack outcomes for the two code examples used in the paper.
"""
import collections
import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare_variants import CODEQL, DETECTORS, EXP, LLM, SAST, detections, exploitable, ground_truth, jsonl, wilson  # noqa: E402

VOLATILE = [
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "<UUID>"),
    (re.compile(r"\b[0-9a-f]{32,64}\b"), "<HEX>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?"), "<TIME>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "<DATE>"),
    (re.compile(r"\b\d{8}[_-]?\d{6}\b"), "<STAMP>"),
    (re.compile(r"\b\d{10}(\.\d+)?\b"), "<EPOCH>"),
    (re.compile(r"0x[0-9a-f]+"), "<ADDR>"),
]


def mask(text):
    text = str(text if text is not None else "")
    for pat, sub in VOLATILE:
        text = pat.sub(sub, text)
    return text


def canon_json(text):
    """Key order and whitespace in a JSON body are not behaviour."""
    try:
        return json.dumps(json.loads(text), sort_keys=True)
    except (TypeError, ValueError):
        return re.sub(r"\s+", " ", text).strip()


def sql_shape(statements):
    return [re.sub(r"\s+", " ", mask(s.get("sql", ""))).strip().lower() for s in statements or []]


def dynamic_rows():
    rows = {}
    for f in glob.glob(str(EXP / "results" / "dynamic" / "*.json")):
        for r in json.load(open(f)):
            rows[(r["id"], r["kind"], r["variant"])] = r
    return rows


def outcome(run):
    """(coarse signal, full observable output) of one normal-input run."""
    if "exit" in run:
        return run.get("exit"), (canon_json(mask(run.get("stdout"))), tuple(mask(c) for c in run.get("commands", [])))
    return run.get("status"), (canon_json(mask(run.get("body"))), tuple(sql_shape(run.get("statements"))))


def errored(run):
    if "exit" in run:
        return run.get("exit") not in (0, None)
    return bool(run.get("error")) or (run.get("status") or 0) >= 500


def equivalence(rows, truth):
    per = collections.defaultdict(collections.Counter)
    differ = []
    for (i, kind, v), r in sorted(rows.items()):
        if kind != "vuln" or v == "ORIG" or i not in truth:
            continue
        base = rows.get((i, kind, "ORIG"))
        if not base or not isinstance(r.get("normal"), dict) or not isinstance(base.get("normal"), dict):
            per[v]["no_data"] += 1
            continue
        c1, f1 = outcome(base["normal"])
        c2, f2 = outcome(r["normal"])
        per[v]["n"] += 1
        per[v]["same_coarse"] += c1 == c2
        per[v]["same_full"] += (c1, f1) == (c2, f2)
        per[v]["base_errored"] += errored(base["normal"])
        if (c1, f1) != (c2, f2):
            differ.append(dict(id=i, variant=v, base=c1, refactored=c2, coarse_differs=c1 != c2,
                               sql=f1[1] != f2[1], output=f1[0] != f2[0]))
    return per, differ


def llm_majority():
    out = {}
    for m in LLM:
        reps = collections.defaultdict(list)
        for r in jsonl(EXP / "results" / "llm_scan" / f"{m}__base.jsonl"):
            if r["parse_ok"]:
                reps[(r["id"], r["kind"])].append(r)
        for (i, k), rs in reps.items():
            out[(m, i, k)] = (sum(bool(r["flagged"]) for r in rs) * 2 > len(rs),
                              sum(bool(r["located"]) for r in rs) * 2 > len(rs))
    return out


def false_alarms(ex):
    flagged = detections("flagged")
    located = detections("located")
    maj = llm_majority()
    programs = sorted({i for (_, i, k, v) in flagged if k == "safe" and v == "ORIG"})
    table = {}
    alarmed = collections.defaultdict(set)
    for t in DETECTORS:
        for label, det in (("file", flagged), ("function", located)):
            hit = []
            for i in programs:
                if t in LLM:
                    h = maj.get((t, i, "safe"), (False, False))[0 if label == "file" else 1]
                else:
                    h = det.get((t, i, "safe", "ORIG"), False)
                if h:
                    hit.append(i)
            c = collections.Counter()
            for i in hit:
                k = (i, "safe", "ORIG")
                c["attack_fires" if ex.get(k) else "attack_blocked" if k in ex else "no_dynamic_data"] += 1
            table.setdefault(t, {})[label] = dict(alarms=len(hit), **c, per_cwe=dict(collections.Counter(i.split("_")[0] for i in hit)))
            if label == "function":
                alarmed[t] = set(hit)
    return table, alarmed


def cross(det, ex, truth):
    variants = sorted({v for (_, _, _, v) in det if v != "ORIG"})
    out = {}
    for t in DETECTORS:
        out[t] = {}
        for author in LLM:
            b = n = 0
            for i in truth:
                if not det.get((t, i, "vuln", "ORIG")):
                    continue
                for v in variants:
                    if not v.startswith(author):
                        continue
                    dk, ek = (t, i, "vuln", v), (i, "vuln", v)
                    if dk in det and ek in ex and ex[ek]:
                        n += 1
                        b += not det[dk]
            out[t][author] = dict(blinded=b, still_vulnerable=n, pct=round(100 * b / n, 2) if n else None,
                                  wilson95=[round(100 * x, 2) for x in wilson(b, n)] if n else None)
    return out


def example(det, ex, rows, i, v):
    tools = {t: dict(original=det.get((t, i, "vuln", "ORIG")), refactored=det.get((t, i, "vuln", v))) for t in DETECTORS}
    return dict(id=i, variant=v, attack_fires_original=ex.get((i, "vuln", "ORIG")), attack_fires_fixed=ex.get((i, "safe", "ORIG")),
                attack_fires_refactored=ex.get((i, "vuln", v)), detectors=tools)


def main():
    ex = exploitable()
    truth = ground_truth(ex)
    rows = dynamic_rows()
    det = detections("flagged")
    report = {}

    print("===== 1. alarms on fixed originals =====")
    fa, alarmed = false_alarms(ex)
    report["false_alarms"] = fa
    for t, d in fa.items():
        print(f"{t:<17} function {d['function']}\n{'':<17} file     {d['file']}")
    print("attack fires on fixed original:", [k[0] for k in sorted(ex) if k[1] == "safe" and k[2] == "ORIG" and ex[k]])
    both = sorted(alarmed["kimi"] & alarmed["sonnet"])
    print(f"flagged by both LLMs ({len(both)}):", both)
    report["both_llm_alarms"] = both

    print("\n===== 2. normal-input equivalence (vulnerable refactorings of ground-truth programs) =====")
    per, differ = equivalence(rows, set(truth))
    total = collections.Counter()
    for v, c in sorted(per.items()):
        total.update(c)
        print(f"{v:<11} {dict(c)}")
    print("all", dict(total))
    print("coarse differences:", [(d["id"], d["variant"], d["base"], d["refactored"]) for d in differ if d["coarse_differs"]][:40])
    print("by cwe, full differences:", collections.Counter(d["id"].split("_")[0] for d in differ))
    print("sql text differs:", sum(d["sql"] for d in differ), " output differs:", sum(d["output"] for d in differ))
    report["equivalence"] = dict(per_variant={k: dict(v) for k, v in per.items()}, total=dict(total), differences=differ)

    print("\n===== 3. blinding by author of the refactoring (flagged) =====")
    cr = cross(det, ex, truth)
    report["cross"] = cr
    for t, d in cr.items():
        print(f"{t:<17}" + "  ".join(f"{a}: {x['blinded']}/{x['still_vulnerable']} = {x['pct']}% {x['wilson95']}" for a, x in d.items()))

    print("\n===== 4. examples =====")
    report["examples"] = [example(det, ex, rows, "89_DS-10", "kimi_L0"), example(det, ex, rows, "77_DS-1", "sonnet_L1")]
    for e in report["examples"]:
        print(json.dumps(e))

    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps(report, indent=1))
        print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
