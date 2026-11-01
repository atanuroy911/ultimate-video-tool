"""The reel director: a script (already spoken, timed and cut) becomes one picture drawn for each stretch of speech.

    read the script  ->  one look for the whole video  ->  slots from the content  ->  a picture per slot (ComfyUI)  ->  scenes

Pictures come from the server's text-to-picture workflow; when it is not reachable a slot becomes a typographic card with its key word, so the
video still makes sense and the person is told. Every picture is cached by its prompt, so running the plan again redraws only what changed.
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any, Callable, Optional

from ..schema import Backdrop, Element, Scene, ScenesFile, Scrim, Title, validate_scenes
from ..util import now_iso, read_json, write_json
from .reading import Reading, read_script
from .slots import Slot, build_slots
from .style import FIGURE, STYLES, prompt_for

READING = "reel_reading.json"
REPORT = "reel_report.json"
Progress = Callable[[float, str], None]


def _norm(w: str) -> str:
    return re.sub(r"[^\w$%]+", "", w.lower())


def _emphasis_word(slot: Slot, words_by_id: dict) -> Optional[str]:
    """The id of the word the caption should light up: the person's choice in the plan, else the AI's (or the rules') emphasis word from the first sentence that has one."""
    chosen = words_by_id.get(getattr(slot, "emphasis_id", "") or "")
    if chosen is not None and not chosen.cut:
        return chosen.id
    for beat, note in zip(slot.beats, slot.notes):
        if not note or not note.emphasis:
            continue
        want = _norm(note.emphasis)
        for wid in beat.word_ids:
            w = words_by_id.get(wid)
            if w is not None and not w.cut and _norm(w.text) == want:
                return wid
    return None


def _draw_for(slot: Slot) -> str:
    """What to show: the sentence note that has a number or a turn, else the first. Never anything the notes do not say."""
    picked = next((n for n in slot.notes if re.search(r"\d", n.draw) or n.turn), None) or (slot.notes[0] if slot.notes else None)
    return picked.draw if picked and picked.draw else " ".join(b.text for b in slot.beats)[:120]


def reachable(url: str) -> tuple[Any, Optional[str]]:
    """(client, None) when the picture workflow can run on the server, else (None, why)."""
    from ..comfy import ComfyClient, ComfyError, load_workflow

    try:
        client = ComfyClient(url)
        problems = load_workflow("zimage_t2i").problems(client.object_info())
    except ComfyError as e:
        return None, str(e)
    except Exception as e:                                              # noqa: BLE001
        return None, f"{type(e).__name__}: {str(e)[:120]}"
    if problems:
        return None, "; ".join(problems[:3])
    return client, None


def slots_from_plan(plan, beats: list[Any]) -> list[Slot]:
    """The slots the person approved: the same sentences, one slot per moment, with the picture text and the word they chose."""
    from .reading import BeatNote

    by_id = {b.id: b for b in beats}
    out = []
    for m in plan.moments:
        bs = [by_id[s] for s in m.sentence_ids if s in by_id]
        if not bs:
            continue
        word = next((w.text for w in m.words if w.id == m.beat.word_id), "")
        out.append(Slot(id=m.id, beats=bs, card=m.card, turn=m.turn, words=sum(len(b.text.split()) for b in bs), start=bs[0].start, end=bs[-1].end,
                        notes=[BeatNote(beat=bs[0].id, draw=m.draw, emphasis=word, turn=m.turn)], emphasis_id=m.beat.word_id))
    return out


def build_reel_plan(project, *, progress: Progress = lambda f, m: None, use_ai: bool = True, generate: bool = True, comfy_url: Optional[str] = None,
                    cancelled: Callable[[], bool] = lambda: False, plan: Any = None, on_moment: Callable[[str, dict], None] = lambda mid, info: None) -> ScenesFile:
    from .. import paths
    from ..comfy import ComfyError, generate_still, load_workflow

    started = time.time()
    meta = project.meta()
    tr, beats_file = project.transcript(), project.beats()
    beats = beats_file.beats
    if not beats:
        raise RuntimeError("there are no sentences to draw yet")
    words_by_id = tr.by_id()

    progress(0.02, "Reading the script")
    if plan is not None:                                                # the person's approved plan: the same moments, pictures and look, nothing re-decided
        raw = read_json(project.dir / READING, None)
        reading = Reading.model_validate(raw) if raw else read_script(beats, use_ai=use_ai)
        style = plan.idea.style if plan.idea.style in STYLES else "cartoon"
        reading.character = plan.idea.character
        slots = slots_from_plan(plan, beats)
        by_moment = {m.id: m for m in plan.moments}
    else:
        reading = read_script(beats, use_ai=use_ai)
        style = meta.options.reel_style if meta.options.reel_style in STYLES else reading.style if reading.style in STYLES else "cartoon"
        reading.character = reading.character.strip() or FIGURE.get(style, "")
        slots = build_slots(beats, reading)
        by_moment = {}
        write_json(project.dir / READING, reading.model_dump())

    client, why_not = (None, "pictures were switched off")
    if generate:
        url = comfy_url or str((read_json(paths.SETTINGS, {}) or {}).get("comfy_url") or "http://192.168.123.47:8188")
        client, why_not = reachable(url)
    workflow = load_workflow("zimage_t2i") if client is not None else None
    scenes: list[Scene] = []
    report: list[dict] = []
    todo = [s for s in slots if (by_moment[s.id].medium == "made" if s.id in by_moment else True)]      # every slot gets a picture, chapter cards included: one design language for the whole video
    made = 0
    last_media: Optional[str] = None
    for i, slot in enumerate(slots):
        if cancelled():
            raise RuntimeError("cancelled")
        moment = by_moment.get(slot.id)
        medium = moment.medium if moment is not None else "made"
        if moment is not None:
            on_moment(slot.id, {"status": "waiting" if medium != "made" else "making"})
        prompt = prompt_for(_draw_for(slot), style, reading.character)
        record: dict[str, Any] = {"slot": slot.id, "beats": [b.id for b in slot.beats], "seconds": round(slot.seconds, 2), "words": slot.words, "card": slot.card, "prompt": prompt}
        media_id: Optional[str] = None
        if medium == "repeat" and last_media:
            media_id = last_media
            record.update(media=media_id, repeated=True)
            on_moment(slot.id, {"status": "ready", "media": media_id})
        elif medium == "card":
            record.update(card_only=True)
            on_moment(slot.id, {"status": "ready"})
        elif client is not None and workflow is not None:
            seed = int(hashlib.sha1(f"{project.id}:{slot.id}:{prompt}".encode()).hexdigest()[:7], 16)
            try:
                item, rec = generate_still(project, client, workflow, prompt, aspect=meta.aspect, seed=seed, caption=_draw_for(slot)[:80], scene=slot.id, checked=True,
                                           progress=lambda f, m, k=made: progress(0.08 + 0.84 * (k + f) / max(1, len(todo)), f"Drawing picture {k + 1} of {len(todo)}: {m}"),
                                           cancelled=cancelled)
                media_id = item.id
                record.update(media=item.id, drawn_in=rec["seconds_taken"])
                on_moment(slot.id, {"status": "ready", "media": item.id, "seconds_taken": rec["seconds_taken"]})
            except ComfyError as e:
                record["problem"] = str(e)[:200]
                on_moment(slot.id, {"status": "failed", "problem": str(e)[:200]})
                if e.kind == "cancelled":
                    raise RuntimeError("cancelled") from e
            made += 1
        elif medium == "made":
            on_moment(slot.id, {"status": "failed", "problem": why_not or "pictures are switched off"})
        if media_id:
            last_media = media_id
        scenes.append(_scene(project, slot, i, media_id, reading, words_by_id, meta.aspect, end_card=meta.options.end_card.strip() if i == len(slots) - 1 else ""))
        report.append(record)
    sf = ScenesFile(theme=meta.theme, planner="llm" if reading.source == "ai" else "rules", scenes=scenes)
    errs = validate_scenes(sf, tr, beats_file, None)
    if errs:
        raise RuntimeError("the reel plan is invalid: " + "; ".join(errs[:4]))
    write_json(project.dir / REPORT, {"at": now_iso(), "seconds": round(time.time() - started, 1), "kind": reading.kind, "style": style, "style_why": reading.style_why,
                                      "reading": reading.source, "hook": reading.hook.model_dump(), "pictures": made if client else 0,
                                      "server": None if client is None else client.url, "no_pictures_because": why_not if client is None else None,
                                      "warnings": reading.warnings, "slots": report})
    progress(1.0, f"{len(scenes)} scenes")
    return sf


def _scene(project, slot: Slot, index: int, media_id: Optional[str], reading: Reading, words_by_id: dict, aspect: str, end_card: str = "") -> Scene:
    emph = _emphasis_word(slot, words_by_id)
    highlight = [emph] if emph else []
    elements: list[Element] = []
    backdrop = None
    if media_id is not None:
        backdrop = Backdrop(media=media_id, motion="kenburns", scrim=Scrim())      # the caption is a pill with its own background: the picture stays sharp, no panel or blur over it
    if slot.card:                                                       # a step or day label sits on the picture; it never replaces it (if step 1 is full screen, so is step 2)
        elements = [Title(text=slot.card[:40], at_word=slot.beats[0].word_ids[0])]
    elif media_id is None:                                                               # no picture: the key word as a card, so the sentence still has something to look at
        word = next((n.emphasis for n in slot.notes if n and n.emphasis), "") or " ".join(slot.beats[0].text.split()[:3])
        elements = [Title(text=word[:40], at_word=slot.beats[0].word_ids[0])]
    if end_card and not slot.card:                                      # the ask, over the last picture, from the first word of the last sentence; only when the person asked for it
        elements = [Title(text=end_card[:40], at_word=slot.beats[-1].word_ids[0])]
    role = "hook" if index == 0 else ("turn" if slot.turn else None)
    return Scene(id=slot.id, beats=[b.id for b in slot.beats], layout="stack", transition_in="cut", elements=elements, tone=index % 6, archetype="reel", role=role,
                 backdrop=backdrop, caption={"highlight_words": highlight})
