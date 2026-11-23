"""The HyperFrames Studio for a person on another computer (docs/plans/PLAN-OPENMOTION.MD, O8 prerequisite).

The Studio that `hyperframes preview` serves listens on 127.0.0.1 only, and it asks for root paths (/api/..., /assets/...), so it cannot sit under a
path of our server. When the server is reachable from other computers, it also listens on one more port (the gateway) and passes every request there
to the open Studio, event streams included.

Who gets through: this computer, or a browser that came with a ticket. Our server hands out a ticket (random, used once, two minutes) only to a caller
it already let in (the key, or the person's trusted network), as part of the Studio's address; the gateway swaps it for a cookie that holds a secret of
this run. The server's key is never put in an address. A web page elsewhere cannot use the gateway (the same Host and Origin rules as the server)."""
from __future__ import annotations

import asyncio
import hmac
import secrets
import threading
import time
from http.cookies import SimpleCookie
from typing import Optional
from urllib.parse import parse_qs, urlencode

COOKIE = "vt_studio"
TICKET_S = 120.0
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length"}
GATE: dict = {"port": None, "secret": secrets.token_urlsafe(32), "tickets": {}}
_lock = threading.Lock()


def running() -> bool:
    return bool(GATE["port"])


def ticket() -> str:
    t = secrets.token_urlsafe(24)
    now = time.time()
    with _lock:
        GATE["tickets"] = {k: v for k, v in GATE["tickets"].items() if v > now}
        GATE["tickets"][t] = now + TICKET_S
    return t


def _use(t: str) -> bool:
    with _lock:
        until = GATE["tickets"].pop(t, 0)
    return until > time.time()


def address_for(request_host: str, studio_url: str) -> Optional[str]:
    """The Studio's address for a caller on another computer: this server's host name as the caller used it, the gateway's port, a ticket, and the
    Studio's own hash (which project, which moment). None when the gateway is not running."""
    if not running():
        return None
    host = request_host.strip()
    if host.startswith("["):
        name = host[: host.find("]") + 1]
    else:
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    frag = studio_url.split("#", 1)[1] if "#" in studio_url else ""
    return f"http://{name}:{GATE['port']}/?{urlencode({'vt_ticket': ticket()})}" + (f"#{frag}" if frag else "")


def _cookie_ok(scope: dict) -> bool:
    raw = next((v.decode("latin-1") for k, v in scope.get("headers") or [] if k == b"cookie"), "")
    c = SimpleCookie(raw)
    return COOKIE in c and hmac.compare_digest(c[COOKIE].value.encode(), GATE["secret"].encode())


async def _reply(send, status: int, text: str, headers: Optional[list] = None) -> None:
    await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"text/plain; charset=utf-8"), *(headers or [])]})
    await send({"type": "http.response.body", "body": text.encode("utf-8")})


def _key_ok(scope: dict) -> bool:
    """The desktop app sends the server's key as a header (a web page cannot): inside the app the Studio is on another site than the app's page,
    where a browser would not send the cookie."""
    from . import serve

    auth = next((v.decode("latin-1") for k, v in scope.get("headers") or [] if k == b"authorization"), "")
    key = serve.STATE.get("key") or ""
    return bool(key) and auth.startswith("Bearer ") and hmac.compare_digest(auth[7:].strip().encode(), key.encode())


def _frame_ok(headers: list[tuple[bytes, bytes]], host: str) -> list[tuple[bytes, bytes]]:
    """The Studio forbids being shown inside another page; Video Tool's editor may: the app on this computer, or the server's own page."""
    out = []
    for k, v in headers:
        n = k.lower()
        if n in (b"x-frame-options",) or n.decode("latin-1") in HOP:
            continue
        if n == b"content-security-policy":
            kept = ";".join(d for d in v.decode("latin-1").split(";") if not d.strip().lower().startswith("frame-ancestors"))
            if kept.strip():
                out.append((k, kept.encode("latin-1")))
            continue
        out.append((k, v))
    from . import serve

    name = serve._name_of(host)
    own = f"http://[{name}]:*" if ":" in name else f"http://{name}:*"
    out.append((b"content-security-policy", f"frame-ancestors 'self' http://127.0.0.1:* http://localhost:* {own}".encode("latin-1")))
    return out


