"""Dynamic check: run every program (base vulnerable, base fixed, each LLM refactoring) with the same
normal input and the same attack input, and record whether the attack succeeds.

Usage: python -I src/dynamic_check/run.py --cwe 77 [--only 77_DS-1,77_DS-2] [--base-only] [--workers 8]
Inputs: src/dynamic_check/specs/<cwe>.json, one entry per program (see README in that folder).
Writes results/dynamic/<cwe>.json.

Each run happens in a fresh temporary directory that holds a copy of the program, the files the spec
asks for and a bin/ directory placed first on PATH. External tools the programs call (ping, ffmpeg,
pg_dump, ...) are replaced there by stubs that only log their command line and exit 0, so nothing is
sent over the network and the system is not changed; the logged command lines are part of the
behaviour that is compared. For CWE-77 the attack input runs an extra command, ``canary``, whose stub
creates a marker file: the attack succeeded if the marker exists afterwards.
"""
import base64
import json
import os
import re
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
PY = EXP / ".venv-dynamic" / "bin" / "python"
TIMEOUT = 30

STUBS = """ping traceroute tracert nslookup dig host whois curl wget gzip gunzip zip unzip tar convert magick
mysqldump mysql pg_dump pg_restore psql mongodump mongorestore soffice libreoffice pandoc ffmpeg ffprobe
wkhtmltoimage wkhtmltopdf cutycapt phantomjs sysctl ip ifconfig route netstat top free lscpu lshw dpkg rpm
brew uname df du ps system_profiler ngrok sudo systemctl service iptables nmap ssh scp rsync""".split()


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def make_sandbox(program, spec):
    sb = Path(tempfile.mkdtemp(prefix="dyn_"))
    shutil.copy(program, sb / "main.py")
    for rel, content in spec.get("files", {}).items():
        p = sb / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    for rel, content in spec.get("files_b64", {}).items():
        p = sb / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(base64.b64decode(content))
    for d in spec.get("dirs", []):
        (sb / d).mkdir(parents=True, exist_ok=True)
    if spec.get("trace_deser"):
        # auto-loaded at interpreter start (PYTHONPATH=sandbox); marks when an UNSAFE deserializer is
        # invoked on the program's input. Safe versions use json/yaml.safe_load/a restricted Unpickler
        # (a pickle.Unpickler subclass whose .load() bypasses these module functions) and never mark.
        (sb / "sitecustomize.py").write_text(
            "import os\n"
            "def _m(*a, **k):\n"
            "    open(os.environ['DYN_MARK'], 'a').close()\n"
            "try:\n"
            "    import pickle\n"
            "    _pl, _pL = pickle.loads, pickle.load\n"
            "    pickle.loads = lambda *a, **k: (_m(), _pl(*a, **k))[1]\n"
            "    pickle.load = lambda *a, **k: (_m(), _pL(*a, **k))[1]\n"
            "except Exception: pass\n"
            "try:\n"
            "    import marshal\n"
            "    _ml = marshal.loads\n"
            "    marshal.loads = lambda *a, **k: (_m(), _ml(*a, **k))[1]\n"
            "except Exception: pass\n"
            "try:\n"
            "    import shelve\n"
            "    _so = shelve.open\n"
            "    shelve.open = lambda *a, **k: (_m(), _so(*a, **k))[1]\n"
            "except Exception: pass\n"
            "try:\n"
            "    import yaml\n"
            "    _yl = yaml.load\n"
            "    def _yw(*a, **k):\n"
            "        if 'Loader' not in k and len(a) < 2: _m()\n"       # yaml.load without a safe Loader
            "        elif k.get('Loader', None).__name__ in ('Loader','UnsafeLoader','FullLoader'): _m()\n"
            "        return _yl(*a, **k)\n"
            "    yaml.load = _yw\n"
            "except Exception: pass\n")
    if spec.get("stub_resolve"):
        # some programs guard the sink with socket.gethostbyname(host); stub it so the attack input
        # reaches the real sink (the command built from the same host) instead of failing name lookup
        (sb / "sitecustomize.py").write_text(
            "import socket\n"
            "socket.gethostbyname = lambda *a, **k: '127.0.0.1'\n"
            "socket.getaddrinfo = lambda *a, **k: [(2, 1, 6, '', ('127.0.0.1', 0))]\n")
    if spec.get("trace_code"):
        # mark when eval/exec is called with the marker string in its code argument (code injection)
        (sb / "sitecustomize.py").write_text(
            "import os, builtins\n"
            "_mk = os.environ.get('DYN_CODE', '')\n"
            "def _t(f):\n"
            "    def w(code, *a, **k):\n"
            "        if isinstance(code, str) and _mk and _mk in code:\n"
            "            open(os.environ['DYN_MARK'], 'a').close()\n"
            "        return f(code, *a, **k)\n"
            "    return w\n"
            "builtins.eval = _t(builtins.eval)\n"
            "builtins.exec = _t(builtins.exec)\n")
    bin_ = sb / "bin"
    bin_.mkdir()
    for name in STUBS:
        (bin_ / name).write_text('#!/bin/sh\necho "$(basename "$0") $*" >> "$DYN_LOG"\nexit 0\n')
    (bin_ / "canary").write_text('#!/bin/sh\necho "canary $*" >> "$DYN_LOG"\ntouch "$DYN_MARK"\n')
    for f in bin_.iterdir():
        f.chmod(0o755)
    return sb


