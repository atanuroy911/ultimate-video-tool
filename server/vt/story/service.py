"""Cartoon 2 for the pipeline, the API and the MCP tools: one set of functions behind all three.

plan_story(p)            the plan a new video gets: rule draft, then the chosen director (an AI on the server designs scene by scene;
                         a director on the person's computer receives the draft as a task and submits the whole story)
story_task(p)            everything an outside director needs: designer rules, catalog, timed captions, cast, the current story
submit_story(p, spec)    validate a story from any director and make it the plan
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from ..project import Project
from ..schema import validate_scenes
from ..script import repairs as REPAIRS
from ..util import read_json, write_json
from . import catalog as SC
from . import engine_validate as V
from .plan import captions_from_words, draft_spec, to_scenes, to_spec

DRAFT = "story_draft.json"          # the engine spec the plan came from (kept so a director can start from it)


def _total(p: Project) -> float:
    cuts = p.cuts()
    return float(cuts.output_duration) if cuts else max((w.end for w in p.transcript().kept()), default=1.0) + 1.0


def _cues(p: Project) -> list[dict] | None:
    """The lines of the person's own subtitle file, when the video came with one (ingest.attach_subtitles)."""
    return read_json(p.dir / "subtitles.cues.json", None)


def plan_story(p: Project, provider=None, progress: Optional[Callable[[float, str], None]] = None) -> tuple[Any, str, str]:
    """Returns (ScenesFile, how, notice). `provider` is the AI the chosen director runs on, None for the rules only."""
    meta = p.meta()
    tr, beats = p.transcript(), p.beats()
    spec, caps = draft_spec(tr, _total(p), meta.language, _cues(p))
    how, notice = "rules", ""
    if provider is not None:
        from ..ai.providers import AIUnavailable
        from .designer import refine

        try:
            spec, used = refine(spec, meta.aspect, progress, provider=provider)
            how = f"ai ({used} of {len(spec['scenes'])} scenes)" if used else "rules"
            if not used:
                notice = "The AI did not return a usable design for any scene, so the rule director's story was kept."
        except AIUnavailable as e:
            notice = f"The AI was not available ({str(e)[:120]}), so the rule director drew the story."
    notes: list[dict] = []
    spec, _, _ = V.validate(spec, notes=notes)
    if how.startswith("ai"):
        try:
            REPAIRS.record(p, notes, "the AI", "story")                                  # Details, Problems: what the story became
        except Exception:                                                               # noqa: BLE001  a report, never a reason to lose a plan
            pass
    write_json(p.dir / DRAFT, spec)
    sf = to_scenes(spec, tr, beats, caps, planner="llm" if how.startswith("ai") else "rules", theme=meta.theme if meta.theme != "auto" else "paper")
    errs = validate_scenes(sf, tr, beats)
    if errs:
        raise RuntimeError("the story plan is invalid: " + "; ".join(errs[:4]))
    return sf, how, notice


def story_task(p: Project) -> dict[str, Any]:
    from .designer import system_prompt

    meta = p.meta()
    sf = p.scenes()
    if sf is not None and any(e.type == "story" for sc in sf.scenes for e in sc.elements):
        spec = to_spec(sf, p.beats(), _total(p), meta.language)          # the story as it is now, with the person's edits
    else:
        spec = read_json(p.dir / DRAFT, None) or draft_spec(p.transcript(), _total(p), meta.language, _cues(p))[0]
    caps = captions_from_words(p.transcript(), _cues(p))
    return {
        "project": p.id, "language": meta.language, "aspect": meta.aspect, "total_seconds": round(_total(p), 2),
        "how_to": "Return the WHOLE story as one JSON spec in the same shape as `current_story` (characters, speak, tags, sfx, scenes with s, e, bg, "
                  "elements). Keep the scene windows contiguous from 0 to total_seconds, keep `at` times on the words they show (use the caption "
                  "times), use only cast ids from `characters`, and call submit_story. Nothing is changed behind your back: whatever the app would have had to drop or replace in "
                  "what you wrote (an element type it cannot draw, a background it does not have, a speaker who is not in the cast, a sound it does not know) comes back as an error; "
                  "fix every error and submit again. Every warning it returns is also something to fix.",
        "designer_rules": system_prompt(meta.aspect),
        "catalog": SC.listing(),
        "captions": [{"s": c["s"], "e": c["e"], "text": c["t"], "quote": c["quote"]} for c in caps],
        "current_story": spec,
    }


MAX_TOLD = 60                                                                # more than this many warnings are counted, not listed (a story with sixty is not one to polish)


def submit_story(p: Project, spec: Any, planner: str = "claude") -> dict[str, Any]:
    """Validate a story from any director and make it the plan. Nothing is changed behind a director's back: with `strict` (a director that can answer, which is everyone but the person's own
    edit) whatever the validator would have had to drop or replace comes back as an error to fix, and the small things it only moved (a time, a gap) in `repairs`. The person's own edit
    is applied as repaired and everything is in `repairs` and in Details, Problems. Every warning comes back (up to MAX_TOLD), not the first eight."""
    if not isinstance(spec, dict):
        return {"ok": False, "errors": ["the story must be a JSON object"]}
    tr, beats = p.transcript(), p.beats()
    strict = planner != "manual"
    spec = {"meta": {"total": _total(p)}, "captions": [], "speak": {}, "tags": [], "sfx": [], **spec}
    notes: list[dict] = []
    fixed, errors, warnings = V.validate(spec, notes=notes)
    told = REPAIRS.meaning(notes) if strict else []
    said = warnings[:MAX_TOLD]
    more = {"warnings_not_listed": len(warnings) - MAX_TOLD} if len(warnings) > MAX_TOLD else {}
    if errors or told:
        return {"ok": False, "errors": (errors + told)[:40], "warnings": said, **more}
    caps = captions_from_words(tr, _cues(p))
    if not fixed.get("captions"):
        fixed["captions"] = [{k: v for k, v in c.items() if k in ("s", "e", "t")} for c in caps]
    try:
        sf = to_scenes(fixed, tr, beats, caps, planner=planner, theme=(p.scenes().theme if p.scenes() else "paper"))
    except Exception as e:                                      # pydantic names the field that is wrong
        return {"ok": False, "errors": [str(e)[:600]]}
    errs = validate_scenes(sf, tr, beats)
    if errs:
        return {"ok": False, "errors": errs[:12]}
    p.save_scenes(sf)
    write_json(p.dir / DRAFT, fixed)
    try:
        REPAIRS.record(p, notes, "the director" if strict else "you", "story")
    except Exception:                                                                   # noqa: BLE001  a report, never a reason to lose a story
        pass
    return {"ok": True, "scenes": len(sf.scenes), "warnings": said, **more, "repairs": REPAIRS.small(notes) if strict else REPAIRS.meaning(notes) + REPAIRS.small(notes)}
