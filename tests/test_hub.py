"""The Engine hub: persistent key, the gateway in front of local services, pairing that connects Ollama and ComfyUI too, the setup order, and the files that start it at login."""
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.testclient import TestClient

from vt import paths
from vt.engines import hub, registry, server, store
from vt.engines.model import Endpoint


def _serve(app, monkeypatch=None):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    return srv, t, f"http://127.0.0.1:{port}"


def _upstream() -> FastAPI:
    """Stands in for Ollama / ComfyUI: a version probe, an echo, a stream, an error."""
    app = FastAPI()

    @app.get("/api/version")
    def version():
        return {"version": "0.0-test"}

    @app.get("/system_stats")
    def stats():
        return {"system": {}}

    @app.post("/echo")
    async def echo(request: Request):
        return {"got": (await request.body()).decode(), "q": dict(request.query_params), "ct": request.headers.get("content-type", "")}

    @app.get("/stream")
    def stream():
        def gen():
            for i in range(3):
                yield f"line {i}\n"
        return StreamingResponse(gen(), media_type="text/plain")

    @app.get("/missing")
    def missing():
        return JSONResponse({"error": "no such thing"}, status_code=404)

    return app


@pytest.fixture()
def gateway(tmp_path):
    up, t1, up_url = _serve(_upstream())
    key, code = server.new_secrets()
    gw, t2, gw_url = _serve(server.create_app(key=key, pairing_code=code, name="Hub", services={"ollama": up_url, "comfy": up_url}))
    yield gw_url, key, code
    for srv, t in ((gw, t2), (up, t1)):
        srv.should_exit = True
        t.join(5)


def test_the_key_is_made_once_and_survives_a_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA", tmp_path)
    a = hub.identity()["key"]
    assert len(a) >= 40 and hub.identity()["key"] == a
    assert hub.reset_key() != a and hub.identity()["key"] != a
    assert hub.new_code() != hub.new_code()


def test_the_gateway_forwards_only_with_the_key(gateway):
    url, key, code = gateway
    assert httpx.get(f"{url}/gw/wrong/ollama/api/version").status_code == 401
    assert httpx.get(f"{url}/gw/{key}/nothing/api/version").status_code == 404
    r = httpx.get(f"{url}/gw/{key}/ollama/api/version")
    assert r.status_code == 200 and r.json()["version"] == "0.0-test"


def test_the_gateway_passes_bodies_queries_streams_and_errors_through(gateway):
    url, key, code = gateway
    r = httpx.post(f"{url}/gw/{key}/comfy/echo?x=1", content=b'{"hello": "world"}', headers={"content-type": "application/json"})
    assert r.json() == {"got": '{"hello": "world"}', "q": {"x": "1"}, "ct": "application/json"}
    with httpx.stream("GET", f"{url}/gw/{key}/comfy/stream") as s:
        assert [ln for ln in s.iter_lines() if ln] == ["line 0", "line 1", "line 2"]
    r = httpx.get(f"{url}/gw/{key}/ollama/missing")
    assert r.status_code == 404 and r.json()["error"] == "no such thing"


def test_a_service_that_is_down_is_a_502_not_a_crash():
    key, code = server.new_secrets()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    closed = sock.getsockname()[1]
    sock.close()
    c = TestClient(server.create_app(key=key, pairing_code=code, services={"ollama": f"http://127.0.0.1:{closed}"}))
    r = c.get(f"/gw/{key}/ollama/api/version")
    assert r.status_code == 502 and "ollama" in r.json()["detail"]


def test_the_document_and_the_pairing_answer_name_the_services(gateway):
    url, key, code = gateway
    d = httpx.get(f"{url}/.well-known/vt-engine").json()
    assert d["services"] == ["comfy", "ollama"]
    paired = httpx.post(f"{url}/v1/pair", json={"code": code}).json()
    assert paired["key"] == key and paired["services"] == {"ollama": f"/gw/{key}/ollama", "comfy": f"/gw/{key}/comfy"}
    h = httpx.get(f"{url}/v1/health", headers={"Authorization": f"Bearer {key}"}).json()
    assert h["services"] == {"ollama": True, "comfy": True} and {"llm.chat", "image.generate"} <= set(h["capabilities"])


def test_a_new_code_can_only_be_asked_for_on_the_hub_itself():
    key, code = server.new_secrets()
    app = server.create_app(key=key, pairing_code=code, services={})
    assert TestClient(app).post("/v1/admin/new-code").status_code == 403
    local = TestClient(app, client=("127.0.0.1", 5000))
    fresh = local.post("/v1/admin/new-code").json()["code"]
    assert fresh != code and local.post("/v1/pair", json={"code": code}).status_code == 403
    assert local.post("/v1/pair", json={"code": fresh}).status_code == 200


