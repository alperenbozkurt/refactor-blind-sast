"""Run targeted probes on the six fixed programs both LLM reviewers flagged, and on their vulnerable
versions as a control.

Usage: .venv/bin/python -I src/dynamic_check/fix_probes.py
Writes results/fix_probes.json.

For 79_DS-19 the server-rendered page is opened in headless Chrome (separate throwaway profile) with a
``welcome`` URL parameter carrying a harmless tag; the page's own script decides whether that tag, or the
tag stored in the bio, becomes a real element of the document.
"""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

EXP = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATA = EXP / "data" / "pysastbench"
PY = EXP / ".venv-dynamic" / "bin" / "python"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PROBES = [("22_DS-1", "sibling_http"), ("22_DS-2", "sibling_flask"), ("22_DS-6", "tar_slip"),
          ("502_DS-8", "joblib_upload"), ("502_DS-1", "restricted_unpickler"), ("79_DS-19", "profile_page")]
WELCOME = '<b id="zzwel">ZZWEL</b>'


def run(pid, kind, probe):
    sb = Path(tempfile.mkdtemp(prefix="probe_"))
    try:
        shutil.copy(DATA / pid / f"{kind}.py", sb / "main.py")
        shutil.copy(HERE / "web_harness.py", sb)
        shutil.copy(HERE / "probe_harness.py", sb)
        page = sb / "page.html"
        p = subprocess.run([str(PY), "-I", "probe_harness.py", probe, str(page)], cwd=sb,
                           capture_output=True, text=True, timeout=120)
        line = next((l for l in reversed(p.stdout.splitlines()) if l.startswith("{")), None)
        out = json.loads(line) if line else {"probe": probe, "error": p.stderr[-600:]}
        if probe == "profile_page":
            out.update(browser(sb, page))
        return out
    finally:
        shutil.rmtree(sb, ignore_errors=True)


def dump_dom(sb, url):
    p = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--disable-extensions",
                        f"--user-data-dir={sb / 'chrome-profile'}", "--virtual-time-budget=3000", "--dump-dom", url],
                       capture_output=True, text=True, timeout=120)
    return p.stdout


def browser(sb, page):
    res = {}
    bio_page, plain_page = Path(f"{page}.bio.html"), Path(f"{page}.plain.html")
    if bio_page.exists():
        dom = dump_dom(sb, bio_page.as_uri())
        res["bio_dom_bytes"] = len(dom)
        res["bio_became_element"] = bool(re.search(r'<b id="zzbio">ZZBIO</b>', dom))
    if plain_page.exists():
        dom = dump_dom(sb, plain_page.as_uri() + "?welcome=" + quote(WELCOME))
        res["plain_dom_bytes"] = len(dom)
        res["welcome_became_element"] = bool(re.search(r'<b id="zzwel">ZZWEL</b>', dom))
    return res


def verdict(r):
    if r.get("error"):
        return "probe error"
    hit = (r.get("leaked") or r.get("opened") or r.get("written_outside") or bool(r.get("deser") and any(
        d != "pickle.Unpickler()" for d in r["deser"])) or r.get("welcome_became_element") or r.get("bio_became_element"))
    return "flaw reachable" if hit else "blocked"


def main():
    rows = []
    for pid, probe in PROBES:
        for kind in ("vuln", "safe"):
            r = run(pid, kind, probe)
            r.update(id=pid, kind=kind, verdict=verdict(r))
            rows.append(r)
            print(f"{pid:<9} {kind:<5} {probe:<21} {r['verdict']:<15} " +
                  json.dumps({k: v for k, v in r.items() if k not in ("id", "kind", "probe", "verdict", "error")})[:220])
            if r.get("error"):
                print("   error:", r["error"].strip().splitlines()[-1][:200])
    out = EXP / "results" / "fix_probes.json"  # not under results/dynamic/, which the oracle readers glob
    out.write_text(json.dumps(rows, indent=1))
    print("saved", out.relative_to(EXP))


if __name__ == "__main__":
    main()
