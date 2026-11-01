"""The rule director for Video Scripts (no AI): turns the rule planner's scenes into a script, and for kind "stick" adds a cast, a set and actions.

question -> think; number -> hold a sign; definition -> point at the board; first scene -> walk in and wave; last scene -> celebrate or wave.
"""
from __future__ import annotations

import re

from ..schema import Beats, ScenesFile, Transcript
from . import catalogue as C
from .compile import script_from_scenes
from .models import VideoScript

SET_WORDS = [("space", r"\b(space|planet|star|galaxy|moon|rocket|orbit)\b"), ("lab", r"\b(lab|experiment|science|chemical|atom|cell)\b"),
             ("market", r"\b(market|shop|price|buy|sell|cost|money|dollars?|taka)\b"), ("office", r"\b(office|company|business|work|team|meeting|boss)\b"),
             ("nature", r"\b(tree|river|forest|nature|animal|plant|water|sun)\b"), ("home", r"\b(home|house|family|kitchen|mother|father)\b"),
             ("street", r"\b(street|road|city|car|walk)\b"), ("classroom", r"\b(learn|lesson|school|teach|student|class|today we)\b")]


def pick_set(text: str) -> str:
    t = text.lower()
    best, n = "classroom", 0
    for name, pat in SET_WORDS:
        k = len(re.findall(pat, t))
        if k > n:
            best, n = name, k
    return best


def emoji_script(tr: Transcript, beats: Beats, sf: ScenesFile, picks: dict, *, language: str = "en", aspect: str = "9:16", title: str = "") -> VideoScript:
    """Emoji video: every scene is told with big colour emoji (one to three per sentence) and the stressed word in type; numbers and charts are not used.
    `picks` is the visual picker's answer per beat (the stressed word and its sticker), so the choice of picture is the usual meaning search."""
    from ..visuals import emoji as emo

    script = script_from_scenes(sf, language, aspect, title)
    script.planner = "rules"
    script.kind = "emoji"  # type: ignore[assignment]
    beats_by = {b.id: b for b in beats.beats}
    words = tr.by_id()
    prev: set[str] = set()                                # the emoji of the previous scene: never shown again right after
    for i, sc in enumerate(script.scenes):
        els: list[dict] = []
        here: set[str] = set()
        for bid in sc.beats:
            pk = picks.get(bid)
            if pk is None:
                continue
            cands = [(pk.word_id, pk.text, pk.sticker)] + [(x["word_id"], x["text"], x.get("sticker")) for x in (pk.extras or [])]
            for wid, text, st in cands:
                if len(els) >= 3 or wid not in words:
                    continue
                key = emo.emoji_key(st) if st else None
                if key and key not in prev and key not in here:
                    els.append({"type": "sticker", "emoji": key, "label": text.strip(" ,.?!।")[:24], "at_word": wid})
                    here.add(key)
        if not els:                                    # nothing picturable: the stressed word of the sentence in big type
            b = beats_by[sc.beats[0]]
            ws = [words[w] for w in b.word_ids if w in words]
            if ws:
                best = max(ws, key=lambda w: len(w.text.strip(" ,.?!।")))
                els.append({"type": "keyword", "text": best.text.strip(" ,.?!।")[:30], "style": "stamp", "at_word": best.id})
        prev = here
        els.sort(key=lambda e: words[e["at_word"]].start)
        sc.overlays = els[:3]
        sc.layout = "hero" if len(els) == 1 else "stack"
        sc.archetype = "emoji"
        sc.transition_in = ["cut", "zoom", "slide_up", "fade", "slide_left"][i % 5] if i else "cut"
        sc.tone = i % 4
        if els:
            sc.highlight_words = [els[0]["at_word"]]
    return script


