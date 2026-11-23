"""Ask an AI (any provider) to write the Video Script; repair and validate it; fall back to the rule director."""
from __future__ import annotations

import logging

from typing import Callable, Optional

from .. import ai
from ..planner.catalogue import all_icon_names
from ..schema import Beats, ScenesFile, Transcript
from .compile import to_json_schema
from .models import VideoScript
from .prompt import build_prompt
from .rules_stick import emoji_script, rules_script
from .repairs import repairer
from .validate import validate_script


def ai_script(tr: Transcript, beats: Beats, *, kind: str = "stick", language: str = "en", aspect: str = "9:16", audience: str = "", tone: str = "",
              draft: Optional[ScenesFile] = None, hint: str = "", media_ids: Optional[set[str]] = None, provider: Optional[ai.Provider] = None,
              progress: Optional[Callable[[float, str], None]] = None, notes: Optional[list[dict]] = None, look_ahead: str = "") -> VideoScript:
    """The AI's script, repaired. Raises ai.AIUnavailable when no valid script comes back (the caller then uses `rules_script`).
    `notes` (when given) receives what the repair changed in the script that is used (script/repairs.py), so the caller can show it."""
    say = progress or (lambda f, m: None)
    notes = notes if notes is not None else []
    icons = all_icon_names()
    schema = to_json_schema()
    from ..compose.composer import FORMATS

    frame = (FORMATS[aspect]['width'], FORMATS[aspect]['height']) if aspect in FORMATS else None
    base = rules_script(tr, beats, draft, kind=kind, language=language, aspect=aspect).model_dump(by_alias=True, exclude_none=True) if draft else None
    system, user = build_prompt(tr, beats, kind=kind, language=language, audience=audience, tone=tone, aspect=aspect, draft=base, hint=hint, schema=schema,
                                look_ahead=look_ahead)
    say(0.1, "Asking the AI to direct the video")
    # A director that can rewrite (Claude, an API model) is told once what the repair would change in what it wrote (a label cut short, an
    # overlay left out) and gets one try to write it right; after that the repaired script is used, as for the local AI (2026-11-22: "Follow the
    # reference tr..." labels). The local model is never asked twice: its second answer is rarely better and the person waits.
    tries = {"n": 0}
    can_rewrite = not isinstance(provider or ai.current_provider(), ai.OllamaProvider)

    first: dict = {}

    def check(d):
        tries["n"] += 1
        errs = validate_script(d, tr, beats, icons, media_ids, None, frame)
        if not errs and can_rewrite and tries["n"] == 1:
            asks = [f"scene {n.get('scene')}: {n.get('says')}; write it so it fits" for n in notes if n.get("meaning")][:8]
            if asks:
                first.update(data=d, notes=list(notes))                    # usable as it is: kept in case the second try fails
            return asks
        return errs
    try:
        data = ai.complete_json(user, schema, system=system, provider=provider, max_tokens=8000, timeout=600, cache=True, retries=1,
                                repair=repairer(tr, beats, kind, notes, frame), check=check)
    except ai.AIUnavailable:
        if not first:
            raise
        data = first["data"]                                               # the second try failed: the first, repaired script is still a good plan
        notes[:] = first["notes"]
    script = VideoScript.model_validate(data)
    script.kind = kind  # type: ignore[assignment]
    if kind == "emoji" and draft is not None and any(not sc.overlays for sc in script.scenes):          # a scene the model left empty gets the rule director's emoji
        from ..visuals.picker import pick_visuals

        try:
            fill = emoji_script(tr, beats, draft, pick_visuals(tr, beats, None), language=language, aspect=aspect)
            by = {tuple(f.beats): f for f in fill.scenes}
            for sc in script.scenes:
                if not sc.overlays and tuple(sc.beats) in by:
                    sc.overlays = by[tuple(sc.beats)].overlays
        except Exception as _e:  # noqa: BLE001 — overlays of the previous plan could not be carried over
            logging.getLogger(__name__).warning("overlays of the previous plan could not be carried over: %s", _e, exc_info=True)
            pass
    who = (provider or ai.current_provider()).name
    script.planner = "claude" if who in ("anthropic", "claude-cli") else "llm"
    script = revise(script, tr, beats, system, schema, kind, icons, media_ids, provider, say, notes)
    say(1.0, "Script ready")
    return script


REVISE_ROUNDS = 2


