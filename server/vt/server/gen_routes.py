"""Pictures for a scene (docs/plans/PLAN-SCENE-TOOLS.MD, G1/G4): the scene's runs, a new run as a job, choose one, forget one."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import scene_gen as G
from .jobs import Cancelled, JobBusy
from .modules_routes import project_or_404

router = APIRouter(prefix="/api", tags=["scene pictures"])


def _models() -> list[dict]:
    from ..engines import fit

    return [{"id": r.id, "label": r.label, "note": getattr(r, "note", ""), "seconds": getattr(r, "seconds", None)} for r in fit.PICTURES]


@router.get("/projects/{pid}/scenes/{sid}/pictures")
def scene_pictures(pid: str, sid: str) -> dict[str, Any]:
    p = project_or_404(pid)
    try:
        return {**G.history(p, sid), "prompt": G.suggest_prompt(p, sid), "words": G.scene_words(p, sid), "models": _models()}
    except G.GenError as e:
        raise HTTPException(404, str(e))


class GenBody(BaseModel):
    prompt: str = Field(min_length=3, max_length=600)
    count: int = Field(default=4, ge=1, le=G.MAX_COUNT)
    recipe: str = ""
    seed: Optional[int] = Field(default=None, ge=0, le=2**31 - 1)


@router.post("/projects/{pid}/scenes/{sid}/pictures")
def scene_pictures_generate(pid: str, sid: str, body: GenBody, request: Request) -> dict:
    """Draw pictures for the scene: a job (progress per picture, cancel through /api/jobs/{id}). One picture job per video at a time."""
    p = project_or_404(pid)
    try:
        G.scene_words(p, sid)
    except G.GenError as e:
        raise HTTPException(404, str(e))
    jobs = request.app.state.jobs
    mine: dict = {}

    def work(cb):
        try:
            run = G.generate(p, sid, body.prompt, count=body.count, recipe=body.recipe, seed=body.seed, progress=lambda f, m: cb("pictures", f, m),
                             cancelled=lambda: bool(mine.get("job") and mine["job"].cancel.is_set()))
        except G.GenError as e:
            raise RuntimeError(str(e)) from e
        if mine.get("job") and mine["job"].cancel.is_set():
            raise Cancelled()
        hub = getattr(request.app.state, "hub", None)
        if hub:
            hub.emit({"type": "changed", "project": pid, "by": "person"})
        return {"run": run["id"], "made": sum(1 for i in run["items"] if i.get("media")), "failed": sum(1 for i in run["items"] if i.get("error"))}

    try:
        mine["job"] = jobs.submit("pictures", pid, f"Pictures for scene {sid}", work, when_busy="refuse")
    except JobBusy as e:
        raise HTTPException(409, "Pictures are already being made for this video.") from e
    return mine["job"].public()


class UseBody(BaseModel):
    media: str


@router.post("/projects/{pid}/scenes/{sid}/pictures/use")
def scene_pictures_use(pid: str, sid: str, body: UseBody) -> dict:
    """Show the scene with this picture (a picture scene, as the Director makes it). Undoable like every edit."""
    from .app import ReshowBody, scene_reshow

    p = project_or_404(pid)
    if not any(m.id == body.media for m in p.meta().media):
        raise HTTPException(404, "That picture is not in the media bin any more.")
    return scene_reshow(pid, sid, ReshowBody(archetype="media_hero", media=body.media))


@router.delete("/projects/{pid}/scenes/{sid}/pictures/{media}")
def scene_pictures_forget(pid: str, sid: str, media: str) -> dict:
    p = project_or_404(pid)
    try:
        return G.forget(p, sid, media)
    except G.GenError as e:
        raise HTTPException(404, str(e))
