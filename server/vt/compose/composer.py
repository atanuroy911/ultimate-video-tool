"""Turns scenes.json + transcript + theme into a self-contained HTML composition.

The same folder is loaded by the Studio preview (iframe) and rendered by HyperFrames, so what you see is what you export.
Word ids are resolved to seconds here and nowhere else.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Optional

from .. import paths
from ..cues import build_cues
from ..visuals import emoji as emo
from ..visuals import icons as icon_sets
from ..schema import Beats, Cuts, ScenesFile, Theme, Transcript, Word, has_transform
from ..util import read_json, write_json

FORMATS = {
    "9:16": {"width": 1080, "height": 1920, "fps": 30, "aspect": "9:16", "tag": "9x16"},
    "1:1": {"width": 1080, "height": 1080, "fps": 30, "aspect": "1:1", "tag": "1x1"},
    "16:9": {"width": 1920, "height": 1080, "fps": 30, "aspect": "16:9", "tag": "16x9"},
}

SENTENCE_END = tuple("।.?!")
SOFT_BREAK = tuple(",;:—–")
SCENE_LEAD = 0.10  # a new scene starts slightly before its first spoken word


# --------------------------------------------------------------------------- captions


def _balanced_split(seg: list[Word], n_lines: int) -> list[list[Word]]:
    """Split a run of words into n_lines pieces of similar character length (never empty)."""
    total = sum(len(w.text) + 1 for w in seg)
    out: list[list[Word]] = []
    cur: list[Word] = []
    acc = 0.0
    for j, w in enumerate(seg):
        cur.append(w)
        acc += len(w.text) + 1
        lines_left = n_lines - len(out) - 1
        words_left = len(seg) - j - 1
        boundary = total * (len(out) + 1) / n_lines
        if lines_left > 0 and words_left >= lines_left and acc >= boundary - (len(w.text) + 1) / 2:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


READ_CPS = 17.0   # characters a second a viewer can still read (subtitling research ceiling; 12 cps is the comfortable standard)


CHUNK_MAX = 4               # words a caption line holds at most: 2 to 3 reads best, 4 only to keep a phrase whole (vt/craft rules: captions)
CAPTION_LAG = 0.06          # a line appears just after its first word is heard: early captions read as broken sync, late ones are invisible
from ..stages.words import ABBREV  # noqa: E402

FUNCTION_WORDS = set("""a an the and or but nor so of to in on at for with by from as than into onto about over under your my his her its our their
this that these those is are was were be been am will would can could should to if then""".split())


def _bare(w: Word) -> str:
    return w.text.strip(" ,.;:!?।\"'").lower()


def _is_numberish(w: Word) -> bool:
    from ..planner.rules import NUM_WORDS

    t = _bare(w)
    return t in NUM_WORDS or t.replace(",", "").replace(".", "").isdigit() or t in ("hundred", "thousand", "million", "billion", "one")


def _line_cost(ws: list[Word], cap: int) -> float:
    n = len(ws)
    if n > cap:
        return 1e9
    cost = (n - 2.5) ** 2                                           # two or three words read best
    last = ws[-1].text.rstrip()
    if _bare(ws[-1]) in FUNCTION_WORDS and not last.endswith((",", ";", ":")):
        cost += 6.0                                                 # "your brain washes away the": the phrase is torn
    if last.endswith((",", ";", ":")):
        cost -= 1.0                                                 # a clause ends here: the natural place to break
    if n == 1 and not last.endswith((".", "!", "?", "।")):
        cost += 3.0                                                 # a lone "While" on screen
    dur = max(0.2, ws[-1].end - ws[0].start + 0.15)
    if n >= 3 and n / dur > 4.4:
        cost += 4.0                                                 # too fast to read
    return cost


def _dark_art(key: str) -> bool:
    """A sticker drawn mostly in near-black (a movie camera, a black cat): it vanishes on a dark background."""
    import re as _re

    from ..visuals import emoji as emo

    svg = emo.svg(key) or ""
    parts = _re.findall(r'fill="#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})"[^>]*?\sd="([^"]*)"', svg)        # each fill, weighted by its path's size (a rough area)
    if not parts:
        return False
    def lum(h: str) -> float:
        h = h if len(h) == 6 else "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    total = sum(len(d) for _, d in parts) or 1
    return sum(lum(h) * len(d) for h, d in parts) / total < 0.3


def _bg_dark(theme) -> bool:
    h = (theme.color.bg or "#ffffff").lstrip("#")
    if len(h) != 6:
        return False
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.2


def _as_line(d: dict) -> None:
    """Sticker -> line icon of the same word (picture dictionary), in place; a keyword just loses its emoji."""
    if d["type"] == "keyword":
        d.pop("emoji", None)
        return
    label = (d.get("label") or "").strip()
    try:
        from ..visuals.lexicon import Lexicon

        m = Lexicon.get().lookup(label) if label else None
    except Exception:                                                                   # noqa: BLE001
        m = None
    if m and m.line:
        at = d.get("at")
        d.clear()
        d.update({"type": "icon", "name": m.line, "label": label, "at": at})
    elif label:
        at = d.get("at")
        d.clear()
        d.update({"type": "keyword", "text": label, "style": "underline", "at": at})


def _tidy_chunks(chunks: list[list[Word]], cap: int) -> list[list[Word]]:
    """Captions read as phrases. The lines between hard breaks (a sentence end, a pause) are split again where it costs least: no line
    ends on "the" or "your", no word stands alone, two or three words a line, never more than `cap` (vt/craft rules: captions)."""
    runs: list[list[Word]] = []
    for c in chunks:
        last = runs[-1][-1].text.strip() if runs else ""
        title = last.endswith(".") and last.rstrip(".").lower() in ABBREV           # "Mr." | "Rich": one name, one line
        if runs and (title or not last.endswith((".", "!", "?", "।"))) and c and c[0].start - runs[-1][-1].end < (1.2 if title else 0.45):
            runs[-1].extend(c)
        elif c:
            runs.append(list(c))
    out: list[list[Word]] = []
    for run in runs:
        n = len(run)
        best = [0.0] + [1e18] * n                                   # best[i]: cheapest way to set the first i words
        back = [0] * (n + 1)
        for i in range(1, n + 1):
            glue = 5.0 if i < n and _is_numberish(run[i - 1]) and not run[i - 1].text.rstrip().endswith((",", ".")) else 0.0   # "seventy | eight", "seven | days"
            if i < n and run[i - 1].text.strip().rstrip(".").lower() in ABBREV and run[i - 1].text.strip().endswith("."):
                glue += 9.0                                                                                              # never "Mr. | Rich"
            for j in range(max(0, i - cap), i):
                c = best[j] + _line_cost(run[j:i], cap) + glue
                if c < best[i]:
                    best[i], back[i] = c, j
        cuts, i = [], n
        while i > 0:
            cuts.append((back[i], i))
            i = back[i]
        out.extend(run[a:b] for a, b in reversed(cuts))
    return out


def build_caption_chunks(words: list[Word], words_per_line: int, max_chars: int, highlight_ids: set[str]) -> list[dict]:
    """Group spoken words into on-screen caption lines.

    A new line starts at a sentence end, after a long pause, or when the line is full.
    Each line stays on screen until the next one starts (or shortly after the last word).
    """
    # 1) split at natural breaks: sentence end, long pause, or a comma after at least two words
    segments: list[list[Word]] = []
    cur: list[Word] = []
    for i, w in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else None
        cur.append(w)
        text = w.text.rstrip()
        gap = (nxt.start - w.end) if nxt else 99
        if nxt is None or text.endswith(SENTENCE_END) or gap > 0.45 or (text.endswith(SOFT_BREAK) and len(cur) >= 2):
            segments.append(cur)
            cur = []
    if cur:
        segments.append(cur)

    # 2) split over-long segments into evenly sized lines (no orphan words)
    chunks: list[list[Word]] = []
    for seg in segments:
        total = sum(len(w.text) + 1 for w in seg)
        n_lines = max(-(-len(seg) // max(1, words_per_line)), -(-total // max(1, max_chars)), 1)
        if n_lines == 1:
            chunks.append(seg)
            continue
        chunks.extend(_balanced_split(seg, n_lines))

    # 3) refine pacing: reading speed is measured in characters a second, the measure subtitling research settled on
    # (Díaz-Cintas & Remael's six-second rule = 12 cps; eye-tracking studies put the comfortable ceiling near 17 cps / 180 wpm).
    # A chunk of >= 3 words that goes by faster than READ_CPS is split into shorter lines so each stays long enough to read.
    refined: list[list[Word]] = []
    for i, ch in enumerate(chunks):
        if len(ch) >= 3:
            nxt_s = chunks[i + 1][0].start - 0.04 if i + 1 < len(chunks) else None
            start = max(0.0, ch[0].start - 0.04)
            dur = (nxt_s - start) if nxt_s is not None else (ch[-1].end - ch[0].start + 0.35)
            chars = sum(len(w.text) for w in ch) + len(ch) - 1
            if dur > 0 and (len(ch) / dur > 4.4 or chars / dur > READ_CPS):
                refined.extend(_balanced_split(ch, max(2, -(-len(ch) // 2))))
                continue
        refined.append(ch)
    chunks = _tidy_chunks(refined, min(words_per_line, CHUNK_MAX)) if words_per_line > 1 else refined

    out: list[dict] = []
    for ci, ch in enumerate(chunks):
        start = max(0.0, ch[0].start + CAPTION_LAG)
        nxt_start = chunks[ci + 1][0].start + CAPTION_LAG if ci + 1 < len(chunks) else None
        end = ch[-1].end + 0.35
        if nxt_start is not None:
            end = min(end, nxt_start) if nxt_start - ch[-1].end < 0.7 else end
            end = min(end, nxt_start)
            # give as much read time as available up to nxt_start
            min_dur = min(nxt_start - start, max(0.4, len(ch) / 4.4))
            end = max(end, start + min_dur)
        else:
            end = max(end, start + max(0.4, len(ch) / 4.4))
        out.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "words": [{"id": w.id, "text": w.text, "start": round(w.start, 3), "end": round(w.end, 3), "hl": w.id in highlight_ids} for w in ch],
        })
    return out


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(chunks: list[dict]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        text = " ".join(w["text"] for w in c["words"])
        lines.append(f"{i}\n{_srt_time(c['start'])} --> {_srt_time(c['end'])}\n{text}\n")
    return "\n".join(lines)


# --------------------------------------------------------------------------- resolve


def scene_starts(sf: ScenesFile, beats: Beats) -> list[float]:
    """Start time of every scene: slightly before its first spoken word, never closer than 0.4 s to the previous scene."""
    beat_by_id = {b.id: b for b in beats.beats}
    starts: list[float] = []
    for i, sc in enumerate(sf.scenes):
        s = 0.0 if i == 0 else sc.start if sc.start is not None else beat_by_id[sc.beats[0]].start - SCENE_LEAD
        if i > 0:
            s = max(s, starts[-1] + (0.001 if sc.start is not None else 0.4))
        starts.append(round(max(0.0, s), 3))
    return starts


def scene_timing(sf: ScenesFile, beats: Beats, duration: float) -> list[dict]:
    starts = scene_starts(sf, beats)
    return [{"id": sc.id, "start": starts[i], "end": starts[i + 1] if i + 1 < len(starts) else round(duration, 3)}
            for i, sc in enumerate(sf.scenes)]


def _nested_assets(d: dict, used_icons: set, used_stickers: set) -> None:
    """Pictures that live inside list-like elements (feature cards, cartoon props): normalise emoji keys, remember what to inline."""
    for it in d.get("items", []) if d["type"] == "feature_grid" else []:
        if it.get("emoji"):
            key = emo.emoji_key(it["emoji"])
            if key:
                it["emoji"] = key
                used_stickers.add(key)
            else:
                it.pop("emoji")
        if it.get("icon"):
            used_icons.add(it["icon"])
    if d["type"] == "pictogram":
        key = emo.emoji_key(d.get("emoji") or "1f9d1") or "1f9d1"
        d["emoji"] = key
        used_stickers.add(key)
    if d["type"] == "cartoon":
        keys = [emo.emoji_key(p) for p in d.get("props", [])]
        d["props"] = [k for k in keys if k]
        used_stickers.update(d["props"])


_BUILTIN_PROPS: Optional[set] = None


def _prop_art(st: dict) -> dict:
    """Colour pictures for props the stick engine does not draw itself (a wallet, a ball, a rocket...): found by name in the emoji library."""
    global _BUILTIN_PROPS
    if _BUILTIN_PROPS is None:
        import re as _re

        js = (paths.RUNTIME / "vt-stick.js").read_text(encoding="utf-8")
        m = _re.search(r"const DRAW = [{](.*?)\n  [}];", js, _re.S)
        _BUILTIN_PROPS = set(_re.findall(r"^\s{4}(\w+):", m.group(1), _re.M)) if m else set()
    names = set((st.get("set") or {}).get("props") or [])
    for a in st.get("actions", []):
        names.update(x for x in (a.get("target"), a.get("prop")) if x)
    names -= _BUILTIN_PROPS | {"viewer", "camera"} | {c["id"] for c in st.get("cast", [])}
    out = {}
    for c in st.get("cast", []):                                                                     # an actor drawn from a sticker (a fox, a coin, a bulb): keyed "actor:<id>"
        if c.get("kind") == "emoji":
            key = emo.emoji_key(c.get("emoji") or "") if c.get("emoji") else None
            if not key:
                try:
                    from ..visuals.search import search

                    hits = search((c.get("name") or c["id"]).replace("_", " "), "sticker", 1)
                    key = hits[0]["id"].split(":", 1)[-1] if hits else None
                except Exception:
                    key = None
            svg = emo.svg(key) if key else None
            if svg:
                out["actor:" + c["id"]] = svg
    from ..art import toon

    chars, places = toon.characters(), toon.scenes()
    for c in st.get("cast", []):                                                                     # an illustrated character: its rigged drawing
        if c.get("kind") == "toon" and c.get("art") in chars:
            out["actor:" + c["id"]] = chars[c["art"]].read_text(encoding="utf-8")
    art = (st.get("set") or {}).get("art")
    if art and art.replace("_", "-") in places:
        out["scene:" + art] = places[art.replace("_", "-")].read_text(encoding="utf-8")
    for n in sorted(names):
        try:
            from ..visuals.search import search

            hits = search(n.replace("_", " "), "sticker", 1)
            key = hits[0]["id"].split(":", 1)[-1] if hits else None
            svg = emo.svg(key) if key else None
            if svg:
                out[n] = svg
        except Exception:
            continue
    return out


AI_PLANNERS = ("llm", "claude", "assistant")        # plans an AI directed: the local AI, Claude, Codex. A scene of such a plan is marked `directed` and nothing of it is hidden, shrunk or dropped by code


def _keep_clear_of_people(scene_d: dict, sc, media: dict, aspect: str) -> None:
    """Nothing is placed on a person. A scene with a picture of people gets its elements into the largest empty rectangle outside the captions' zone (a `stage` override for the
    renderer); when there is no room worth using, the elements are dropped for this shape and the picture stays clear. (vt/people.py)"""
    from .. import people as PE

    if scene_d.get("edited") or any(e.get("free") for e in scene_d.get("elements", [])):
        return  # Manual content/placement must survive every aspect ratio.

    bd = sc.backdrop
    m = media.get(bd.media) if bd else None
    if not bd or not m or not scene_d["elements"] or not m.get("w") or not m.get("h"):
        return
    if bd.person:
        grid = PE.unpack(bd.person)
    elif m.get("faces"):
        grid = PE.to_grid(PE.face_body_mask(m["faces"][0], 90, 160))             # a photo with a face and no stored mask: the body shape from the face
    else:
        return
    if not grid.any():
        return
    out_aspect = FORMATS[aspect]["width"] / FORMATS[aspect]["height"]
    occ = PE.to_output(grid, m["w"] / m["h"], out_aspect, bd.fx, bd.fy, bd.motion if m.get("kind") == "video" or bd.motion != "none" else "none")
    tall = out_aspect < 1
    # the captions live in the lower part (9:16: above the platform buttons' zone, lower 30 %; wide pictures: the lower 20 %): never use it
    rect = PE.largest_free_rect(occ, 0.04, 0.66 if tall else 0.78, 0.30 if tall else 0.22, 0.12 if tall else 0.20)
    if rect is None:
        if scene_d.get("directed"):                      # an AI put these elements here: they stay, and the facts say there is no room beside the person (the director moves them)
            scene_d["no_room_beside_person"] = True
            return
        scene_d["elements"] = []
        scene_d["cleared_for_person"] = True
        return
    x, y, w, h = rect
    pad = 0.012
    scene_d["stage"] = [round(x + pad, 4), round(y + pad, 4), round(max(0.05, w - 2 * pad), 4), round(max(0.05, h - 2 * pad), 4)]
    scene_d["layout"] = "stack" if tall or w < 0.45 else "stack"


PAGE_MAX = {"9:16": 3, "1:1": 3, "16:9": 4}      # pictures one screen holds at full size
TOGETHER = 0.35                                    # pictures arriving this close together (a sticker and its label) stay on one page
PAGEABLE = {"sticker", "keyword", "tag", "icon", "quote", "question", "title"}   # separate pictures; a card, an arrow, a row of coins, a chart or a list is a build-up that accumulates on one screen
MIN_SHOT = 1.2                                     # seconds a page stays up before the next picture gets a page of its own (no flicker)


def paginate(scenes: list[dict], aspect: str) -> list[dict]:
    """A scene lays out every element at once, even those that appear later, so five pictures in one scene all sit at 40 % size
    with the space of the unseen ones left empty. An editor cuts to a new shot instead: a scene with more elements than a screen
    holds becomes pages, each starting when its first picture arrives, each laid out alone at full size. Stick-figure scenes and
    scenes over a picture or the speaker (backdrop) keep their single layout: their elements are placed on a stage of their own."""
    out = []
    cap = PAGE_MAX.get(aspect, 3)
    for sc in scenes:
        for i, e in enumerate(sc.get("elements", [])):
            e.setdefault("_i", i)                       # the element's place in the plan: the editor picks by (scene, index) even after paging
        if sc.get("stick") and len(sc.get("elements", [])) > 1:
            out += _one_at_a_time(sc, cap)
            continue
        if any(e.get("_placed") for e in sc.get("elements", [])):     # a hand-placed picture keeps the scene's one layout; a re-timed one still gets its own shot
            out.append(sc)
            continue
        els = sorted(sc.get("elements", []), key=lambda e: e.get("at", sc["start"]))
        parts = sum(e.get("type") not in PAGEABLE for e in els)
        heading = parts and any(e.get("type") == "title" for e in els)             # a title over a list or a chart is its heading
        if len(els) > 1 and not sc.get("backdrop") and parts >= 2 and not heading:
            k = next(i for i, e in enumerate(els) if e.get("type") not in PAGEABLE)
            if not k and len(els) >= 4:                                 # a long build-up: two shots, cut at its biggest pause
                gap, k = max((els[i]["at"] - els[i - 1]["at"], i) for i in range(2, len(els) - 1))
                k = k if gap >= MIN_SHOT else 0
            if k and els[k]["at"] - els[0]["at"] >= 0.9:               # separate pictures (or the first half) before a build-up: their own shot first
                a = {**sc, "elements": els[:k], "end": round(els[k]["at"], 3)}
                b = {**sc, "id": f"{sc['id']}p2", "src": sc.get("src", sc["id"]), "start": round(els[k]["at"], 3), "elements": els[k:], "cont": True,
                     "transition_in": "cut" if sc.get("stick") else "fade"}
                if sc.get("sfx"):
                    a["sfx"] = [c for c in sc["sfx"] if c["t"] < b["start"]]
                    b["sfx"] = [c for c in sc["sfx"] if c["t"] >= b["start"]]
                out += [a] + paginate([b], aspect)                     # the rest may still be a long build-up: the same rules again
                continue
        if len(els) <= 1 or sc.get("backdrop") or parts >= 2 or heading:      # connected parts: a build-up on one screen
            out.append(sc)
            continue
        bundles: list[list[dict]] = []                   # what arrives together
        for e in els:
            if bundles and e["at"] - bundles[-1][-1]["at"] <= TOGETHER:
                bundles[-1].append(e)
            else:
                bundles.append([e])
        groups: list[list[dict]] = []                    # a new shot for every new picture, unless the current one has only just started
        for b in bundles:
            if groups and len(groups[-1]) + len(b) <= cap and b[0]["at"] - groups[-1][0]["at"] < MIN_SHOT:
                groups[-1].extend(b)
            else:
                groups.append(list(b))
        if len(groups) == 1:
            out.append(sc)
            continue
        for i, g in enumerate(groups):
            t0 = sc["start"] if i == 0 else g[0]["at"]
            t1 = groups[i + 1][0]["at"] if i + 1 < len(groups) else sc["end"]
            page = {**sc, "id": sc["id"] if i == 0 else f"{sc['id']}p{i + 1}", "src": sc.get("src", sc["id"]), "start": round(t0, 3), "end": round(t1, 3), "elements": g}
            if i:
                page["transition_in"] = "cut" if sc.get("stick") else "fade"     # stick figures: the same drawing continues, only the labels change
                page["cont"] = True
                g[0]["at"] = page["start"]
            if sc.get("sfx"):
                page["sfx"] = [c for c in sc["sfx"] if t0 <= c["t"] < t1]
            out.append(page)
    return out


def _one_at_a_time(sc: dict, cap: int) -> list[dict]:
    """A cartoon shows one picture at a time over its drawing: the next picture takes over, the last one leaves (owner, 2026-11-08:
    pictures piled up, a clock drawn over a shop sign). A picture shares the frame only when it arrives with another (a sticker and
    its label), when it is part of a build-up (a list, a row of coins), or when the director or the person kept the earlier one on
    screen past this one's arrival (an until_word, an end time): then they were meant to be seen together. A placed picture
    (x, y, scale) is paged like any other, so moving one never changes when the others show."""
    els = sorted(sc["elements"], key=lambda e: e.get("at", sc["start"]))
    groups: list[list[dict]] = []
    for e in els:
        if groups:
            g = groups[-1]
            arrives_with = e["at"] - g[-1]["at"] <= TOGETHER
            build_up = e.get("type") not in PAGEABLE and g[-1].get("type") not in PAGEABLE
            held = any(x.get("_held") and x.get("until") is not None and x["until"] - e["at"] > 0.3 for x in g)
            if len(g) < cap and (arrives_with or build_up or held):
                g.append(e)
                continue
        groups.append([e])
    if len(groups) == 1:
        return [sc]
    pages = []
    for i, g in enumerate(groups):
        t0 = sc["start"] if i == 0 else g[0]["at"]
        t1 = groups[i + 1][0]["at"] if i + 1 < len(groups) else sc["end"]
        page = {**sc, "id": sc["id"] if i == 0 else f"{sc['id']}p{i + 1}", "src": sc.get("src", sc["id"]), "start": round(t0, 3), "end": round(t1, 3), "elements": g}
        for e in g:
            if e.get("free") and not e.get("_held") and e.get("until", t1) > t1:
                e["until"] = round(t1, 3)               # a placed picture is drawn on its own layer: it leaves with its shot, not with the scene
        if i:
            page["transition_in"] = "cut"               # the same drawing continues: only the picture changes
            page["cont"] = True
        if sc.get("sfx"):
            page["sfx"] = [c for c in sc["sfx"] if t0 <= c["t"] < t1]
        pages.append(page)
    return pages


HOLD_MIN, HOLD_MAX = 1.5, 3.0                    # pacing.dwell: the main thing for 1.5 to 3 s, then the picture behind it again
# full-frame text cards: in a video with pictures they say their line and give the frame back to a picture
CARD_TYPES = {"title", "big_number", "value_card", "quote", "question", "cta", "definition", "keyword", "tag", "stat_row", "equation", "price_tag"}


def _hand_cards_back(scenes: list[dict]) -> None:
    """A card scene marked `_card_out` borrows the nearest picture (the one before it, else the one after), which fades in at that time
    while the card's parts leave. Only in a video that has pictures: a video made of cards keeps its cards."""
    pictured = [i for i, s in enumerate(scenes) if s.get("backdrop") and not str(s["backdrop"].get("media", "")).startswith("shot:")]   # a shot is its own scene's, never borrowed
    for i, s in enumerate(scenes):
        out = s.pop("_card_out", None)
        if out is None or not pictured:
            continue
        j = max((k for k in pictured if k < i), default=None)
        j = j if j is not None else min(k for k in pictured if k > i)
        bd = dict(scenes[j]["backdrop"])
        bd.pop("offset", None)                        # an A-roll's place in the recording belongs to its own scene
        bd["from"] = out
        s["backdrop"] = bd
        for e in s["elements"]:
            e["until"] = out


