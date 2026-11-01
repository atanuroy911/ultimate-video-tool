"""Studio API for engines: what is connected, where, healthy or not; connect, test and switch off. Keys are accepted and never returned."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..engines import registry, store
from ..engines.model import Endpoint

router = APIRouter(prefix="/api", tags=["engines"])


class EndpointBody(BaseModel):
    mode: str = Field(pattern="^(local|remote|off)$")
    url: str = Field(default="", max_length=300)
    key: Optional[str] = Field(default=None, max_length=300, description="None keeps the stored key, an empty string removes it")
    gpu: Optional[int] = Field(default=None, ge=0, le=16)
    data_dir: str = Field(default="", max_length=400)
    workers: list[str] = Field(default_factory=list, max_length=8, description="more servers of the same engine, for example a second ComfyUI on another GPU")


def _card(engine_id: str, with_health: bool) -> dict[str, Any]:
    s = registry.spec(engine_id)
    ep = registry.endpoint(engine_id)
    card = {"id": s.id, "kind": s.kind, "label": s.label, "about": s.about, "capabilities": list(s.capabilities), "needs_key": s.needs_key,
            "default_url": s.default_url, "local_install": s.local_install, "endpoint": ep.public()}
    card["health"] = registry.health(engine_id).public() if with_health else None
    return card


def _valid_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "The address must start with http:// or https://, for example http://192.168.1.20:3900")
    return url


@router.get("/engines")
def list_engines(health: bool = True) -> list[dict]:
    return [_card(s.id, health) for s in registry.engines()]


@router.get("/engines/{engine_id}")
def one_engine(engine_id: str) -> dict:
    try:
        return _card(engine_id, True)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.put("/engines/{engine_id}")
def set_engine(engine_id: str, body: EndpointBody) -> dict:
    try:
        registry.spec(engine_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    old = registry.endpoint(engine_id)
    url = _valid_url(body.url) if body.mode != "off" else (body.url.strip().rstrip("/") or old.url)
    key = old.key if body.key is None else body.key
    store.save(engine_id, Endpoint(mode=body.mode, url=url, key=key, gpu=body.gpu, data_dir=body.data_dir, workers=[_valid_url(u) for u in body.workers]))
    registry.forget(engine_id)
    return _card(engine_id, True)


class PairBody(BaseModel):
    url: str = Field(max_length=300)
    code: str = Field(min_length=3, max_length=40)
    use: Optional[list[str]] = None        # which of the hub's services to use here (default: all it offers)


@router.post("/engines/vtengine/pair")
def pair_engine(body: PairBody) -> dict:
    """Trade the one-time code shown by `vt engine run` (or `vt serve-engine`) for its key, and connect to it. The key is stored, never returned."""
    from ..engines import vtengine

    url = _valid_url(body.url)
    try:
        got = vtengine.pair_full(url, body.code)
    except vtengine.EngineServerError as e:
        raise HTTPException(403, str(e))
    except Exception as e:                                           # noqa: BLE001
        raise HTTPException(502, f"Could not reach {url}: {type(e).__name__}: {str(e)[:160]}")
    store.save("vtengine", Endpoint(mode="remote", url=url, key=got["key"]))
    registry.forget("vtengine")
    connected: list[str] = []
    for name, path in (got.get("services") or {}).items():          # one computer that runs everything: its Ollama and ComfyUI are used through the same key
        if name in ("ollama", "comfy") and (body.use is None or name in body.use):
            store.save(name, Endpoint(mode="remote", url=url.rstrip("/") + path))
            registry.forget(name)
            connected.append(name)
    return {**_card("vtengine", True), "also_connected": connected}


@router.post("/engines/{engine_id}/test")
def test_engine(engine_id: str, body: Optional[EndpointBody] = None) -> dict:
    """Try an address and key without saving them: what the Settings page does when the person presses Test."""
    try:
        s = registry.spec(engine_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if body is None:
        return registry.health(engine_id, fresh=True).public()
    ep = Endpoint(mode="remote", url=_valid_url(body.url), key=registry.endpoint(engine_id).key if body.key is None else body.key)
    try:
        h = s.check(ep) if s.check else None
    except Exception as e:                                           # noqa: BLE001
        raise HTTPException(502, f"Could not reach {ep.url}: {type(e).__name__}: {str(e)[:160]}")
    return (h.public() if h else {"ok": False, "why_not": "no check for this engine"})


# ------------------------------------------------------------------ on the server computer itself (vt/engines/placement.py; `vt server --ollama ...` does the same)
class PlaceBody(BaseModel):
    choice: str = Field(pattern="^(existing|own|off)$")
    url: str = Field(default="", max_length=600, description="existing only: an address that is not on the usual port; comma-separated for more ComfyUIs")


@router.get("/engines/{engine_id}/here")
def engine_here(engine_id: str) -> dict:
    """What this computer already has for the engine: servers answering on the usual ports, and whether our own copy is installed (and on which port it runs)."""
    from ..engines import placement

    if engine_id not in placement.ENGINES:
        raise HTTPException(404, f"{engine_id} cannot run on this computer through Video Tool")
    own = placement.own_url(engine_id) if engine_id in placement.OWN_BASE else ""
    return {"existing": placement.find_existing(engine_id, skip=(own,)), "own_possible": bool(own), "own_installed": placement.own_installed(engine_id), "own_url": own}


@router.post("/engines/{engine_id}/place")
def engine_place(engine_id: str, body: PlaceBody) -> dict:
    """Use the one already running here (never started, stopped or changed), or start our own copy on its own port, or switch it off."""
    from ..engines import placement

    if engine_id not in placement.ENGINES:
        raise HTTPException(404, f"{engine_id} cannot run on this computer through Video Tool")
    p = placement.place({engine_id: body.choice}, {engine_id: body.url}, say=lambda *_: None)[engine_id]
    registry.forget(engine_id)
    if body.choice != "off" and p.source == "off":
        raise HTTPException(409, p.note)
    return {"source": p.source, "url": p.url, "workers": p.workers, "note": p.note, "card": _card(engine_id, True)}