def revise(script: VideoScript, tr: Transcript, beats: Beats, system: str, schema: dict, kind: str, icons, media_ids, provider, say, notes: Optional[list[dict]] = None) -> VideoScript:
    """The editor's notes go back to the director: the critic's scene-by-scene issues, at most REVISE_ROUNDS times, and a revision
    is kept only when the critic likes it better. Any failure keeps the script we have (it is already valid)."""
    import json

    from .critic import review

    best, rv = script, review(script, tr, beats)
    for rnd in range(REVISE_ROUNDS):
        if not rv["issues"]:
            break
        say(0.6 + 0.15 * rnd, f"Reviewing the cut: {len(rv['issues'])} note(s) for the director")
        editor_notes = "\n".join(f"- {i['scene']}: {i['problem']}. Fix: {i['fix']}." for i in rv["issues"][:12])
        user = ("This is your Video Script:\n" + json.dumps(best.model_dump(by_alias=True, exclude_none=True), ensure_ascii=False)
                + "\n\nAn experienced editor watched it and wrote these notes:\n" + editor_notes
                + "\n\nReturn the whole script as JSON with these notes fixed. Change only the scenes named in the notes; keep every beat, "
                  "word id and the order of scenes exactly as they are. Do not invent facts that are not in the words.")
        mine: list[dict] = []
        try:
            data = ai.complete_json(user, schema, system=system, provider=provider, max_tokens=8000, timeout=600, cache=True, retries=1,
                                    repair=repairer(tr, beats, kind, mine),
                                    check=lambda d: validate_script(d, tr, beats, icons, media_ids))
            cand = VideoScript.model_validate(data)
            cand.kind, cand.planner = best.kind, best.planner
        except Exception as _e:  # noqa: BLE001 — an improved script did not validate; the best earlier one is kept
            logging.getLogger(__name__).warning("an improved script did not validate; the best earlier one is kept: %s", _e, exc_info=True)
            break
        rv2 = review(cand, tr, beats)
        if rv2["score"] <= rv["score"]:
            break
        best, rv = cand, rv2
        if notes is not None:
            notes[:] = mine                                                         # the revision is the script now: its repairs are the ones to show
    return best


def plan_script(tr: Transcript, beats: Beats, *, draft: ScenesFile, use_ai: bool = True, **kw) -> tuple[VideoScript, str]:
    """(script, how it was made): the AI's script when it works, otherwise the rule director's; either way the enricher then fills
    any still stretch the critic finds (vt/script/critic.py)."""
    from .critic import enrich

    cartoon = kw.get("kind") == "cartoon"
    if cartoon:                                                  # the cartoon style is directed like the stick style, then drawn with illustrated characters
        kw["kind"] = "stick"
    script, how = _plan_script(tr, beats, draft=draft, use_ai=use_ai, **kw)
    script, n = enrich(script, tr, beats)
    from .animals import animalize

    script, _ = animalize(script)                                # an animal is never played by a person
    if cartoon:
        from ..art.toon import toonify

        script = toonify(script)
    return script, (f"{how} + {n} added" if n else how)


def _plan_script(tr: Transcript, beats: Beats, *, draft: ScenesFile, use_ai: bool = True, **kw) -> tuple[VideoScript, str]:
    ctx_kw = {k: kw.pop(k) for k in ("ctx",) if k in kw}
    look = kw.pop("look_ahead", "")
    if use_ai:
        try:
            return ai_script(tr, beats, draft=draft, look_ahead=look, **kw), "ai"
        except ai.AIUnavailable as e:
            why = str(e)
    else:
        why = "AI not used"
    kw.update(ctx_kw)
    if kw.get("kind") == "emoji":
        from ..visuals.picker import pick_visuals

        try:
            picks = pick_visuals(tr, beats, None)
        except Exception as _e:  # noqa: BLE001 — the picture dictionary could not be used; scenes show words
            logging.getLogger(__name__).warning("the picture dictionary could not be used; scenes show words: %s", _e, exc_info=True)
            picks = {}
        from .rules_stick import emoji_script

        return emoji_script(tr, beats, draft, picks, language=kw.get("language", "en"), aspect=kw.get("aspect", "9:16")), f"rules ({why})"
    kw.pop("media_ids", None)
    kw.pop("hint", None)
    kw.pop("provider", None)
    kw.pop("progress", None)
    kw.pop("audience", None)
    kw.pop("tone", None)
    ctx = kw.pop("ctx", None)
    return rules_script(tr, beats, draft, kind=kw.get("kind", "stick"), language=kw.get("language", "en"), aspect=kw.get("aspect", "9:16"), ctx=ctx), f"rules ({why})"