def resolve_composition(sf: ScenesFile, tr: Transcript, beats: Beats, theme: Theme, aspect: str,
                        duration: float, icons: Optional[dict[str, str]] = None, media: Optional[dict] = None,
                        envelope: Optional[dict] = None, language: str = "bn") -> dict:
    fmt = {k: v for k, v in FORMATS[aspect].items() if k != "tag"}
    words_by_id = tr.by_id()
    kept = tr.kept()

    starts = scene_starts(sf, beats)
    sentence_end = {wid: words_by_id[b.word_ids[-1]].end for b in beats.beats for wid in b.word_ids if b.word_ids and b.word_ids[-1] in words_by_id}
    scenes_out = []
    used_icons: set[str] = {"circle-help"}
    used_stickers: set[str] = set()
    dark_bg = _bg_dark(theme)
    for i, sc in enumerate(sf.scenes):
        start = starts[i]
        end = starts[i + 1] if i + 1 < len(starts) else round(duration, 3)
        els = []
        story = None
        for el in sc.elements:
            if el.type == "story":                     # Cartoon 2 draws the whole frame itself (runtime/vt-story.js); its times are already video seconds
                story = _story_data(el, media or {})
                continue
            d = el.model_dump(exclude_none=True)
            w = words_by_id[el.at_word]
            at = min(max(w.start - 0.04, start + (0 if i == 0 else 0.05)), max(start, end - 0.3))
            d["at"] = round(at, 3)
            d.pop("at_word", None)
            uw = d.pop("until_word", None)
            if uw in words_by_id:
                d["until"] = round(words_by_id[uw].end + 0.15, 3)
            elif sc.backdrop is not None:                  # over a picture: leave after its sentence so the picture is seen again (pacing.dwell)
                d["until"] = round(min(at + HOLD_MAX, max(at + HOLD_MIN, sentence_end.get(el.at_word, at) + 0.2)), 3)
            if d.get("until", end) >= end - 0.35:          # the scene cuts first: no exit of its own
                d.pop("until", None)
            if el.keyframes or el.start is not None or el.end is not None or el.x is not None or el.y is not None or el.scale != 1 or el.rotation != 0 or el.opacity != 1 or has_transform(el.transform):
                d["free"] = True
                if el.keyframes or el.x is not None or el.y is not None or el.scale != 1 or el.rotation != 0 or el.opacity != 1 or has_transform(el.transform):
                    d["_placed"] = True                    # placed by hand, not only re-timed: the scene keeps one layout for every shape
                d["at"] = round(el.start if el.start is not None else at, 3)
                d["until"] = round(el.end if el.end is not None else max(d["at"] + .1, end), 3)
            if el.end is not None or (uw in words_by_id and "until" in d):
                d["_held"] = True                          # someone chose when it leaves (an end time, an until_word): a cartoon keeps it with the next picture
            els.append(d)
            _nested_assets(d, used_icons, used_stickers)
            if d["type"] == "icon":
                used_icons.add(d["name"])
            if d["type"] in ("icon_row", "keyword") and d.get("icon") and d["icon"] != "coin":
                used_icons.add(d["icon"])
            if d["type"] == "sticker" and d.get("emoji") and dark_bg and _dark_art(emo.emoji_key(d["emoji"]) or d["emoji"]):
                _as_line(d)                                    # a near-black picture on a dark background: its line icon instead (readable)
                if d["type"] == "icon":
                    used_icons.add(d["name"])
            if getattr(theme, "picture", "emoji") == "line" and d["type"] in ("sticker", "keyword"):
                _as_line(d)                                    # a drawn style: the line icon for the same word, never a colour emoji
                if d["type"] == "icon":
                    used_icons.add(d["name"])
            if d["type"] in ("sticker", "keyword") and d.get("emoji"):
                key = emo.emoji_key(d["emoji"])
                if key:
                    d["emoji"] = key
                    used_stickers.add(key)
                else:
                    d.pop("emoji")
        first = min(els, key=lambda x: x["at"]) if els else None
        if first is not None and not first.get("free"):  # generated timing only: when the person timed the scene's first picture, nothing else is pulled forward in its place
            if i == 0:
                first["at"] = round(start, 3)            # the opening picture is on screen from the first frame (thumbnail, first impression)
            elif first["at"] - start > 0.6:
                first["at"] = round(min(start + 0.4, max(start, end - 0.3)), 3)
        scene_d = {"id": sc.id, "start": start, "end": end, "layout": sc.layout,
                   "transition_in": sc.transition_in, "tone": sc.tone, "elements": els}
        scene_d["transition_effect"] = sc.transition_effect
        scene_d["camera_move"] = sc.camera_move
        if sc.start is not None or any(e.edited for e in sc.elements):
            scene_d["edited"] = True
        elif sf.planner in AI_PLANNERS:
            scene_d["directed"] = True                  # decision 1: code never hides, shrinks or drops what an AI put on screen; it measures and tells the director
        if not scene_d.get("edited") and sc.backdrop is None and els and all(e["type"] in CARD_TYPES for e in els) and not sc.stick:
            last = max(sc.elements, key=lambda e: words_by_id[e.at_word].start)
            last_at = max(e["at"] for e in els)
            out = min(last_at + HOLD_MAX, max(last_at + HOLD_MIN, sentence_end.get(last.at_word, last_at) + 0.2))
            if out < end - 0.8:
                scene_d["_card_out"] = round(out, 3)       # decided below, once it is known whether the video has pictures
        if sc.archetype:
            scene_d["archetype"] = sc.archetype
        if sc.backdrop:
            scene_d["backdrop"] = sc.backdrop.model_dump(exclude_none=True)
            if (media or {}).get(sc.backdrop.media, {}).get("role") == "a_roll":          # the A-roll is cut to the edited voice: the scene's own start is the place in the picture
                scene_d["backdrop"]["offset"] = round(start, 3)
        _keep_clear_of_people(scene_d, sc, media or {}, aspect)
        if sc.sfx:
            scene_d["sfx"] = [{"t": round(words_by_id[c["at_word"]].start, 3), "id": c["id"]} for c in sc.sfx if c.get("at_word") in words_by_id]
        if story is not None:
            scene_d["story"] = story
            scene_d["archetype"] = "story"
        overlay = [it for e in els if e["type"] == "cartoon" for it in e.get("extras", [])]
        if overlay:                                    # Cartoon 1 with story-engine extras on top (vt/story/motifs.py)
            scene_d["story_overlay"] = [{k: v for k, v in it.items() if not (k == "move" and not v)} for it in overlay]
        if sc.stick:
            st = dict(sc.stick)
            st["t0"], st["t1"] = start, end
            if st.get("set") and not st["set"].get("art"):                                  # decoration the kind of place brings (a classroom's board, door, window) that no action or shot names: nobody placed it
                from ..script import catalogue as C

                named = {a.get(k) for a in st.get("actions", []) for k in ("target", "prop")} | {(st.get("camera") or {}).get("focus")}
                st["set"] = {**st["set"], "scenery": [n for n in C.SETS.get(st["set"].get("kind"), ()) if n in st["set"].get("props", []) and n not in named]}
            st["propArt"] = _prop_art(st)
            scene_d["stick"] = st
            scene_d["archetype"] = "stick"
        scenes_out.append(scene_d)

    _hand_cards_back(scenes_out)
    highlight = {wid for sc in sf.scenes for wid in sc.caption.highlight_words}
    cap = theme.caption
    max_chars = {"9:16": 40, "1:1": 34, "16:9": 52}[aspect]
    automatic_words = [w for w in kept if w.caption_start is None and w.caption_end is None]
    captions = build_caption_chunks(automatic_words, cap.words_per_line, max_chars, highlight)
    for w in kept:
        if w.caption_start is not None or w.caption_end is not None:
            a = w.caption_start if w.caption_start is not None else w.start
            b = w.caption_end if w.caption_end is not None else w.end
            if b > a:
                one = w.model_copy(update={"start": a, "end": b})
                chunks = build_caption_chunks([one], 1, max_chars, highlight)
                for chunk in chunks:
                    chunk["start"], chunk["end"] = a, b
                captions.extend(chunks)
    captions.sort(key=lambda c: c["start"])
    caption_heights = {sc.id: sc.caption.y for sc in sf.scenes if sc.caption.y is not None}
    if caption_heights:
        for c in captions:
            at = next((s["id"] for s in scenes_out if s["start"] <= c["start"] < s["end"]), None)
            if at in caption_heights:
                c["y"] = caption_heights[at]

    scenes_out = paginate(scenes_out, aspect)
    thinned = build_cues(scenes_out)

    return {
        "comp_id": "root",
        "format": fmt,
        "duration": round(duration, 3),
        "theme": theme.model_dump(exclude_none=True),
        "icons": {n: ((icons or {}).get(n) or icon_sets.inner(n) or "") for n in sorted(used_icons)},
        "stickers": {k: emo.svg(k) or "" for k in sorted(used_stickers)},
        "scenes": scenes_out,
        "captions": captions,
        "cues": thinned,
        "media": media or {},
        "envelope": envelope,
        "language": language,
        **({"story_cast": {k: v.model_dump(exclude_none=True) for k, v in sf.story_cast.items()},
            "story_fonts": {"head": _font_stack(theme.font.headline, "serif"), "body": _font_stack(theme.font.body, "sans-serif")}}
           if any(e.type == "story" or (e.type == "cartoon" and e.extras) for sc in sf.scenes for e in sc.elements) else {}),
    }


