"""One server (docs/plans/PLAN-CLIENT-SERVER.MD CS1 + CS2): the Studio and the engine contract on one port, one key, one pairing.

    vt server                  # 0.0.0.0:8765, starts Ollama/ComfyUI, prints the addresses and a one-time pairing code
    vt studio                  # the same server, on 127.0.0.1 only (no pairing needed)

A client on another computer trades the pairing code for the key once (`POST /api/pair`, or `/v1/pair` for an engine client) and sends it on every
request: `Authorization: Bearer <key>`, the `vt_token` cookie that `/api/pair` sets (so the Studio page, its <video> tags and its websocket work
without code changes), or `?token=` where neither can be sent. The key is the hub's (vt/engines/hub.py identity), so pairing survives restarts.

Requests from this computer need nothing, unless they carry a proxy's forwarding header: a tunnel on this computer would otherwise turn every
internet request into a "local" one.
"""
from __future__ import annotations

import hmac
import json
import subprocess
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ..engines.server import engine_router, new_state
from . import clients

VERSION = "1"
COOKIE = "vt_token"
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
FORWARDED = {b"x-forwarded-for", b"forwarded", b"x-real-ip", b"cf-connecting-ip"}
# open to anyone who can reach the port: discovery, pairing, the engine contract (it checks the key itself) and the page's own files
OPEN = ("/.well-known/", "/v1/", "/gw/", "/api/pair")
GUARDED = ("/api", "/ws", "/media")

STATE: dict[str, Any] = new_state(name="Video Tool")
STATE["exposed"] = False                         # True once `vt server` listens beyond this computer


def configure(*, key: str, code: str = "", name: str = "", services: Optional[dict[str, str]] = None, exposed: bool = False,
              argv: Optional[list[str]] = None) -> None:
    STATE.update(key=key, code=code, exposed=exposed, argv=argv)
    if name:
        STATE["name"] = name
    STATE["services"].clear()
    STATE["services"].update(services or {})


def _guarded(path: str) -> bool:
    if path.startswith(OPEN):
        return False
    return any(path == g or path.startswith(g + "/") for g in GUARDED)


def _token(scope: dict) -> str:
    headers = dict(scope.get("headers") or [])
    auth = headers.get(b"authorization", b"").decode("latin-1")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    cookie = SimpleCookie(headers.get(b"cookie", b"").decode("latin-1"))
    if COOKIE in cookie:
        return cookie[COOKIE].value
    return (parse_qs(scope.get("query_string", b"").decode("latin-1")).get("token") or [""])[0]


def is_local(scope: dict) -> bool:
    host = (scope.get("client") or ("", 0))[0]
    return host in LOOPBACK and not any(k in FORWARDED for k, _ in scope.get("headers") or [])


def allowed(scope: dict) -> bool:
    path = scope.get("path", "")
    if path == "/mcp" or path.startswith("/mcp/"):
        pass                                             # the assistant tools always need a token (see _MCPEndpoint)
    elif not STATE["exposed"] or not _guarded(path) or is_local(scope):
        return True
    if scope.get("method") == "PUT" and path.endswith("/file"):
        from .uploads import ticket_ok

        if ticket_ok(path, scope.get("query_string", b"").decode("latin-1")):
            return True                                  # an assistant elsewhere sending a file with its one-time upload ticket
    token = _token(scope)
    if STATE["key"] and hmac.compare_digest(token, STATE["key"]):
        return True
    return clients.known(token) is not None


