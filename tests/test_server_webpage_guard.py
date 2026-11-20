"""A web page never reaches the server through someone's browser, in any mode; other computers need the server's key unless the person
turned on "Computers on my network can connect without the key" (docs/plans/PLAN-WORKBENCH.MD, W2, decisions D3 and D4).

Before the fix, a server that listened only on this computer let every request through without looking at Host or Origin, so any website open in the
person's browser could call it (`POST /api/llm/setup`, `POST /api/jobs/<id>/cancel` need no body), and any private address (a café's Wi-Fi) counted as
"the same network" with full access and no key."""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vt.server import jobs, serve, uploads
from vt.server.app import app

KEY = "k" * 43
HOME = ("192.168.1.20", 50000)            # another computer on the same Wi-Fi
TAILNET = ("100.64.1.2", 50000)           # a Tailscale device
HERE = ("127.0.0.1", 50000)
EVIL = {"Origin": "https://evil.example"}


@pytest.fixture()
def server(monkeypatch, tmp_path):
    """A configured server, in the mode the test asks for: `server(exposed=..., trust=...)`."""
    from vt import paths

    monkeypatch.setattr(paths, "DATA", tmp_path)
    saved = {**serve.STATE, "services": dict(serve.STATE["services"])}

    def make(exposed: bool, trust: bool = False) -> None:
        serve.configure(key=KEY, exposed=exposed)
        monkeypatch.setitem(serve.STATE, "trust_network", trust)

    yield make
    services = saved.pop("services")
    serve.configure(**{k: saved[k] for k in ("key", "name", "exposed")}, services=services)


@pytest.fixture()
def submitted(monkeypatch):
    """The jobs a request managed to start."""
    calls = []
    monkeypatch.setattr(jobs, "submit", lambda *a, **k: calls.append((a, k)) or (_ for _ in ()).throw(RuntimeError("a job was started")))
    return calls


FIXED = pytest.mark.xfail(strict=True, reason="fixed in W2.2")


# 1 ------------------------------------------------------------------------------------------------------------------------------------------
@FIXED
def test_a_page_from_another_site_cannot_start_work_on_a_local_server(server, submitted):
    server(exposed=False)
    c = TestClient(app, client=HERE, raise_server_exceptions=False)
    r = c.post("/api/llm/setup", headers=EVIL)
    assert r.status_code in (401, 403)
    assert submitted == []


# 2 ------------------------------------------------------------------------------------------------------------------------------------------
@FIXED
def test_a_name_pointed_at_this_computer_is_refused_on_a_local_server(server):
    server(exposed=False)
    c = TestClient(app, client=HERE)
    assert c.get("/api/projects", headers={"Host": "evil.example:8790"}).status_code in (401, 403)
    assert c.get("/api/projects", headers={"Host": "evil.example.com"}).status_code in (401, 403)


# 3 ------------------------------------------------------------------------------------------------------------------------------------------
@FIXED
def test_a_page_cannot_open_the_live_connection_of_a_local_server(server):
    server(exposed=False)
    with pytest.raises(WebSocketDisconnect) as e:
        with TestClient(app, client=HERE).websocket_connect("/ws", headers=EVIL):
            pass
    assert e.value.code == 4401


# 4 ------------------------------------------------------------------------------------------------------------------------------------------
def test_the_desktop_app_and_curl_still_work_on_a_local_server(server):
    """They send no Origin, and their Host is an address."""
    server(exposed=False)
    c = TestClient(app, client=HERE)
    r = c.post("/api/projects/nothing-here/duplicate", headers={"Host": "127.0.0.1:8790"})
    assert r.status_code not in (401, 403)
    assert c.get("/api/health", headers={"Host": "localhost:8790"}).status_code == 200


# 5 ------------------------------------------------------------------------------------------------------------------------------------------
@FIXED
def test_a_sandboxed_page_is_refused_on_a_local_server(server):
    server(exposed=False)
    assert TestClient(app, client=HERE).get("/api/health", headers={"Origin": "null"}).status_code in (401, 403)


# 6 ------------------------------------------------------------------------------------------------------------------------------------------
@FIXED
def test_a_page_the_server_serves_itself_is_allowed(server):
    server(exposed=False)
    c = TestClient(app, client=HERE)
    r = c.get("/api/health", headers={"Host": "127.0.0.1:8790", "Origin": "http://127.0.0.1:8790"})
    assert r.status_code == 200
    assert c.get("/api/health", headers={"Host": "127.0.0.1:8790", "Origin": "http://127.0.0.1:9999"}).status_code in (401, 403)


# 7 ------------------------------------------------------------------------------------------------------------------------------------------
@FIXED
def test_another_computer_needs_the_key_by_default(server):
    server(exposed=True)
    c = TestClient(app, client=HOME)
    r = c.get("/api/health")
    assert r.status_code == 401
    assert c.get("/api/health", headers={"Authorization": f"Bearer {KEY}"}).status_code == 200
    assert c.get("/api/health", headers={"Authorization": "Bearer wrong"}).status_code == 401


# 8 ------------------------------------------------------------------------------------------------------------------------------------------
def test_another_computer_needs_nothing_when_the_person_turned_trust_on(server):
    server(exposed=True, trust=True)
    assert TestClient(app, client=HOME).get("/api/health").status_code == 200
    # a web page still cannot use the server through that computer, trusted network or not
    assert TestClient(app, client=HOME).get("/api/health", headers=EVIL).status_code == 401


# 9 ------------------------------------------------------------------------------------------------------------------------------------------
def test_this_computer_never_needs_the_key(server):
    server(exposed=True)
    assert TestClient(app, client=HERE).get("/api/health").status_code == 200
    assert TestClient(app, client=("::1", 50000)).get("/api/health").status_code == 200
    # unless something forwarded the request: that is an outside one
    assert TestClient(app, client=HERE).get("/api/health", headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 401


# 10 -----------------------------------------------------------------------------------------------------------------------------------------
@FIXED
def test_a_tailscale_address_needs_the_key_unless_trust_is_on(server):
    server(exposed=True)
    assert TestClient(app, client=TAILNET).get("/api/health").status_code == 401
    server(exposed=True, trust=True)
    assert TestClient(app, client=TAILNET).get("/api/health").status_code == 200


# 11 -----------------------------------------------------------------------------------------------------------------------------------------
@FIXED
def test_discovery_is_read_only_for_everyone(server):
    """A page may read who this server is (nothing private is in it); it may not change anything through the open paths."""
    server(exposed=False)
    c = TestClient(app, client=HERE)
    assert c.get("/.well-known/video-tool", headers=EVIL).status_code == 200
    assert c.post("/.well-known/video-tool", headers=EVIL).status_code in (401, 403)
    server(exposed=True)
    other = TestClient(app, client=HOME)
    assert other.get("/.well-known/video-tool").json()["needs_key"] is True
    assert other.get("/.well-known/video-tool", headers=EVIL).status_code == 200


# 12 -----------------------------------------------------------------------------------------------------------------------------------------
@FIXED
def test_an_assistant_elsewhere_can_still_send_a_file_with_its_ticket(server):
    server(exposed=True)
    made = uploads.new_ticketed("clip.mp3", 5)
    c = TestClient(app, client=HOME)
    good = c.put(f"/api/uploads/{made['id']}/file?ticket={made['ticket']}", content=b"abcde")
    assert good.status_code not in (401, 403)
    assert c.put(f"/api/uploads/{made['id']}/file?ticket=wrong", content=b"abcde").status_code == 401
    assert c.put(f"/api/uploads/{made['id']}/file", content=b"abcde").status_code == 401
