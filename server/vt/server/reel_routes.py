"""Studio API for changing one picture of a reel: draw it again, describe it differently, or go back to an earlier try (docs/plans/PLAN-EDITOR-UI.MD U5)."""
from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..schema import Backdrop, Scrim
from ..util import read_json, write_json
from .modules_routes import project_or_404

router = APIRouter(prefix="/api/projects/{pid}/scenes/{sid}", tags=["reel"])
TRIES = "reel_tries.json"
KEEP = 4                                                    # the current picture and the three before it


class RedrawBody(BaseModel):
    draw: Optional[str] = Field(default=None, max_length=300, description="a new description; omitted keeps the director's")
    seed: Optional[int] = Field(default=None, ge=0, le=2**31 - 1)
    recipe: str = Field(default="", max_length=80)


class UseBody(BaseModel):
    media: str = Field(min_length=1, max_length=80)


def _scene(project, sid: str):
    sf = project.scenes()
    sc = next((s for s in (sf.scenes if sf else []) if s.id == sid), None)
    if sc is None:
        raise HTTPException(404, f"scene '{sid}' not found")
    return sf, sc


def _draw_text(project, scene) -> str:
    """What the picture of this scene is meant to show: the director's note for its sentences, or the sentence itself."""
    saved = (read_json(project.dir / "scene_direction.json", {}) or {}).get(scene.id, {})
    if saved.get("picture_prompt"):
        return saved["picture_prompt"]
    reading = read_json(project.dir / "reel_reading.json", {}) or {}
    notes = {n["beat"]: n for n in reading.get("notes", [])}
    for b in scene.beats:
        if notes.get(b, {}).get("draw"):
            return notes[b]["draw"]
    beats = {b.id: b for b in project.beats().beats}
    return " ".join(beats[b].text for b in scene.beats if b in beats)[:200]


def _tries(project) -> dict[str, list[dict]]:
    return read_json(project.dir / TRIES, {}) or {}


def _remember(project, sid: str, media: str, draw: str, seed: Optional[int]) -> None:
    log = _tries(project)
    mine = [t for t in log.get(sid, []) if t["media"] != media]
    mine.append({"media": media, "draw": draw, "seed": seed, "at": time.strftime("%Y-%m-%d %H:%M")})
    log[sid] = mine[-KEEP:]
    write_json(project.dir / TRIES, log)


def _url_of(project, media_id: str) -> Optional[str]:
    item = next((m for m in project.meta().media if m.id == media_id), None)
    return f"/media/{project.id}/{item.file}" if item else None


@router.get("/picture")
def picture(pid: str, sid: str) -> dict[str, Any]:
    project = project_or_404(pid)
    _, scene = _scene(project, sid)
    current = scene.backdrop.media if scene.backdrop else None
    tries = [{**t, "url": _url_of(project, t["media"]), "current": t["media"] == current} for t in _tries(project).get(sid, []) if _url_of(project, t["media"])]
    return {"scene": sid, "draw": _draw_text(project, scene), "media": current, "url": _url_of(project, current) if current else None, "tries": tries,
            "reel": project.meta().options.look == "reel"}


def _set_picture(project, sid: str, media_id: str) -> None:
    sf, scene = _scene(project, sid)
    if not any(m.id == media_id for m in project.meta().media):
        raise HTTPException(404, "that picture is not in the media bin")
    scene.backdrop = Backdrop(media=media_id, motion="kenburns", scrim=Scrim())
    project.save_scenes(sf)


@router.post("/picture/use")
def use_picture(pid: str, sid: str, body: UseBody) -> dict[str, Any]:
    """Go back to an earlier try, or put one of the person's own pictures on this scene."""
    from .app import changed, compose_all

    project = project_or_404(pid)
    _set_picture(project, sid, body.media)
    compose_all(project)
    changed(pid)
    return picture(pid, sid)


@router.post("/redraw")
def redraw(pid: str, sid: str, body: RedrawBody) -> dict[str, Any]:
    """Draw this scene's picture again on the picture server (a new seed, or a new description) as a job; the old picture stays in the tries."""
    from .app import changed, compose_all, jobs

    project = project_or_404(pid)
    _, scene = _scene(project, sid)
    draw = (body.draw or "").strip() or _draw_text(project, scene)
    from ..engines.fit import BY_ID
    if body.recipe and body.recipe not in BY_ID:
        raise HTTPException(422, "Unknown picture model")
    seed = body.seed if body.seed is not None else int(time.time()) % 2**31

    def work(cb):
        from ..modules.executor import Executor

        cb("redraw", 0.05, "Drawing the picture")
        r = Executor(project.dir).call("fill.generated_still", {"draw": draw, "scene": sid, "seed": seed, "recipe": body.recipe}, caller="person", why="The person asked for another picture.", force=True, skip_prerequisites=True)
        if not r.ok:
            raise RuntimeError(r.fix or r.summary)
        media = r.output["media"]["id"]
        _, latest = _scene(project, sid)
        if latest.model_dump() != scene.model_dump():
            raise RuntimeError("The scene changed during generation. Your edits were kept; the new picture is available in Media.")
        _set_picture(project, sid, media)
        _remember(project, sid, media, draw, seed)
        cb("redraw", 0.9, "Putting it in the video")
        compose_all(project)
        changed(pid)
        return {"media": media}

    current = scene.backdrop.media if scene.backdrop else None
    if current:                                                         # keep what is there so "go back" always works
        _remember(project, sid, current, _draw_text(project, scene), None)
    return jobs.submit("redraw", pid, f"Drawing scene {sid} again", work, when_busy="refuse").public()


hook_router = APIRouter(prefix="/api/projects/{pid}/hook", tags=["reel"])


class ApplyHook(BaseModel):
    script: str = Field(min_length=3, max_length=60000, description="the whole script of one of the proposals")


@hook_router.get("")
def hook_proposals(pid: str, ai: bool = True) -> dict[str, Any]:
    """Is the opening weak, and what could it be instead. Nothing is changed."""
    from ..reel import hook as H

    project = project_or_404(pid)
    text = str((read_json(project.script_path, {}) or {}).get("text", ""))
    if not text:
        raise HTTPException(409, "This video was not made from a typed script, so there is no opening to rewrite.")
    weak = H.is_weak(text)
    return {"weak": weak, "first": (H.sentences(text) or [""])[0], "proposals": H.propose(text, ai_rewrites=H.ai_first_lines(text) if ai and weak else None) if weak else []}


@hook_router.post("/apply")
def hook_apply(pid: str, body: ApplyHook) -> dict[str, Any]:
    """The person chose a proposal: the script is replaced and the video is made again from the voice."""
    from .app import changed, start_pipeline

    project = project_or_404(pid)
    data = read_json(project.script_path, {}) or {}
    if not data.get("text"):
        raise HTTPException(409, "This video was not made from a typed script.")
    write_json(project.dir / "script.before-hook.json", data)             # the original is kept
    write_json(project.script_path, {**data, "text": body.script.strip()})
    job = start_pipeline(project, "voice", True)
    changed(pid)
    return {"job": job.public() if job else None}
