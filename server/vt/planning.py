"""Planning requests: the bridge between Studio and a connected MCP assistant.

Studio buttons write a request file; Codex or Claude picks it up via MCP tools
(list_pending_requests -> get_planning_task -> submit_scenes) and the result is validated and saved here.
"""
from __future__ import annotations

import uuid
import os
from typing import Any, Optional

from pydantic import ValidationError

from .pipeline import compose_all
from .planner.catalogue import all_icon_names, catalogue_summary
from .planner.prompt import PLANNER_RULES, SCENE_RULES
from .project import Project, load_theme
from .schema import PlanRequest, Scene, ScenesFile, validate_scenes
from .util import now_iso, read_json, write_json


def create_request(project: Project, kind: str = "full", scene_id: Optional[str] = None, hint: str = "",
                   alternatives: int = 1) -> PlanRequest:
    if kind == "scene":
        sf = project.scenes()
        if not sf or scene_id not in [s.id for s in sf.scenes]:
            raise ValueError(f"scene '{scene_id}' not found")
    # one open request per (kind, scene): replace the older one so the queue does not fill with duplicates
    for r in project.requests():
        if r.status == "queued" and r.kind == kind and r.scene_id == scene_id:
            (project.requests_dir / f"{r.id}.json").unlink(missing_ok=True)
    req = PlanRequest(id=uuid.uuid4().hex[:8], project=project.id, kind=kind, scene_id=scene_id, hint=hint.strip(),
                      alternatives=max(1, min(4, alternatives)), created_at=now_iso())
    project.save_request(req)
    project.update_meta(status="waiting_for_claude")
    return req


def pending() -> list[dict]:
    out = []
    for proj in Project.list_all():
        for r in proj.requests():
            if r.status == "queued":
                out.append({"project": proj.id, "title": proj.meta().title, **r.model_dump()})
    return out


def _beats_payload(project: Project) -> list[dict]:
    tr = project.transcript()
    words = tr.by_id()
    out = []
    for b in project.beats().beats:
        out.append({
            "id": b.id, "start": round(b.start, 2), "end": round(b.end, 2), "text": b.text,
            "words": [f"{wid}:{words[wid].text}@{words[wid].start:.2f}" for wid in b.word_ids if wid in words],
        })
    return out


def visual_suggestions(project: Project) -> list[dict]:
    """Per sentence: the stressed word and the best visual for it (from the visual dictionary). Cached per transcript."""
    from .visuals import emoji as emo
    from .visuals.picker import pick_visuals

    try:
        picks = pick_visuals(project.transcript(), project.beats(), project.cut_audio if project.cut_audio.exists() else None)
    except Exception:
        return []
    out = []
    for bid, k in picks.items():
        out.append({"beat": bid, "word_id": k.word_id, "word": k.text, "emphasis": round(k.emphasis, 2), "suggest": k.kind,
                    "icon": k.line, "sticker": ({"hex": k.sticker, "emoji": emo.index().get(k.sticker, {}).get("emoji", ""), "name": emo.label(k.sticker)} if k.sticker else None),
                    "other_candidates": k.alternatives})
    return out


def usecase_info(project: Project) -> dict:
    """Which kind of video this is and what that kind favours (from design/profiles/*.json), so a plan fits it."""
    from .director import profiles
    from .director.plan import ARCHETYPE_LABELS

    meta = project.meta()
    used = (read_json(project.dir / "usecase.json", {}) or {}).get("used") or (meta.usecase if meta.usecase != "auto" else "general")
    prof = profiles.get(used)
    fav = sorted(prof.get("weights", {}).items(), key=lambda kv: -kv[1])[:8]
    return {"requested": meta.usecase, "used": used, "about": prof.get("about", ""), "favoured_scene_types": [k for k, v in fav if v > 0.8],
            "scene_types": ARCHETYPE_LABELS, "pace_seconds_per_scene": prof["pace"]}