def rules_script(tr: Transcript, beats: Beats, sf: ScenesFile, *, kind: str = "stick", language: str = "en", aspect: str = "9:16", title: str = "", ctx=None) -> VideoScript:
    """Stick mode: the story director (vt/script/story.py: cast, places, events from the words); the old one-figure rotation only if that fails."""
    if kind == "stick":
        try:
            from .story import story_script
            from .validate import validate_script

            out = story_script(tr, beats, sf, kind=kind, language=language, aspect=aspect, title=title, ctx=ctx)
            if not validate_script(out.model_dump(by_alias=True), tr, beats):
                return out
        except Exception:                                                  # never lose a video to the director: fall back to the plain one below
            pass
    script = script_from_scenes(sf, language, aspect, title)
    script.planner = "rules"
    script.kind = kind  # type: ignore[assignment]
    if kind != "stick":
        return script
    words = tr.by_id()
    beats_by = {b.id: b for b in beats.beats}
    kind_set = pick_set(" ".join(w.text for w in tr.words))
    for sc in script.scenes:                          # the stick figure IS the character: no second (cartoon) character, no speaker card of the discussion profile
        sc.overlays = [o for o in sc.overlays if o.get("type") not in ("cartoon", "speaker_card")]
        stickers = [o for o in sc.overlays if o.get("type") == "sticker"]
        for extra in stickers[2:]:                    # a tall stack of emoji would run into the figure's head in the square shape
            sc.overlays.remove(extra)
    script.cast = [{"id": "maya", "role": "teacher", "name": "Maya", "style": {"accessory": "glasses"}}]          # type: ignore[list-item]
    script.sets = [{"id": "main", "kind": kind_set, "props": []}]                                                 # type: ignore[list-item]
    from .models import Action, Character, SetDef

    script.cast = [Character.model_validate(c) if isinstance(c, dict) else c for c in script.cast]
    script.sets = [SetDef.model_validate(c) if isinstance(c, dict) else c for c in script.sets]
    props = C.SETS[kind_set]
    board = "board" if "board" in props else props[0]
    rot = ["explain", "nod", "explain", "shrug"]
    n = len(script.scenes)
    for i, sc in enumerate(script.scenes):
        sc.set = "main"
        sc.camera.shot = "medium" if i % 3 else "close"
        sc.camera.move = ["push_in", "none", "pan_right", "none", "pull_out"][i % 5]            # type: ignore[assignment]
        acts: list = []
        for k, bid in enumerate(sc.beats):
            b = beats_by[bid]
            ids = [w for w in b.word_ids if w in words]
            first = ids[0]
            ov = [o for o in sc.overlays if o.get("at_word") in ids]
            anchor = ov[0]["at_word"] if ov else first
            if i == 0 and k == 0:
                acts.append(Action(at_word=first, who="maya", do="walk_in", **{"from": "left"}, to=0.45))
                acts.append(Action(at_word=ids[min(2, len(ids) - 1)] if len(ids) > 2 else anchor, who="maya", do="wave"))
            elif "?" in b.text:
                acts.append(Action(at_word=first, who="maya", do="think"))
            elif re.search(r"\d", b.text) and ov:
                num = re.search(r"\d[\d,.]*\s?%?", b.text).group(0).strip()                    # type: ignore[union-attr]
                acts.append(Action(at_word=anchor, who="maya", do="hold_sign", bubble=num[:20]))
            elif any(o.get("type") == "definition" for o in ov):
                acts.append(Action(at_word=anchor, who="maya", do="point", target=board))
            elif i == n - 1 and k == len(sc.beats) - 1:
                acts.append(Action(at_word=first, who="maya", do="celebrate" if n > 2 else "wave"))
            else:
                acts.append(Action(at_word=anchor, who="maya", do=rot[(i + k) % len(rot)]))        # type: ignore[arg-type]
            if len(ids) > 4 and (words[ids[-1]].end - words[acts[-1].at_word].start) > 3.0:      # a long sentence: something changes again
                acts.append(Action(at_word=ids[len(ids) // 2 + 1], who="maya", do="nod"))
        acts.sort(key=lambda a: words[a.at_word].start)
        sc.actions = acts[:24]
    return script
