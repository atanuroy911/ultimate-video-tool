"""One server (docs/plans/PLAN-CLIENT-SERVER.MD CS1 + CS2): the Studio and the engine contract on one port.

    vt server                  # 0.0.0.0:8765, starts Ollama/ComfyUI, prints the addresses
    vt studio                  # the same server, on 127.0.0.1 only

A computer on the server's own network connects with the address alone: no code, no approval, no key (docs/plans/PLAN-PERFECT.MD, decision 7). That means this
computer, a private or link-local address, or a Tailscale address (100.64.0.0/10), provided nothing forwarded the request and it is not a web page working
through someone's browser (`trusted`). Anything else must send the server's own key (the hub's, vt/engines/hub.py identity) as `Authorization: Bearer <key>`, the
`vt_token` cookie, or `?token=`: a connection from the internet through a port forward, or one that a tunnel or proxy on this computer passed on, which is
why a forwarding header turns a "local" request into an outside one.
"""
from __future__ import annotations

import hmac
import ipaddress
import json
import re
import subprocess
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..engines.server import engine_router, new_state

VERSION = "1"
COOKIE = "vt_token"
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
FORWARDED = {b"x-forwarded-for", b"forwarded", b"x-real-ip", b"cf-connecting-ip"}
SHARED_ADDRESSES = ipaddress.ip_network("100.64.0.0/10")           # Tailscale, and carrier-grade NAT: the person's own devices
DEVICE = re.compile(r"[A-Za-z0-9_-]{4,40}")
LOCAL_NAMES = (".local", ".lan", ".home.arpa", ".internal", ".localdomain", ".localhost", ".ts.net")
# open to anyone who can reach the port: discovery, the engine contract (it checks the key itself) and the page's own files
OPEN = ("/.well-known/", "/v1/", "/gw/")
GUARDED = ("/api", "/ws", "/media")

STATE: dict[str, Any] = new_state(name="Video Tool")
STATE["exposed"] = False                         # True once `vt server` listens beyond this computer


def configure(*, key: str, name: str = "", services: Optional[dict[str, str]] = None, exposed: bool = False, argv: Optional[list[str]] = None) -> None:
    STATE.update(key=key, exposed=exposed, argv=argv)
    if name:
        STATE["name"] = name
    STATE["services"].clear()
    STATE["services"].update(services or {})


def _guarded(path: str) -> bool:
    if path.startswith(OPEN):
        return False
    return any(path == g or path.startswith(g + "/") for g in GUARDED)


def _header(scope: dict, name: bytes) -> str:
    return next((v for k, v in scope.get("headers") or [] if k == name), b"").decode("latin-1")


def _token(scope: dict) -> str:
    auth = _header(scope, b"authorization")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    cookie = SimpleCookie(_header(scope, b"cookie"))
    if COOKIE in cookie:
        return cookie[COOKIE].value
    return (parse_qs(scope.get("query_string", b"").decode("latin-1")).get("token") or [""])[0]


def is_local(scope: dict) -> bool:
    host = (scope.get("client") or ("", 0))[0]
    return host in LOOPBACK and not any(k in FORWARDED for k, _ in scope.get("headers") or [])


def on_own_network(scope: dict) -> bool:
    """The sender is this computer, or on a private, link-local or Tailscale address."""
    host = str((scope.get("client") or ("", 0))[0]).split("%")[0]
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_loopback or ip.is_private or ip.is_link_local or ip in SHARED_ADDRESSES


def _name_of(host: str) -> str:
    h = host.strip().lower()
    if h.startswith("["):
        return h[1:h.find("]")] if "]" in h else h
    return h.rsplit(":", 1)[0] if h.count(":") == 1 else h


def browser_safe(scope: dict) -> bool:
    """A web page cannot use a server through this. Its Host must be an address or a local name (a name that anyone on the internet could point at this
    computer is how a page reaches a server on a private network), and its Origin, when it has one, must be this same server (a page from another site has
    its own). The apps, the helper, Claude Code and `curl` send no Origin."""
    host = _header(scope, b"host")
    name = _name_of(host)
    if name:
        try:
            ipaddress.ip_address(name)
        except ValueError:
            if "." in name and not name.endswith(LOCAL_NAMES):
                return False
    origin = _header(scope, b"origin")
    return not origin or urlsplit(origin).netloc.lower() == host.strip().lower()


