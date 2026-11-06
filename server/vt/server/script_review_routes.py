"""The director's script, reviewed round by round after the direction is done (Studio page /p/{id}/script).

Nothing here decides anything new: it puts what the director already chose next to the words it was chosen for, scene by scene, so the person can
(1) change the options of a scene by hand (the existing scene PATCH), (2) ask the director to redo one scene or the whole video with a sentence of
feedback (the existing request queue: a Claude/Codex director answers with alternatives to choose from), and (3) approve. Every round is recorded.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import planning
from ..compose import scene_timing
from ..util import now_iso, read_json, write_json
from .modules_routes import project_or_404

router = APIRouter(prefix="/api/projects/{pid}/script-review", tags=["script-review"])
FILE = "script_review.json"


def _state(p) -> dict[str, Any]:
    s = read_json(p.dir / FILE, None) or {}
    s.setdefault("rounds", [])
    s.setdefault("approved_at", "")
    return s


def _element_label(el: Any) -> str:
    d = el.model_dump(exclude_none=True) if hasattr(el, "model_dump") else dict(el)
    kind = str(d.get("type", "element"))
    text = d.get("text") or d.get("title") or d.get("value") or d.get("label") or d.get("name") or d.get("src") or ""
    if not text and isinstance(d.get("items"), list) and d["items"]:
        text = str(d["items"][0] if not isinstance(d["items"][0], dict) else next(iter(d["items"][0].values()), ""))
    return f"{kind}: {str(text)[:60]}" if text else kind


def _view(p) -> dict[str, Any]:
    sf = p.scenes()
    if not sf:
        raise HTTPException(409, "The director has not planned this video yet.")
    cuts = p.cuts()
    dur = cuts.output_duration if cuts else max((w.end for w in p.transcript().kept()), default=1.0) + 0.5
    timing = {t["id"]: t for t in scene_timing(sf, p.beats(), dur)}
    beats = {b.id: b for b in p.beats().beats}
    requests: dict[str, dict] = {}
    for r in p.requests():
        d = r.model_dump()
        d["alternatives_available"] = len(planning.alternatives(p, r.id)) if r.status == "done" else 0
        requests[r.scene_id or "*"] = d
    rows = []
    for i, sc in enumerate(sf.scenes, 1):
        t = timing.get(sc.id, {})
        rows.append({
            "id": sc.id, "number": i, "start": round(t.get("start", 0.0), 2), "end": round(t.get("end", 0.0), 2),
            "narration": " ".join(beats[b].text for b in sc.beats if b in beats),
            "archetype": sc.archetype, "role": sc.role, "layout": sc.layout, "transition_in": sc.transition_in,
            "transition_effect": sc.transition_effect, "camera_move": sc.camera_move,
            "elements": [_element_label(e) for e in sc.elements], "request": requests.get(sc.id),
        })
    s = _state(p)
    meta = p.meta()
    kept = meta.options.recording_edit == "subtitles"
    return {"title": meta.title, "status": meta.status, "planner": sf.planner, "director": meta.options.director, "director_used": meta.director or {},
            "kept_as_recorded": kept, "recording_edit": meta.options.recording_edit, "scenes": rows, "whole_request": requests.get("*"),
            "rounds": s["rounds"], "approved": bool(s["approved_at"]), "approved_at": s["approved_at"],
            "options": {"layouts": ["stack", "split", "hero", "grid", "side", "lower", "upper"], "transitions": ["cut", "fade", "slide_up", "slide_left", "zoom", "wipe", "whip"]}}


@router.get("/render-check", include_in_schema=True)
def render_check(pid: str) -> dict[str, Any]:
    """HyperFrames' pre-flight over the current composition (script errors, missing files, text leaving the picture, unreadable text)."""
    from ..compose import FORMATS
    from ..render.hyperframes import check

    p = project_or_404(pid)
    tag = FORMATS[p.meta().aspect]["tag"]
    comp = p.comp_dir / tag
    if not (comp / "index.html").exists():
        raise HTTPException(409, "Nothing to check yet: the video has no composition.")
    return check(comp)


@router.get("")
def get_review(pid: str) -> dict[str, Any]:
    return _view(project_or_404(pid))


class AskBody(BaseModel):
    note: str
    scene_id: Optional[str] = None            # None: the whole script
    alternatives: int = 2


@router.post("/ask")
def ask(pid: str, body: AskBody) -> dict[str, Any]:
    """Send feedback to the director: the scene (or the whole script) is planned again with this sentence as its brief; the answers come back as choices."""
    p = project_or_404(pid)
    note = body.note.strip()
    if not note:
        raise HTTPException(422, "Write what should change, for example: make this more visual, or use fewer words on screen.")
    try:
        req = planning.create_request(p, "scene" if body.scene_id else "full", body.scene_id, note, body.alternatives)
    except ValueError as e:
        raise HTTPException(422, str(e))
    s = _state(p)
    s["rounds"].append({"at": now_iso(), "scene": body.scene_id or "", "note": note[:500], "request": req.id})
    s["approved_at"] = ""                                   # asking again reopens the review
    write_json(p.dir / FILE, s)
    return _view(p)


@router.post("/add-graphics")
def add_graphics(pid: str) -> dict[str, Any]:
    """A recording kept as recorded has one scene and nothing for the director to decide. This switches it to 'screen recording + graphics': the picture stays whole and the
    director adds titles and step callouts where they help; the plan is made again as a job."""
    p = project_or_404(pid)
    m = p.meta()
    if m.options.recording_edit == "screen":
        raise HTTPException(409, "This video already has graphics.")
    if m.options.recording_edit == "auto":
        raise HTTPException(409, "This video is directed normally already.")
    m.options.recording_edit = "screen"
    p.save_meta(m)
    for name in ("scenes.json",):
        (p.dir / name).unlink(missing_ok=True)
    from .app import start_pipeline

    job = start_pipeline(p, "plan", True)
    return {"job": job.public() if hasattr(job, "public") else job}


@router.post("/approve")
def approve(pid: str) -> dict[str, Any]:
    p = project_or_404(pid)
    if any(r.status == "queued" for r in p.requests()):
        raise HTTPException(409, "The director is still answering. Wait for the answer, choose one, then approve.")
    s = _state(p)
    s["approved_at"] = now_iso()
    write_json(p.dir / FILE, s)
    if p.meta().status in ("review", "waiting_for_claude"):
        p.update_meta(status="planned")
    return _view(p)


@router.post("/reopen")
def reopen(pid: str) -> dict[str, Any]:
    p = project_or_404(pid)
    s = _state(p)
    s["approved_at"] = ""
    write_json(p.dir / FILE, s)
    return _view(p)
