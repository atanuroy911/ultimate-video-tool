"""One server (docs/plans/PLAN-CLIENT-SERVER.MD CS1): the Studio and the engine contract answer on the same port, with one key and one pairing code."""
import socket
import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient

from vt.engines import vtengine
from vt.server import serve
from vt.server.app import app


@pytest.fixture()
def configured(monkeypatch, tmp_path):
    from vt import paths

    monkeypatch.setattr(paths, "DATA", tmp_path)          # clients.json goes here
    saved = {**serve.STATE, "services": dict(serve.STATE["services"])}
    serve.configure(key="k" * 43, code="ab12-cd34-ef56", name="GPU box", services={"ollama": "http://127.0.0.1:9"}, exposed=True)
    yield serve.STATE
    services = saved.pop("services")
    serve.configure(**{k: saved[k] for k in ("key", "code", "name", "exposed")}, services=services)


def test_the_studio_port_also_speaks_the_engine_contract(configured):
    c = TestClient(app, client=("127.0.0.1", 50000))
    eng =c.get("/.well-known/vt-engine").json()
    assert eng["name"] == "GPU box" and eng["needs_pairing"] and eng["services"] == ["ollama"]
    vt = c.get("/.well-known/video-tool").json()
    assert vt["app"] == "video-tool" and vt["needs_pairing"]
    assert c.get("/api/health").json()["ok"]                      # the Studio API, same app


def test_one_code_pairs_either_kind_of_client_once(configured):
    c = TestClient(app, client=("10.0.0.7", 50000))
    token = c.post("/api/pair", json={"code": "ab12-cd34-ef56"}).json()["key"]
    assert token and token != "k" * 43                                       # a Studio device gets its own token, not the server key
    assert c.post("/v1/pair", json={"code": "ab12-cd34-ef56"}).status_code == 403   # used up, for the engine route too
    assert c.post("/api/pair", json={"code": "ab12-cd34-ef56"}).status_code == 403


def test_the_engine_key_opens_the_studio_and_the_engine(configured):
    c = TestClient(app, client=("10.0.0.7", 50000))
    h = {"Authorization": "Bearer " + "k" * 43}
    assert c.get("/v1/health", headers=h).json()["ok"]
    assert c.get("/api/health", headers=h).status_code == 200


def test_an_engine_client_pairs_with_vt_server_over_real_http(configured):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    try:
        for _ in range(200):
            if srv.started:
                break
            time.sleep(0.05)
        assert vtengine.pair(f"http://127.0.0.1:{port}", "ab12-cd34-ef56") == "k" * 43
    finally:
        srv.should_exit = True
        t.join(5)
