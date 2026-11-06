"""Cartoon 1 gets the story engine's best trick: the thing a sentence names appears on the word that names it.

The zip's lexicons (engine_rules.MOTIFS / EMOTIONS and its number readers) find a spoken number, money, an idea, a lie, a heart, a clock, days or
a feeling in a scene's words; each becomes a small story-engine item (a counting number, an icon, a beating heart, a clock, calendar days, a
thought cloud, impact lines, sparkles) drawn over the cartoon at the exact word (vt-story.js overlay). At most two per scene, in the free band
above the characters; all of them are ordinary story items, so the Studio edits them like any Cartoon 2 item.
"""
from __future__ import annotations

import re

from . import engine_rules as R

SLOTS = [(420, 220), (130, 230)]          # design units: above the characters, left and right of the bubble area
MAX_EXTRAS = 2


def _trigger(words: list, roots: list[str]):
    for w in words:
        low = w.text.lower().strip(".,!?।“”\"'")
        if any(low.startswith(r.strip().lower()) for r in roots if len(r.strip()) >= 2):
            return w
    return None


def extras_for(words: list, language: str = "", shown: frozenset = frozenset()) -> list[dict]:
    """Story items for one scene's words (each word has .text and .start in video seconds). `shown` is the types of the other things already on
    top of the scene: the extras never repeat them (a number card already shows the number) and never crowd a scene that has its own overlays."""
    if not words or shown - {"cartoon"}:
        return []
    text = " ".join(w.text for w in words)
    plain = text.replace("{", "").replace("}", "")
    motifs, emotions = dict(R.MOTIFS), dict(R.EMOTIONS)
    found: list[dict] = []
    latin = (language or ("bn" if re.search("[ঀ-৿]", plain) else "en")) != "bn"
    num = R.spoken_number(plain)
    if num:
        w = next((w for w in words if any(ch.isdigit() for ch in w.text)), None) or words[len(words) // 2]
        try:
            value = float(num.replace(",", "."))
            decimals = len(num.split(".")[1]) if "." in num else 0
            found.append({"type": "counter", "from": 0, "to": value, "decimals": min(decimals, 2), "latin": latin, "size": 76, "at": round(w.start, 2),
                          "dur": 0.9, "enter": "pop"})
        except ValueError:
            pass
    for key in [k for k in R.hits(plain, R.MOTIFS)]:
        w = _trigger(words, motifs[key])
        if w is None:
            continue
        at = round(w.start, 2)
        if key == "money":
            found.append({"type": "icon", "name": "money", "at": at, "loop": "float", "s": 1.1})
        elif key == "idea":
            found.append({"type": "icon", "name": "bulb", "at": at, "loop": "glow", "s": 1.1})
        elif key == "lie":
            found.append({"type": "icon", "name": "cross", "at": at})
        elif key == "heart":
            beats = [round(x.start, 2) for x in words if x.start >= w.start][:4]
            found.append({"type": "heart", "beats": beats, "at": at, "s": 1.2})
        elif key == "clock":
            found.append({"type": "clock", "hour": R.clock_hour(plain) or 10, "minute": 0, "r": 70, "at": at})
        elif key == "calendar":
            n = R.count_before(plain, ["দিন", "মাস", "বছর", "day", "month", "year", "week"])
            if n:
                found.append({"type": "calendar", "count": min(n, 6), "cols": 6, "interval": 0.25, "at": at, "s": 0.8})
        elif key == "think":
            found.append({"type": "thought", "text": "?", "w": 120, "h": 90, "size": 34, "at": at})
    for key in R.hits(plain, R.EMOTIONS):
        w = _trigger(words, emotions[key])
        if w is None:
            continue
        at = round(w.start, 2)
        if key == "shock":
            found.append({"type": "lines", "at": at, "until": round(at + 1.2, 2)})
        elif key == "smile":
            found.append({"type": "particles", "kind": "sparkle", "count": 14, "at": at, "x": 270, "y": 360, "fixed": True})
        elif key == "scared":
            found.append({"type": "icon", "name": "exclaim", "at": at, "loop": "shake", "loopAmp": 0.5})
    clock = next((i for i in found if i["type"] == "clock"), None)
    if clock is not None:                                   # "ten o'clock" is a clock, not a counting ten
        found = [i for i in found if not (i["type"] == "counter" and i["to"] == clock["hour"])]
    out = []
    for item, (x, y) in zip(sorted(found, key=lambda i: i["at"])[:MAX_EXTRAS], SLOTS):
        item = dict(item)
        if not item.pop("fixed", False):
            item.setdefault("x", x)
            item.setdefault("y", y)
        out.append(item)
    return out
