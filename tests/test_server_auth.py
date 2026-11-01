"""The token guard (docs/plans/PLAN-CLIENT-SERVER.MD CS2): another computer needs the key for /api, /ws and /media; this computer does not."""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vt.server import serve
from vt.server.app import app

KEY = "k" * 43
REMOTE = ("192.168.1.20", 50000)


@pytest.fixture()
def exposed(monkeypatch, tmp_path):
    from vt import paths

    monkeypatch.setattr(paths, "DATA", tmp_path)          # clients.json goes here
    saved = {**serve.STATE, "services": dict(serve.STATE["services"])}
    serve.configure(key=KEY, code="ab12-cd34-ef56", exposed=True)
    yield
    services = saved.pop("services")
    serve.configure(**{k: saved[k] for k in ("key", "code", "name", "exposed")}, services=services)


def test_another_computer_without_the_key_is_turned_away(exposed):
    c = TestClient(app, client=REMOTE)
    r = c.get("/api/health")
    assert r.status_code == 401 and "pairing" in r.json()["detail"]["errors"][0]
    assert c.get("/media/anything/x.mp3").status_code == 401
    assert c.get("/api/health", headers={"Authorization": "Bearer wrong"}).status_code == 401
    with pytest.raises(WebSocketDisconnect) as e:
        with c.websocket_connect("/ws"):
            pass
    assert e.value.code == 4401


def test_the_key_works_as_header_cookie_or_query(exposed):
    c = TestClient(app, client=REMOTE)
    assert c.get("/api/health", headers={"Authorization": f"Bearer {KEY}"}).status_code == 200
    assert c.get(f"/api/health?token={KEY}").status_code == 200
    c.post("/api/pair", json={"code": "ab12-cd34-ef56"})          # sets the cookie the Studio page then sends by itself
    assert c.get("/api/health").status_code == 200
    with c.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"


def test_discovery_pairing_and_the_page_need_no_key(exposed):
    c = TestClient(app, client=REMOTE)
    assert c.get("/.well-known/video-tool").status_code == 200
    assert c.get("/.well-known/vt-engine").status_code == 200
    assert c.get("/").status_code == 200


def test_this_computer_needs_no_key_unless_a_proxy_forwarded_it(exposed):
    local = TestClient(app, client=("127.0.0.1", 50000))
    assert local.get("/api/health").status_code == 200
    assert local.get("/api/health", headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 401
    assert local.get("/api/health", headers={"CF-Connecting-IP": "203.0.113.9"}).status_code == 401


def test_a_loopback_only_studio_keeps_working_without_pairing():
    assert not serve.STATE["exposed"]
    assert TestClient(app, client=REMOTE).get("/api/health").status_code == 200


def test_a_new_pairing_code_comes_from_the_server_page_not_a_command(exposed):
    here = TestClient(app, client=("127.0.0.1", 50000))
    info = here.get("/api/server").json()
    assert info["exposed"] and info["addresses"]
    code = here.post("/api/server/code").json()["code"]
    away = TestClient(app, client=REMOTE)
    assert away.post("/api/server/code", headers={"Authorization": f"Bearer {KEY}"}).status_code == 403   # even paired, not from afar
    assert "addresses" not in away.get("/api/server", headers={"Authorization": f"Bearer {KEY}"}).json()
    assert away.post("/api/pair", json={"code": code}).status_code == 200


def test_each_device_has_its_own_token_and_one_can_be_turned_away(exposed):
    here = TestClient(app, client=("127.0.0.1", 50000))
    phone, laptop = TestClient(app, client=REMOTE), TestClient(app, client=("192.168.1.21", 50000))
    phone.post("/api/pair", json={"code": "ab12-cd34-ef56"}, headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Mobile"})
    laptop.post("/api/pair", json={"code": here.post("/api/server/code").json()["code"], "device": "Roy's laptop"})
    devices = here.get("/api/server/clients").json()
    assert [d["name"] for d in devices] == ["Chrome on Android", "Roy's laptop"] and "hash" not in devices[0]
    assert phone.get("/api/health").status_code == 200 and laptop.get("/api/health").status_code == 200
    assert phone.get("/api/server/clients").status_code == 403                      # managed only on the server computer
    assert here.delete(f"/api/server/clients/{devices[0]['id']}").json()["ok"]
    assert phone.get("/api/health").status_code == 401 and laptop.get("/api/health").status_code == 200
    assert here.delete(f"/api/server/clients/{devices[0]['id']}").status_code == 404


def test_the_server_can_start_by_itself_the_same_way(exposed, monkeypatch, tmp_path):
    from pathlib import Path

    from vt.engines import hub

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    ran = []
    monkeypatch.setattr(hub, "apply_service", lambda spec: [ran.append(spec), *[Path(f).parent.mkdir(parents=True, exist_ok=True) or Path(f).write_text(t) for f, t in spec["files"].items()]] and ["ok"])
    monkeypatch.setattr(serve.subprocess, "run", lambda cmd, **kw: ran.append(cmd) or type("R", (), {"returncode": 0})())
    here = TestClient(app, client=("127.0.0.1", 50000))
    assert "autostart" not in here.get("/api/server").json()                         # not started by `vt server`: nothing to repeat
    serve.STATE["argv"] = ["server", "--host", "0.0.0.0", "--comfy", "existing", "--comfy-url", "http://127.0.0.1:8188,http://127.0.0.1:8189", "--port", "8767"]
    assert here.get("/api/server").json()["autostart"] is False
    assert TestClient(app, client=REMOTE).post("/api/server/autostart", json={"on": True}, headers={"Authorization": f"Bearer {KEY}"}).status_code == 403
    r = here.post("/api/server/autostart", json={"on": True}).json()
    text = "\n".join(ran[0]["files"].values())
    assert r["autostart"] and "--comfy-url" in text and "8767" in text and "engine run" not in text
    assert here.get("/api/server").json()["autostart"] is True
    assert here.post("/api/server/autostart", json={"on": False}).json()["autostart"] is False
    assert here.get("/api/server").json()["autostart"] is False
    serve.STATE["argv"] = None