def named_device(scope: dict) -> str:
    """The name a helper gives its computer in `X-VT-Device` (a web page cannot set a header on a websocket, so a browser tab never has one)."""
    value = _header(scope, b"x-vt-device")
    return value if DEVICE.fullmatch(value) else ""


def trusted(scope: dict) -> bool:
    """Someone on the server's own network, asking for it directly: no key needed."""
    return on_own_network(scope) and not any(k in FORWARDED for k, _ in scope.get("headers") or []) and browser_safe(scope)


def allowed(scope: dict) -> bool:
    path = scope.get("path", "")
    mcp = path == "/mcp" or path.startswith("/mcp/")
    if not mcp and (not STATE["exposed"] or not _guarded(path)):
        return True
    if trusted(scope):
        return True
    if scope.get("method") == "PUT" and path.endswith("/file"):
        from .uploads import ticket_ok

        if ticket_ok(path, scope.get("query_string", b"").decode("latin-1")):
            return True                                  # an assistant elsewhere sending a file with its one-time upload ticket
    return bool(STATE["key"]) and hmac.compare_digest(_token(scope), STATE["key"])


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
        body = json.dumps({"detail": {"errors": ["This Video Tool server only accepts computers on its own network. Connect from a computer on the same network, using the server's address."]}}).encode()
        await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")]})
        await send({"type": "http.response.body", "body": body})


router = APIRouter()
router.include_router(engine_router(STATE))


@router.get("/.well-known/video-tool")
def well_known(request: Request) -> dict[str, Any]:
    """What a client shows before connecting: whose server this is, and whether this asker would have to bring a key (only from outside the server's network)."""
    needs_key = bool(STATE["exposed"]) and not trusted(request.scope)
    return {"app": "video-tool", "server": VERSION, "name": STATE["name"], "needs_key": needs_key, "needs_pairing": False, "engines": sorted(STATE["services"])}


@router.get("/api/servers")
def servers(timeout: float = 2.0) -> list[dict[str, Any]]:
    """The Video Tool servers on this network (`vt servers`)."""
    from .discovery import find

    return find(min(max(timeout, 0.5), 5.0))


@router.get("/api/server")
def server_info(request: Request) -> dict[str, Any]:
    """This server as the Engines page shows it: is it open to other computers, and at which addresses (only to this computer)."""
    from ..engines import hub

    out: dict[str, Any] = {"name": STATE["name"], "exposed": bool(STATE["exposed"])}
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


def _only_here(request: Request) -> None:
    if not is_local(request.scope):
        raise HTTPException(403, "This can only be changed on the server computer itself.")


# ----------------------------------------------------------------------------- the MCP tools on the same port (CS6)
_mcp: dict[str, Any] = {"app": None, "stack": None}


class _MCPEndpoint:
    """`/mcp`: Claude Code or another assistant on a client computer drives this server's tools. Like the rest of the API it needs no key from the server's own
    network (a web page is refused by `trusted`: the tools can do anything, and a page could otherwise reach them through localhost), and the server's key
    from anywhere else. On the server computer itself the stdio form (.mcp.json, `python -m vt.mcp.server`) needs nothing."""

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
def assistant_connection(body: AssistantBody, request: Request) -> dict[str, Any]:
    """What an AI assistant (Claude Code, Cursor ...) on the device asking needs: the address of the tools, and the `.mcp.json` that uses it. No key is needed
    from the server's own network; the server's key is sent only to an asker from outside it (never by this route: that asker already has it)."""
    if not STATE["exposed"]:
        raise HTTPException(409, "This Studio only listens on this computer: assistants here use the built-in connection (Settings, AI assistants).")
    url = str(request.base_url).rstrip("/") + "/mcp"
    return {"url": url, "mcp_json": {"mcpServers": {"video-tool": {"type": "http", "url": url}}}}