def _font_stack(families: list[str], generic: str) -> str:
    return ", ".join([f"'{f}'" for f in families] + [generic])


def _story_data(el, media: dict) -> dict:
    """A story element as the story engine reads it. A picture item names a media id; the page needs that file's path."""
    d = el.model_dump(exclude_none=True)
    items = []
    for it in d.get("items", []):
        if it.get("type") == "image" and it.get("src") in media:
            it = {**it, "src": media[it["src"]].get("src", it["src"])}
        if not it.get("move"):
            it.pop("move", None)
        items.append(it)
    return {"bg": d.get("bg") or {"type": "plain"}, "items": items, "tag": d.get("tag", ""), "push": d.get("push", 0.05), "speak": d.get("speak", {})}


def layers_for_composition(project, duration: float) -> list[dict]:
    """The visual layers (text, pictures, video clips) from layers.json, bottom first, for the page to draw above the scenes."""
    from .. import layers as L

    doc = L.load(project)
    kinds = L.media_kinds(project)
    clean, errors = L.validate(doc, duration, kinds)
    if errors:                                                 # a half-edited document must not break the preview: draw what is valid
        clean = L.validate({"tracks": doc["tracks"], "clips": [c for c in doc["clips"]]}, duration, kinds)[0]
    tracks = {t["id"]: t for t in clean["tracks"]}
    order = {t["id"]: i for i, t in enumerate(clean["tracks"])}      # the first track is the top layer
    out = []
    for c in sorted((c for c in clean["clips"] if c["type"] != "audio"), key=lambda c: (-order[c["track"]], c["start"])):
        t = tracks[c["track"]]
        if t["hidden"]:
            continue
        out.append({**c, "end": round(c["start"] + c["dur"], 3)})
    return out


