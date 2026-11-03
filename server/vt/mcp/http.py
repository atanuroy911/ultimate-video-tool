"""Remote MCP over HTTPS-ready streamable HTTP, protected by a per-install token (for ChatGPT connectors, Gemini, Cursor ...).

    vt-mcp --http --port 8766        -> http://127.0.0.1:8766/mcp   (send "Authorization: Bearer <token>" or ?token=<token>)

The token lives in settings.json (mcp_token). It is created on first use and can be revoked from Settings. Listening is on 127.0.0.1 only; to let
a cloud assistant reach it the user starts a tunnel (cloudflared / ngrok) themselves, which exposes the local tools, so the token is mandatory.
"""
from __future__ import annotations

import hmac
import secrets
import time
from typing import Any

from .. import paths
from ..util import read_json, write_json

RATE = 120                    # requests per minute per token


def _settings() -> dict:
    return read_json(paths.SETTINGS, {}) or {}


def get_token() -> str:
    return _settings().get("mcp_token", "")


def ensure_token() -> str:
    s = _settings()
    if not s.get("mcp_token"):
        s["mcp_token"] = secrets.token_urlsafe(32)
        write_json(paths.SETTINGS, s)
    return s["mcp_token"]


def revoke_token() -> str:
    """A new token; every client holding the old one is locked out."""
    s = _settings()
    s["mcp_token"] = secrets.token_urlsafe(32)
    write_json(paths.SETTINGS, s)
    return s["mcp_token"]


class TokenGate:
    """ASGI middleware: 401 without the right token, 429 when a client is too fast. The token is compared in constant time and re-read on each call so a revoke is immediate."""

    def __init__(self, app: Any):
        self.app = app
        self.hits: list[float] = []

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        got = auth[7:] if auth.lower().startswith("bearer ") else ""
        if not got:
            for part in scope.get("query_string", b"").decode().split("&"):
                if part.startswith("token="):
                    got = part[6:]
        want = get_token()
        if not want or not hmac.compare_digest(got.encode(), want.encode()):
            return await _reply(send, 401, b'{"error":"missing or wrong token"}')
        now = time.time()
        self.hits = [t for t in self.hits if now - t < 60]
        if len(self.hits) >= RATE:
            return await _reply(send, 429, b'{"error":"too many requests"}')
        self.hits.append(now)
        await self.app(scope, receive, send)


async def _reply(send: Any, status: int, body: bytes) -> None:
    await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


def make_app(server: Any) -> Any:
    from mcp.server.transport_security import TransportSecuritySettings

    ensure_token()
    inner = server.streamable_http_app(transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))   # the token protects it
    return TokenGate(inner)


def run_http(server: Any, port: int = 8766, host: str = "127.0.0.1") -> None:
    import sys

    import uvicorn

    app = make_app(server)
    print(f"Video Tool MCP on http://{host}:{port}/mcp  (token in settings.json: mcp_token)", file=sys.stderr)
    uvicorn.run(app, host=host, port=port, log_level="warning")