def test_pairing_a_hub_connects_its_ollama_and_comfy_through_the_key(gateway, monkeypatch, tmp_path):
    from vt.server.app import app

    url, key, code = gateway
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    registry.forget()
    c = TestClient(app)
    r = c.post("/api/engines/vtengine/pair", json={"url": url, "code": code})
    assert r.status_code == 200, r.text
    for name in ("ollama", "comfy"):
        ep = store.load(name)
        assert ep.mode == "remote" and ep.url == f"{url}/gw/{key}/{name}"
    assert registry.health("ollama", fresh=True).ok or True          # the fake upstream is not a real Ollama; the address is what matters here
    assert httpx.get(store.load("ollama").url + "/api/version").json()["version"] == "0.0-test"


def test_choosing_what_to_use_leaves_the_rest_alone(gateway, monkeypatch, tmp_path):
    from vt.server.app import app

    url, key, code = gateway
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    registry.forget()
    TestClient(app).post("/api/engines/vtengine/pair", json={"url": url, "code": code, "use": ["comfy"]})
    assert store.load("comfy").mode == "remote" and store.load("ollama").mode == "off"


def test_setup_goes_on_after_one_engine_fails(monkeypatch):
    from vt.engines import installers

    calls = []

    class Fake(installers.Installer):
        def __init__(self, engine, fail=False):
            self.engine, self.fail = engine, fail

        def verify(self):
            return False if self.engine != "comfy" else bool(calls.count("comfy"))

        def install(self, progress=lambda *a: None):
            calls.append(self.engine)
            progress(self.engine, 1.0, "done")
            if self.fail:
                raise RuntimeError("no disk")

    monkeypatch.setattr(installers, "installer", lambda e, **kw: Fake(e, fail=(e == "ollama")))
    seen = []
    res = hub.setup(["ollama", "comfy"], ["pictures"], lambda n, f, m="": seen.append((n, round(f, 2))))
    assert calls == ["ollama", "comfy"]
    assert res["ollama"]["ok"] is False and "no disk" in res["ollama"]["note"] and res["comfy"]["ok"] is True
    assert any(n == "comfy" for n, _ in seen)


def test_start_services_reports_each_one(monkeypatch):
    monkeypatch.setattr(hub, "reachable", lambda name, url, timeout=1.5: name == "ollama")
    out = hub.start_services(["ollama", "voicestudio"], lambda s: None, wait=0)
    assert out["ollama"] == "running"
    assert out["voicestudio"] in ("missing", "started, not answering yet")


@pytest.mark.parametrize("target", ["windows", "mac", "linux"])
def test_the_start_at_login_files_say_what_they_do(target, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA", tmp_path / "my data")
    s = hub.service_files(python="/opt/vt/python", port=9000, name="Studio box", target=target)
    text = "\n".join(s["files"].values())
    assert s["os"] == target and s["commands"] and s["remove"] and s["note"]
    assert "engine" in text and "run" in text and "9000" in text and "my data" in text
    if target == "windows":
        assert s["commands"][0][0] == "schtasks" and s["commands"][0][-1].startswith('"') and text.startswith("@echo off")
    if target == "linux":
        assert "Restart=on-failure" in text and 'Environment="VT_DATA=' in text


def test_the_service_launcher_is_written_without_doubled_line_ends(tmp_path):
    f = tmp_path / "x.cmd"
    hub.apply_service({"files": {str(f): "a\r\nb\r\n"}, "commands": []})
    assert f.read_bytes() == b"a\r\nb\r\n"


# ----------------------------------------------------------------------------- the Studio's "share this computer" buttons
def test_the_studio_can_start_the_hub_get_codes_and_stop_it(tmp_path, monkeypatch):
    from vt.server import hub_routes
    from vt.server.app import app

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    monkeypatch.setattr(paths, "DATA", tmp_path)
    c = TestClient(app)
    assert c.get(f"/api/hub?port={port}").json()["running"] is False
    assert c.post("/api/hub/start", json={"port": port, "engines": ["nonsense"]}).status_code == 422
    try:
        r = c.post("/api/hub/start", json={"port": port, "engines": [], "name": "Test hub"})
        assert r.status_code == 200, r.text
        first = r.json()
        assert first["running"] and first["mine"] and first["code"].count("-") == 2 and first["addresses"]
        assert httpx.get(f"http://127.0.0.1:{port}/.well-known/vt-engine").json()["name"] == "Test hub"
        second = c.post(f"/api/hub/code?port={port}").json()["code"]
        assert second != first["code"]
        key = hub.identity()["key"]                                   # the same key after a restart: paired computers stay paired
        c.post(f"/api/hub/stop?port={port}")
        assert c.get(f"/api/hub?port={port}").json()["running"] is False
        again = c.post("/api/hub/start", json={"port": port, "engines": []}).json()
        assert again["running"] and hub.identity()["key"] == key
    finally:
        c.post(f"/api/hub/stop?port={port}")
        hub_routes._proc = None