# --------------------------------------------------------------------------- write


def _sync(src: Path, dst: Path) -> None:
    """Copy only when the content differs. Rewriting unchanged files while the browser is downloading them
    produced truncated responses (ERR_CONTENT_LENGTH_MISMATCH)."""
    data = src.read_bytes()
    if dst.exists() and dst.stat().st_size == len(data) and dst.read_bytes() == data:
        return
    _put(dst, data)


def _put(dst: Path, data: bytes) -> None:
    """Write via a temp file of its own and an atomic replace. Windows refuses to replace a file that is being read, so this retries for up to ~3 s;
    two writers never share a temp name (they used to, and one renamed the other's file away: HTTP 500)."""
    import os
    import threading
    import time

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f"{dst.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_bytes(data)
    for attempt in range(25):
        try:
            os.replace(tmp, dst)
            return
        except PermissionError:
            time.sleep(0.03 * (attempt + 1))
    try:
        dst.write_bytes(data)  # last resort: the file stayed locked for seconds
    finally:
        tmp.unlink(missing_ok=True)


_FONT_BLOCK = re.compile(r"/\*[^*]*\*/\s*@font-face\s*\{[^}]*\}", re.S)


def _copy_fonts(dest: Path, theme: Theme, all_fonts: bool = False) -> None:
    families = set()
    for lst in (theme.font.headline, theme.font.body, theme.font.numeral or [], theme.font.caption or []):
        families.update(lst)
    css_src = (paths.FONTS / "fonts.css").read_text(encoding="utf-8")
    dest.mkdir(parents=True, exist_ok=True)
    keep = []
    for block in _FONT_BLOCK.findall(css_src):
        fam = re.search(r"font-family:\s*'([^']+)'", block)
        if not fam or (not all_fonts and fam.group(1) not in families):
            continue
        m = re.search(r"url\(\./([^)]+)\)", block)
        if m and (paths.FONTS / m.group(1)).exists():
            _sync(paths.FONTS / m.group(1), dest / m.group(1))
            keep.append(block)
    _put(dest / "fonts.css", ("\n\n".join(keep)).encode("utf-8"))


