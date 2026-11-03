"""Project-level glue for Video Scripts: the task handed to an assistant over MCP, and applying a script an assistant (or the app's AI) produced."""
from __future__ import annotations

from typing import Any, Optional

from .. import paths
from ..planner.catalogue import all_icon_names
from ..project import Project, load_theme
from ..schema import ScenesFile
from ..util import read_json, write_json
from .compile import compile_script, to_json_schema
from .models import VideoScript
from .prompt import build_prompt
from .validate import repair_script, validate_script


def script_kind(p: Project) -> str:
    return (read_json(p.dir / "script_kind.json", {}) or {}).get("kind") or "explainer"


def set_script_kind(p: Project, kind: str) -> None:
    write_json(p.dir / "script_kind.json", {"kind": kind})


def script_task(p: Project, kind: Optional[str] = None, hint: str = "") -> dict[str, Any]:
    """One call returns everything an assistant with no other context needs to write a valid script."""
    meta = p.meta()
    kind = kind or script_kind(p)
    tr, beats = p.transcript(), p.beats()
    sf = p.scenes()
    system, user = build_prompt(tr, beats, kind=kind, language=meta.language, aspect=meta.aspect, hint=hint,
                                draft=None, schema=None, with_examples=True)
    return {
        "instructions": system, "task": user, "schema": to_json_schema(), "kind": kind,
        "project": {"id": p.id, "title": meta.title, "language": meta.language, "aspect": meta.aspect, "theme": load_theme(meta.theme).name},
        "media_bin": [{"id": m.id, "kind": m.kind, "caption": m.caption, "role": m.role} for m in meta.media],
        "aroll_direction": "If media id 'aroll' is present, use it as scene backdrop media to keep the recorded speaker visible; place overlays around the face.",
        "has_draft": bool(sf),
        **_craft_and_style(p, meta.theme),
        "submit": "Call submit_script(project, script=<the JSON object>). If it returns errors, fix exactly those and call it again until ok is true.",
    }


def _craft_and_style(p: Project, theme: str) -> dict[str, Any]:
    """What every director gets: the craft rules (vt/craft.py), the chosen film style's bible (vt/styles.py) and what the current plan breaks."""
    from .. import craft, styles

    out: dict[str, Any] = {"craft_rules": craft.brief(),
                           "craft_check": "After submitting, call module craft.check (module_call) and fix every critical and major violation."}
    st = styles.for_theme(theme)
    if st:
        out["style"] = styles.brief(st["slug"])
    if p.scenes():
        try:
            rep = craft.check(p)
            out["craft_report"] = {"score": rep["score"], "violations": rep["violations"][:12]}
        except Exception:                                                               # noqa: BLE001
            pass
    return out


def apply_script(p: Project, data: dict, *, planner: str = "claude", compose: bool = True) -> dict[str, Any]:
    """Repair, validate and compile `data`; on success it becomes the project's plan. Returns {ok, errors, repaired}."""
    meta = p.meta()
    tr, beats = p.transcript(), p.beats()
    media = {m.id for m in meta.media}
    icons = all_icon_names()
    before = validate_script(data, tr, beats, icons, media) if isinstance(data, dict) else ["the script must be a JSON object"]
    fixed = repair_script(data, tr, beats) if isinstance(data, dict) else data
    errs = validate_script(fixed, tr, beats, icons, media) if isinstance(fixed, dict) else before
    if errs:
        return {"ok": False, "errors": errs[:12]}
    script = VideoScript.model_validate(fixed)
    script.planner = planner  # type: ignore[assignment]
    sf = compile_script(script, tr, beats, meta.theme)
    from .story_kit import apply_story_kit
    sf = apply_story_kit(sf, script, tr, beats, meta.options.cartoon_template)
    # The A-roll video is already cut to the edited voice. Anchor every requested
    # speaker backdrop to its first beat, even when an assistant omits the offset.
    beat_by_id = {b.id: b for b in beats.beats}
    for scene in sf.scenes:
        if scene.backdrop and scene.backdrop.media == "aroll" and scene.beats[0] in beat_by_id:
            scene.backdrop.offset = round(beat_by_id[scene.beats[0]].start, 3)
    from ..planning import refresh_scrims
    from ..schema import validate_scenes

    try:
        sf = refresh_scrims(p, sf)
    except Exception:
        pass
    errs = validate_scenes(sf, tr, beats, icons, media)
    if errs:
        return {"ok": False, "errors": errs[:12]}
    cur = p.scenes()
    if cur:
        write_json(p.dir / "scenes.prev.json", cur.model_dump(exclude_none=True))
    write_json(p.dir / "video_script.json", script.model_dump(by_alias=True, exclude_none=True))
    p.save_scenes(sf)
    p.update_meta(status="planned")
    if compose:
        from ..pipeline import compose_all

        compose_all(p)
    return {"ok": True, "applied": True, "scenes": len(sf.scenes), "repaired": len(before), "kind": script.kind}


def current_script(p: Project) -> Optional[dict]:
    return read_json(p.dir / "video_script.json", None)


def direct(p: Project, sf: ScenesFile, say=None) -> tuple[ScenesFile, str]:
    """The plan stage's script step. `kind` stick and emoji always go through a Video Script (AI when one answers, else the rule director);
    other kinds use the AI script only when settings.json has ai_script=true. Returns (plan, how it was made)."""
    from .. import ai
    from ..planner.catalogue import all_icon_names
    from ..schema import validate_scenes
    from .planner import plan_script

    meta = p.meta()
    kind = script_kind(p)
    want_ai = bool((read_json(paths.SETTINGS, {}) or {}).get("ai_script"))
    if kind not in ("stick", "emoji", "cartoon") and not want_ai:
        return sf, "plan"
    tr, beats = p.transcript(), p.beats()
    use_ai = ai.provider_status().get("available", False)
    from .. import context as CX

    from .. import taste

    script, how = plan_script(tr, beats, draft=sf, use_ai=use_ai, kind=kind if kind != "explainer" else "explainer", language=meta.language, aspect=meta.aspect, hint=taste.director_hint(),
                              media_ids={m.id for m in meta.planner_media()}, progress=say, ctx=CX.load(p))
    out = compile_script(script, tr, beats, sf.theme)
    from .story_kit import apply_story_kit
    out = apply_story_kit(out, script, tr, beats, meta.options.cartoon_template)
    if validate_scenes(out, tr, beats, all_icon_names()):
        return sf, "plan"
    write_json(p.dir / "video_script.json", script.model_dump(by_alias=True, exclude_none=True))
    save_report(p, script, tr, beats, how)
    return out, how


def save_report(p: Project, script: VideoScript, tr, beats, how: str) -> dict:
    """director.json: how the plan was made and what the critic still says about it (shown in the Studio, read by assistants over MCP)."""
    from ..util import now_iso
    from .critic import review

    rv = review(script, tr, beats)
    doc = {"at": now_iso(), "how": how, "score": rv["score"], "metrics": rv["metrics"], "issues": rv["issues"]}
    write_json(p.dir / "director.json", doc)
    return doc
