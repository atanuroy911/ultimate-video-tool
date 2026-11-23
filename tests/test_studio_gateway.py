"""The HyperFrames Studio for another computer (vt/server/studio_gateway.py): a ticket from our server becomes a cookie, the desktop app may send the key
instead, a page from elsewhere is refused, and what the Studio answers is passed on (with the framing rule loosened only for Video Tool)."""
from __future__ import annotations

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture()
def studio(monkeypatch):
    """A stand-in for `hyperframes preview` on 127.0.0.1 that remembers what it was asked."""
    from vt import shot_studio as ST
    from vt.server import serve, studio_gateway as G

    seen = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append({"path": self.path, "host": self.headers.get("host"), "cookie": self.headers.get("cookie"), "auth": self.headers.get("authorization")})
            body = b"<html>studio</html>"
            self.send_response(200)
            self.send_header("content-type", "text/html")
            self.send_header("x-frame-options", "SAMEORIGIN")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):                                                  # the Studio saving an edit
            got = self.rfile.read(int(self.headers.get("content-length") or 0))
            seen.append({"path": self.path, "body": got})
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", "11")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(ST, "status", lambda: {"open": True, "port": srv.server_address[1], "key": "p/video/9x16"})
    monkeypatch.setitem(serve.STATE, "key", "server-key")
    monkeypatch.setitem(G.GATE, "port", 8766)
    yield seen
    srv.shutdown()


def _get(path, headers=None, client=("192.168.1.50", 5000)):
    import httpx

    from vt.server.studio_gateway import app

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=client), base_url="http://192.168.1.10:8766") as c:
            return await c.get(path, headers=headers or {})

    return asyncio.run(go())


def test_another_computer_needs_the_ticket_then_its_cookie(studio):
    from vt.server import studio_gateway as G

    assert _get("/").status_code == 401, "no ticket, no cookie, no key: refused"
    url = G.address_for("192.168.1.10:8765", "http://127.0.0.1:5555/#project/studio-9x16")
    assert url.startswith("http://192.168.1.10:8766/?vt_ticket=") and url.endswith("#project/studio-9x16")
    t = url.split("vt_ticket=")[1].split("#")[0]
    r = _get(f"/?vt_ticket={t}")
    assert r.status_code == 303 and r.headers["location"] == "/" and "HttpOnly" in r.headers["set-cookie"]
    assert _get(f"/?vt_ticket={t}").status_code == 401, "a ticket is used once"
    cookie = r.headers["set-cookie"].split(";")[0]
    ok = _get("/assets/a.js", {"cookie": cookie})
    assert ok.status_code == 200 and ok.text == "<html>studio</html>"
    assert "x-frame-options" not in ok.headers and "frame-ancestors" in ok.headers["content-security-policy"]
    assert "http://192.168.1.10:*" in ok.headers["content-security-policy"] and "http://*:*" not in ok.headers["content-security-policy"]
    assert studio[-1]["path"] == "/assets/a.js" and studio[-1]["host"].startswith("127.0.0.1:") and not studio[-1]["cookie"], "our cookie stays with us"


def test_the_desktop_app_sends_the_key_and_a_page_from_elsewhere_is_refused(studio):
    assert _get("/", {"authorization": "Bearer server-key"}).status_code == 200
    assert studio[-1]["auth"] is None, "the key is not passed on to the Studio"
    assert _get("/", {"authorization": "Bearer wrong"}).status_code == 401
    assert _get("/", {"authorization": "Bearer server-key", "origin": "http://evil.example"}).status_code == 403
    assert _get("/", client=("127.0.0.1", 5000)).status_code == 200, "this computer needs nothing"


def test_the_server_gives_other_computers_the_gateway_address(studio, monkeypatch):
    from types import SimpleNamespace

    from vt.server.shot_routes import _for_caller
    from vt.server import studio_gateway as G

    def req(client):
        return SimpleNamespace(scope={"client": client, "headers": [(b"host", b"192.168.1.10:8765")]})

    local = {"open": True, "url": "http://127.0.0.1:5555/#project/studio-9x16"}
    assert _for_caller(req(("127.0.0.1", 1)), local)["url"] == local["url"], "this computer opens the Studio directly"
    there = _for_caller(req(("192.168.1.50", 1)), local)["url"]
    assert there.startswith("http://192.168.1.10:8766/?vt_ticket=")
    monkeypatch.setitem(G.GATE, "port", None)
    off = _for_caller(req(("192.168.1.50", 1)), local)
    assert off["url"] is None and "does not offer" in off["why"]


def test_an_edit_reaches_the_studio_and_the_same_address_opens_again(studio):
    import httpx

    from vt.server import studio_gateway as G

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=G.app, client=("192.168.1.50", 5000)), base_url="http://192.168.1.10:8766") as c:
            t = G.address_for("192.168.1.10:8765", "x#project/a").split("vt_ticket=")[1].split("#")[0]
            first = await c.get(f"/?vt_ticket={t}")
            cookie = first.headers["set-cookie"].split(";")[0]
            again = await c.get(f"/?vt_ticket={t}", headers={"cookie": cookie})               # the window shown again with the same address
            saved = await c.post("/api/projects/a/files/index.html", content=b"<html>edited</html>", headers={"cookie": cookie})
            return again, saved

    again, saved = asyncio.run(go())
    assert again.status_code == 303, "a used ticket with the cookie: let in again"
    assert saved.status_code == 200 and saved.json() == {"ok": True}
    assert studio[-1] == {"path": "/api/projects/a/files/index.html", "body": b"<html>edited</html>"}