def director_args(p: Project) -> dict:
    """What the director needs to know about a project (language, kind of video, pictures, media, story brief)."""
    meta = p.meta()
    used = (read_json(p.dir / "usecase.json", {}) or {}).get("used") or (meta.usecase if meta.usecase != "auto" else "general")
    try:
        from .visuals.picker import pick_visuals

        picks = pick_visuals(p.transcript(), p.beats(), p.cut_audio if p.cut_audio.exists() else None)
    except Exception:
        picks = {}
    return {"language": meta.language, "usecase": used, "picks": picks, "media": meta.planner_media(), "brief": (read_json(p.dir / "ai_notice.json", {}) or {}).get("brief"), "seed": p.id}


def refresh_scrims(project: Project, sf: ScenesFile) -> ScenesFile:
    """Text over a picture is checked by the contrast engine, whoever wrote the plan: the scrim of every backdrop is (re)computed here."""
    from .director.contrast import decide_for_media

    if not any(s.backdrop for s in sf.scenes):
        return sf
    meta = project.meta()
    beats = {b.id: b for b in project.beats().beats}
    scenes = []
    for s in sf.scenes:
        if s.backdrop:
            t0, t1 = beats[s.beats[0]].start, beats[s.beats[-1]].end
            scrim = decide_for_media(project, s.backdrop.media, meta.aspect, s.layout, t0, t1)
            s = s.model_copy(update={"backdrop": s.backdrop.model_copy(update={"scrim": scrim})})
        scenes.append(s)
    return sf.model_copy(update={"scenes": scenes})


def _craft_and_style(project: Project, theme: str) -> dict[str, Any]:
    from .script.service import _craft_and_style as cs

    return cs(project, theme)


def planning_task(project: Project, request_id: str) -> dict[str, Any]:
    req = next((r for r in project.requests() if r.id == request_id), None)
    if not req:
        raise ValueError(f"request '{request_id}' not found in project '{project.id}'")
    meta = project.meta()
    theme = load_theme(meta.theme)
    sf = project.scenes()
    task: dict[str, Any] = {
        "request": req.model_dump(),
        "instructions": PLANNER_RULES if req.kind == "full" else SCENE_RULES,
        "project": {"id": project.id, "title": meta.title, "language": meta.language,
                    "script_policy": meta.options.script_policy, "theme": theme.name, "currency": theme.currency,
                    "aspects": ["9:16", "1:1", "16:9"], "glossary": project.glossary()},
        "beats": _beats_payload(project),
        "catalogue": catalogue_summary(),
        "usecase": usecase_info(project),
        "media_bin": [{"id": m.id, "kind": m.kind, "caption": m.caption, "role": m.role, "ratio": round(m.width / m.height, 2) if m.height else 1.0, "duration": m.duration} for m in meta.media],
        "visual_suggestions": visual_suggestions(project),
        **_craft_and_style(project, meta.theme),
        "submit": "Call submit_scenes(project, request_id, scenes=[...])" if req.kind == "full" else
                  "Call submit_scenes(project, request_id, scenes=[<scene>, ...]) with `alternatives` scene objects for scene "
                  f"'{req.scene_id}' (same beats).",
    }
    if sf:
        if req.kind == "full":
            task["draft_plan_from_rules"] = sf.model_dump(exclude_none=True)["scenes"]
        else:
            scenes = sf.model_dump(exclude_none=True)["scenes"]
            idx = next(i for i, s in enumerate(scenes) if s["id"] == req.scene_id)
            task["target_scene"] = scenes[idx]
            task["previous_scene"] = scenes[idx - 1] if idx > 0 else None
            task["next_scene"] = scenes[idx + 1] if idx + 1 < len(scenes) else None
    return task


def _short(errors: list[str], n: int = 12) -> list[str]:
    return errors[:n] + ([f"... and {len(errors) - n} more"] if len(errors) > n else [])


