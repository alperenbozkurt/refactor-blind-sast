"""Ask an LLM to review programs for vulnerabilities, with the same prompt for every program.

Usage: python -I src/llm_scan.py --model sonnet|kimi|ollama:<name>|fake --set base|variants [--repeat 3]
                                  [--limit N] [--workers 4] [--budget 10] [--rescore]
  --set base      the 240 base programs (data/pysastbench/<id>/{vuln,safe}.py)
  --set variants  every LLM refactoring in data/llm_variants/<id>/<kind>/<variant>/main.py
Writes results/llm_scan/<model>__<set>.jsonl (resumable) and prints a summary.

The model only sees the code; jobs run in a fixed random order. Scoring uses the accepted CWE sets
of the SAST scan (src/scan_base.py):
  * ``flagged``  = at least one reported CWE in the accepted set;
  * ``located``  = such a finding also names the vulnerable function (or a line inside it);
  * on fixed ("safe") programs ``flagged`` is a false alarm.
"""
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from llm_backend import EXP, Client  # noqa: E402
from prompts import DETECT  # noqa: E402
from runner import run_jobs  # noqa: E402
from scan_base import ACCEPT, DATA, function_lines  # noqa: E402

VARIANTS = EXP / "data" / "llm_variants"


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def extract_json(text):
    """The answer object: the last ```json block if any, otherwise the last decodable object that has
    a "vulnerable" or "findings" key (models sometimes reason in prose, with braces, before it)."""
    text = text or ""
    candidates = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.S)[::-1] + [text]
    dec = json.JSONDecoder()
    for chunk in candidates:
        found = None
        for m in re.finditer(r"\{", chunk):
            try:
                obj, _ = dec.raw_decode(chunk[m.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and ("vulnerable" in obj or "findings" in obj):
                found = obj
        if found is not None:
            return found
    return None


def parse(text):
    out = extract_json(text)
    if out is None:
        return None
    fs = out.get("findings") or []
    return dict(vulnerable=bool(out.get("vulnerable")), findings=[f for f in fs if isinstance(f, dict)])


def cwe_num(s):
    m = re.search(r"(\d+)", str(s))
    return int(m.group(1)) if m else None


def score(sample, parsed, path=None):
    accept = ACCEPT[sample["cwe"]]
    path = EXP / (path or DATA / sample["id"] / f"{sample['kind']}.py")  # stored paths are repo-relative
    try:
        span = function_lines(path, sample["vul_position"])
    except SyntaxError:
        span = None
    hits = [f for f in parsed["findings"] if cwe_num(f.get("cwe")) in accept]
    target = sample["vul_position"].split(".")[-1]

    def at(f):
        fn = str(f.get("function") or "")
        line = f.get("line")
        return fn.split(".")[-1] == target or bool(span and isinstance(line, int) and span[0] <= line <= span[1])

    return dict(flagged=bool(hits), located=any(at(f) for f in hits), any_finding=bool(parsed["findings"]))


def jobs_for(which):
    metas = {d.name: json.loads((d / "meta.json").read_text()) for d in sorted(DATA.iterdir())}
    jobs = []
    if which == "base":
        for i, m in metas.items():
            for kind in ("vuln", "safe"):
                jobs.append(dict(key=f"{i}/{kind}/ORIG", id=i, kind=kind, variant="ORIG",
                                 path=str((DATA / i / f"{kind}.py").relative_to(EXP))))
    else:
        for f in sorted(VARIANTS.glob("*/*/*/main.py")):
            i, kind, variant = f.parts[-4], f.parts[-3], f.parts[-2]
            jobs.append(dict(key=f"{i}/{kind}/{variant}", id=i, kind=kind, variant=variant, path=str(f.relative_to(EXP))))
    for j in jobs:
        j.update(cwe=metas[j["id"]]["cwe"], vul_position=metas[j["id"]]["vul_position"])
    random.Random(2026).shuffle(jobs)
    return jobs


def majority(rows):
    """Collapse repeated answers per program: a field is true if most readable repeats say so."""
    by = {}
    for r in rows:
        by.setdefault((r["id"], r["kind"], r["variant"]), []).append(r)
    out = []
    for reps in by.values():
        ok = [r for r in reps if r["parse_ok"]]
        if not ok:
            continue
        m = dict(ok[0], n_repeats=len(ok))
        for f in ("flagged", "located", "any_finding"):
            m[f] = sum(bool(r[f]) for r in ok) * 2 > len(ok)
            m[f + "_agree"] = len({bool(r[f]) for r in ok}) == 1
        out.append(m)
    return out


def summary(rows, label):
    n_bad = sum(not r["parse_ok"] for r in rows)
    rows = majority(rows)
    reps = max((r["n_repeats"] for r in rows), default=1)
    print(f"\n{label}: {len(rows)} programs, up to {reps} answers each (majority vote), {n_bad} unreadable answers")
    for c in sorted({r["cwe"] for r in rows}) + ["all"]:
        v = [r for r in rows if r["kind"] == "vuln" and (c == "all" or r["cwe"] == c)]
        s = [r for r in rows if r["kind"] == "safe" and (c == "all" or r["cwe"] == c)]
        print(f"CWE {c!s:<4} vulnerable flagged {sum(r['flagged'] for r in v):>4}/{len(v):<4} (located {sum(r['located'] for r in v):>4})"
              f" | fixed flagged {sum(r['flagged'] for r in s):>4}/{len(s):<4}")
    if reps > 1:
        print(f"repeats agree on 'flagged' for {sum(r['flagged_agree'] for r in rows)}/{len(rows)} programs, "
              f"on 'located' for {sum(r['located_agree'] for r in rows)}/{len(rows)}")


def rescore(out):
    """Re-parse and re-score saved answers (no API calls), e.g. after a parser fix."""
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    changed = 0
    for r in rows:
        p = parse(r["raw"])
        new = dict(parse_ok=p is not None, **(score(r, p, r["path"]) if p else dict(flagged=None, located=None, any_finding=None)))
        if any(r.get(k) != v for k, v in new.items()):
            changed += 1
            r.update(new)
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"rescored {out.name}: {changed} of {len(rows)} rows changed")
    return rows


def main():
    alias, which = arg("--model"), arg("--set", "base")
    out = EXP / "results" / "llm_scan" / f"{alias.replace(':', '_').replace('/', '_')}__{which}.jsonl"
    if "--rescore" in sys.argv:
        summary(rescore(out), f"{alias} / {which}")
        return
    client = Client(alias)
    jobs = jobs_for(which)
    if arg("--limit"):
        jobs = jobs[: int(arg("--limit"))]
    # models without temperature control are asked several times (--repeat); the first answer of a
    # program keeps the plain key so that single-answer runs stay compatible
    repeat = int(arg("--repeat", 1))
    jobs = [dict(j, key=j["key"] + (f"/r{k}" if k else ""), rep=k) for k in range(repeat) for j in jobs]

    def work(job):
        code = (EXP / job["path"]).read_text()
        r = client.ask(DETECT.format(code=code.rstrip()), max_tokens=8000, json_mode=True)
        p = parse(r["text"])
        sc = score(job, p, job["path"]) if p else dict(flagged=None, located=None, any_finding=None)
        row = dict({k: v for k, v in job.items() if k != "key"}, model=alias, settings=client.settings(),
                   stop=r["stop"], usage=r["usage"], latency_ms=r["latency_ms"], raw=r["text"], reasoning=r.get("reasoning"),
                   parse_ok=p is not None, **sc)
        return row, client.cost(r["usage"])

    run_jobs(jobs, work, out, workers=int(arg("--workers", 4)),
             budget_usd=float(arg("--budget")) if arg("--budget") else None, label=f"scan {alias} {which}")
    if out.exists():
        summary([json.loads(l) for l in out.read_text().splitlines() if l.strip()], f"{alias} / {which}")


if __name__ == "__main__":
    main()
