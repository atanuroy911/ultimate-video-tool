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
                                draft=None, schema=None, with_examples=not compact, compact=compact)
    return {
        "instructions": system, "task": user, "schema": to_json_schema(), "kind": kind,
        "project": {"id": p.id, "title": meta.title, "language": meta.language, "aspect": meta.aspect, "theme": load_theme(meta.theme).name},
        "media_bin": [{"id": m.id, "kind": m.kind, "caption": m.caption, "role": m.role} for m in meta.media],
        "aroll_direction": "If media id 'aroll' is present, use it as scene backdrop media to keep the recorded speaker visible; place overlays around the face. "
                           "A scene you leave with no overlays and no backdrop shows the speaker. A scene with only a word or a small sticker shows the speaker "
                           "too, with that word over the picture, but never more than two such scenes in a row: put a real graphic (a chart, a number card, "
                           "steps, a list) in at least every third scene, so the picture changes.",
        "has_draft": bool(sf), "has_current_script": (p.dir / "video_script.json").is_file(),
        **_craft_and_style(p, meta.theme, include_draft_report=not compact),
        "submit": "Call submit_script(project, script=<the JSON object>). If it returns errors, fix exactly those and call it again until ok is true.",
    }


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


UNDO_STATE = "state.prev.json"            # the plan one undo away together with its script and record (chat.director_state); scenes.prev.json stays beside it
SCRIPT_PLAN = "video_script.plan.json"   # what the current script compiled to, to see what was edited after it


def _compile_for(p: Project, script: VideoScript, tr, beats, meta) -> ScenesFile:
    """A Video Script as this project's plan: compiled, with the cartoon kit, the speaker's place in the recording and the scrims over its pictures."""
    from .story_kit import apply_story_kit

    sf = compile_script(script, tr, beats, meta.theme)
    sf = apply_story_kit(sf, script, tr, beats, meta.options.cartoon_template)
    # The A-roll video is already cut to the edited voice. Anchor every requested
    # speaker backdrop to its first beat, even when an assistant omits the offset.
    beat_by_id = {b.id: b for b in beats.beats}
    for scene in sf.scenes:
        if scene.backdrop and scene.backdrop.media == "aroll" and scene.beats and scene.beats[0] in beat_by_id:
            scene.backdrop.offset = round(beat_by_id[scene.beats[0]].start, 3)
    from ..planning import refresh_scrims

    try:
        sf = refresh_scrims(p, sf)
    except Exception:
        pass
    return sf


def carry_forward(current: ScenesFile, was: ScenesFile, new: ScenesFile) -> tuple[ScenesFile, list[str]]:
    """A revised script replaces only the scenes it changed. `was` is what the script compiled to before the revision, `new` what it compiles to
    now, `current` what is on the timeline (the person's edits, the director's own fixes after looking at its frames). A scene that compiles the
    same as before keeps what is on the timeline. Returns (the plan to save, the ids of the scenes whose new version was used).

    When the revision keeps the scene structure, the timeline's own structure stays too (scenes split, merged, removed or re-timed by hand), as long
    as every changed scene is still there with the same sentences. Otherwise each scene is decided alone: kept when it still has its sentences."""
    def same(a, b) -> bool:
        return a.model_dump(exclude_none=True) == b.model_dump(exclude_none=True)

    def structure(x: ScenesFile) -> list:
        return [(s.id, tuple(s.beats)) for s in x.scenes]

    was_by, cur_by, new_by = ({s.id: s for s in x.scenes} for x in (was, current, new))
    changed = [s.id for s in new.scenes if s.id not in was_by or not same(s, was_by[s.id])]
    if structure(was) == structure(new) and all(c in cur_by and cur_by[c].beats == new_by[c].beats for c in changed):
        scenes = [new_by[s.id].model_copy(update={"start": s.start}) if s.id in changed else s for s in current.scenes]
        return new.model_copy(update={"scenes": scenes}), changed
    used: list[str] = []
    scenes = []
    for s in new.scenes:
        if s.id not in changed and s.id in cur_by and cur_by[s.id].beats == s.beats:
            scenes.append(cur_by[s.id])
        else:
            scenes.append(s)
            used.append(s.id)
    return new.model_copy(update={"scenes": scenes}), used


def forget_script(p: Project) -> None:
    """The plan no longer comes from the saved Video Script (a fresh plan by the rules, a new direction about to start): the script, its record and its
    report go, so nobody later revises a script that is not what is on screen."""
    for name in ("video_script.json", SCRIPT_PLAN, "director.json"):
        (p.dir / name).unlink(missing_ok=True)


def remember_for_undo(p: Project, plan: Optional[ScenesFile] = None) -> None:
    """The plan about to be replaced, with the script it came from, so that scenes/undo brings both back: never a plan on screen with another plan's script
    behind it (the next director turn would revise the wrong video)."""
    from .chat import director_state

    state = director_state(p, plan)
    if not state.get("plan"):
        return
    write_json(p.dir / "scenes.prev.json", state["plan"])
    write_json(p.dir / UNDO_STATE, state)


