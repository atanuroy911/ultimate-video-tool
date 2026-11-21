"""With "Computers on my network can connect without the key" turned on (docs/plans/PLAN-WORKBENCH.MD, decision D4), the server's own network needs no key:
typing the address is enough. A request from outside that network, one a proxy forwarded, and one that comes through a web page in someone's browser still
need the server's key. With it off (the default), only this computer is let in without the key: tests/test_server_webpage_guard.py."""
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vt import directors
from vt.server import serve
from vt.server.app import app

KEY = "k" * 43
HOME = ("192.168.1.20", 50000)            # another computer on the home network
OUTSIDE = ("8.8.8.8", 50000)              # an address on the internet
HERE = ("127.0.0.1", 50000)


@pytest.fixture()
def exposed(monkeypatch, tmp_path):
    from vt import paths

    monkeypatch.setattr(paths, "DATA", tmp_path)
    saved = {**serve.STATE, "services": dict(serve.STATE["services"])}
    serve.configure(key=KEY, exposed=True, trust_network=True)               # the person turned the setting on; the default is in test_server_webpage_guard.py
    yield
    services = saved.pop("services")
    serve.configure(**{k: saved[k] for k in ("key", "name", "exposed")}, services=services)


@pytest.fixture(autouse=True)
def _no_one_left_connected():
    yield
    for d in directors.broker.devices():
        directors.broker.disconnect(d.device_id)


@pytest.mark.parametrize("address", ["192.168.1.20", "10.0.0.7", "172.16.5.5", "169.254.3.4", "100.101.102.103", "127.0.0.1", "::1", "fd12:3456::1", "fe80::1", "::ffff:192.168.1.9"])
def test_a_computer_on_the_same_network_needs_nothing(exposed, address):
    c = TestClient(app, client=(address, 50000))
    assert c.get("/api/health").status_code == 200
    assert c.get("/media/anything/x.mp3").status_code == 404                  # past the guard, the file is just not there
    assert c.post("/mcp", json={}).status_code != 401                         # the assistant tools follow the same rule (they are not mounted in this test)
    with c.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"


@pytest.mark.parametrize("address", ["8.8.8.8", "1.1.1.1", "2606:4700::1111", "11.0.0.1", "172.32.0.1", "100.63.0.1", "100.128.0.1"])
def test_an_address_on_the_internet_needs_the_servers_key(exposed, address):
    c = TestClient(app, client=(address, 50000))
    r = c.get("/api/health")
    assert r.status_code == 401 and "Copy key" in r.json()["detail"]["errors"][0] and "pairing" not in r.text.lower()
    assert c.get("/media/anything/x.mp3").status_code == 401
    assert c.post("/mcp", json={}).status_code == 401
    assert c.get("/api/health", headers={"Authorization": "Bearer wrong"}).status_code == 401
    with pytest.raises(WebSocketDisconnect) as e:
        with c.websocket_connect("/ws"):
            pass
    assert e.value.code == 4401


def test_the_key_still_works_from_outside_as_header_cookie_or_query(exposed):
    c = TestClient(app, client=OUTSIDE)
    assert c.get("/api/health", headers={"Authorization": f"Bearer {KEY}"}).status_code == 200
    assert c.get(f"/api/health?token={KEY}").status_code == 200
    assert TestClient(app, client=OUTSIDE, cookies={"vt_token": KEY}).get("/api/health").status_code == 200
    assert c.post("/mcp", json={}, headers={"Authorization": f"Bearer {KEY}"}).status_code == 404       # let in, and the tools are not mounted here
    with c.websocket_connect("/ws", headers={"Authorization": f"Bearer {KEY}"}) as ws:
        assert ws.receive_json()["type"] == "hello"


def test_a_request_a_proxy_forwarded_is_an_outside_one_even_from_this_computer(exposed):
    local = TestClient(app, client=HERE)
    assert local.get("/api/health").status_code == 200
    for header in ("X-Forwarded-For", "CF-Connecting-IP", "X-Real-IP", "Forwarded"):
        assert local.get("/api/health", headers={header: "203.0.113.9"}).status_code == 401, header


def test_a_web_page_cannot_use_the_server(exposed):
    c = TestClient(app, client=HOME)
    assert c.get("/api/health").status_code == 200
    # a page from another site (its Origin is not this server) and a sandboxed one
    assert c.get("/api/health", headers={"Origin": "https://evil.example"}).status_code == 401
    assert c.get("/api/health", headers={"Origin": "null"}).status_code == 401
    assert c.post("/mcp", json={}, headers={"Origin": "https://evil.example"}).status_code == 401
    # a page that makes a name of its own point at this computer ("DNS rebinding"): its Host is not an address or a local name
    assert c.get("/api/health", headers={"Host": "evil.example.com"}).status_code == 401
    assert c.get("/api/health", headers={"Host": "evil.example.com:8790", "Origin": "http://evil.example.com:8790"}).status_code == 401
    # the server's own page, and the ways people really reach it
    assert c.get("/api/health", headers={"Origin": "http://testserver"}).status_code == 200                # the Studio served by this server
    for host in ("192.168.1.5:8790", "[fd12::5]:8790", "localhost:8790", "roy-ct500:8790", "video-box.local", "box.lan:8790", "box.home.arpa", "roy-ct500.tailnet-1.ts.net"):
        assert c.get("/api/health", headers={"Host": host}).status_code == 200, host
    assert c.get("/api/health", headers={"Host": "192.168.1.5:8790", "Origin": "http://192.168.1.5:8790"}).status_code == 200
    assert c.get("/api/health", headers={"Host": "192.168.1.5:8790", "Origin": "http://192.168.1.6:8790"}).status_code == 401
    # a page cannot open the live connection either, and the key still opens everything for a program that has it
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws", headers={"Origin": "https://evil.example"}):
            pass
    assert c.get("/api/health", headers={"Origin": "https://evil.example", "Authorization": f"Bearer {KEY}"}).status_code == 200


