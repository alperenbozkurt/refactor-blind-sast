"""Drive one web endpoint of main.py (imported, never run as a server) and report what SQL it ran.

Usage: python -I web_harness.py <spec.json> <normal|attack>
Run inside a sandbox whose working directory holds main.py. The spec describes the framework, the
endpoint and the parameters for each case. sqlite3's execute/executemany are wrapped so every SQL
statement text and its parameters are recorded. The caller marks the input with a sentinel; if the
sentinel appears inside a statement's text the input reached SQL unsanitised (injectable), if it
appears only in the parameters the query is parameterised (safe).

Output (stdout, one JSON object): status, body (trimmed), the recorded statements and whether the
sentinel reached any statement text ("in_sql") or only parameters ("in_params").
"""
import builtins
import json
import os
import sqlite3
import sys
import traceback

SQL_LOG = []
OPEN_LOG = []
_real_connect = sqlite3.connect
_real_open = builtins.open


def _traced_open(file, *a, **k):
    try:
        OPEN_LOG.append(os.path.realpath(file) if isinstance(file, (str, bytes, os.PathLike)) else str(file))
    except Exception:
        pass
    return _real_open(file, *a, **k)


builtins.open = _traced_open

# programs create their base dirs (often /etc or /var) at import; swallow the failure so the module
# still loads, then make_config_dirs remaps those dirs to writable sandbox folders.
_real_makedirs = os.makedirs


def _safe_makedirs(name, *a, **k):
    try:
        return _real_makedirs(name, *a, **k)
    except OSError:
        return None


os.makedirs = _safe_makedirs
SYS_DIR = ("/etc", "/var", "/opt", "/srv", "/usr", "/root")

CODE_LOG = []
_real_eval, _real_exec, _real_compile = builtins.eval, builtins.exec, builtins.compile


def _traced_eval(code, *a, **k):
    if isinstance(code, str):
        CODE_LOG.append(code)
    return _real_eval(code, *a, **k)


def _traced_exec(code, *a, **k):
    if isinstance(code, str):
        CODE_LOG.append(code)
    return _real_exec(code, *a, **k)


def _traced_compile(src, *a, **k):
    if isinstance(src, str):
        CODE_LOG.append(src)
    return _real_compile(src, *a, **k)


builtins.eval, builtins.exec, builtins.compile = _traced_eval, _traced_exec, _traced_compile

DESER = []  # unsafe-deserializer calls (pickle/marshal/shelve/yaml-without-safe-Loader)


def _patch_deser():
    import pickle
    _pl, _pL = pickle.loads, pickle.load
    pickle.loads = lambda *a, **k: (DESER.append("pickle.loads"), _pl(*a, **k))[1]
    pickle.load = lambda *a, **k: (DESER.append("pickle.load"), _pL(*a, **k))[1]
    try:
        import marshal
        _m = marshal.loads
        marshal.loads = lambda *a, **k: (DESER.append("marshal.loads"), _m(*a, **k))[1]
    except Exception:
        pass
    try:
        import yaml
        _y = yaml.load
        def _yw(*a, **k):
            ldr = k.get("Loader")
            if (ldr is None and len(a) < 2) or getattr(ldr, "__name__", "") in ("Loader", "UnsafeLoader", "FullLoader"):
                DESER.append("yaml.load")
            return _y(*a, **k)
        yaml.load = _yw
    except Exception:
        pass


_patch_deser()


def _rec(sql, params=None):
    SQL_LOG.append({"sql": str(sql), "params": None if params is None else [str(p) for p in _flat(params)]})


def _flat(params):
    if isinstance(params, dict):
        return list(params.values())
    try:
        return list(params)
    except TypeError:
        return [params]


class _CurProxy:
    """sqlite3.Cursor is a C type whose methods cannot be patched, so wrap it by composition."""
    def __init__(self, cur):
        object.__setattr__(self, "_c", cur)

    def execute(self, sql, *a):
        _rec(sql, a[0] if a else None)
        self._c.execute(sql, *a)
        return self

    def executemany(self, sql, *a):
        _rec(sql, a[0] if a else None)
        self._c.executemany(sql, *a)
        return self

    def __getattr__(self, n):
        return getattr(self._c, n)

    def __setattr__(self, n, v):
        setattr(self._c, n, v)

    def __iter__(self):
        return iter(self._c)


