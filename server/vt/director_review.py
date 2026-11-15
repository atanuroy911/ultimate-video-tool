"""The director looks at its own cut: a frame of every scene goes back to the AI that planned the video, and what it decides is applied.

The AI sees what the viewer would see and can change anything about what is on screen: move, resize or remove an element, change its fields, move a
character, move a story item. Nothing here judges the frame; code only keeps a change the plan's schema accepts. A director working from the person's
computer does the same through MCP (preview_frames, update_scene). Every prompt and answer is in Details, AI conversations (vt/ai/talk.py).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from PIL import Image

from .compose import FORMATS
from .house_rules import prompt as notes
from .project import Project
from .schema import Scene, validate_scenes
from .util import file_hash, now_iso, read_json, write_json

REPORT = "director_review.json"
ROUNDS = 1                                   # one look and one revision (owner decision 9): what is still wrong after it is listed for the person, who fixes it in the editor
MAX_SCENES = 12

SCHEMA = {
    "type": "object",
    "properties": {
        "people": {"type": "array", "items": {"type": "string"}},
        "what_i_see": {"type": "string"},
        "looks_right": {"type": "boolean"},
        "changes": {"type": "array", "items": {"type": "object", "properties": {
            "element": {"type": "integer", "minimum": 0},
            "remove": {"type": "boolean"},
            "item": {"type": "integer", "minimum": 0},
            "set": {"type": "object"},
        }, "required": ["element"]}},
    },
    "required": ["people", "what_i_see", "looks_right", "changes"],
}

SYSTEM = """You are the director of this video, looking at one frame of your own cut, exactly as the viewer will see it. Judge it the way a viewer would: is the \
frame clear, does it show what the narrator is saying, can every word be read, is anyone's face covered, is it attractive enough to keep watching?

If it is right, say so and change nothing. If not, change whatever you need. Each change names an element by its number and either removes it or sets fields on it:
- x and y place an element: the centre of the element, as a fraction of the frame, 0 to 1 from the left and from the top. scale resizes it (1 is normal), rotation turns it. On a cartoon, move a character with its own x and y (feet) in `cast`, not by moving the whole set; `arrive` says when it appears (0 is already there), and entrance "none" removes an element's fade.
- Any other field the element shows below can be changed too, for example a shorter text.
- On a cartoon, set `cast` to the whole list again with new x values to move the characters across the set.
- On a story element, add `item` (its number) and set that item's fields; its x and y are in design units, 0-540 across and 0-960 down.
To take an element away, give it "remove": true; never set a field to "none".
You cannot add an element here, and an element keeps its `type`. To show something better in an element's place, change its fields (another emoji or icon from the choices, a shorter text): do not remove it first. Remove an element only when the frame is better without it. The elements are what the viewer watches: a scene with nothing left but the caption has lost its picture, so never remove everything a scene shows. Change only elements you can see in this frame; one you cannot see belongs to another moment of the scene and is not wrong for being absent here.
The captions always sit near the bottom of the frame.

Look before you decide. In `people`, write one line for each person or character: can you see their eyes, nose and mouth, or does something sit in front of them, and what? In `what_i_see`, say what sits on top of what, and what a viewer reads first. Only then answer `looks_right` and give your changes. Return only the JSON.

