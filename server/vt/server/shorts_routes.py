"""Server routes for AI YouTube Shorts & Highlight Extraction."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List, Optional, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..pipeline import export as render_export
from ..project import Project
from ..shorts.detector import detect_highlights
from ..shorts.splitter import slice_short_project
from ..util import read_json, write_json

router = APIRouter(prefix="/api", tags=["shorts"])


def project_or_404(pid: str) -> Project:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", pid) or pid in (".", ".."):
        raise HTTPException(400, "Invalid project ID")
    project = Project(pid)
    if not project.exists(): raise HTTPException(404, f"Project '{pid}' not found")
    return project


class DetectShortsRequest(BaseModel):
    num_clips: int = Field(default=5, ge=1, le=12)


class SliceShortRequest(BaseModel):
    index: int = Field(default=0)
    highlight: Optional[dict[str, Any]] = None
    aroll: Literal["auto", "off"] = "auto"
    caption_style: Literal["pop", "box", "pill", "underline", "theme"] = "pop"


class BatchSliceRequest(BaseModel):
    indices: List[int] = Field(default_factory=list)
    aroll: Literal["auto", "off"] = "auto"
    caption_style: Literal["pop", "box", "pill", "underline", "theme"] = "pop"


class AnalyzeUrlRequest(BaseModel):
    url: str
    num_clips: int = Field(default=5, ge=1, le=12)
    language: str = Field(default="auto")


@router.get("/projects/{pid}/shorts")
def get_project_shorts(pid: str) -> dict[str, Any]:
    """Get detected shorts candidates for a project."""
    p = project_or_404(pid)

    cache_file = p.dir / "shorts_candidates.json"
    data = (read_json(cache_file) or {}) if cache_file.exists() else {"highlights": [], "content_info": {}, "total_duration": 0.0}
    source = p.input_audio if p.input_audio.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm") else (p.ensure_preview_audio() or p.input_audio)
    data["preview_url"] = f"/media/{p.id}/{source.name}" if source.exists() else None
    return data


@router.post("/projects/{pid}/shorts/detect")
def detect_project_shorts(pid: str, req: DetectShortsRequest, request: Request) -> dict[str, Any]:
    """Run highlight detection on a project's transcript."""
    p = project_or_404(pid)

    # Ensure transcript exists
    raw_video = p.input_audio.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")
    tr_path = p.raw_transcript_path if raw_video and p.raw_transcript_path.exists() else (p.transcript_path if p.transcript_path.exists() else p.raw_transcript_path)
    if not tr_path.exists():
        raise HTTPException(400, "Project has no transcript yet. Run speech recognition first.")

    transcript = read_json(tr_path) or {}
    jobs = request.app.state.jobs

    def work(cb):
        def on_progress(frac: float, msg: str):
            cb("shorts", frac, msg)

        # the audio that matches the transcript's clock: the edited track for the edited transcript, the original for the raw one
        audio = p.cut_audio if tr_path == p.transcript_path and p.cut_audio.exists() else (p.input_audio if p.input_audio.exists() else None)
        events = (read_json(p.dir / "sounds_events.json") or {}).get("events") if (p.dir / "sounds_events.json").exists() else None
        res = detect_highlights(transcript, num_clips=req.num_clips, progress_cb=on_progress, audio_path=audio, sound_events=events)
        write_json(p.dir / "shorts_candidates.json", res)
        # Notify clients
        hub = getattr(request.app.state, "hub", None)
        if hub:
            hub.emit({"type": "shorts_detected", "project": pid, "count": len(res.get("highlights", []))})
        return res

    job = jobs.submit("shorts", pid, "Detect Viral Shorts Highlights", work, when_busy="reuse")
    return job.public()


@router.post("/projects/{pid}/shorts/slice")
def slice_one_short(pid: str, req: SliceShortRequest, request: Request) -> dict[str, Any]:
    """Slice one candidate short into an independent 9:16 child project."""
    p = project_or_404(pid)

    highlight = req.highlight
    if not highlight:
        cache_file = p.dir / "shorts_candidates.json"
        if not cache_file.exists():
            raise HTTPException(400, "No highlights found for this project. Detect them first.")
        cached = read_json(cache_file) or {}
        highlights = cached.get("highlights", [])
        if not (0 <= req.index < len(highlights)):
            raise HTTPException(400, f"Highlight index {req.index} out of range (total {len(highlights)})")
        highlight = highlights[req.index]

    def work(cb):
        cb("slice", 0.1, "Cutting the selected video")
        child = slice_short_project(pid, highlight, index=req.index + 1, run_pipeline=True, aroll=req.aroll, caption_style=req.caption_style)
        cb("slice", 1.0, "Short is ready")
        hub = getattr(request.app.state, "hub", None)
        if hub: hub.emit({"type": "project_created", "project": child.id})
        return {"child_project_id": child.id, "title": child.meta().title, "aspect": child.meta().aspect}
    return request.app.state.jobs.submit("shorts_slice", pid, "Create Short", work).public()


@router.post("/projects/{pid}/shorts/batch-slice")
def batch_slice_shorts(pid: str, req: BatchSliceRequest, request: Request) -> dict[str, Any]:
    """Slice multiple candidate shorts into child projects."""
    p = project_or_404(pid)

    cache_file = p.dir / "shorts_candidates.json"
    if not cache_file.exists():
        raise HTTPException(400, "No highlights found for this project.")
    cached = read_json(cache_file) or {}
    all_highlights = cached.get("highlights", [])

    indices = req.indices if req.indices else list(range(len(all_highlights)))
    if any(idx < 0 or idx >= len(all_highlights) for idx in indices):
        raise HTTPException(400, "A highlight index is out of range")
    def work(cb):
        created = []
        for n, idx in enumerate(indices):
            cb("slice", n / max(1, len(indices)), f"Creating Short {n+1}/{len(indices)}")
            child = slice_short_project(pid, all_highlights[idx], index=idx + 1, run_pipeline=True, aroll=req.aroll, caption_style=req.caption_style)
            created.append({"child_project_id": child.id, "title": child.meta().title})
            hub = getattr(request.app.state, "hub", None)
            if hub: hub.emit({"type": "project_created", "project": child.id})
        return {"created": created, "total": len(created)}
    return request.app.state.jobs.submit("shorts_batch", pid, "Create Shorts", work).public()


@router.post("/projects/{pid}/shorts/batch-export")
def batch_export_shorts(pid: str, req: BatchSliceRequest, request: Request) -> dict[str, Any]:
    p = project_or_404(pid)
    highlights = (read_json(p.dir / "shorts_candidates.json") or {}).get("highlights", [])
    indices = req.indices if req.indices else list(range(len(highlights)))
    if not indices or any(idx < 0 or idx >= len(highlights) for idx in indices):
        raise HTTPException(400, "Choose valid highlights first")
    def work(cb):
        exports = []
        for n, idx in enumerate(indices):
            cb("slice", n / len(indices), f"Preparing Short {n+1}/{len(indices)}")
            child = slice_short_project(pid, highlights[idx], index=idx + 1, run_pipeline=True, aroll=req.aroll, caption_style=req.caption_style)
            result = render_export(child, "9:16", progress=lambda stage, frac, msg="": cb(stage, (n + frac) / len(indices), msg))
            exports.append({"child_project_id": child.id, "video": str(result["video"]), "url": f"/media/{child.id}/exports/{Path(result['video']).name}"})
        return {"exports": exports}
    return request.app.state.jobs.submit("shorts_export", pid, "Export Shorts", work).public()
