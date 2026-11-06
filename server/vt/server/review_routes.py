"""Studio API for judging a finished video: the automatic judges (vt/judges.py) and the short human checklist (docs/TEST-PLAN.md section 5)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from ..util import read_json, write_json
from .modules_routes import project_or_404

router = APIRouter(prefix="/api/projects/{pid}", tags=["review"])

CHECKLIST = [
    {"id": "hook", "q": "Does the first second make you want the next one?"},
    {"id": "match", "q": "Does each picture show what the sentence says?"},
    {"id": "timing", "q": "Does the picture change when the sentence changes?"},
    {"id": "facts", "q": "Is every claim, number and name something the speaker said?"},
    {"id": "broken", "q": "Is anything broken (a flash, a cut-off picture, garbled text, a figure that turns into someone else)?"},
    {"id": "captions", "q": "Do the captions help (readable, on the right word)?"},
    {"id": "voice", "q": "Does the voice suit the content?"},
    {"id": "sound", "q": "Does the music or sound help the voice?"},
    {"id": "post", "q": "Would you post it under your name?"},
    {"id": "world", "q": "For a long video: does it still feel like one world at the end?"},
]


def newest_export(project, name: Optional[str] = None) -> Path:
    files = sorted(project.exports_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True) if project.exports_dir.exists() else []
    f = next((x for x in files if name is None or x.name == name), None)
    if f is None:
        raise HTTPException(409, "Make the video first, then it can be checked.")
    return f


def judge_export(project, video: Path) -> dict[str, Any]:
    """Run the judges on one finished video with the project's own words, scenes and captions; saved next to the video."""
    from ..compose import FORMATS
    from ..judges import judge_video

    meta = project.meta()
    aspect = next((a for a, v in FORMATS.items() if f"-{v['tag']}-" in video.name), meta.aspect)
    comp = read_json(project.comp_dir / FORMATS[aspect]["tag"] / "data.json", None)
    beats = {b.id: b for b in project.beats().beats}
    sf = project.scenes()
    scenes = []
    for s in (sf.scenes if sf else []):
        if s.beats and s.beats[0] in beats and s.beats[-1] in beats:
            scenes.append({"id": s.id, "backdrop": s.backdrop.model_dump() if s.backdrop else None, "card": any(getattr(e, "type", "") == "title" for e in s.elements), "start": beats[s.beats[0]].start, "end": beats[s.beats[-1]].end})
    report = (read_json(project.dir / "reel_report.json", {}) or {})
    kind = report.get("kind") or "explanation"
    result = judge_video(video, words=[w.model_dump() for w in project.transcript().kept()], scenes=scenes if meta.options.look == "reel" else None, composition=comp, kind=kind)
    result["file"] = video.name
    result["at"] = time.strftime("%Y-%m-%d %H:%M")
    write_json(video.with_suffix(".judges.json"), result)
    return result


def judges_summary(video: Path) -> Optional[dict[str, Any]]:
    r = read_json(video.with_suffix(".judges.json"), None)
    if not r:
        return None
    return {"passed": r["passed"], "failed": r["failed"], "skipped": r["skipped"], "at": r.get("at", ""), "says": [v["says"] for v in r["verdicts"] if v["passed"] is False]}


@router.post("/judge")
def judge(pid: str, name: Optional[str] = None) -> dict[str, Any]:
    """Check the newest export (or `name`) with every automatic judge. Takes a few seconds."""
    project = project_or_404(pid)
    return judge_export(project, newest_export(project, name))


@router.get("/judge")
def judge_saved(pid: str, name: Optional[str] = None) -> dict[str, Any]:
    project = project_or_404(pid)
    f = newest_export(project, name)
    return {"result": read_json(f.with_suffix(".judges.json"), None), "file": f.name}


@router.get("/look-at")
def look_at(pid: str) -> dict[str, Any]:
    """What is left to look at in the cut, for the Quality check. A plan an AI directed: what the page still measures wrong after the director's rounds (`left`; code never fixes it
    behind the director's back). A plan made by the rules: what the layout guard changed (`changed`). `current` says whether the plan is still the one that was looked at."""
    from ..layout_check import REPORT as GUARD
    from ..director_review import REPORT as REVIEW
    from ..util import file_hash

    project = project_or_404(pid)
    sf = project.scenes()
    number = {s.id: i + 1 for i, s in enumerate(sf.scenes)} if sf else {}
    now = file_hash(project.scenes_path) if project.scenes_path.exists() else ""
    review = read_json(project.dir / REVIEW, None) or {}
    guard = read_json(project.dir / GUARD, None) or {}
    left = [{**row, "number": number.get(row.get("scene"))} for row in review.get("left", [])]
    return {
        "planner": sf.planner if sf else "",
        "looked": "left" in review and not review.get("facts_error"), "left": left, "current": review.get("scenes_hash") == now,
        "changed": guard.get("scenes", []), "guard_current": guard.get("scenes_hash") == now,
    }


@router.get("/checklist")
def checklist(pid: str) -> dict[str, Any]:
    project = project_or_404(pid)
    saved = read_json(project.dir / "checklist.json", {}) or {}
    return {"questions": CHECKLIST, "answers": saved.get("answers", {}), "notes": saved.get("notes", {}), "at": saved.get("at", "")}


@router.put("/checklist")
def save_checklist(pid: str, body: dict[str, Any]) -> dict[str, Any]:
    """Answers are yes, no or a number as text; a note is kept for any 'no' (the checklist asks for one sentence for every no)."""
    project = project_or_404(pid)
    ids = {q["id"] for q in CHECKLIST}
    answers = {k: str(v)[:20] for k, v in (body.get("answers") or {}).items() if k in ids}
    notes = {k: str(v)[:400] for k, v in (body.get("notes") or {}).items() if k in ids}
    write_json(project.dir / "checklist.json", {"answers": answers, "notes": notes, "at": time.strftime("%Y-%m-%d %H:%M")})
    return checklist(pid)