class Guard:
    """ASGI middleware (it must see websockets too, which BaseHTTPMiddleware does not)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket") or allowed(scope):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4401})
            return
        body = json.dumps({"detail": {"errors": ["This Video Tool server needs pairing. Enter the code shown where the server was started."]}}).encode()
        await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")]})
        await send({"type": "http.response.body", "body": body})


class PairBody(BaseModel):
    code: str
    device: str = ""                                     # a name for this device in the server's list; guessed from the browser when empty


router = APIRouter()
router.include_router(engine_router(STATE))


@router.get("/.well-known/video-tool")
def well_known() -> dict[str, Any]:
    """What a client shows before pairing: whose server this is and whether it wants a code."""
    return {"app": "video-tool", "server": VERSION, "name": STATE["name"], "needs_pairing": bool(STATE["exposed"]), "engines": sorted(STATE["services"])}


@router.get("/api/servers")
def servers(timeout: float = 2.0) -> list[dict[str, Any]]:
    """The Video Tool servers on this network (`vt servers`)."""
    from .discovery import find

    return find(min(max(timeout, 0.5), 5.0))


@router.post("/api/pair")
def pair(body: PairBody, request: Request, response: Response) -> dict[str, Any]:
    if not STATE["code"] or not hmac.compare_digest(body.code.strip(), STATE["code"]):
        raise HTTPException(403, "That pairing code is not right, or it was already used. Get a new one on the server computer: Engines, This server, New pairing code.")
    STATE["code"] = ""                                   # one use
    device, token = clients.add(body.device or clients.device_name(request.headers.get("user-agent", "")))
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=request.url.scheme == "https", max_age=10 * 365 * 24 * 3600)
    return {"key": token, "name": STATE["name"], "device": device}


@router.get("/api/server")
def server_info(request: Request) -> dict[str, Any]:
    """This server as the Engines page shows it: is it open to other computers, and at which addresses (only to this computer)."""
    from ..engines import hub

    out: dict[str, Any] = {"name": STATE["name"], "exposed": bool(STATE["exposed"]), "has_code": bool(STATE["code"])}
    if STATE["exposed"] and is_local(request.scope):
        out["addresses"] = hub.address_hints(request.url.port or 8765)
        if STATE.get("argv"):
            out["autostart"] = Path(_service()["installed"]).exists()
    return out


def _service() -> dict[str, Any]:
    from ..engines import hub

    return hub.service_files(args=STATE["argv"], service="server")


def autostart(on: bool) -> dict[str, Any]:
    """Start this server by itself at login (or stop doing that), with the engines and port it runs with now."""
    from ..engines import hub

    if not STATE.get("argv"):
        raise HTTPException(409, "Only a server started with `vt server` can start by itself.")
    spec = _service()
    if on:
        return {"done": hub.apply_service(spec), "note": spec["note"], "autostart": True}
    done = []
    for cmd in spec.get("remove", []):
        r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        done.append(f"{' '.join(cmd[:3])}: {'ok' if r.returncode == 0 else 'not set'}")
    for f in spec["files"]:
        Path(f).unlink(missing_ok=True)
    return {"done": done, "note": "It will no longer start by itself.", "autostart": False}


class AutostartBody(BaseModel):
    on: bool


@router.post("/api/server/autostart")
def server_autostart(body: AutostartBody, request: Request) -> dict[str, Any]:
    _only_here(request)
    return autostart(body.on)


@router.post("/api/server/code")
def server_code(request: Request) -> dict[str, str]:
    """A new one-time pairing code (the same one `vt engine pair` prints). Only on the server computer itself."""
    from ..engines import hub

    if not is_local(request.scope):
        raise HTTPException(403, "A new pairing code can only be made on the server computer itself.")
    if not STATE["exposed"]:
        raise HTTPException(409, "This Studio only listens on this computer, so there is nothing to pair. Start it as a server to let other computers in.")
    STATE["code"] = hub.new_code()
    return {"code": STATE["code"]}


def _only_here(request: Request) -> None:
    if not is_local(request.scope):
        raise HTTPException(403, "Paired devices can only be managed on the server computer itself.")


@router.get("/api/server/clients")
def server_clients(request: Request) -> list[dict[str, Any]]:
    """The devices paired with this server."""
    _only_here(request)
    return clients.listing()


@router.delete("/api/server/clients/{client_id}")
def server_revoke(client_id: str, request: Request) -> dict[str, bool]:
    """Turn one device away: it must pair again with a new code. The others keep working."""
    _only_here(request)
    if not clients.revoke(client_id):
        raise HTTPException(404, "That device is not paired (any more).")
    return {"ok": True}


# ----------------------------------------------------------------------------- the MCP tools on the same port (CS6)
_mcp: dict[str, Any] = {"app": None, "stack": None}


class _MCPEndpoint:
    """`/mcp`: Claude Code or another assistant on a client computer drives this server's tools. Always needs a token (Guard), even from this
    computer: the tools can do anything, and a web page could otherwise reach them through localhost. On the server computer itself the stdio
    form (.mcp.json, `python -m vt.mcp.server`) needs nothing."""

    async def __call__(self, scope, receive, send) -> None:
        if _mcp["app"] is None:
            body = b'{"error":"MCP is offered only by a server started with vt server"}'
            await send({"type": "http.response.start", "status": 404, "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": body})
            return
        await _mcp["app"](scope, receive, send)


def install_mcp(app) -> None:
    from contextlib import AsyncExitStack

    from starlette.routing import Route

    app.router.routes.insert(0, Route("/mcp", endpoint=_MCPEndpoint(), methods=["GET", "POST", "DELETE"]))

    @app.on_event("startup")
    async def _mcp_up() -> None:
        if not STATE["exposed"]:
            return
        from mcp.server.transport_security import TransportSecuritySettings

        from ..mcp.server import server as mcp_server

        _mcp["app"] = mcp_server.streamable_http_app(transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))   # Guard checks
        _mcp["stack"] = AsyncExitStack()
        await _mcp["stack"].enter_async_context(mcp_server.session_manager.run())

    @app.on_event("shutdown")
    async def _mcp_down() -> None:
        if _mcp["stack"] is not None:
            await _mcp["stack"].aclose()
        _mcp.update(app=None, stack=None)


class AssistantBody(BaseModel):
    name: str = "AI assistant"


@router.post("/api/server/assistant")
def assistant_key(body: AssistantBody, request: Request) -> dict[str, Any]:
    """A key for an AI assistant (Claude Code, Cursor ...) on the device asking, and the `.mcp.json` that uses it. It appears in the
    paired devices list and is revoked there like any device."""
    if not STATE["exposed"]:
        raise HTTPException(409, "This Studio only listens on this computer: assistants here use the built-in connection (Settings, AI assistants).")
    device, token = clients.add(body.name or "AI assistant")
    url = str(request.base_url).rstrip("/") + "/mcp"
    config = {"mcpServers": {"video-tool": {"type": "http", "url": url, "headers": {"Authorization": f"Bearer {token}"}}}}
    return {"device": device, "url": url, "token": token, "mcp_json": config}
