"""The engines block of settings.json: {"engines": {"comfy": {"mode": "remote", "url": "...", "key": "..."}}}.

The old flat settings (`ollama_url`, `comfy_url`) are read as a fallback so nothing that already works stops working; saving writes the new block and keeps the
old keys in step for the code that still reads them.
"""
from __future__ import annotations

from typing import Any

from .. import paths
from ..util import read_json, write_json
from .model import Endpoint

LEGACY = {"ollama": "ollama_url", "comfy": "comfy_url"}


def _settings() -> dict[str, Any]:
    return read_json(paths.SETTINGS, {}) or {}


def load(engine_id: str, default_url: str = "") -> Endpoint:
    s = _settings()
    raw = (s.get("engines") or {}).get(engine_id)
    if raw:
        return Endpoint(mode=raw.get("mode", "off"), url=str(raw.get("url", "")).strip().rstrip("/"), key=str(raw.get("key", "")), gpu=raw.get("gpu"), data_dir=str(raw.get("data_dir", "")),
                        workers=[str(u).strip().rstrip("/") for u in raw.get("workers", []) if str(u).strip()])
    legacy = s.get(LEGACY.get(engine_id, ""))
    if legacy:                                              # an address typed into the old Settings page: it was a server, so it is remote
        return Endpoint(mode="remote", url=str(legacy).strip().rstrip("/"))
    return Endpoint(mode="off", url=default_url)


def configured(engine_id: str) -> bool:
    """Whether the person chose this engine's mode or address, including an explicit Off."""
    s = _settings()
    raw = (s.get("engines") or {}).get(engine_id)
    if raw:
        return not raw.get("automatic_selection", False)
    return bool(s.get(LEGACY.get(engine_id, "")))


def save(engine_id: str, endpoint: Endpoint, *, provisional: bool = False) -> Endpoint:
    s = _settings()
    block = dict(s.get("engines") or {})
    block[engine_id] = {"mode": endpoint.mode, "url": endpoint.url.strip().rstrip("/"), "key": endpoint.key, "gpu": endpoint.gpu, "data_dir": endpoint.data_dir,
                       "workers": [u.strip().rstrip("/") for u in endpoint.workers if u.strip()]}
    if provisional:
        block[engine_id]["automatic_selection"] = True
    s["engines"] = block
    if engine_id in LEGACY and endpoint.mode == "remote":
        s[LEGACY[engine_id]] = endpoint.url.strip().rstrip("/")
    write_json(paths.SETTINGS, s)
    return load(engine_id)
