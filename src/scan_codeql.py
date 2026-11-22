"""Scan base programs and LLM refactorings with CodeQL (taint-tracking SAST).

Usage: python -I src/scan_codeql.py --work DIR [--jobs N] [--only ID[,ID...]] [--limit N]

Every target (one main.py) gets its own database, so programs cannot influence each other. Databases
are built in DIR and deleted right after analysis. Findings are appended to
results/codeql/findings.jsonl, so an interrupted run resumes where it stopped; the file holds rule
ids and line numbers only, no source code.

The matching rules are those of src/scan_base.py: accepted CWE, not on an import line, severity above
LOW. CodeQL's "note" level maps to LOW. The local threat model is enabled for every target because
many programs read their input from the command line, stdin or files, which CodeQL's default
(remote-only) sources ignore. Writes results/codeql_detections.json in the format of the
other detectors, with variant "ORIG" for the base programs.
"""
import argparse
import concurrent.futures as cf
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scan_base import ACCEPT, DATA, EXP, counts, function_lines, import_lines  # noqa: E402

VARIANTS = EXP / "data" / "llm_variants"
OUT = EXP / "results" / "codeql"
FINDINGS = OUT / "findings.jsonl"
PACK = "codeql/python-queries"
SUITE = "codeql-suites/python-security-extended.qls"
SEVERITY = {"error": "ERROR", "warning": "WARNING", "note": "LOW", "recommendation": "LOW"}


def targets():
    """(key, source file) for every base program and refactoring."""
    out = []
    for d in sorted(DATA.iterdir()):
        for kind in ("vuln", "safe"):
            out.append(((d.name, kind, "ORIG"), d / f"{kind}.py"))
    for p in sorted(VARIANTS.glob("*/*/*/main.py")):
        out.append(((p.parts[-4], p.parts[-3], p.parts[-2]), p))
    return out


def rule_table(run):
    table = {}
    for comp in [run["tool"]["driver"]] + run["tool"].get("extensions", []):
        for r in comp.get("rules", []):
            tags = r.get("properties", {}).get("tags", [])
            table[r["id"]] = dict(
                cwes=sorted({int(m.group(1)) for t in tags if (m := re.fullmatch(r"external/cwe/cwe-(\d+)", t))}),
                level=r.get("defaultConfiguration", {}).get("level", "warning"),
            )
    return table


def parse_sarif(path):
    run = json.loads(Path(path).read_text())["runs"][0]
    rules = rule_table(run)
    found = []
    for r in run.get("results", []):
        info = rules.get(r["ruleId"], dict(cwes=[], level="warning"))
        loc = r["locations"][0]["physicalLocation"]
        found.append(dict(rule=r["ruleId"], cwes=info["cwes"], line=loc["region"]["startLine"],
                          severity=SEVERITY.get(r.get("level", info["level"]), "WARNING")))
    return found


def scan(key, src, work, pack_ref):
    """Build a database for one file, analyse it, delete it."""
    name = "__".join(key)
    root = work / name
    shutil.rmtree(root, ignore_errors=True)
    (root / "src").mkdir(parents=True)
    shutil.copy(src, root / "src" / "main.py")
    t0 = time.time()
    res = dict(key=list(key), ok=False, findings=[])
    try:
        for cmd in (
            ["codeql", "database", "create", str(root / "db"), "--language=python", "--threads=1", "--ram=2048",
             f"--source-root={root / 'src'}", "--overwrite", "--quiet"],
            ["codeql", "database", "analyze", str(root / "db"), f"{pack_ref}:{SUITE}", "--format=sarif-latest",
             f"--output={root / 'out.sarif'}", "--threat-model=local", "--threads=1", "--ram=2048", "--quiet",
             "--no-print-diagnostics-summary",
             "--no-print-metrics-summary"],
        ):
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if p.returncode:
                res["error"] = p.stderr[-800:]
                return res
        res["findings"] = parse_sarif(root / "out.sarif")
        res["ok"] = True
        return res
    except (subprocess.TimeoutExpired, KeyError, IndexError, json.JSONDecodeError) as e:
        res["error"] = repr(e)
        return res
    finally:
        res["seconds"] = round(time.time() - t0, 1)
        shutil.rmtree(root, ignore_errors=True)


def load_done():
    done = {}
    if FINDINGS.exists():
        for line in FINDINGS.read_text().splitlines():
            r = json.loads(line)
            if r["ok"]:
                done[tuple(r["key"])] = r
    return done


def build_rows(done, src_of):
    metas = {d.name: json.loads((d / "meta.json").read_text()) for d in DATA.iterdir()}
    rows = []
    for key, r in sorted(done.items()):
        i, kind, variant = key
        meta = metas[i]
        path = src_of[key]
        try:
            span = function_lines(path, meta["vul_position"])
        except SyntaxError:
            span = None
        imp = import_lines(path)
        fs = [f for f in r["findings"] if f["line"] not in imp]
        match = [f for f in fs if counts(f, ACCEPT[meta["cwe"]])]
        rows.append(dict(id=i, cwe=meta["cwe"], kind=kind, variant=variant, tool="codeql", detected=bool(match),
                         in_function=bool(span and any(span[0] <= f["line"] <= span[1] for f in match)),
                         span_found=bool(span), rules=sorted({f["rule"] for f in match}),
                         other_rules=sorted({f["rule"] for f in fs if f not in match})))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    version = json.loads((OUT / "versions.json").read_text())
    pack_ref = f"{PACK}@{version['pack']}"

    all_targets = targets()
    src_of = {k: p for k, p in all_targets}
    done = load_done()
    todo = [(k, p) for k, p in all_targets if k not in done]
    if args.only:
        wanted = set(args.only.split(","))
        todo = [(k, p) for k, p in todo if k[0] in wanted]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(all_targets)} targets, {len(done)} done, {len(todo)} to run", flush=True)

    t0 = time.time()
    failed = 0
    with cf.ThreadPoolExecutor(args.jobs) as ex, FINDINGS.open("a") as log:
        futs = [ex.submit(scan, k, p, args.work, pack_ref) for k, p in todo]
        for n, fut in enumerate(cf.as_completed(futs), 1):
            r = fut.result()
            log.write(json.dumps(r) + "\n")
            log.flush()
            if r["ok"]:
                done[tuple(r["key"])] = r
            else:
                failed += 1
                print("FAILED", r["key"], r.get("error", "")[:300], flush=True)
            if n % 25 == 0 or n == len(futs):
                print(f"{n}/{len(futs)}  {time.time() - t0:.0f}s  failed={failed}", flush=True)

    rows = build_rows(done, src_of)
    (EXP / "results" / "codeql_detections.json").write_text(json.dumps(rows, indent=1))
    print(f"saved {len(rows)} rows; failed this run: {failed}")


if __name__ == "__main__":
    main()
