"""The computer's live numbers for the Studio's System panel (vt/sysstats.py): processor, memory, disk, every graphics card and which one is in use."""
import threading
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from .. import gpuassign, sysstats

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/restart")
def restart_status(request: Request) -> dict:
    from . import restart
    manager = request.app.state.jobs
    return {**restart.describe(),"busy":any(j.status in ("queued","running") for j in manager.snapshot()),"restarting":manager.restarting,"error":restart.last_error}


@router.post("/restart")
def restart_server(request: Request, background: BackgroundTasks) -> dict:
    from .restart import request as restart_request
    return restart_request(request.app.state.jobs,background)


@router.get("/stats")
def stats() -> dict:
    return sysstats.snapshot()


class GpuBody(BaseModel):
    allowed: Optional[list[str]] = Field(default=None, max_length=16, description="the cards Video Tool may use (uuid, index or name; ['all'] for every card; [] for none)")
    primary: Optional[str] = Field(default=None, max_length=80, description="'auto' or a card (uuid, index or name)")
    render: Optional[str] = Field(default=None, max_length=80, description="'primary' or a card")
    speech: Optional[str] = Field(default=None, max_length=80, description="'primary' or a card")


@router.get("/gpus")
def gpus() -> dict:
    """The cards, the saved choice, the card each of Video Tool's own jobs uses now and why, and where the separate programs (Ollama, ComfyUI) run."""
    return gpuassign.describe()


@router.put("/gpu")
def set_gpu(body: GpuBody) -> dict:
    """Change which cards Video Tool may use and which card each job uses. Video Tool's own Ollama or ComfyUI that now belongs on another card is restarted there, in the background."""
    try:
        restarting = gpuassign.change({k: v for k, v in body.model_dump().items() if v is not None})
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {**gpuassign.describe(), "restarting": restarting}


class OwnBody(BaseModel):
    engine: str = Field(pattern="^(ollama|comfy)$")


@router.post("/engine-own")
def use_own(body: OwnBody) -> dict:
    """Use Video Tool's own copy of an engine instead of the one that was already running (which is left exactly as it is). It starts in the background, on its job's card."""
    from ..engines import placement, where

    try:
        if body.engine not in where.LABEL or not placement.own_installed(body.engine):
            raise ValueError(f"Video Tool's own {where.LABEL.get(body.engine, body.engine)} is not installed yet. Install it from the Engines page first.")
        p = placement.place({body.engine: "own"}, run=False)[body.engine]
    except ValueError as e:
        raise HTTPException(409, str(e))
    threading.Thread(target=placement.start, args=(p, lambda *a: None), daemon=True, name=f"start-own-{body.engine}").start()
    return {"engine": body.engine, "source": p.source, "url": p.url, "starting": True, "gpus": gpuassign.describe()}