_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="fonts/fonts.css">
<link rel="stylesheet" href="runtime/vt.css">
<link rel="stylesheet" href="runtime/vt-info.css">
<link rel="stylesheet" href="runtime/vt-media.css">
<link rel="stylesheet" href="runtime/vt-layers.css">
<link rel="stylesheet" href="runtime/vt-diagrams.css">
<link rel="stylesheet" href="runtime/vt-stick.css">
</head>
<body>
<div id="root" data-composition-id="root" data-start="0" data-duration="__DURATION__" data-width="__W__" data-height="__H__"></div>
<script src="runtime/gsap.min.js"></script>
<script>window.__VT__ = __DATA__;</script>
<script src="runtime/vt.js"></script>
<script src="runtime/vt-info.js"></script>
<script src="runtime/vt-cartoon.js"></script>
<script src="runtime/vt-stick.js"></script>
<script src="runtime/vt-media.js"></script>
<script src="runtime/vt-layers.js"></script>
<script src="runtime/vt-diagrams.js"></script>
<script src="runtime/vt-motion.js"></script>
<script src="runtime/vt-keyframes.js"></script>
<script src="runtime/vt-world.js"></script>
<script src="runtime/vt-story.js"></script>
<script type="module">
import * as THREE from './runtime/three.module.js';
window.THREE = THREE;
window.VTX.start();
window.__timelines = window.__timelines || {}; window.__timelines["root"] = window.__vt.timeline();
</script>
</body>
</html>
"""


def write_composition(out_dir: Path, data: dict, theme: Theme, title: str = "Video", all_fonts: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rt = out_dir / "runtime"
    rt.mkdir(exist_ok=True)
    for name in ("vt.js", "vt.css", "vt-info.js", "vt-info.css", "vt-cartoon.js", "vt-media.js", "vt-media.css", "vt-layers.js", "vt-layers.css", "vt-diagrams.js", "vt-diagrams.css", "vt-stick.js", "vt-stick.css", "vt-motion.js", "vt-keyframes.js", "vt-world.js", "vt-story.js"):
        _sync(paths.RUNTIME / name, rt / name)
    three = paths.RENDERER / "node_modules" / "three"
    for name in ("three.module.js", "three.core.js"):
        _sync(three / "build" / name, rt / name)
    _sync(three / "LICENSE", rt / "three-LICENSE.txt")
    for item in (data.get("media") or {}).values():            # media is copied next to the composition so the page is self-contained
        src = item.pop("_abs", None)
        if src and Path(src).exists():
            _sync(Path(src), out_dir / item["src"])
    gsap = paths.RENDERER / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    _sync(gsap, rt / "gsap.min.js")
    _copy_fonts(out_dir / "fonts", theme, all_fonts)
    tex = out_dir / "textures"
    tex.mkdir(exist_ok=True)
    _sync(paths.DESIGN / "textures" / "paper-grain.png", tex / "paper-grain.png")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = (_HTML.replace("__TITLE__", title.replace("<", ""))
            .replace("__DURATION__", str(data["duration"]))
            .replace("__W__", str(data["format"]["width"]))
            .replace("__H__", str(data["format"]["height"]))
            .replace("__DATA__", payload))
    if any(item.get('kind')=='video' for item in data.get('media',{}).values()):
        # HyperFrames detects runtime-created media by scanning inline scripts.
        # With only external factories and a known duration it skips discovery,
        # so no source frames are extracted and the export holds frame zero.
        # Inline the actual factory (not a dummy detection hint) so its normal
        # DOM probe discovers every timed video before rendering.
        media_runtime=(paths.RUNTIME/'vt-media.js').read_text(encoding='utf-8')
        media_runtime=re.sub(r'</script',r'<\\/script',media_runtime,flags=re.I)
        html=html.replace('<script src="runtime/vt-media.js"></script>','<script>'+media_runtime+'</script>')
    _put(out_dir / "index.html", html.encode("utf-8"))
    _put(out_dir / "data.json", json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    return out_dir / "index.html"


def _beat_sync(data: dict, music_id: str) -> None:
    """Nudge pictures and sound cues onto the beat of the project's music. Never stops a composition: no music file, no ffmpeg, no sync."""
    from .. import beatsync
    from ..render.mux import resolve_music

    try:
        track = resolve_music(music_id)
        if track is None:
            return
        known = next((m.get("bpm") for m in read_json(paths.MUSIC / "index.json", []) or [] if m.get("file") == track.name), None)
        bpm, offset = beatsync.grid_for(track, known)
        beatsync.apply(data, bpm, offset)
    except Exception:
        pass