def normalise(text, sb):
    text = text.replace(str(sb), "<SB>").replace(os.path.realpath(sb), "<SB>")
    text = re.sub(r"\d{8}[_-]?\d{6}(\.\d+)?", "<TS>", text)                     # 20261029_231500
    text = re.sub(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?", "<TS>", text)  # 2026-10-29 23:15:00
    text = re.sub(r"\b\d{10}(\.\d+)?\b", "<TS>", text)                           # unix time
    text = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<UUID>", text)
    return text


def run_case(program, spec, case):
    sb = make_sandbox(program, spec)
    log, mark = sb / "commands.log", sb / "CANARY_MARK"
    env = dict(PATH=f"{sb / 'bin'}:/usr/bin:/bin", HOME=str(sb), LANG="C.UTF-8", PYTHONHASHSEED="0",
               PYTHONPATH=str(sb), DYN_CODE="9173337", DYN_LOG=str(log), DYN_MARK=str(mark))
    c = spec[case]
    stdin = "".join(line + "\n" for line in c.get("stdin", []))
    try:
        p = subprocess.run([str(PY), "main.py", *c.get("argv", [])], cwd=sb, env=env, input=stdin,
                           capture_output=True, text=True, timeout=TIMEOUT)
        code, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        code, out, err = "timeout", (e.stdout or b"").decode(errors="replace"), ""
    res = dict(exit=code, stdout=normalise(out, sb), stderr_tail=normalise(err, sb)[-600:],
               commands=normalise(log.read_text(), sb).splitlines() if log.exists() else [],
               exploited=mark.exists())
    shutil.rmtree(sb, ignore_errors=True)
    return res


def programs(pid, base_only):
    yield "vuln", "ORIG", DATA / pid / "vuln.py"
    yield "safe", "ORIG", DATA / pid / "safe.py"
    if base_only:
        return
    for kind in ("vuln", "safe"):
        for f in sorted((VARIANTS / pid / kind).glob("*/main.py")):
            yield kind, f.parent.name, f


def main():
    cwe = arg("--cwe")
    specs = json.loads((SPECS / f"{cwe}.json").read_text())
    ids = arg("--only").split(",") if arg("--only") else sorted(specs)
    jobs = [(pid, kind, variant, path) for pid in ids for kind, variant, path in programs(pid, "--base-only" in sys.argv)]

    def one(job):
        pid, kind, variant, path = job
        return dict(id=pid, kind=kind, variant=variant,
                    normal=run_case(path, specs[pid], "normal"), attack=run_case(path, specs[pid], "attack"))

    with ThreadPoolExecutor(int(arg("--workers", 8))) as ex:
        rows = list(ex.map(one, jobs))
    out = EXP / "results" / "dynamic" / f"{cwe}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    old = {(r["id"], r["kind"], r["variant"]): r for r in json.loads(out.read_text())} if out.exists() else {}
    old.update({(r["id"], r["kind"], r["variant"]): r for r in rows})
    out.write_text(json.dumps(sorted(old.values(), key=lambda r: (r["id"], r["kind"], r["variant"])), indent=1))
    for r in rows:
        if r["variant"] == "ORIG":
            print(f"{r['id']:<10} {r['kind']:<5} attack={'SUCCESS' if r['attack']['exploited'] else 'no':<8}"
                  f" exit={r['attack']['exit']}  normal-cmds={len(r['normal']['commands'])}")
    print(f"{len(rows)} programs run, saved {out.relative_to(EXP)}")


if __name__ == "__main__":
    main()
