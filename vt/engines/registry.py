from __future__ import annotations

import threading
import time
from typing import Optional

from . import store
from .model import Endpoint, EngineSpec, Health

_CACHE: dict[str, tuple[float, str, Health]] = {}
_LOCK = threading.RLock()
TTL = 8.0                                               # seconds a health answer is reused: the top bar asks often


def _specs() -> dict[str, EngineSpec]:
    from .specs import SPECS

    return SPECS


def engines() -> list[EngineSpec]:
    return list(_specs().values())


def spec(engine_id: str) -> EngineSpec:
    try:
        return _specs()[engine_id]
    except KeyError:
        raise KeyError(f"no engine called '{engine_id}'") from None


def endpoint(engine_id: str) -> Endpoint:
    return store.load(engine_id, spec(engine_id).default_url)


def health(engine_id: str, *, fresh: bool = False) -> Health:
    s = spec(engine_id)
    ep = endpoint(engine_id)
    if ep.mode == "off":
        return Health(ok=False, why_not="not connected", note="off")
    ident = f"{ep.mode}|{ep.url}|{bool(ep.key)}"
    with _LOCK:
        hit = _CACHE.get(engine_id)
        if hit and not fresh and hit[1] == ident and time.monotonic() - hit[0] < TTL:
            return hit[2]
    started = time.monotonic()
    try:
        h = s.check(ep) if s.check else Health(ok=False, why_not="no check for this engine")
    except Exception as e:                              # noqa: BLE001 - a broken engine must never break the page that lists it
        h = Health(ok=False, why_not=f"{type(e).__name__}: {str(e)[:160]}")
    h.seconds = time.monotonic() - started
    with _LOCK:
        _CACHE[engine_id] = (time.monotonic(), ident, h)
    return h


def forget(engine_id: Optional[str] = None) -> None:
    with _LOCK:
        _CACHE.pop(engine_id, None) if engine_id else _CACHE.clear()


def resolve(capability: str) -> Optional[str]:
    """The id of the engine that should answer `capability`: connected and healthy first, in the order the specs are listed. None when no engine can."""
    for s in engines():
        if capability in s.capabilities and endpoint(s.id).mode != "off" and health(s.id).ok:
            return s.id
    return None
