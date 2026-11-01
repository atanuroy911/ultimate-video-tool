"""Visual heartbeat: no scene sits still for long.

A scene whose pictures all arrive early (or that has only one) shows the same thing for many seconds, and viewers leave. Where a gap between two visible changes is longer than the
target (2.5 s tall, 2.6 s wide; the rule is 3 s and the retention scorecard measures against 3 in both), one more thing is added at a word that is spoken in the middle of that gap:
  1. a picture for that word, when the picture dictionary has one for it (a sticker or a line icon);
  2. else the word itself in type, when it carries meaning (terms.is_content_word: not "the", "your" or "I've"); like the kinetic-type reels, a typed word
     is a real change on screen and can never show the wrong meaning;
  3. else nothing: an unrelated picture would be worse than a still one.
It never touches scenes that already move (the speaker's own picture, stick figures, charts that animate inside) and never makes a scene hold more than four elements.
"""
from __future__ import annotations

from typing import Optional

from ..schema import Beats, Icon, Keyword, ScenesFile, Sticker, Transcript

TARGET = {"tall": 2.5, "wide": 2.6}          # the hard rule is a visible change at least every 3 s in every shape; aiming a little under it leaves room for where words fall
STATIC = {"keyword", "title", "sticker", "icon", "icon_row", "tag", "value_card", "big_number", "price_tag", "quote"}      # element types that do not move once they have appeared
MAX_ELEMENTS = 4
EDGE = 0.9                                                                                   # a new thing never appears closer than this to the end of the scene


def _span(sc, bmap) -> Optional[tuple[float, float]]:
    bs = [bmap[b] for b in sc.beats if b in bmap]
    return (min(b.start for b in bs), max(b.end for b in bs)) if bs else None


def still_scenes(sf: ScenesFile, tr: Transcript, beats: Beats, aspect: str, slack: float = 0.5) -> list[str]:
    """Ids of scenes that are still too still after the heartbeat (a gap longer than the target plus `slack`) and hold only static elements: where there was no real word to show."""
    limit = TARGET["tall" if aspect == "9:16" else "wide"] + slack
    words = {w.id: w for w in tr.kept()}
    bmap = {b.id: b for b in beats.beats}
    out = []
    for sc in sf.scenes:
        span = _span(sc, bmap)
        if span is None or sc.stick or sc.backdrop is not None or any(getattr(e, "type", "") not in STATIC for e in sc.elements):
            continue
        times = sorted([span[0]] + [words[e.at_word].start for e in sc.elements if e.at_word in words] + [span[1]])
        if max((y - x for x, y in zip(times, times[1:])), default=0.0) > limit:
            out.append(sc.id)
    return out


def add_heartbeats(sf: ScenesFile, tr: Transcript, beats: Beats, aspect: str, context=None) -> int:
    """Fill long stills in the plan (in place). Returns how many elements were added."""
    from .. import context as CX
    from ..visuals import emoji as emo
    from ..visuals import terms as T
    from ..visuals.lexicon import Lexicon

    limit = TARGET["tall" if aspect == "9:16" else "wide"]
    words = {w.id: w for w in tr.kept()}
    bmap = {b.id: b for b in beats.beats}
    lex = Lexicon.get()
    topics = T.topic_counts(w.text for w in words.values())
    added = 0
    for sc in sf.scenes:
        span = _span(sc, bmap)
        if span is None or sc.stick or (sc.backdrop is not None) or any(getattr(e, "type", "") not in STATIC for e in sc.elements):
            continue
        t0, t1 = span
        seq = [words[i] for bid in sc.beats if bid in bmap for i in bmap[bid].word_ids if i in words]
        used = {getattr(e, "emoji", None) or getattr(e, "name", None) for e in sc.elements}
        for _ in range(MAX_ELEMENTS):
            if len(sc.elements) >= MAX_ELEMENTS:
                break
            times = sorted([t0] + [words[e.at_word].start for e in sc.elements if e.at_word in words] + [t1])
            gap, a, b = max(((y - x, x, y) for x, y in zip(times, times[1:])), default=(0.0, 0.0, 0.0))
            if gap <= limit:
                break
            mid = (a + b) / 2
            windows = [[w for w in seq if a + 0.8 <= w.start <= b - EDGE]]     # anywhere in the gap; the meaning counts most, then nearness to its middle
            made = None
            for cands in windows:
                for w in sorted(cands, key=lambda w: -(T.score(w.text, topics) - 0.15 * abs(w.start - mid))):
                    label = w.text.strip(" ,.;:!?।\"'")[:24]
                    strong = CX.term_ok(w.text, topics)                     # a real topic word: a picture is safe
                    m = lex.lookup(w.text) if strong else None
                    if m and m.usable() and m.sticker and emo.emoji_key(m.sticker) and m.sticker not in used:
                        made, key = Sticker(at_word=w.id, emoji=emo.emoji_key(m.sticker), label=label), m.sticker
                    elif m and m.usable() and m.line and m.line not in used:
                        made, key = Icon(at_word=w.id, name=m.line, label=label), m.line
                    elif (strong or T.is_content_word(w.text)) and label.lower() not in used:
                        made, key = Keyword(at_word=w.id, text=label, style="underline"), label.lower()   # the spoken word in type: never the wrong meaning
                    if made:
                        used.add(key)
                        break
                if made:
                    break
            if not made:
                break
            sc.elements.append(made)
            added += 1
    return added