CAPTION_FOR_KIND = {"steps": "keyword", "list": "keyword", "story": "pop", "explanation": "pop", "argument": "word", "opinion": "pop"}


def reel_caption_preset(project) -> str:
    """The caption look the content wants (docs/plans/PLAN-REEL-DIRECTOR.MD section 5), read from what the reel director decided about the script."""
    kind = (read_json(project.dir / "reel_report.json", {}) or {}).get("kind", "")
    return CAPTION_FOR_KIND.get(kind, "pop")


def compose_project(project, aspect: Optional[str] = None, duration: Optional[float] = None, captions: bool = True) -> Path:
    """Compose a project for one aspect. Returns the path to index.html."""
    from ..project import load_theme

    meta = project.meta()
    aspect = aspect or meta.aspect
    sf = project.scenes()
    if sf is None:
        raise RuntimeError("no scenes.json yet - run the planning stage first")
    theme = project.theme(sf.theme or meta.theme)
    from ..planner.rules import detect_currency

    theme = theme.model_copy(update={"currency": detect_currency(project.transcript(), meta.language, theme.currency)})
    cs = meta.options.caption_style
    if cs in ("auto", "theme") and meta.options.look == "reel" and not (theme.style or "").startswith("lemo:"):
        cs = reel_caption_preset(project)                       # the reading decides: steps and lists light the key word, an argument shows one word at a time, a story shows short lines
    if cs == "auto":
        cs = "pop" if aspect == "9:16" else "theme"
    if cs != "theme":
        upd = {"style": cs}
        if cs == "pop":
            upd.update({"words_per_line": min(3, theme.caption.words_per_line), "reveal": "line"})     # three words at a time, read in one glance
        elif cs == "word":
            upd.update({"words_per_line": 1, "reveal": "line"})
        elif cs == "keyword":
            upd.update({"words_per_line": min(4, theme.caption.words_per_line), "reveal": "line"})
        theme = theme.model_copy(update={"caption": theme.caption.model_copy(update=upd)})
    tr = project.transcript()
    beats = project.beats()
    if duration is None:
        cuts = project.cuts()
        duration = cuts.output_duration if cuts else (max((w.end for w in tr.kept()), default=1.0) + 0.5)
    icons = read_json(paths.ICONS / "lucide.json", {})
    from ..director.media import composition_media, speech_envelope

    media = composition_media(project)
    if any(sc.shot for sc in sf.scenes):
        from .. import shots as SH

        sf, shot_media = SH.place_on_scenes(project, sf, aspect)
        media.update(shot_media)
    data = resolve_composition(sf, tr, beats, theme, aspect, duration, icons, media=media,
                               envelope=speech_envelope(project.cut_audio) if project.cut_audio.exists() else None, language=meta.language)
    if not captions:
        data["captions_enabled"] = False
    data["layers"] = layers_for_composition(project, duration)
    from . import motion as MO

    MO.apply(data, meta.options.motion, seed=project.id)                 # motion recipes first, so beat sync moves their start times too
    if meta.options.music and meta.options.beat_sync:
        _beat_sync(data, meta.options.music)
    if meta.options.recording_edit != 'auto':
        from ..screen_recording import layout
        layout(data,meta)
    out = project.comp_dir / FORMATS[aspect]["tag"]
    return write_composition(out, data, theme, meta.title or project.id)