def submit(project: Project, request_id: str, scenes: list[dict]) -> dict[str, Any]:
    """Validate and apply an assistant's answer; return errors it can fix and retry."""
    req = next((r for r in project.requests() if r.id == request_id), None)
    if not req:
        return {"ok": False, "errors": [f"request '{request_id}' not found"]}
    if not isinstance(scenes, list) or not scenes:
        return {"ok": False, "errors": ["`scenes` must be a non-empty list of scene objects"]}
    meta = project.meta()
    tr, beats = project.transcript(), project.beats()
    icons = all_icon_names()
    current = project.scenes()
    planner = "assistant" if os.environ.get("VT_MCP_CLIENT") == "codex" else "claude"

    try:
        parsed = [Scene.model_validate(s) for s in scenes]
    except ValidationError as e:
        errs = [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]
        return {"ok": False, "errors": _short(errs)}

    if req.kind == "full":
        candidates = [ScenesFile(theme=meta.theme, planner=planner, scenes=parsed)]
    else:
        if not current:
            return {"ok": False, "errors": ["project has no plan yet"]}
        base = next((s for s in current.scenes if s.id == req.scene_id), None)
        if not base:
            return {"ok": False, "errors": [f"scene '{req.scene_id}' no longer exists"]}
        candidates = []
        for s in parsed[: req.alternatives]:
            s = s.model_copy(update={"id": base.id, "beats": base.beats})
            new = [s if x.id == base.id else x for x in current.scenes]
            candidates.append(ScenesFile(theme=current.theme, planner=planner, scenes=new))
    errs: list[str] = []
    media_ids = {m.id for m in meta.media}
    for k, c in enumerate(candidates):
        try:
            candidates[k] = refresh_scrims(project, c)
        except Exception:
            pass
    for i, c in enumerate(candidates):
        for e in validate_scenes(c, tr, beats, icons, media_ids):
            errs.append(e if len(candidates) == 1 else f"alternative {i + 1}: {e}")
    if errs:
        return {"ok": False, "errors": _short(errs)}

    project.requests_dir.mkdir(parents=True, exist_ok=True)
    if req.kind == "scene" and len(candidates) > 1:
        write_json(project.requests_dir / f"{req.id}.alternatives.json",
                   [next(s for s in c.scenes if s.id == req.scene_id).model_dump(exclude_none=True) for c in candidates])
        req.status = "done"
        project.save_request(req)
        project.update_meta(status="planned")
        return {"ok": True, "applied": False, "message": f"{len(candidates)} alternatives saved; the user picks one in Studio"}
    if current:
        write_json(project.dir / "scenes.prev.json", current.model_dump(exclude_none=True))
    project.save_scenes(candidates[0])
    req.status = "done"
    project.save_request(req)
    project.update_meta(status="planned")
    compose_all(project)
    return {"ok": True, "applied": True, "scenes": len(candidates[0].scenes)}


def alternatives(project: Project, request_id: str) -> list[dict]:
    return read_json(project.requests_dir / f"{request_id}.alternatives.json", []) or []


def apply_alternative(project: Project, request_id: str, index: int) -> ScenesFile:
    alts = alternatives(project, request_id)
    req = next((r for r in project.requests() if r.id == request_id), None)
    if not alts or not req or not req.scene_id or not (0 <= index < len(alts)):
        raise ValueError("no such alternative")
    current = project.scenes()
    assert current
    base = next(s for s in current.scenes if s.id == req.scene_id)
    new_scene = Scene.model_validate({**alts[index], "id": base.id, "beats": base.beats})
    sf = ScenesFile(theme=current.theme, planner="assistant", scenes=[new_scene if s.id == base.id else s for s in current.scenes])
    errs = validate_scenes(sf, project.transcript(), project.beats(), all_icon_names())
    if errs:
        raise ValueError("; ".join(errs))
    write_json(project.dir / "scenes.prev.json", current.model_dump(exclude_none=True))
    project.save_scenes(sf)
    compose_all(project)
    return sf
