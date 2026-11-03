"""Illustrated cartoon characters and painted scenes (from Cartoon Studio, Apache-2.0, see third_party/cartoon-studio/NOTICE.md).

A character is a flat SVG drawing. To talk, its drawn mouth is replaced by a "rig": a group of the nine Preston Blair mouth shapes
(X closed, A-H open variants) of which the renderer shows one at a time, following the loudness of the voice (vt-stick.js), so it
works for Bangla as well as English. The rig is placed by geometry alone: two eye-like shapes of the same size on one line, then the
dark, wider-than-tall shape below them is the mouth (a port of Cartoon Studio's `svgRig.ts`); without a clear pair of eyes, the
dark wide shape in the lower middle of the drawing.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .. import paths

ROOT = paths.ASSETS / "cartoon"
RIG_WIDTH = 180          # the rig's shapes are drawn about this wide at scale 1

MOUTH_RIG = """<g class="mouth-rig" transform="translate({cx:.2f} {cy:.2f}) scale({s:.4f})">
<g class="mouth-group mouth-X"><path d="M -75 0 L 75 0" fill="none" stroke="#0c0c0c" stroke-width="22" stroke-linecap="round"/></g>
<g class="mouth-group mouth-A" opacity="0"><path d="M -80 0 Q 0 18 80 0" fill="none" stroke="#0c0c0c" stroke-width="22" stroke-linecap="round"/></g>
<g class="mouth-group mouth-B" opacity="0"><ellipse cx="0" cy="0" rx="75" ry="12" fill="#3B1414"/></g>
<g class="mouth-group mouth-C" opacity="0"><ellipse cx="0" cy="8" rx="70" ry="38" fill="#3B1414" stroke="#0c0c0c" stroke-width="7"/></g>
<g class="mouth-group mouth-D" opacity="0"><ellipse cx="0" cy="0" rx="90" ry="60" fill="#3B1414" stroke="#0c0c0c" stroke-width="7"/></g>
<g class="mouth-group mouth-E" opacity="0"><ellipse cx="0" cy="0" rx="55" ry="40" fill="#3B1414" stroke="#0c0c0c" stroke-width="7"/></g>
<g class="mouth-group mouth-F" opacity="0"><ellipse cx="0" cy="0" rx="32" ry="36" fill="#3B1414" stroke="#0c0c0c" stroke-width="7"/></g>
<g class="mouth-group mouth-G" opacity="0"><path d="M -80 -8 L 80 -8 L 70 22 L -70 22 Z" fill="#3B1414" stroke="#0c0c0c" stroke-width="7"/></g>
<g class="mouth-group mouth-H" opacity="0"><ellipse cx="0" cy="0" rx="72" ry="42" fill="#3B1414" stroke="#0c0c0c" stroke-width="7"/><ellipse cx="0" cy="0" rx="32" ry="22" fill="#D47272"/></g>
</g>"""

_PATH = re.compile(r"<path\b[^>]*\bd=\"([^\"]+)\"[^>]*/?>(?:\s*</path>)?")
_NUM = re.compile(r"-?\d*\.?\d+(?:e-?\d+)?")


def _viewbox(svg: str) -> tuple[float, float, float, float]:
    m = re.search(r'viewBox="([^"]+)"', svg)
    if m:
        p = [float(x) for x in re.split(r"[ ,]+", m.group(1).strip())[:4]]
        if len(p) == 4:
            return p[0], p[1], p[2], p[3]
    return 0.0, 0.0, 2048.0, 2048.0


def _bbox(d: str) -> Optional[tuple[float, float, float, float]]:
    nums = [float(x) for x in _NUM.findall(d)]
    if len(nums) < 4:
        return None
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def _dark(fill: str) -> bool:
    m = re.match(r"rgb\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)", fill or "", re.I)
    if m:
        return sum(int(v) for v in m.groups()) < 150
    h = (fill or "").lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", h):
        return sum(int(h[i:i + 2], 16) for i in (0, 2, 4)) < 150
    return bool(re.match(r"^#?[012]", fill or ""))


def _paths(svg: str) -> list[dict]:
    x0, y0, W, H = _viewbox(svg)
    out = []
    for m in _PATH.finditer(svg):
        bb = _bbox(m.group(1))
        if not bb:
            continue
        x, y, w, h = bb
        fill = (re.search(r'\bfill="([^"]+)"', m.group(0)) or [None, ""])[1]
        out.append({"full": m.group(0), "bbox": bb, "fill": fill, "cx": (x + w / 2 - x0) / W, "cy": (y + h / 2 - y0) / H,
                    "nw": w / W, "aspect": w / h if h > 0 else 999.0})
    return out


def find_mouth(svg: str) -> Optional[dict]:
    """The path that draws the mouth, by the eyes above it (any canvas, any head size), else by position."""
    ps = _paths(svg)
    eyes = [p for p in ps if 0.6 <= p["aspect"] <= 1.8 and 0.025 <= p["nw"] <= 0.20 and p["cy"] < 0.70]
    best, best_s = None, -1e9
    for i, a in enumerate(eyes):
        for b in eyes[i + 1:]:
            ratio = min(a["nw"], b["nw"]) / max(a["nw"], b["nw"])
            dy, dx = abs(a["cy"] - b["cy"]), abs(a["cx"] - b["cx"])
            if ratio < 0.7 or dy > 0.05 or not 0.04 <= dx <= 0.40:
                continue
            s = ratio + min(a["nw"], b["nw"]) * 5 - dy * 20
            if s > best_s:
                best, best_s = (a, b), s
    if best:
        a, b = best
        mx, my, span = (a["cx"] + b["cx"]) / 2, (a["cy"] + b["cy"]) / 2, abs(a["cx"] - b["cx"])
        cands = [p for p in ps if _dark(p["fill"]) and p["aspect"] >= 1.5 and my + 0.005 < p["cy"] <= my + span * 3
                 and abs(p["cx"] - mx) <= span * 2 and p["nw"] <= 0.30]
        if cands:
            return max(cands, key=lambda p: p["aspect"] - abs(p["cy"] - (my + span * 0.95)) * 10 - abs(p["cx"] - mx) * 8)
    cands = [p for p in ps if _dark(p["fill"]) and p["aspect"] >= 1.5 and 0.02 <= p["nw"] <= 0.18 and p["cy"] >= 0.4]
    return max(cands, key=lambda p: p["aspect"] - abs(p["cx"] - 0.5) * 4 - abs(p["cy"] - 0.6) * 4) if cands else None


def rig(svg: str) -> tuple[str, bool]:
    """(svg with a talking mouth, whether it worked). Already rigged drawings are returned as they are."""
    if 'class="mouth-group' in svg:
        return svg, True
    m = find_mouth(svg)
    if m is None:
        return svg, False
    x, y, w, h = m["bbox"]
    s = min(2.0, max(0.5, w / RIG_WIDTH))
    return svg.replace(m["full"], MOUTH_RIG.format(cx=x + w / 2, cy=y + h / 2, s=s), 1), True


def characters() -> dict[str, Path]:
    d = ROOT / "characters"
    return {p.stem: p for p in sorted(d.glob("*.svg"))} if d.exists() else {}


def scenes() -> dict[str, Path]:
    d = ROOT / "scenes"
    return {p.stem.removeprefix("scene-"): p for p in sorted(d.glob("*.svg"))} if d.exists() else {}


SET_ART = {"street": "street", "city": "street", "market": "street", "home": "living_room", "kitchen": "living_room", "office": "living_room",
           "nature": "park", "school_yard": "park", "mountain": "park", "island": "park", "farm": "backyard", "plain": "backyard"}
FEMALE = re.compile(r"\b(she|her|girl|woman|mother|mom|sister|queen|wife|lady|jane|maya|rina)\b|মেয়ে|মা\b|বোন", re.I)


def toonify(script) -> "VideoScript":
    """The cartoon style: every person becomes an illustrated character (distinct drawings while there are enough), every dog-like
    actor the dog, and every place a painted backdrop when one fits. Works on any script, from the AI or from the rules."""
    s = script.model_copy(deep=True)
    boys, used = ["bill", "ted"], set()
    for c in s.cast:
        who = f"{c.name} {c.id} {c.role}"
        if c.kind == "emoji" and ("dog" in who.lower() or (c.emoji or "").lower() in ("1f415", "1f436")):
            c.kind, c.art = "toon", "max"
        elif c.kind == "person":
            want = ["jane"] if FEMALE.search(who) else boys
            art = next((a for a in want if a not in used), None) or next((a for a in boys + ["jane"] if a not in used), want[0])
            c.kind, c.art = "toon", art
        if c.art:
            used.add(c.art)
    for st in s.sets:
        st.art = st.art or SET_ART.get(st.kind)
    s.kind = "cartoon"
    return s