def record_baseline(p: Project, sf: Optional[ScenesFile]) -> None:
    """Remember the plan as the machine made it, so what is changed afterwards on the timeline can be told apart (edits_since_script)."""
    if sf is not None and (p.dir / "video_script.json").is_file():
        write_json(p.dir / SCRIPT_PLAN, sf.model_dump(exclude_none=True))
    else:
        (p.dir / SCRIPT_PLAN).unlink(missing_ok=True)


def apply_script(p: Project, data: dict, *, planner: str = "claude", compose: bool = True, strict: bool = False,
                 expected_plan: Optional[dict] = None, previous: Optional[dict] = None) -> dict[str, Any]:
    """Repair, validate and compile `data`; on success it becomes the project's plan. Returns {ok, errors, repaired, repairs}.

    Nothing the repair does is silent (repair_script's notes). With `strict` (a director that can answer: Claude or Codex over MCP) every repair that changes what it wrote (a word
    moved, a text cut short, a value left out, scenes restructured) is an error it must fix and submit again, and the small ones it filled in come back as `repairs`. Without it
    (the local AI, the person's own edit) the script is used as repaired and everything the repair did is in Details, Problems.

    `previous` is the script this one revises: the one the plan on the timeline was made from. With it, only the scenes the revision changed are replaced; the rest keep what is on
    the timeline (carry_forward), and `replaced_edits` names the changed scenes that had edits of their own. Without it the script is a new direction and replaces the whole plan."""
    meta = p.meta()
    tr, beats = p.transcript(), p.beats()
    media = {m.id for m in meta.media}
    icons = all_icon_names()
    before = validate_script(data, tr, beats, icons, media) if isinstance(data, dict) else ["the script must be a JSON object"]
    dropped: list[str] = []
    notes: list[dict] = []
    chosen = (read_json(p.dir / "script_kind.json", {}) or {}).get("kind")   # the type the person chose on the New page wins over what the script says it is;
    fixed = repair_script(data, tr, beats, kind=chosen or None, dropped=dropped, notes=notes) if isinstance(data, dict) else data   # "auto" saves none: the AI picks
    errs = validate_script(fixed, tr, beats, icons, media) if isinstance(fixed, dict) else before
    if strict:                                                 # a director that can answer is told, instead of finding its picture gone or its words changed
        errs = REPAIRS.meaning(notes) + errs
    if errs:
        return {"ok": False, "errors": errs[:12]}
    script = VideoScript.model_validate(fixed)
    script.planner = planner  # type: ignore[assignment]
    sf = _compile_for(p, script, tr, beats, meta)
    from ..schema import validate_scenes

    errs = validate_scenes(sf, tr, beats, icons, media)
    if errs:
        return {"ok": False, "errors": errs[:12]}
    was = None
    if previous:
        try:
            was = _compile_for(p, VideoScript.model_validate(previous), tr, beats, meta)
        except Exception:                                      # noqa: BLE001  a script that no longer compiles has nothing to carry forward
            was = None
    # Compare and commit the plan plus both script sidecars under the same per-project lock. Every save_scenes caller participates,
    # so an edit either lands before this check (and causes a conflict) or after this complete commit (and therefore wins).
    replaced_edits: list[str] = []
    with p.scenes_lock():
        cur = p.scenes()
        if expected_plan is not None and (not cur or cur.model_dump(exclude_none=True) != expected_plan):
            return {"ok": False, "conflict": True,
                    "errors": ["The video was edited while the director was working. The newer edits were kept; send the request again."]}
        plan, baseline = sf, sf
        if was is not None and cur is not None:
            merged, used = carry_forward(cur, was, sf)
            if not validate_scenes(merged, tr, beats, icons, media):
                plan = merged
                try:                                           # what the machine made, scene by scene: the old record for the kept scenes, the new compile for the changed ones
                    old_base = read_json(p.dir / SCRIPT_PLAN, None)
                    base = ScenesFile.model_validate(old_base) if old_base else was
                    baseline = carry_forward(base, was, sf)[0]
                    base_by = {s.id: s for s in base.scenes}
                    replaced_edits = [s.id for s in cur.scenes if s.id in used and s.id in base_by
                                      and s.model_dump(exclude_none=True) != base_by[s.id].model_dump(exclude_none=True)]
                except Exception:                              # noqa: BLE001  the record only tells what was edited: never a reason to refuse a script
                    baseline = sf
        if cur:
            remember_for_undo(p, cur)
        write_json(p.dir / "video_script.json", script.model_dump(by_alias=True, exclude_none=True))
        write_json(p.dir / SCRIPT_PLAN, baseline.model_dump(exclude_none=True))
        p.save_scenes(plan)
        p.update_meta(status="planned")
    sf = plan
    if compose:
        from ..pipeline import compose_all

        compose_all(p)
    try:
        REPAIRS.record(p, notes, "the director" if strict else "the AI")
    except Exception:                                                                    # noqa: BLE001  a report, never a reason to lose a script
        pass
    return {"ok": True, "applied": True, "scenes": len(sf.scenes), "plan": sf.model_dump(exclude_none=True),
            "repaired": len(before), "dropped": dropped, "kind": script.kind, "replaced_edits": replaced_edits,
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
                              media_ids={m.id for m in meta.planner_media()}, progress=say, ctx=CX.load(p), notes=notes)
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
