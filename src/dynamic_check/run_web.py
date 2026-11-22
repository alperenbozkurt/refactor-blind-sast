"""Dynamic check for the web (SQL-injection etc.) programs: drive one endpoint of every version with
a normal input and with an input carrying a benign marker, using src/dynamic_check/web_harness.py.

Usage: python -I src/dynamic_check/run_web.py --cwe 89 [--only 89_DS-1,...] [--base-only] [--workers 6]
Spec file: src/dynamic_check/specs/<cwe>_web.json.
Writes results/dynamic/<cwe>_web.json.

For CWE-89 the marker is a value with an embedded quote; the attack input is "exploitable" when the
marker reaches the SQL statement text (``in_sql``). The normal input is used to compare behaviour
(status code and the set of SQL statements, with the marker and volatile values masked).
"""
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EXP = Path(__file__).resolve().parents[2]
DATA = EXP / "data" / "pysastbench"
VARIANTS = EXP / "data" / "llm_variants"
SPECS = Path(__file__).resolve().parent / "specs"
HARNESS = Path(__file__).resolve().parent / "web_harness.py"
PY = EXP / ".venv-dynamic" / "bin" / "python"
TIMEOUT = 60


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def run_case(program, spec, case, extra):
    sb = Path(tempfile.mkdtemp(prefix="dynweb_"))
    shutil.copy(program, sb / "main.py")
    shutil.copy(HARNESS, sb / "web_harness.py")
    for rel, content in extra.get("files", {}).items():
        p = sb / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    for d in extra.get("dirs", []):
        (sb / d).mkdir(parents=True, exist_ok=True)
    (sb / "spec.json").write_text(json.dumps(spec))
    try:
        p = subprocess.run([str(PY), "-I", "web_harness.py", "spec.json", case], cwd=sb,
                           capture_output=True, text=True, timeout=TIMEOUT)
        # frameworks may print to stdout; our result is the last JSON line
        line = next((l for l in reversed(p.stdout.splitlines()) if l.strip().startswith("{")), "")
        out = json.loads(line) if line else {"error": (p.stderr or "no output")[-400:]}
    except subprocess.TimeoutExpired:
        out = {"error": "timeout"}
    except json.JSONDecodeError:
        out = {"error": (p.stdout or p.stderr)[-400:]}
    shutil.rmtree(sb, ignore_errors=True)
    return out


def programs(pid, base_only):
    yield "vuln", "ORIG", DATA / pid / "vuln.py"
    yield "safe", "ORIG", DATA / pid / "safe.py"
    if not base_only:
        for kind in ("vuln", "safe"):
            for f in sorted((VARIANTS / pid / kind).glob("*/main.py")):
                yield kind, f.parent.name, f


def main():
    cwe = arg("--cwe")
    allspecs = json.loads((SPECS / f"{cwe}_web.json").read_text())
    ids = arg("--only").split(",") if arg("--only") else sorted(allspecs)
    jobs = [(pid, kind, variant, path) for pid in ids if allspecs[pid].get("framework") not in (None, "skip")
            for kind, variant, path in programs(pid, "--base-only" in sys.argv)]

    # file-reading programs get a marker planted outside every app's base directory; ../ traversal that
    # opens it (opened_marker) or returns its content (leaked) proves the traversal still works
    if any("open_marker" in s or "leak_marker" in s for s in allspecs.values()):
        md = Path("/tmp/dynmark"); md.mkdir(parents=True, exist_ok=True)
        content = next((s["leak_marker"] for s in allspecs.values() if s.get("leak_marker")), "ZZSECRET_LEAK")
        for name in ("MARKER.txt","MARKER.log","MARKER.json","MARKER.yaml","MARKER.yml","MARKER.conf","MARKER.mp4","MARKER.css"):
            (md / name).write_text(content + "\n")

    def exploited(spec, res):
        if "deser_marker" in spec:
            return bool(res.get("deser_sink"))
        if "code_marker" in spec:
            return bool(res.get("code_sink"))
        if "open_marker" in spec:
            return bool(res.get("opened_marker") or res.get("leaked"))
        if "leak_marker" in spec:
            return bool(res.get("leaked"))
        return bool(res.get("in_sql"))

    def one(job):
        pid, kind, variant, path = job
        spec = allspecs[pid]
        extra = spec.get("extra", {})
        r = dict(id=pid, kind=kind, variant=variant, framework=spec["framework"])
        for case in ("normal", "attack"):
            r[case] = run_case(path, spec, case, extra)
        r["exploitable"] = exploited(spec, r["attack"])
        return r

    with ThreadPoolExecutor(int(arg("--workers", 6))) as ex:
        rows = list(ex.map(one, jobs))
    out = EXP / "results" / "dynamic" / f"{cwe}_web.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    old = {(r["id"], r["kind"], r["variant"]): r for r in json.loads(out.read_text())} if out.exists() else {}
    old.update({(r["id"], r["kind"], r["variant"]): r for r in rows})
    out.write_text(json.dumps(sorted(old.values(), key=lambda r: (r["id"], r["kind"], r["variant"])), indent=1))
    for r in rows:
        if r["variant"] == "ORIG":
            a = r["attack"]
            print(f"{r['id']:<10} {r['framework']:<9} {r['kind']:<5} exploitable={str(r['exploitable']):<5}"
                  f" status={a.get('status')} err={bool(a.get('error'))}")
    print(f"{len(rows)} runs, saved {out.relative_to(EXP)}")


if __name__ == "__main__":
    main()
