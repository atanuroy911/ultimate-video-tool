"""Studio API for generated motion clips: ComfyUI status, the workflows on offer, and one job that turns a still into B-roll."""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import paths
from ..comfy import ComfyClient, ComfyError, generate_clip, list_workflows, load_workflow
from ..comfy.gpu_share import release_ollama_models, same_machine
from ..project import Project
from .jobs import Cancelled, JobBusy
from ..util import read_json

router = APIRouter(prefix="/api", tags=["comfy"])
def comfy_url() -> str:
    """The picture server to use: an address set in Settings, else the one the engine page connected, else the ComfyUI on this computer. Never another computer's address
    that nobody chose (until 2026-11-21 an unset address meant the owner's GPU server, which a test on another machine would have reached)."""
    settings = read_json(paths.SETTINGS, {}) or {}
    if str(settings.get("comfy_url") or "").strip():
        return str(settings["comfy_url"]).strip()
    from ..engines import registry

    ep = registry.endpoint("comfy")
    return (ep.url if ep.mode != "off" and ep.url else registry.spec("comfy").default_url).strip()


def project_or_404(pid: str) -> Project:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", pid) or pid in (".", ".."):
        raise HTTPException(400, "Invalid project ID")
    project = Project(pid)
    if not project.exists():
        raise HTTPException(404, f"Project '{pid}' not found")
    return project


class GenerateClip(BaseModel):
    media_id: str = Field(description="a picture in the project's media bin: the first frame of the clip")
    prompt: str = Field(min_length=3, max_length=600)
    workflow: str = "wan22_i2v"
    aspect: str = Field(default="9:16", pattern=r"^(9:16|16:9)$")
    seconds: float = Field(default=3.0, ge=1.0, le=8.0)
    seed: Optional[int] = Field(default=None, ge=0, le=2**31 - 1)
    scene: Optional[str] = None
    focus_x: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="where the subject is in the picture (0 = left); the clip is framed around it")
    focus_y: Optional[float] = Field(default=None, ge=0.0, le=1.0)


@router.get("/comfy/status")
def comfy_status(check: bool = False) -> dict:
    """Is ComfyUI reachable, what GPU and queue does it have, and (check=true) can each workflow run there right now?"""
    client = ComfyClient(comfy_url())
    try:
        status = client.status()
        workflows = []
        info = client.object_info() if (check and status["ok"]) else None
        for wf in list_workflows():
            entry = wf.public()
            if info is not None:
                entry["problems"] = wf.problems(info)
                entry["ready"] = not entry["problems"]
            workflows.append(entry)
        return {**status, "workflows": workflows}
    except ComfyError as e:
        return {"ok": False, "url": client.url, "error": str(e), "workflows": [w.public() for w in list_workflows()]}
    finally:
        client.close()


@router.get("/projects/{pid}/comfy/clips")
def comfy_clips(pid: str) -> dict:
    """Every clip made for this project, with the prompt, seed, workflow and time it took."""
    project = project_or_404(pid)
    return read_json(project.dir / "comfy_clips.json", {"clips": []}) or {"clips": []}


@router.post("/projects/{pid}/comfy/generate")
def comfy_generate(pid: str, body: GenerateClip, request: Request) -> dict:
    """Queue one clip. A job: progress, cancel and errors come through /api/jobs/{id}. One at a time per server."""
    project = project_or_404(pid)
    item = next((m for m in project.meta().media if m.id == body.media_id), None)
    if item is None or item.kind != "image":
        raise HTTPException(422, "Pick a picture from the media bin as the first frame.")
    try:
        workflow = load_workflow(body.workflow)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if body.aspect not in workflow.sizes:
        raise HTTPException(422, f"{workflow.label} does not make {body.aspect} clips.")
    url = comfy_url()
    jobs = request.app.state.jobs
    still = project.dir / item.file
    mine: dict = {}                                  # filled with the job below, so the work can see its own cancel flag

    def work(cb):
        client = ComfyClient(url)
        try:
            ollama = str((read_json(paths.SETTINGS, {}) or {}).get("ollama_url") or "")
            if ollama and same_machine(url, ollama):
                cb("comfy", 0.01, "Freeing the GPU")
                release_ollama_models(ollama)               # the chat model sharing this GPU steps aside; it reloads on its next question
            media, record = generate_clip(project, client, workflow, still, body.prompt, aspect=body.aspect, seconds=body.seconds, seed=body.seed,
                                          caption=body.prompt[:80], scene=body.scene, source_media=body.media_id, focus=(item.fx if body.focus_x is None else body.focus_x, item.fy if body.focus_y is None else body.focus_y), progress=lambda f, m: cb("comfy", f, m),
                                          cancelled=lambda: bool(mine.get("job") and mine["job"].cancel.is_set()))
        except ComfyError as e:
            if e.kind == "cancelled":
                raise Cancelled() from e
            raise RuntimeError(str(e)) from e
        finally:
            client.close()
        hub = getattr(request.app.state, "hub", None)
        if hub:
            hub.emit({"type": "changed", "project": pid})
        return {"media": media.id, "record": record}

    try:
        mine["job"] = jobs.submit("comfy", pid, "Generate a motion clip", work, when_busy="refuse")
    except JobBusy as e:
        raise HTTPException(409, "A clip is already being made for this project.") from e
    return mine["job"].public()
