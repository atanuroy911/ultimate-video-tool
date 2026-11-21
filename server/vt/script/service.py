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
from . import repairs as REPAIRS
from .prompt import build_prompt
from .validate import repair_script, validate_script


def script_kind(p: Project) -> str:
    return (read_json(p.dir / "script_kind.json", {}) or {}).get("kind") or "explainer"


def set_script_kind(p: Project, kind: str) -> None:
    write_json(p.dir / "script_kind.json", {"kind": kind})


def script_task(p: Project, kind: Optional[str] = None, hint: str = "", *, compact: bool = False) -> dict[str, Any]:
    """One call returns everything an assistant with no other context needs to write a valid script."""
    meta = p.meta()
    kind = kind or script_kind(p)
    tr, beats = p.transcript(), p.beats()
    sf = p.scenes()
    system, user = build_prompt(tr, beats, kind=kind, language=meta.language, aspect=meta.aspect, hint=hint,
                                draft=None, schema=None, with_examples=not compact, compact=compact, look_ahead=_look_ahead(p, beats))
    return {
        "instructions": system, "task": user, "schema": to_json_schema(), "kind": kind,
        "project": {"id": p.id, "title": meta.title, "language": meta.language, "aspect": meta.aspect, "theme": load_theme(meta.theme).name},
        "media_bin": [{"id": m.id, "kind": m.kind, "caption": m.caption, "role": m.role} for m in meta.media],
        "aroll_direction": "If media id 'aroll' is present, use it as scene backdrop media to keep the recorded speaker visible; place overlays around the face.",
        "has_draft": bool(sf), "has_current_script": (p.dir / "video_script.json").is_file(),
        **_craft_and_style(p, meta.theme, include_draft_report=not compact),
        "submit": "Call submit_script(project, script=<the JSON object>). If it returns errors, fix exactly those and call it again until ok is true.",
    }


def _look_ahead(p: Project, beats, say=lambda f, m: None) -> str:
    """A long talk with the speaker's picture is read ahead first (C10, vt/talk_outline.py); its examples go into the director's task."""
    from .. import talk_outline

    return talk_outline.look_ahead_text(talk_outline.ensure(p, progress=say), beats)


def _craft_and_style(p: Project, theme: str, *, include_draft_report: bool = True) -> dict[str, Any]:
    """What every director gets: the craft rules (vt/craft.py), the chosen film style's bible (vt/styles.py) and what the current plan breaks."""
    from .. import craft, styles

    out: dict[str, Any] = {"craft_rules": craft.brief(),
                           "craft_check": "After submitting, call module craft.check (module_call) and fix every critical and major violation."}
    st = styles.for_theme(theme)
    if st:
        out["style"] = styles.brief(st["slug"])
    if include_draft_report and p.scenes():
        try:
            rep = craft.check(p)
            out["craft_report"] = {"score": rep["score"], "violations": rep["violations"][:12]}
        except Exception:                                                               # noqa: BLE001
            pass
    return out


SCRIPT_PLAN = "video_script.plan.json"   # what the current script compiled to, to see what was edited after it


def apply_script(p: Project, data: dict, *, planner: str = "claude", compose: bool = True, strict: bool = False,
                 expected_plan: Optional[dict] = None) -> dict[str, Any]:
    """Repair, validate and compile `data`; on success it becomes the project's plan. Returns {ok, errors, repaired, repairs}.

    Nothing the repair does is silent (repair_script's notes). With `strict` (a director that can answer: Claude or Codex over MCP) every repair that changes what it wrote (a word
    moved, a text cut short, a value left out, scenes restructured) is an error it must fix and submit again, and the small ones it filled in come back as `repairs`. Without it
    (the local AI, the person's own edit) the script is used as repaired and everything the repair did is in Details, Problems."""
    meta = p.meta()
    tr, beats = p.transcript(), p.beats()
    media = {m.id for m in meta.media}
    icons = all_icon_names()
    from .. import shots as SH
    from ..compose.composer import FORMATS

    have_shots = {s["id"] for s in SH.list_shots(p) if "error" not in s}
    frame = (FORMATS[meta.aspect]["width"], FORMATS[meta.aspect]["height"]) if meta.aspect in FORMATS else None
    before = validate_script(data, tr, beats, icons, media, have_shots, frame) if isinstance(data, dict) else ["the script must be a JSON object"]
    dropped: list[str] = []
    notes: list[dict] = []
    fixed = repair_script(data, tr, beats, dropped=dropped, notes=notes, frame=frame, known_shots=have_shots) if isinstance(data, dict) else data
    errs = validate_script(fixed, tr, beats, icons, media, have_shots, frame) if isinstance(fixed, dict) else before
    if strict:                                                 # a director that can answer is told, instead of finding its picture gone or its words changed
        errs = REPAIRS.meaning(notes) + errs
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
    # Compare and commit the plan plus both script sidecars under the same per-project lock. Every save_scenes caller participates,
    # so an edit either lands before this check (and causes a conflict) or after this complete commit (and therefore wins).
    with p.scenes_lock():
        cur = p.scenes()
        if expected_plan is not None and (not cur or cur.model_dump(exclude_none=True) != expected_plan):
            return {"ok": False, "conflict": True,
                    "errors": ["The video was edited while the director was working. The newer edits were kept; send the request again."]}
        if cur:
            write_json(p.dir / "scenes.prev.json", cur.model_dump(exclude_none=True))
        for sh in script.shots:                               # the director's shots; the person's visual edits (overrides.json) are kept
            d = SH.shot_dir(p, sh.id)
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(sh.html, encoding="utf-8")
            write_json(d / "shot.json", {"title": sh.title or sh.id, "knobs": [k.model_dump() for k in sh.knobs], "made_by": planner})
        write_json(p.dir / "video_script.json", script.model_dump(by_alias=True, exclude_none=True))
        write_json(p.dir / SCRIPT_PLAN, sf.model_dump(exclude_none=True))
        p.save_scenes(sf)
        p.update_meta(status="planned")
    if compose:
        from ..pipeline import compose_all

        compose_all(p)
    try:
        REPAIRS.record(p, notes, "the director" if strict else "the AI")
    except Exception:                                                                    # noqa: BLE001  a report, never a reason to lose a script
        pass
    return {"ok": True, "applied": True, "scenes": len(sf.scenes), "plan": sf.model_dump(exclude_none=True),
            "repaired": len(before), "dropped": dropped, "kind": script.kind,
            "repairs": REPAIRS.small(notes) if strict else REPAIRS.meaning(notes) + REPAIRS.small(notes)}