def test_a_helper_is_named_by_its_header_and_a_browser_tab_is_not_a_device(exposed):
    announce = {"type": "director", "director": "claude", "device_name": "Roy's laptop", "version": "2.1", "logged_in": True}
    with TestClient(app, client=HOME) as client:
        with client.websocket_connect("/ws", headers={"X-VT-Device": "lap-1234"}) as ws:
            assert ws.receive_json()["type"] == "hello"
            ws.send_json(announce)
            for _ in range(100):
                if directors.broker.ready("lap-1234"):
                    break
                time.sleep(0.02)
            assert directors.broker.ready("lap-1234") and directors.broker.devices()[0].device_name == "Roy's laptop"
        directors.broker.disconnect("lap-1234")
        for header in ({}, {"X-VT-Device": "a b"}, {"X-VT-Device": "x"}, {"X-VT-Device": "q" * 41}):          # a browser tab names nothing; a bad name counts as none
            with client.websocket_connect("/ws", headers=header) as ws:
                ws.receive_json()
                ws.send_json(announce)
                time.sleep(0.3)
                assert directors.broker.devices() == [], f"a tab with {header} became a director while it was connected"


def test_discovery_and_the_page_need_no_key_and_say_who_must_bring_one(exposed):
    home, outside = TestClient(app, client=HOME), TestClient(app, client=OUTSIDE)
    for c in (home, outside):
        assert c.get("/.well-known/vt-engine").status_code == 200
        assert c.get("/").status_code == 200
        assert c.get("/.well-known/video-tool").status_code == 200
    assert home.get("/.well-known/video-tool").json()["needs_key"] is False
    assert outside.get("/.well-known/video-tool").json()["needs_key"] is True
    assert home.get("/.well-known/video-tool").json()["needs_pairing"] is False, "older apps read this name"


def test_there_is_no_pairing_any_more(exposed):
    here = TestClient(app, client=HERE)
    assert here.post("/api/pair", json={"code": "ab12-cd34-ef56"}).status_code in (404, 405)
    assert here.post("/api/server/code").status_code in (404, 405)
    assert here.get("/api/server/clients").status_code in (404, 405)
    assert here.post("/api/directors/token", json={}).status_code in (404, 405)
    info = here.get("/api/server").json()
    assert info["exposed"] and info["addresses"] and "has_code" not in info
    made = TestClient(app, client=HOME).post("/api/server/assistant", json={"name": "Claude Code"}).json()
    assert made["url"].endswith("/mcp") and "token" not in made and "headers" not in made["mcp_json"]["mcpServers"]["video-tool"]


def test_a_loopback_only_studio_keeps_working():
    assert not serve.STATE["exposed"]
    assert TestClient(app, client=OUTSIDE).get("/api/health").status_code == 200


def test_the_server_can_start_by_itself_the_same_way(exposed, monkeypatch, tmp_path):
    from pathlib import Path

    from vt.engines import hub

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    ran = []
    monkeypatch.setattr(hub, "apply_service", lambda spec: [ran.append(spec), *[Path(f).parent.mkdir(parents=True, exist_ok=True) or Path(f).write_text(t) for f, t in spec["files"].items()]] and ["ok"])
    monkeypatch.setattr(serve.subprocess, "run", lambda cmd, **kw: ran.append(cmd) or type("R", (), {"returncode": 0})())
    here = TestClient(app, client=HERE)
    assert "autostart" not in here.get("/api/server").json()                         # not started by `vt server`: nothing to repeat
    serve.STATE["argv"] = ["server", "--host", "0.0.0.0", "--comfy", "existing", "--comfy-url", "http://127.0.0.1:8188,http://127.0.0.1:8189", "--port", "8767"]
    assert here.get("/api/server").json()["autostart"] is False
    assert TestClient(app, client=HOME).post("/api/server/autostart", json={"on": True}).status_code == 403, "changed only on the server computer itself"
    assert TestClient(app, client=OUTSIDE).post("/api/server/autostart", json={"on": True}, headers={"Authorization": f"Bearer {KEY}"}).status_code == 403
    r = here.post("/api/server/autostart", json={"on": True}).json()
    text = "\n".join(ran[0]["files"].values())
    assert r["autostart"] and "--comfy-url" in text and "8767" in text and "engine run" not in text
    assert here.get("/api/server").json()["autostart"] is True
    assert here.post("/api/server/autostart", json={"on": False}).json()["autostart"] is False
    assert here.get("/api/server").json()["autostart"] is False
    serve.STATE["argv"] = None
