"""Pure functions that edit a ScenesFile (split / merge / delete / move boundary / patch).
Elements stay attached to the scene that contains their anchor word; ids stay unique."""
from __future__ import annotations

from typing import Any, Optional

from .schema import Beats, Scene, ScenesFile, Transcript


class OpError(ValueError):
    pass


def _find(sf: ScenesFile, sid: str) -> int:
    for i, s in enumerate(sf.scenes):
        if s.id == sid:
            return i
    raise OpError(f"scene '{sid}' not found")


def _word_to_beat(beats: Beats) -> dict[str, str]:
    return {w: b.id for b in beats.beats for w in b.word_ids}


def _next_id(sf: ScenesFile) -> str:
    n = 1
    used = {s.id for s in sf.scenes}
    while f"s{n}" in used:
        n += 1
    return f"s{n}"


def _redistribute(sf: ScenesFile, beats: Beats) -> ScenesFile:
    """Make sure every element/highlight lives in the scene whose beats contain its anchor word."""
    w2b = _word_to_beat(beats)
    owner: dict[str, str] = {}
    for s in sf.scenes:
        for b in s.beats:
            owner[b] = s.id
    pool_el: dict[str, list] = {s.id: [] for s in sf.scenes}
    pool_hl: dict[str, list] = {s.id: [] for s in sf.scenes}
    for s in sf.scenes:
        for el in s.elements:
            tgt = owner.get(w2b.get(el.at_word, ""), s.id)
            pool_el[tgt].append(el)
        for wid in s.caption.highlight_words:
            tgt = owner.get(w2b.get(wid, ""), s.id)
            pool_hl[tgt].append(wid)
    scenes = []
    for s in sf.scenes:
        scenes.append(s.model_copy(update={"elements": pool_el[s.id], "caption": s.caption.model_copy(update={"highlight_words": pool_hl[s.id]})}))
    return _restick(sf.model_copy(update={"scenes": scenes}), beats)


def _join_stick(keep: Scene, other: Scene) -> dict | None:
    """The stick data of `keep` with the actions of `other` added (two scenes becoming one)."""
    if not keep.stick and not other.stick:
        return None
    base = keep.stick or other.stick
    acts = list((keep.stick or {}).get("actions", [])) + list((other.stick or {}).get("actions", []))
    return {**base, "actions": sorted(acts, key=lambda a: a.get("start", 0))}


def _restick(sf: ScenesFile, beats: Beats) -> ScenesFile:
    """Stick-figure actions and sound cues follow their anchor word into whichever scene now contains it. A scene with no stick data of its own
    takes the set, camera and cast of the nearest scene that has some, so a split or merge never loses the characters."""
    have = [s for s in sf.scenes if s.stick]
    if not have:
        return sf
    w2b = _word_to_beat(beats)
    owner = {b: s.id for s in sf.scenes for b in s.beats}
    acts: dict[str, list] = {s.id: [] for s in sf.scenes}
    sfx: dict[str, list] = {s.id: [] for s in sf.scenes}
    for s in sf.scenes:
        for a in (s.stick or {}).get("actions", []):
            acts[owner.get(w2b.get(a.get("at_word", ""), ""), s.id)].append(a)
        for c in s.sfx:
            sfx[owner.get(w2b.get(c.get("at_word", ""), ""), s.id)].append(c)
    out = []
    for i, s in enumerate(sf.scenes):
        base = s.stick or next((x.stick for x in sf.scenes[i::-1] if x.stick), None) or have[0].stick
        out.append(s.model_copy(update={"stick": {**base, "actions": sorted(acts[s.id], key=lambda a: a.get("start", 0))}, "sfx": sfx[s.id],
                                        "archetype": s.archetype or "stick"}))
    return sf.model_copy(update={"scenes": out})


