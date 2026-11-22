"""Targeted probes for the six fixed programs that both LLM reviewers flagged.

Usage (inside a sandbox holding main.py and web_harness.py):
    python -I probe_harness.py <probe> [page_out]

Each probe tries the path a fix may have left open, with a harmless marker, and prints one JSON line.
Importing web_harness installs its tracers (file opens, unsafe deserializers).
"""
import base64
import contextlib
import io
import json
import os
import pickle
import sys
import tarfile
import traceback
import types

sys.path.insert(0, os.getcwd())  # -I leaves the sandbox directory off the import path
import web_harness as W  # noqa: E402

# joblib and other pure-Python unpicklers go through pickle._Unpickler, which web_harness does not trace
_real_unpickler_load = pickle._Unpickler.load


def _traced_unpickler_load(self, *a, **k):
    W.DESER.append("pickle._Unpickler.load")
    return _real_unpickler_load(self, *a, **k)


pickle._Unpickler.load = _traced_unpickler_load

BENIGN_PICKLE = base64.b64decode("gASVDQAAAAAAAAB9lIwCenqUjAFNlHMu")  # {'zz': 'M'}
MARK = "ZZPROBE_MARKER"


def stub_modules(*names):
    """Unused optional imports (h5py, onnxruntime) are missing from the sandbox environment."""
    for n in names:
        try:
            __import__(n)
        except ImportError:
            sys.modules[n] = types.ModuleType(n)


def load(framework=None):
    m = W.load_module(framework)
    W.make_config_dirs(m)
    return m


def sibling_http(out):
    """22_DS-1: request a file in a sibling directory whose name extends the base directory."""
    m = load()
    cls = m.FileServerHandler
    base = os.path.abspath(cls.BASE_DIR)
    sib = base + "_zz"
    os.makedirs(sib, exist_ok=True)
    target = os.path.join(sib, "MARK.txt")
    with open(target, "w") as f:
        f.write(MARK)
    h = cls.__new__(cls)
    h.wfile = io.BytesIO()
    h.send_response = h.send_header = h.end_headers = lambda *a, **k: None
    h.serve_file("../" + os.path.basename(sib) + "/MARK.txt")
    out["leaked"] = MARK.encode() in h.wfile.getvalue()
    out["opened"] = os.path.realpath(target) in W.OPEN_LOG


def sibling_flask(out):
    """22_DS-2: same, through the view function with an allowed extension."""
    m = load("flask")
    up = os.path.abspath(m.app.config["UPLOAD_FOLDER"])
    sib = up + "_zz"
    os.makedirs(sib, exist_ok=True)
    target = os.path.join(sib, "x.png")
    with open(target, "w") as f:
        f.write(MARK)
    with m.app.test_request_context():
        try:
            resp = m.download_image("../" + os.path.basename(sib) + "/x.png")
            resp.direct_passthrough = False
            out["leaked"] = MARK.encode() in resp.get_data()
        except Exception as e:  # abort() raises an HTTPException
            out["leaked"] = False
            out["raised"] = type(e).__name__ + ": " + str(e)[:120]
    out["opened"] = os.path.realpath(target) in W.OPEN_LOG


def tar_slip(out):
    """22_DS-6: restore an archive whose member name climbs out of the extraction directory."""
    m = load("flask")
    bd = os.path.abspath(m.app.config["BACKUP_DIR"])
    os.makedirs(bd, exist_ok=True)
    data = MARK.encode()
    with tarfile.open(os.path.join(bd, "b.tar.gz"), "w:gz") as tar:
        info = tarfile.TarInfo("../zz_tarslip.txt")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    escaped = os.path.join(os.path.dirname(bd), "zz_tarslip.txt")
    out["returned"] = repr(m.BackupManager().restore_backup("b.tar.gz"))
    out["written_outside"] = os.path.exists(escaped)


def joblib_upload(out):
    """502_DS-8: upload a benign pickle with an allowed extension."""
    stub_modules("h5py", "onnxruntime")
    m = load("flask")
    from webtest import TestApp
    r = TestApp(m.app).post("/upload_model", upload_files=[("model", "m.joblib", BENIGN_PICKLE)], expect_errors=True)
    out["status"] = r.status_int
    out["deser"] = list(W.DESER)


def restricted_unpickler(out):
    """502_DS-1: hand the loader the uploaded bytes, as the program's POST handler does."""
    real = pickle.Unpickler

    def construct(*a, **k):  # returns the real class, so the program's behaviour is unchanged
        W.DESER.append("pickle.Unpickler()")
        return real(*a, **k)

    pickle.Unpickler = construct
    m = load()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out["returned"] = repr(m.AnalyticsConfig().load_from_pickle(BENIGN_PICKLE))
    out["printed"] = buf.getvalue().strip()[:200]
    out["deser"] = list(W.DESER)


def profile_page(out, page_out):
    """79_DS-19: render the profile page twice, once with a bio that tries to close the script block
    (written to <page_out>.bio.html) and once with a plain bio, for the welcome-parameter test
    (<page_out>.plain.html). The two attacks are kept apart because the first breaks the page script."""
    m = load("sanic")
    c = W._real_connect("profiles.db")
    c.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT, full_name TEXT, bio TEXT, created_at TEXT)")
    c.commit()
    c.close()
    spec = {"framework": "sanic", "attack": {"steps": [{"method": "GET", "path": "/profile",
                                                         "params": {"username": "zz", "theme": "light"}}]}}
    # no quotes in the tag, so JSON escaping cannot alter the id attribute
    for label, bio in (("bio", "</script><b id=zzbio>ZZBIO</b><script>"), ("plain", "b")):
        c = W._real_connect("profiles.db")
        c.execute("DELETE FROM users")
        c.execute("INSERT INTO users (id,username,full_name,bio,created_at) VALUES (?,?,?,?,?)", ("id1", "zz", "x", bio, "2026"))
        c.commit()
        c.close()
        status, body = W.drive(m, spec, "attack")
        out[f"status_{label}"] = status
        with W._real_open(f"{page_out}.{label}.html", "w") as f:
            f.write(body)


PROBES = {"sibling_http": sibling_http, "sibling_flask": sibling_flask, "tar_slip": tar_slip,
          "joblib_upload": joblib_upload, "restricted_unpickler": restricted_unpickler}


def main():
    name = sys.argv[1]
    out = {"probe": name, "error": None}
    try:
        if name == "profile_page":
            profile_page(out, sys.argv[2])
        else:
            PROBES[name](out)
    except Exception:
        out["error"] = traceback.format_exc()[-600:]
    print(json.dumps(out))


if __name__ == "__main__":
    main()