def current_script(p: Project) -> Optional[dict]:
    return read_json(p.dir / "video_script.json", None)


def edits_since_script(p: Project) -> list[dict]:
    """Scenes that differ from what the Video Script compiled to: fixes made on the timeline live in the plan, not the script, and a new script replaces them."""
    was = read_json(p.dir / SCRIPT_PLAN, None)
    sf = p.scenes()
    if not was or not sf:
        return []
    before = {s["id"]: s for s in was.get("scenes", [])}
    now = {s["id"]: s for s in sf.model_dump(exclude_none=True)["scenes"]}
    out = [{"scene": i, "change": "removed"} for i in before if i not in now]
    for i, s in now.items():
        if i not in before:
            out.append({"scene": i, "change": "added", "now": s})
        elif s != before[i]:
            out.append({"scene": i, "change": "edited", "now": s})
    return out


def uses_script(p: Project, chosen: str) -> bool:
    """Does this video's plan come from a Video Script? Stick, emoji and cartoon always do. So does every video directed by an AI that only plans
    through scripts (Claude, Codex); the local model plans explainers with its picture planner unless settings.json has ai_script=true."""
    return chosen != "local" or script_kind(p) in ("stick", "emoji", "cartoon") or bool((read_json(paths.SETTINGS, {}) or {}).get("ai_script"))


def direct(p: Project, sf: ScenesFile, say=None, want_ai: bool = False) -> tuple[ScenesFile, str]:
    """The plan stage's script step: the director's Video Script (AI when one answers, else the rule director). Returns (plan, how it was made)."""
    from .. import ai
    from ..planner.catalogue import all_icon_names
    from ..schema import validate_scenes
    from .planner import plan_script

    meta = p.meta()
    kind = script_kind(p)
    want_ai = want_ai or bool((read_json(paths.SETTINGS, {}) or {}).get("ai_script"))
    if kind not in ("stick", "emoji", "cartoon") and not want_ai:
        return sf, "plan"
    tr, beats = p.transcript(), p.beats()
    use_ai = ai.provider_status().get("available", False)
    from .. import context as CX

    from .. import taste

    notes: list[dict] = []                                                                  # what repairing the AI's script changed in it (script/repairs.py)
    script, how = plan_script(tr, beats, draft=sf, use_ai=use_ai, kind=kind if kind != "explainer" else "explainer", language=meta.language, aspect=meta.aspect, hint=taste.director_hint(),
                              media_ids={m.id for m in meta.planner_media()}, progress=say, ctx=CX.load(p), notes=notes,
                              look_ahead=_look_ahead(p, beats, say))
    if how.startswith("rules") and kind not in ("stick", "emoji", "cartoon"):           # the AI could not write it: an explainer keeps its rule draft as it is
        return sf, how
    out = compile_script(script, tr, beats, sf.theme)
    from .story_kit import apply_story_kit
    out = apply_story_kit(out, script, tr, beats, meta.options.cartoon_template, motifs=how.startswith("rules"))     # word-spotted extras only help the rule draft; an AI decides for itself
    if validate_scenes(out, tr, beats, all_icon_names()):
        return sf, "plan"
    write_json(p.dir / "video_script.json", script.model_dump(by_alias=True, exclude_none=True))
    save_report(p, script, tr, beats, how)
    if notes and how.startswith("ai"):
        try:
            REPAIRS.record(p, notes, "the AI")                                              # Details, Problems: what the script became
        except Exception:                                                                   # noqa: BLE001  a report, never a reason to lose a plan
            pass
    return out, how


def save_report(p: Project, script: VideoScript, tr, beats, how: str) -> dict:
    """director.json: how the plan was made and what the critic still says about it (shown in the Studio, read by assistants over MCP)."""
    from ..util import now_iso
    from .critic import review

    rv = review(script, tr, beats)
    doc = {"at": now_iso(), "how": how, "score": rv["score"], "metrics": rv["metrics"], "issues": rv["issues"]}
    write_json(p.dir / "director.json", doc)
    return doc