def split_scene(sf: ScenesFile, beats: Beats, sid: str, at_beat: str) -> ScenesFile:
    i = _find(sf, sid)
    s = sf.scenes[i]
    if at_beat not in s.beats or s.beats[0] == at_beat:
        raise OpError("choose a beat inside the scene, other than its first, to split at")
    k = s.beats.index(at_beat)
    first = s.model_copy(update={"beats": s.beats[:k]})
    # The second half keeps the look of the scene it was cut from: its picture (a reel or a speaker scene would otherwise go blank) and its colour tone.
    # With the same picture behind both halves the change is a plain cut: a fade between two identical pictures only flickers.
    second = Scene(id=_next_id(sf), beats=s.beats[k:], layout=s.layout if s.backdrop else "stack", transition_in="cut" if s.backdrop else "fade", elements=[],
                   backdrop=s.backdrop.model_copy() if s.backdrop else None, tone=s.tone)
    scenes = sf.scenes[:i] + [first, second] + sf.scenes[i + 1:]
    return _redistribute(sf.model_copy(update={"scenes": scenes}), beats)


def merge_with_next(sf: ScenesFile, beats: Beats, sid: str) -> ScenesFile:
    i = _find(sf, sid)
    if i + 1 >= len(sf.scenes):
        raise OpError("this is the last scene")
    a, b = sf.scenes[i], sf.scenes[i + 1]
    merged = a.model_copy(update={"beats": a.beats + b.beats, "elements": list(a.elements) + list(b.elements),
                                  "caption": a.caption.model_copy(update={"highlight_words": a.caption.highlight_words + b.caption.highlight_words}),
                                  "sfx": list(a.sfx) + list(b.sfx), "stick": _join_stick(a, b)})
    return _restick(sf.model_copy(update={"scenes": sf.scenes[:i] + [merged] + sf.scenes[i + 2:]}), beats)


def delete_scene(sf: ScenesFile, beats: Beats, sid: str) -> ScenesFile:
    """Remove a scene's elements; its beats join the previous scene (or the next one if it is first)."""
    i = _find(sf, sid)
    if len(sf.scenes) == 1:
        raise OpError("a video needs at least one scene")
    s = sf.scenes[i]
    if i > 0:
        prev = sf.scenes[i - 1]
        prev = prev.model_copy(update={"beats": prev.beats + s.beats, "sfx": list(prev.sfx) + list(s.sfx), "stick": _join_stick(prev, s)})
        scenes = sf.scenes[: i - 1] + [prev] + sf.scenes[i + 1:]
    else:
        nxt = sf.scenes[1]
        nxt = nxt.model_copy(update={"beats": s.beats + nxt.beats, "transition_in": "cut", "sfx": list(s.sfx) + list(nxt.sfx), "stick": _join_stick(nxt, s)})
        scenes = [nxt] + sf.scenes[2:]
    return _restick(sf.model_copy(update={"scenes": scenes}), beats)


def move_boundary(sf: ScenesFile, beats: Beats, sid: str, new_first_beat_of_next: str) -> ScenesFile:
    """Move the boundary between scene `sid` and the following scene so that the next scene starts at the given beat."""
    i = _find(sf, sid)
    if i + 1 >= len(sf.scenes):
        raise OpError("this is the last scene")
    a, b = sf.scenes[i], sf.scenes[i + 1]
    pool = a.beats + b.beats
    if new_first_beat_of_next not in pool or pool[0] == new_first_beat_of_next:
        raise OpError("each scene must keep at least one beat")
    k = pool.index(new_first_beat_of_next)
    na = a.model_copy(update={"beats": pool[:k]})
    nb = b.model_copy(update={"beats": pool[k:]})
    return _redistribute(sf.model_copy(update={"scenes": sf.scenes[:i] + [na, nb] + sf.scenes[i + 2:]}), beats)


def boundary_choices(sf: ScenesFile, beats: Beats, duration: float) -> dict[str, list[dict]]:
    """Legal shared-edge destinations, in the exact clock used by preview/export."""
    from .compose.composer import scene_timing

    original = scene_timing(sf, beats, duration)
    by_id = {b.id: b for b in beats.beats}
    result = {}
    for i, a in enumerate(sf.scenes[:-1]):
        b = sf.scenes[i + 1]
        choices = []
        for bid in (a.beats + b.beats)[1:]:
            try:
                changed = move_boundary(sf, beats, a.id, bid)
                timing = scene_timing(changed, beats, duration)
            except OpError:
                continue
            at = timing[i]["end"]
            if at - original[i]["start"] < 0.399 or original[i + 1]["end"] - at < 0.399:
                continue
            if any(t != original[j] for j, t in enumerate(timing) if j not in (i, i + 1)):
                continue
            choices.append({"at_beat": bid, "time": at, "text": by_id[bid].text, "current": bid == b.beats[0]})
        result[a.id] = choices
    return result


