"""The client side of the Engine Server (vt/engines/server.py): another computer running `vt serve-engine`, used like any other engine."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .model import Endpoint, Health


class EngineServerError(RuntimeError):
    pass


def _headers(ep: Endpoint) -> dict[str, str]:
    return {"Authorization": f"Bearer {ep.key}"} if ep.key else {}


def check(ep: Endpoint) -> Health:
    r = httpx.get(ep.url.rstrip("/") + "/.well-known/vt-engine", timeout=6, follow_redirects=True)
    if r.status_code != 200 or "engine_server" not in r.text:
        return Health(ok=False, why_not="That address answers, but it is not a Video Tool engine server.")
    doc = r.json()
    if not ep.key:
        return Health(ok=True, note="reachable; pair it with the code shown where it was started", capabilities=[], version=doc.get("name", ""))
    h = httpx.get(ep.url.rstrip("/") + "/v1/health", headers=_headers(ep), timeout=6)
    if h.status_code == 401:
        return Health(ok=False, why_not="The key was refused. Pair again with a new code.")
    return Health(ok=True, version=doc.get("name", ""), capabilities=list(h.json().get("capabilities", [])))


def pair_full(url: str, code: str) -> dict[str, Any]:
    """Trade a pairing code for {"key", "services": {name: path}}. The caller stores the key and never shows it."""
    r = httpx.post(url.rstrip("/") + "/v1/pair", json={"code": code}, timeout=10)
    if r.status_code != 200:
        raise EngineServerError((r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else "") or f"HTTP {r.status_code}")
    return r.json()


def pair(url: str, code: str) -> str:
    """Trade a pairing code for the key only."""
    return pair_full(url, code)["key"]


def voices(ep: Endpoint) -> list[dict[str, Any]]:
    r = httpx.get(ep.url.rstrip("/") + "/v1/voice/list", headers=_headers(ep), timeout=20)
    if r.status_code != 200:
        raise EngineServerError(f"the engine server could not list voices (HTTP {r.status_code})")
    return r.json()["voices"]


def speak(ep: Endpoint, text: str, out: Path, *, engine: str, voice: str, rate: float = 1.0, language: str = "") -> None:
    r = httpx.post(ep.url.rstrip("/") + "/v1/voice/speak", headers=_headers(ep), json={"text": text, "engine": engine, "voice": voice, "rate": rate, "language": language}, timeout=600)
    if r.status_code != 200:
        detail = r.json().get("detail", "") if r.headers.get("content-type", "").startswith("application/json") else ""
        raise EngineServerError(str(detail) or f"HTTP {r.status_code}")
    out.write_bytes(r.content)
