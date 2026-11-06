"""One server (docs/plans/PLAN-CLIENT-SERVER.MD CS1): the Studio and the engine contract answer on the same port, with one key (and, since decision 7 of
docs/plans/PLAN-PERFECT.MD, no pairing code: the server's own network needs nothing, anyone else needs the key)."""
import pytest
from fastapi.testclient import TestClient

from vt.server import serve
from vt.server.app import app


@pytest.fixture()
def configured(monkeypatch, tmp_path):
    from vt import paths

    monkeypatch.setattr(paths, "DATA", tmp_path)
    saved = {**serve.STATE, "services": dict(serve.STATE["services"])}
    serve.configure(key="k" * 43, name="GPU box", services={"ollama": "http://127.0.0.1:9"}, exposed=True)
    yield serve.STATE
    services = saved.pop("services")
    serve.configure(**{k: saved[k] for k in ("key", "name", "exposed")}, services=services)


def test_the_studio_port_also_speaks_the_engine_contract(configured):
    c = TestClient(app, client=("127.0.0.1", 50000))
    eng = c.get("/.well-known/vt-engine").json()
    assert eng["name"] == "GPU box" and eng["needs_key"] and eng["services"] == ["ollama"] and eng["needs_pairing"] is False
    vt = c.get("/.well-known/video-tool").json()
    assert vt["app"] == "video-tool" and vt["needs_key"] is False                  # this computer needs none; a computer on the internet would
    assert TestClient(app, client=("8.8.8.8", 50000)).get("/.well-known/video-tool").json()["needs_key"] is True
    assert c.get("/api/health").json()["ok"]                                       # the Studio API, same app


def test_the_merged_server_hands_out_no_code(configured):
    c = TestClient(app, client=("10.0.0.7", 50000))
    assert c.post("/v1/pair", json={"code": "ab12-cd34-ef56"}).status_code == 403
    assert c.post("/api/pair", json={"code": "ab12-cd34-ef56"}).status_code in (404, 405)


def test_the_engine_key_opens_the_studio_and_the_engine(configured):
    h = {"Authorization": "Bearer " + "k" * 43}
    for address in ("10.0.0.7", "8.8.8.8"):
        c = TestClient(app, client=(address, 50000))
        assert c.get("/v1/health", headers=h).json()["ok"]
        assert c.get("/api/health", headers=h).status_code == 200