""" + notes("plan")


def _frame_times(comp_dir: Path, sf) -> list[tuple[str, float]]:
    """One moment per scene, once what it shows has arrived. A scene laid out as several pages (compose/composer.py) is looked at on the page that shows
    the most: a second look at the same scene would be judged on a frame taken before the first look changed it, and its changes would land on top."""
    data = read_json(comp_dir / "data.json", {}) or {}
    planned = {s.id for s in sf.scenes}
    best: dict[str, tuple[int, float]] = {}                                     # scene -> (how many elements its page shows, the moment)
    for s in data.get("scenes", []):
        sid = s.get("src") or s.get("id")
        if sid not in planned or s.get("end", 0) <= s.get("start", 0):
            continue
        shown = s.get("elements", [])
        arrived = max([float(e.get("at", s["start"])) for e in shown] or [s["start"]])
        at = round(min(s["end"] - 0.15, max(arrived + 0.8, (s["start"] + s["end"]) / 2)), 3)
        if sid not in best or len(shown) > best[sid][0]:
            best[sid] = (len(shown), at)
    return sorted(((sid, at) for sid, (_, at) in best.items()), key=lambda x: x[1])[:MAX_SCENES]


def problems(facts: Optional[list[str]]) -> list[str]:
    """The measured facts that are about something wrong. 'Nothing covers any character' and 'Empty across the frame' are information for the director, not trouble."""
    return [f for f in facts or [] if f != "Nothing covers any character." and not f.startswith("Empty across the frame")]


def _left(measured: Optional[tuple[list[tuple[str, float]], dict]]) -> list[dict]:
    """What is still wrong in the cut as it now stands, scene by scene: the Quality check lists it for the person (code never fixes it behind the director's back)."""
    times, facts = measured or ([], {})
    return [{"scene": sid, "at": at, "facts": bad} for sid, at in times if (bad := problems(facts.get(at)))]


def _png(path: Path, side: int = 768) -> bytes:
    from .ai.vision import _png as png

    return png(Image.open(path), side)


def _scene_prompt(sc: Scene, words: str, facts: Optional[list[str]] = None) -> str:
    from .visuals.choices import prompt as visual_choices

    els = [{"element": i, "type": e.type, **e.model_dump(exclude_none=True, exclude_defaults=True, exclude={"edited", "id", "type"})} for i, e in enumerate(sc.elements)]
    measured = "Measured on this exact frame (exact numbers; your eyes can miss these):\n" + "\n".join("- " + f for f in facts) + "\nFor each problem fact, give one change to the element it names. Change only what those facts name; leave correct parts alone. This is your one revision.\n\n" if facts else ""
    choices = visual_choices([(sc.id, words)])
    return f'{measured}The narrator is saying: "{words}"\n\nThe elements of this scene, by number (each appears at its `at_word`; one that is not in this frame is shown at another moment of the scene):\n{json.dumps(els, ensure_ascii=False, indent=1)}' + ("\n\n" + choices if choices else "")


def apply_changes(sc: Scene, changes: list[dict]) -> tuple[Scene, list[str]]:
    """The director's changes, one at a time: one the schema refuses is reported and the others stay."""
    current, skipped, gone = sc, [], set()
    replaced = {ch.get("element") for ch in changes or [] if isinstance(ch, dict) and ch.get("set") and not ch.get("remove")}
    for ch in changes or []:
        i = ch.get("element")
        if not isinstance(i, int) or not 0 <= i < len(sc.elements):
            skipped.append(f"there is no element {i}")
            continue
        if ch.get("remove"):
            if i in replaced:                               # "remove it, then set it" in one answer means put this in its place: the new fields decide, and
                continue                                    # a replacement the schema refuses leaves the element as it was, not a hole
            gone.add(i)
            continue
        fields = ch.get("set") or {}
        if not fields:
            continue
        d = current.model_dump(exclude_none=True)
        el = d["elements"][i]
        if ch.get("item") is not None:
            items = el.get("items") or []
            if not 0 <= ch["item"] < len(items):
                skipped.append(f"element {i} has no item {ch['item']}")
                continue
            items[ch["item"]].update(fields)
        else:
            el.update(fields)
        try:
            current = Scene.model_validate(d)
        except Exception as e:
            if hasattr(e, "errors"):
                details = "; ".join(f"{'.'.join(map(str, error['loc']))}: {error['msg']}" for error in e.errors()[:3])
            else:
                details = str(e)
            skipped.append(f"element {i}: {details[:400]}")
    if gone and len(gone) >= len(sc.elements):             # a revision is a change to the picture, not its removal: a scene with nothing left but the caption is an invalid
        skipped.append("removing every element would leave the scene with only its caption, so nothing was removed; change the elements instead")
        gone = set()                                        # result, refused like any other and reported, and the director's other changes to the scene stand
    if gone:
        d = current.model_dump(exclude_none=True)
        d["elements"] = [e for i, e in enumerate(d["elements"]) if i not in gone]
        current = Scene.model_validate(d)
    return current, skipped


def review(p: Project, progress: Callable[[float, str], None] = lambda f, m: None, compose: Optional[Callable[[Project], Any]] = None, provider=None) -> dict:
    """The director looks at the whole cut (ROUNDS: one look and one revision). Returns the report it also writes to director_review.json, with what is left to look at."""
    from .ai.providers import AIUnavailable, complete_json
    from .pipeline import compose_all
    from .render.hyperframes import frame_facts, snapshot

    compose = compose or compose_all
    report = read_json(p.dir / REPORT, None)
    if report and report.get("scenes_hash") == file_hash(p.scenes_path):       # this exact plan was already looked at
        return report
    tag = FORMATS[p.meta().aspect]["tag"]
    tr, beats = p.transcript(), p.beats()
    by_beat = {b.id: b.text for b in beats.beats}
    report = {"at": now_iso(), "rounds": [], "changed": 0}
    measured, stale = None, False                                               # the latest measurement of the cut, and whether the cut changed since
    for rnd in range(ROUNDS):
        sf = p.scenes()
        times = _frame_times(p.comp_dir / tag, sf)
        if not times:
            break
        files = snapshot(p.comp_dir / tag, p.dir / "snapshots" / "review", [t for _, t in times])
        if len(files) != len(times):
            raise RuntimeError(f"{len(files)} frames came back for {len(times)} scenes")
        try:
            facts = frame_facts(p.comp_dir / tag, [t for _, t in times])
        except Exception as e:                                                  # noqa: BLE001  the director still has its eyes
            facts, report["facts_error"] = {}, str(e)[:200]
        measured, stale = (times, facts), False
        round_changed, seen = 0, []
        scenes = {s.id: s for s in sf.scenes}
        for n, ((sid, at), frame) in enumerate(zip(times, files)):
            progress((rnd + n / len(times)) / ROUNDS, f"The director is looking at scene {n + 1} of {len(times)}")
            sc = scenes[sid]
            words = " ".join(by_beat.get(b, "") for b in sc.beats)
            try:
                answer = complete_json(_scene_prompt(sc, words, facts.get(at)), SCHEMA, [_png(frame)], system=SYSTEM, provider=provider, cache=False, retries=1, max_tokens=1500, timeout=240, temperature=0.2)
            except AIUnavailable as e:
                seen.append({"scene": sid, "error": str(e)[:200]})
                continue
            new, skipped = apply_changes(sc, [] if answer.get("looks_right") else answer.get("changes"))
            changed = new != sc
            if changed:
                scenes[sid] = new
                round_changed += 1
            seen.append({"scene": sid, "people": answer.get("people", []), "saw": answer.get("what_i_see", ""), "measured": facts.get(at, []), "changed": changed, "skipped": skipped})
        report["rounds"].append(seen)
        if not round_changed:
            break
        kept = sf                                                               # a change the plan refuses costs only its own scene
        round_changed = 0
        for row in seen:
            sid = row.get("scene")
            if not row.get("changed"):
                continue
            trial = kept.model_copy(update={"scenes": [scenes[s.id] if s.id == sid else s for s in kept.scenes]})
            errs = validate_scenes(trial, tr, beats)
            if errs:
                row["changed"], row["refused"] = False, "; ".join(errs[:3])
            else:
                kept, round_changed = trial, round_changed + 1
        if not round_changed:
            break
        p.save_scenes(kept)
        report["changed"] += round_changed
        compose(p)
        stale = True
    if stale:                                                                   # the last round changed the cut: measure what it looks like now
        try:
            times = _frame_times(p.comp_dir / tag, p.scenes())
            measured = (times, frame_facts(p.comp_dir / tag, [t for _, t in times])) if times else None
        except Exception as e:                                                  # noqa: BLE001
            measured, report["facts_error"] = None, str(e)[:200]
    report["left"] = _left(measured)
    report["scenes_hash"] = file_hash(p.scenes_path)
    write_json(p.dir / REPORT, report)
    return report


def remeasure(p: Project) -> None:
    """The cut was changed after the director looked (the viewer-test revision): measure the cut as it now stands, page facts only, so the Quality check lists what is
    really left for the person. Nobody is asked and nothing is changed; the director's own record of what it saw stays as it was."""
    from .render.hyperframes import frame_facts

    report = read_json(p.dir / REPORT, None)
    if not report or report.get("error"):
        return                                                                  # no look was made: there is nothing to bring up to date
    tag = FORMATS[p.meta().aspect]["tag"]
    times = _frame_times(p.comp_dir / tag, p.scenes())
    try:
        measured = (times, frame_facts(p.comp_dir / tag, [t for _, t in times])) if times else None
        report.pop("facts_error", None)
        report["left"] = _left(measured)
    except Exception as e:                                                      # noqa: BLE001
        report["facts_error"] = str(e)[:200]
    report["scenes_hash"] = file_hash(p.scenes_path)
    report["remeasured"] = now_iso()
    write_json(p.dir / REPORT, report)