def patch_scene(sf: ScenesFile, sid: str, patch: dict[str, Any], tr: Optional[Transcript] = None, beats: Optional[Beats] = None) -> ScenesFile:
    """Change anything about a scene except where it sits in the narration (validated by pydantic). Beats and the exact start have their own
    operations (split / merge / move), because they must stay in order across scenes. A `stick` patch changes the stick block, it does not replace it
    (the cast, set and camera stay unless named), and actions written as in the script (at_word, no times) are timed here when `tr` is given."""
    i = _find(sf, sid)
    allowed = {"layout", "transition_in", "transition_effect", "camera_move", "elements", "caption", "backdrop", "tone", "archetype", "role", "stick", "sfx"}
    patch = dict(patch)
    data = sf.scenes[i].model_dump()
    if "camera" in patch and data.get("stick"):          # the Video Script writes a scene's camera at the scene level; on the timeline it lives with the stick figures
        data["stick"]["camera"] = {**(data["stick"].get("camera") or {}), **(patch.pop("camera") or {})}
    if isinstance(patch.get("stick"), dict) and data.get("stick"):
        block = {**data["stick"], **patch["stick"]}
        acts = block.get("actions")
        if isinstance(acts, list) and any(isinstance(a, dict) and ("start" not in a or "end" not in a) for a in acts):
            if tr is None or beats is None:
                raise OpError("these actions have no times yet; add them with the action operations, which time them from their words")
            scene_end = max((b.end for b in beats.beats if b.id in sf.scenes[i].beats), default=0.0)
            block["actions"] = _requeue([dict(a) for a in acts], tr, scene_end)
        patch["stick"] = block
    bad = set(patch) - allowed
    if bad:
        raise OpError(f"cannot change {sorted(bad)} here: a scene's beats and start move with split, merge and move; its actions and cast have their own "
                      f"operations; a scene patch may set {sorted(allowed)}")
    data.update(patch)
    try:
        new = Scene.model_validate(data)
    except Exception as e:  # pydantic ValidationError
        raise OpError(str(e)) from e
    return sf.model_copy(update={"scenes": sf.scenes[:i] + [new] + sf.scenes[i + 1:]})


def reorder_elements(sf: ScenesFile, sid: str, order: list[int]) -> ScenesFile:
    i = _find(sf, sid)
    els = sf.scenes[i].elements
    if sorted(order) != list(range(len(els))):
        raise OpError("order must be a permutation of element indexes")
    return patch_scene(sf, sid, {"elements": [els[k].model_dump() for k in order]})


# --------------------------------------------------------------------------- stick figures
def _stick_scene(sf: ScenesFile, sid: str) -> tuple[int, Scene]:
    i = _find(sf, sid)
    if not sf.scenes[i].stick:
        raise OpError(f"scene '{sid}' has no stick figures")
    return i, sf.scenes[i]


def _requeue(actions: list[dict], tr: Transcript, scene_end: float) -> list[dict]:
    """Times in seconds from the anchor words; one character does one thing at a time (a later action waits for the earlier one)."""
    from .script.catalogue import verb_seconds

    words = tr.by_id()
    busy: dict[str, float] = {}
    # Queue by playback time but retain stable indices: the editor selects actions by index.
    out = list(actions)
    ordered = sorted(enumerate(actions), key=lambda item: item[1].get("start", 0) if item[1].get("_timed") else words[item[1]["at_word"]].start if item[1].get("at_word") in words else item[1].get("start", 0))
    for index, a in ordered:
        if a.get("_timed"):
            busy[a["who"]] = max(busy.get(a["who"], 0), a["end"])
            continue
        start = max(words[a["at_word"]].start if a.get("at_word") in words else a.get("start", 0.0), busy.get(a["who"], 0.0))
        end = min(start + verb_seconds(a["do"]), max(start + 0.2, scene_end))
        busy[a["who"]] = end
        out[index] = {**a, "start": round(start, 3), "end": round(end, 3)}
    return out


