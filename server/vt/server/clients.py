"""The devices paired with this server (docs/plans/PLAN-CLIENT-SERVER.MD CS4): one token each, so one can be turned away without the others.

Only a hash of each token is kept, in `<DATA>/clients.json`. The server's own key (vt/engines/hub.py identity) stays valid too: engine clients
(`/v1/pair`) and `vt engine` tools use it.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from typing import Any, Optional

from .. import paths
from ..util import read_json, write_json

_lock = threading.Lock()
_cache: dict[str, Any] = {"mtime": None, "items": []}


def _path():
    return paths.DATA / "clients.json"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _load() -> list[dict]:
    p = _path()
    m = p.stat().st_mtime_ns if p.exists() else None
    if m != _cache["mtime"] or _cache.get("file") != str(p):
        items = read_json(p, []) or []
        _cache.update(mtime=m, file=str(p), items=[c for c in items if isinstance(c, dict) and c.get("hash")])
    return _cache["items"]


def add(name: str) -> tuple[dict, str]:
    """A new device; returns its public record and its token (shown to the device once, never stored)."""
    token = secrets.token_urlsafe(32)
    rec = {"id": secrets.token_hex(4), "name": (name or "A device").strip()[:80], "paired": int(time.time()), "hash": _hash(token)}
    with _lock:
        items = list(_load()) + [rec]
        write_json(_path(), items)
    return public(rec), token


def known(token: str) -> Optional[dict]:
    if not token:
        return None
    h = _hash(token)
    for c in _load():
        if hmac.compare_digest(c["hash"], h):
            return c
    return None


def public(c: dict) -> dict:
    return {k: c[k] for k in ("id", "name", "paired")}


def listing() -> list[dict]:
    return [public(c) for c in _load()]


def revoke(client_id: str) -> bool:
    with _lock:
        items = _load()
        keep = [c for c in items if c["id"] != client_id]
        if len(keep) == len(items):
            return False
        write_json(_path(), keep)
    return True


def device_name(user_agent: str) -> str:
    """A readable guess from the browser's User-Agent ("Chrome on Windows"), used when the device does not say."""
    ua = user_agent or ""
    app = next((n for k, n in (("Edg/", "Edge"), ("Electron/", "Video Tool app"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari")) if k in ua), "")
    os_ = next((n for k, n in (("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"), ("Mac OS", "Mac"), ("Linux", "Linux")) if k in ua), "")
    return " on ".join(x for x in (app, os_) if x) or "A device"