class _ConnProxy:
    def __init__(self, conn):
        object.__setattr__(self, "_c", conn)

    def cursor(self, *a, **k):
        return _CurProxy(self._c.cursor(*a, **k))

    def execute(self, sql, *a):
        _rec(sql, a[0] if a else None)
        return _CurProxy(self._c.execute(sql, *a))

    def executemany(self, sql, *a):
        _rec(sql, a[0] if a else None)
        return _CurProxy(self._c.executemany(sql, *a))

    def __getattr__(self, n):
        return getattr(self._c, n)

    def __setattr__(self, n, v):
        setattr(self._c, n, v)

    def __enter__(self):
        self._c.__enter__()
        return self

    def __exit__(self, *a):
        return self._c.__exit__(*a)


def install_sqlite_trace():  # only for SQL-injection runs; it would break aiosqlite's own wrapping
    sqlite3.connect = lambda *a, **k: _ConnProxy(_real_connect(*a, **k))


def _patch_asyncpg():
    """Shim asyncpg (not installed / no Postgres): provide a fake module that records the SQL text so
    the marker-in-query check works for asyncpg programs too."""
    import types
    try:
        import asyncpg
    except Exception:
        asyncpg = types.ModuleType("asyncpg")
        asyncpg.Record = dict
        asyncpg.exceptions = types.SimpleNamespace(PostgresError=Exception, UniqueViolationError=Exception)
        sys.modules["asyncpg"] = asyncpg

    class _Conn:
        async def execute(self, sql, *a): _rec(sql, list(a)); return "OK"
        async def executemany(self, sql, a=()): _rec(sql, list(a)); return "OK"
        async def fetch(self, sql, *a): _rec(sql, list(a)); return []
        async def fetchval(self, sql, *a): _rec(sql, list(a)); return 0
        async def fetchrow(self, sql, *a): _rec(sql, list(a)); return None
        async def close(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    class _Acquire:
        async def __aenter__(self): return _Conn()
        async def __aexit__(self, *a): pass

    class _Pool:
        def acquire(self, *a, **k): return _Acquire()
        async def close(self): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    async def _connect(*a, **k): return _Conn()
    async def _create_pool(*a, **k): return _Pool()
    asyncpg.connect = _connect
    asyncpg.create_pool = _create_pool


_patch_asyncpg()


def setup_django():
    """Configure a minimal Django with a sandbox sqlite DB before main.py's `from django.db import
    connection` runs. Django's backend calls sqlite3.dbapi2.connect, so patch that too."""
    import django
    from django.conf import settings
    if not settings.configured:
        settings.configure(DEBUG=True, DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3",
                            "NAME": os.path.abspath("django.db")}}, INSTALLED_APPS=[], ALLOWED_HOSTS=["*"],
                            USE_TZ=True, DEFAULT_CHARSET="utf-8")
        django.setup()
    from django.conf import LazySettings  # the program may also call settings.configure(); make it idempotent
    _ocfg = LazySettings.configure
    LazySettings.configure = lambda self, *a, **k: None if self.configured else _ocfg(self, *a, **k)
    sqlite3.dbapi2.connect = lambda *a, **k: _ConnProxy(_real_connect(*a, **k))