def edit_action(sf: ScenesFile, tr: Transcript, beats: Beats, sid: str, index: int, patch: dict[str, Any] | None, delete: bool = False) -> ScenesFile:
    """Re-time (at_word) or change (bubble, target, emotion ...) one stick-figure action, or delete it."""
    from .script.models import Action

    i, sc = _stick_scene(sf, sid)
    acts = [dict(a) for a in sc.stick.get("actions", [])]
    if not 0 <= index < len(acts):
        raise OpError("no such action")
    if delete:
        acts.pop(index)
    else:
        cur = {**acts[index], **(patch or {})}
        if "start" in (patch or {}) or "end" in (patch or {}):
            from math import isfinite
            if not all(isfinite(cur.get(k, -1)) for k in ("start", "end")) or not 0 <= cur["start"] < cur["end"]:
                raise OpError("Action end must be after its start")
            cur["_timed"] = True
        elif "at_word" in (patch or {}):
            cur.pop("_timed", None)
        words = {w for bb in beats.beats if bb.id in sc.beats for w in bb.word_ids}
        if cur.get("at_word") not in words and sc.start is None:
            raise OpError("an action must be anchored to a word inside its scene")
        try:
            Action.model_validate({k: v for k, v in cur.items() if k not in ("start", "end", "_timed")})
        except Exception as e:
            raise OpError(str(e)[:200]) from e
        acts[index] = cur
    end = max((b.end for b in beats.beats if b.id in sc.beats), default=0.0)
    st = {**sc.stick, "actions": _requeue(acts, tr, end)}
    return sf.model_copy(update={"scenes": sf.scenes[:i] + [sc.model_copy(update={"stick": st})] + sf.scenes[i + 1:]})


def add_action(sf: ScenesFile, tr: Transcript, beats: Beats, sid: str, action: dict[str, Any]) -> ScenesFile:
    """Add a new stick-figure animation action to a scene."""
    from .script.models import Action

    i, sc = _stick_scene(sf, sid)
    acts = [dict(a) for a in sc.stick.get("actions", [])]
    words = {w for bb in beats.beats if bb.id in sc.beats for w in bb.word_ids}
    if action.get("at_word") not in words:
        raise OpError("an action must be anchored to a word inside its scene")
    try:
        Action.model_validate({k: v for k, v in action.items() if k not in ("start", "end")})
    except Exception as e:
        raise OpError(str(e)[:200]) from e
    acts.append(dict(action))
    end = max((b.end for b in beats.beats if b.id in sc.beats), default=0.0)
    st = {**sc.stick, "actions": _requeue(acts, tr, end)}
    return sf.model_copy(update={"scenes": sf.scenes[:i] + [sc.model_copy(update={"stick": st})] + sf.scenes[i + 1:]})


def edit_cast(sf: ScenesFile, cast_id: str, patch: dict[str, Any]) -> ScenesFile:
    """Change a character in every scene that has it: name, role, who plays it (kind: a stick figure "person", an illustrated
    "toon" with its art, an "emoji" animal with its code) and its look (colour, head, accessory, height, hair, shirt, skin)."""
    from .script.models import Character

    found = False
    scenes = []
    for sc in sf.scenes:
        if not sc.stick:
            scenes.append(sc)
            continue
        cast = []
        for c in sc.stick.get("cast", []):
            if c["id"] == cast_id:
                found = True
                new = {**c, **{k: v for k, v in patch.items() if k in ("name", "role", "kind", "emoji", "art")}}
                if "style" in patch:
                    new["style"] = {**c.get("style", {}), **patch["style"]}
                try:
                    new = Character.model_validate(new).model_dump()
                except Exception as e:
                    raise OpError(str(e)[:200]) from e
                cast.append(new)
            else:
                cast.append(c)
        scenes.append(sc.model_copy(update={"stick": {**sc.stick, "cast": cast}}))
    if not found:
        raise OpError(f"no character '{cast_id}'")
    return sf.model_copy(update={"scenes": scenes})