async def app(scope, receive, send) -> None:
    """The gateway: check who asks, then pass the request to the open Studio."""
    from . import serve
    from .. import shot_studio as ST

    if scope["type"] == "lifespan":
        while True:
            m = await receive()
            if m["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif m["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    if scope["type"] != "http":
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4404})
        return
    if not serve.browser_safe(scope):
        await _reply(send, 403, "This Studio does not answer web pages from elsewhere.")
        return
    q = parse_qs(scope.get("query_string", b"").decode("latin-1"))
    t = (q.get("vt_ticket") or [""])[0]
    if t:
        if not _use(t) and not (_cookie_ok(scope) or _key_ok(scope) or serve.trusted(scope)):   # the same address again: fine for one let in already
            await _reply(send, 401, "This Studio link has expired. Open the Studio again from Video Tool.")
            return
        rest = urlencode([(k, v) for k, vs in q.items() if k != "vt_ticket" for v in vs])
        where = (scope.get("path") or "/") + (f"?{rest}" if rest else "")       # the browser keeps the #hash across the redirect
        await send({"type": "http.response.start", "status": 303, "headers": [
            (b"location", where.encode("latin-1")),
            (b"set-cookie", f"{COOKIE}={GATE['secret']}; HttpOnly; SameSite=Lax; Path=/".encode("latin-1"))]})
        await send({"type": "http.response.body", "body": b""})
        return
    if not (_cookie_ok(scope) or _key_ok(scope) or serve.trusted(scope)):
        await _reply(send, 401, "Open the Studio from Video Tool: this address needs the link it gives.")
        return
    st = ST.status()
    if not st.get("open"):
        await _reply(send, 404, "Nothing is open in the Studio. Open it again from Video Tool.")
        return
    await _forward(scope, receive, send, int(st["port"]))


async def _forward(scope, receive, send, port: int) -> None:
    import httpx

    body = b""
    while True:
        m = await receive()
        if m["type"] == "http.disconnect":
            return
        body += m.get("body", b"")
        if not m.get("more_body"):
            break
    headers = [(k, v) for k, v in scope.get("headers") or [] if k.decode("latin-1").lower() not in HOP and k.lower() not in (b"cookie", b"authorization")]
    asked_host = next((v.decode("latin-1") for k, v in scope.get("headers") or [] if k == b"host"), "")
    headers.append((b"host", f"127.0.0.1:{port}".encode()))
    qs = scope.get("query_string", b"").decode("latin-1")
    url = f"http://127.0.0.1:{port}{scope.get('raw_path', b'').decode('latin-1') or scope.get('path', '/')}"
    if qs and "?" not in url:
        url += "?" + qs
    gone = asyncio.Event()

    async def watch() -> None:                                       # the browser went away (an event stream that is closed): stop passing it on
        while True:
            m = await receive()
            if m["type"] == "http.disconnect":
                gone.set()
                return

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=None)) as client:
        try:
            r = await client.send(client.build_request(scope["method"], url, headers=headers, content=body), stream=True)
        except httpx.HTTPError as e:
            await _reply(send, 502, f"The Studio did not answer: {str(e)[:120]}")
            return
        watcher = asyncio.create_task(watch())
        try:
            await send({"type": "http.response.start", "status": r.status_code, "headers": _frame_ok(list(r.headers.raw), asked_host)})
            async for chunk in r.aiter_raw():
                if gone.is_set():
                    break
                await send({"type": "http.response.body", "body": chunk, "more_body": True})
            if not gone.is_set():
                await send({"type": "http.response.body", "body": b""})
        finally:
            watcher.cancel()
            await r.aclose()


def start(host: str, port: int) -> int:
    """Listen on `port` (the first free one from there) beside the server, in a thread of its own. Returns the port."""
    import socket

    import uvicorn

    for p in range(port, port + 20):
        with socket.socket() as probe:                                   # something already answers there on this computer (Windows lets 0.0.0.0 bind
            probe.settimeout(0.3)                                        # a port another program holds on 127.0.0.1: both would listen, 2026-11-24)
            if probe.connect_ex(("127.0.0.1", p)) == 0:
                continue
        with socket.socket() as s:
            try:
                s.bind((host, p))
            except OSError:
                continue
        server = uvicorn.Server(uvicorn.Config(app, host=host, port=p, log_level="warning", lifespan="on"))
        server.install_signal_handlers = lambda: None                   # the main server owns Ctrl+C
        threading.Thread(target=server.run, name="studio-gateway", daemon=True).start()
        GATE["port"] = p
        return p
    raise OSError(f"No free port for the Studio from {port}")