def load_module(framework=None):
    if framework == "django":
        setup_django()
    import importlib.util
    spec = importlib.util.spec_from_file_location("main", "main.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["main"] = m
    spec.loader.exec_module(m)
    return m


def call_target(m, target, *a, **k):
    """Resolve 'func' or 'Class.method'/'instance.method' on the module and call it."""
    parts = target.split(".")
    if len(parts) == 1:
        return getattr(m, parts[0])(*a, **k)
    obj = getattr(m, parts[0])
    if not isinstance(obj, type):          # module-level instance (e.g. report_storage) -> use it directly
        return getattr(obj, parts[1])(*a, **k)
    try:
        inst = obj()
    except Exception:
        inst = obj.__new__(obj)
    return getattr(inst, parts[1])(*a, **k)


def drive_direct(m, spec, case):
    """Call the vulnerable function/method by name (preserved across refactorings) with a mock request,
    bypassing routing. Used for frameworks without a simple in-process client."""
    c = spec[case]
    fw, target = spec["framework"], spec["target"]
    method, params, body = c.get("method", "GET"), c.get("params", {}), c.get("json")
    kw = c.get("kwargs", {})
    if fw == "plain":
        # call the vulnerable method directly (e.g. socket handlers, file readers) with a pickle
        # payload, a fake connection, or a traversal path; the tracers report whether the sink fired
        import base64
        payload = base64.b64decode(spec["payload_b64"]) if spec.get("payload_b64") else b""
        trav = "../" * 12 + "tmp/dynmark/" + spec.get("trav_name", "MARKER.txt")

        class _FakeConn:
            def __init__(self, data):
                self._d = data
            def recv(self, *a):
                d, self._d = self._d, b""
                return d
            def sendall(self, *a, **k): pass
            def send(self, *a, **k): pass
            def close(self, *a, **k): pass
            def __getattr__(self, n): return lambda *a, **k: None

        built = []
        for spec_arg in c.get("args", []):
            if spec_arg == "payload":
                built.append(payload)
            elif spec_arg == "conn":
                built.append(_FakeConn(payload))
            elif spec_arg == "addr":
                built.append(("127.0.0.1", 0))
            elif spec_arg == "meta_dict":
                built.append({"metadata": payload, "binary": "AA==", "device_id": "d", "version": "1"})
            elif spec_arg == "task_dict":
                built.append({"function": payload, "args": payload, "kwargs": payload})
            elif spec_arg == "path":
                built.append(trav)
            elif spec_arg == "path_normal":
                built.append("ok.txt")
            else:
                built.append(spec_arg)
        try:
            if spec.get("flask_ctx") and getattr(m, "app", None) is not None:
                with m.app.test_request_context(), m.app.app_context():
                    call_target(m, target, *built, **kw)
            else:
                call_target(m, target, *built, **kw)
        except Exception:
            pass
        return None, ""
    if fw == "django":
        from django.test import RequestFactory
        rf = RequestFactory()
        if method == "GET":
            req = rf.get("/", data=params)
        else:
            req = rf.post("/", data=json.dumps(body) if body is not None else params,
                          content_type="application/json" if body is not None else "application/x-www-form-urlencoded")
        resp = call_target(m, target, req, **kw)
        return getattr(resp, "status_code", None), getattr(resp, "content", b"").decode("utf-8", "replace")
    if fw == "pyramid":
        from pyramid import testing
        req = testing.DummyRequest(post=params, params=params)
        req.method = method
        if c.get("matchdict"): req.matchdict = c["matchdict"]
        if body is not None:
            req.json_body = body
        resp = call_target(m, target, req, **kw)
        txt = getattr(resp, "body", getattr(resp, "text", ""))
        return getattr(resp, "status_code", None), (txt.decode() if isinstance(txt, bytes) else str(txt))
    if fw == "tornado":
        import tornado.web
        import tornado.httputil
        from urllib.parse import urlencode
        clsname, meth = target.split(".")
        HandlerCls = getattr(m, clsname)
        app = m.make_app() if hasattr(m, "make_app") else tornado.web.Application()
        init_kwargs = {}
        for router in (getattr(app, "wildcard_router", None), getattr(app, "default_router", None)):
            for rule in getattr(router, "rules", []):
                tgt = getattr(rule, "target", None)
                if tgt is HandlerCls or getattr(tgt, "__name__", None) == clsname:
                    init_kwargs = getattr(rule, "target_kwargs", None) or {}
        uri = "/?" + urlencode(params) if method == "GET" else "/"
        if c.get("json") is not None:
            body, ctype = json.dumps(c["json"]).encode(), "application/json"
        else:
            body, ctype = (urlencode(params).encode() if method != "GET" else b""), "application/x-www-form-urlencoded"
        req = tornado.httputil.HTTPServerRequest(method=method, uri=uri, body=body,
                                                 headers=tornado.httputil.HTTPHeaders({"Content-Type": ctype}))
        tornado.httputil.parse_body_arguments(ctype, body, req.body_arguments, req.files)  # tornado does this per request

        class _Stub:  # minimal connection so RequestHandler can be constructed without a server
            def set_close_callback(self, *a): pass
            def write_headers(self, *a, **k): pass
            def write(self, *a, **k): pass
            def finish(self, *a, **k): pass
        req.connection = _Stub()
        h = HandlerCls(app, req, **init_kwargs)
        h._transforms = []
        out = {"body": "", "status": 200}
        h.write = lambda chunk, *a, **k: out.__setitem__("body", out["body"] + (json.dumps(chunk) if not isinstance(chunk, (str, bytes)) else (chunk.decode() if isinstance(chunk, bytes) else chunk)))
        h.set_status = lambda code, *a: out.__setitem__("status", code)
        h.finish = lambda *a, **k: None
        h.flush = lambda *a, **k: None
        getattr(h, meth)(*kw.values())
        return out["status"], out["body"]
    raise SystemExit(f"no direct driver for {fw}")


def wsgi_app(m, spec):
    fw = spec["framework"]
    if fw == "flask":
        return m.app
    if fw == "bottle":
        return next(v for v in vars(m).values() if type(v).__name__ == "Bottle")
    if fw == "pyramid":
        return m.main({})
    if fw == "cherrypy":
        import cherrypy
        root = getattr(m, spec.get("cherrypy_root", "root"), None)
        if root is None:
            classes = [v for v in vars(m).values() if isinstance(v, type) and v.__module__ == "main"]
            # prefer the class that actually exposes handlers (has an index or an @cherrypy.expose method)
            cls = next((c for c in classes if any(getattr(getattr(c, a, None), "exposed", False) or a == "index"
                                                  for a in dir(c))), classes[0] if classes else None)
            root = cls()
        app = cherrypy.tree.mount(root, "/")
        return app
    if fw == "django":
        return m.application
    raise SystemExit(f"no wsgi for {fw}")


def drive(m, spec, case):
    """Run the case's request, or its list of ``steps`` (e.g. POST to store then GET to view, for
    stored XSS), sharing one client and the module's state across steps; return the LAST response."""
    c = spec[case]
    reqs = c["steps"] if "steps" in c else [c]
    fw = spec["framework"]
    last = (None, "")

    if fw in ("flask", "bottle", "pyramid", "cherrypy", "django"):
        from webtest import TestApp
        app = TestApp(wsgi_app(m, spec))
        for req in reqs:
            method, path, params, body = req.get("method", "GET"), req["path"], req.get("params", {}), req.get("json")
            up = req.get("upload")  # [field, filename, base64-bytes] -> multipart file upload
            if up:
                import base64 as _b64
                r = app.post(path, params=params, upload_files=[(up[0], up[1], _b64.b64decode(up[2]))], expect_errors=True)
                last = (r.status_int, r.text)
                continue
            fn = {"GET": app.get, "POST": app.post_json if body is not None else app.post,
                  "PUT": app.put_json if body is not None else app.put, "DELETE": app.delete}[method]
            hdr = req.get("headers")
            if method in ("GET", "DELETE"):
                r = fn(path, params=params, headers=hdr, expect_errors=True)
            elif body is not None:
                r = fn(path + (("?" + "&".join(f"{k}={v}" for k, v in params.items())) if params else ""), body, expect_errors=True)
            else:
                r = fn(path, params=params, expect_errors=True)
            last = (r.status_int, r.text)
        return last
    if fw in ("fastapi", "starlette"):
        from fastapi.testclient import TestClient
        with TestClient(m.app) as cl:
            for req in reqs:
                r = cl.request(req.get("method", "GET"), req["path"], params=req.get("params", {}),
                               json=req.get("json"), data=req.get("data"), headers=req.get("headers"))
                last = (r.status_code, r.text)
        return last
    if fw == "quart":
        # drive via ASGI + httpx with a real lifespan startup; quart's own test_client rejects some
        # form posts (400) without the app fully started
        import asyncio
        import httpx
        app = m.app

        async def go():
            q = asyncio.Queue()
            await q.put({"type": "lifespan.startup"})
            ls = asyncio.ensure_future(app({"type": "lifespan"}, q.get, lambda msg: asyncio.sleep(0)))
            await asyncio.sleep(0.2)
            out = (None, "")
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as cl:
                    for req in reqs:
                        r = await cl.request(req.get("method", "GET"), req["path"], params=req.get("params", {}),
                                             json=req.get("json"), data=req.get("data"), headers=req.get("headers"),
                                             follow_redirects=True)
                        out = (r.status_code, r.text)
            finally:
                await q.put({"type": "lifespan.shutdown"})
                try:
                    await asyncio.wait_for(ls, timeout=2)
                except Exception:
                    ls.cancel()
            return out
        return asyncio.get_event_loop().run_until_complete(go())
    if fw == "sanic":
        # drive Sanic through its ASGI interface (its sanic-testing client is broken in this version)
        import asyncio
        import httpx
        app = next(v for v in vars(m).values() if type(v).__name__ == "Sanic")

        from sanic_routing.exceptions import NotFound as _NF
        def _raise_nf(*a, **k):  # the generated signal find_route references NotFound without importing it
            raise _NF("no signal route")
        app.signal_router.get = _raise_nf

        async def go():
            # run the ASGI lifespan startup (httpx does not); this sets app.loop so requests can run
            q = asyncio.Queue()
            await q.put({"type": "lifespan.startup"})
            ls = asyncio.ensure_future(app({"type": "lifespan"}, q.get, lambda m: asyncio.sleep(0)))
            await asyncio.sleep(0.2)
            out = (None, "")
            try:
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as cl:
                    for req in reqs:
                        r = await cl.request(req.get("method", "GET"), req["path"], params=req.get("params", {}),
                                             json=req.get("json"), data=req.get("data"), headers=req.get("headers"))
                        out = (r.status_code, r.text)
            finally:
                await q.put({"type": "lifespan.shutdown"})
                try:
                    await asyncio.wait_for(ls, timeout=2)
                except Exception:
                    ls.cancel()
            return out
        return asyncio.get_event_loop().run_until_complete(go())
    if fw == "falcon":
        # call the WSGI app with a plain BytesIO environ; TestClient wraps wsgi.input in wsgiref's
        # validator, which rejects the handlers' req.stream.read() (no size arg) that works on a real server
        from falcon.testing import create_environ, StartResponseMock
        from urllib.parse import urlencode
        app = getattr(m, "app", None) or next(v for v in vars(m).values() if type(v).__name__ in ("App", "API"))
        for req in reqs:
            body = json.dumps(req["json"]) if req.get("json") is not None else ""
            hdrs = dict(req.get("headers") or {})
            if req.get("json") is not None:
                hdrs.setdefault("Content-Type", "application/json")
            env = create_environ(path=req["path"], method=req.get("method", "GET"),
                                 query_string=urlencode(req.get("params", {})), body=body, headers=hdrs)
            srm = StartResponseMock()
            chunks = app(env, srm)
            text = b"".join(chunks).decode("utf-8", "replace")
            last = (int(srm.status.split()[0]) if srm.status else None, text)
        return last
    if fw == "aiohttp":
        import asyncio
        from aiohttp import web as aweb
        from aiohttp.test_utils import TestClient, TestServer
        app = getattr(m, "app", None)
        if app is None:
            app = aweb.Application()
            app.add_routes(m.routes)

        async def go():
            out = (None, "")
            async with TestClient(TestServer(app)) as cl:
                for req in reqs:
                    r = await cl.request(req.get("method", "GET"), req["path"], params=req.get("params", {}),
                                         json=req.get("json"), headers=req.get("headers"))
                    out = (r.status, await r.text())
            return out
        return asyncio.get_event_loop().run_until_complete(go())
    raise SystemExit(f"no driver for {fw}")


def make_config_dirs(m):
    """Point every configured directory (UPLOAD_FOLDER, LOG_DIR, ...) at a writable sandbox folder and
    create it, so that ../ traversal out of it resolves. The real program creates these in __main__,
    which import does not run, and some point at /etc or /var which cannot be created here. The app's
    own path-safety checks use the same remapped value, so a fixed version still blocks the traversal."""
    def remap(val):
        local = os.path.abspath("_b_" + str(abs(hash(val))))
        _real_makedirs(local, exist_ok=True)
        return local

    cfg = getattr(getattr(m, "app", None), "config", None)
    if cfg:
        for k, v in list(cfg.items()):
            if isinstance(v, str) and v not in ("/", "") and any(t in k for t in
                                                                 ("ROOT", "DIR", "FOLDER", "TEMPLATES", "SOURCES")):
                cfg[k] = remap(v)
    # base dirs kept as instance attributes of the program's own classes (self.base_dir = '/etc/...')
    for obj in list(vars(m).values()):
        try:
            if getattr(type(obj), "__module__", "") != "main":  # skip proxies (request), framework objects
                continue
            d = obj.__dict__
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        for k, v in list(d.items()):
            if isinstance(v, str) and (v.startswith(SYS_DIR) or any(t in k.lower() for t in
                                       ("dir", "root", "folder", "path", "base"))) and v not in ("/", "", "."):
                if v.startswith(SYS_DIR) or not os.path.isabs(v):
                    try:
                        setattr(obj, k, remap(v))
                    except Exception:
                        pass
    # dir constants on the program's own classes (e.g. BASE_DIR = './files' on an http.server handler):
    # create them so that ../ traversal out of them resolves (http.server has no app.config)
    for cls in [v for v in vars(m).values() if isinstance(v, type) and getattr(v, "__module__", "") == "main"]:
        for k in list(vars(cls)):
            v = getattr(cls, k, None)
            if isinstance(v, str) and not os.path.isabs(v) and v not in ("", ".", "/") and any(
                    t in k.lower() for t in ("dir", "root", "folder")):
                try:
                    _real_makedirs(v, exist_ok=True)
                except OSError:
                    pass


def main():
    spec = json.loads(open(sys.argv[1]).read())
    case = sys.argv[2]
    sentinel = spec.get("sentinel")
    marker = spec.get("leak_marker")
    open_marker = os.path.realpath(spec["open_marker"]) if spec.get("open_marker") else None
    out = dict(status=None, body="", statements=[], error=None, in_sql=False, in_params=False,
               leaked=False, opened_marker=False)
    if sentinel:  # SQL-injection runs need the sqlite tracer; others (XSS/aiosqlite) must not have it
        install_sqlite_trace()
    try:
        m = load_module(spec.get("framework"))
        make_config_dirs(m)
        if "seed" in spec and hasattr(m, spec["seed"]):
            getattr(m, spec["seed"])()
        for ps in spec.get(case, {}).get("pre_sql", []):  # seed a DB row directly (store endpoint unusable)
            import sqlite3 as _s
            c = _real_connect(ps["db"])
            c.execute(ps["sql"], [marker if x == "@MARKER@" else x for x in ps.get("params", [])])
            c.commit(); c.close()
        setup = spec.get(case, {}).get("setup")
        if setup:  # inject stored state directly (the vuln sink is the view/render, not the store path)
            def _fill(x):
                if isinstance(x, str):
                    return x.replace("@MARKER@", marker or "")
                if isinstance(x, dict):
                    return {k: _fill(v) for k, v in x.items()}
                if isinstance(x, list):
                    return [_fill(v) for v in x]
                return x
            for gname, gval in setup.items():
                setattr(m, gname, _fill(gval))
        for pc in spec.get(case, {}).get("pre_calls", []):  # store data first (stored XSS), then view
            args = [marker if x == "marker" else x for x in pc.get("args", [])]
            try:
                call_target(m, pc["target"], *args)
            except Exception:
                pass
        status, body = drive_direct(m, spec, case) if spec.get("direct") else drive(m, spec, case)
        out["status"], out["body"] = status, body[:1200]
        if marker and marker in body:
            out["leaked"] = True
    except Exception:
        out["error"] = traceback.format_exc()[-800:]
    if open_marker and any(p == open_marker for p in OPEN_LOG):
        out["opened_marker"] = True
    code_marker = spec.get("code_marker")
    out["code_sink"] = bool(code_marker and any(code_marker in c for c in CODE_LOG))
    out["deser_sink"] = bool(spec.get("deser_marker") and DESER)
    out["statements"] = SQL_LOG
    for s in SQL_LOG:
        if sentinel and sentinel in s["sql"]:
            out["in_sql"] = True
        if sentinel and s["params"] and any(sentinel in p for p in s["params"]):
            out["in_params"] = True
    print(json.dumps(out))


if __name__ == "__main__":
    main()
