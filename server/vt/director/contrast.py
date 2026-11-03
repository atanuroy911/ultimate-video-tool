"""Contrast-aware text over photos and video.

For a scene whose background is media, decide (before rendering) which text ink to use and how much scrim to lay on the picture so that
the text reaches WCAG contrast (4.5:1) against the WORST pixels it may sit on, not the average. The maths mirrors exactly what the
renderer draws (the gradient stops in vt-media.css), so the decision can be checked against a rendered frame.

Treatments, lightest first: none -> gradient scrim from the bottom/top edge -> full-frame tint. The ink (light or dark) is chosen
first: whichever reads better on the raw picture.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np

from ..schema import Scrim
from ..util import CREATE_NO_WINDOW, find_tool

TARGET = 4.5                     # WCAG AA for normal text; the captions are not always "large" text, so the stricter value is used everywhere
ALPHAS = [round(a, 2) for a in np.arange(0.15, 0.931, 0.05)]
WORST_PERCENTILE = 3.0           # ignore the extreme 3% of pixels (a few specular dots); everything else must pass


# --------------------------------------------------------------------------- WCAG maths
def _lin(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(rgb: np.ndarray) -> np.ndarray:
    """Relative luminance of an (..., 3) 0-255 array."""
    l = _lin(rgb.astype("float64"))
    return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]


def contrast_ratio(l1: np.ndarray | float, l2: np.ndarray | float):
    hi, lo = np.maximum(l1, l2), np.minimum(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def worst_ratio(lum: np.ndarray, ink_lum: float) -> float:
    """Contrast of the ink against the worst of the pixels (the percentile that is hardest for this ink)."""
    q = WORST_PERCENTILE
    # white-ish ink struggles on the brightest pixels, black-ish ink on the darkest
    ref = np.percentile(lum, 100 - q) if ink_lum > 0.5 else np.percentile(lum, q)
    # a pixel set can also straddle the ink's own luminance: take the minimum over both tails
    other = np.percentile(lum, q) if ink_lum > 0.5 else np.percentile(lum, 100 - q)
    return float(min(contrast_ratio(ink_lum, ref), contrast_ratio(ink_lum, other)))


# --------------------------------------------------------------------------- what the renderer draws
def alpha_profile(y: np.ndarray, a: float, edge: str) -> np.ndarray:
    """Scrim opacity at vertical position y (0 top .. 1 bottom), as drawn by .bd-gradient in vt-media.css."""
    if edge == "full":
        return np.full_like(y, a, dtype="float64")
    d = (1.0 - y) if edge == "bottom" else y            # distance from the edge the gradient starts at
    out = np.where(d <= 0.38, a * (1 - 0.15 * d / 0.38), np.where(d <= 0.78, a * 0.85 * (1 - (d - 0.38) / 0.40), 0.0))
    return out


def zones(aspect: str, layout: str = "stack") -> list[tuple[float, float]]:
    """Vertical spans where text can appear. Usually one block; with the 'upper' layout the elements are at the top and the caption at the bottom,
    and the middle (where the people are) is not measured."""
    if layout == "upper":
        if aspect == "9:16":
            return [(200 / 1920, 0.42), (1 - 580 / 1920, 1 - 400 / 1920)]
        if aspect == "1:1":
            return [(80 / 1080, 0.42), (1 - 230 / 1080, 1 - 110 / 1080)]
        return [(70 / 1080, 0.45), (1 - 130 / 1080, 1 - 58 / 1080)]
    return [zone(aspect, layout)]


def zone(aspect: str, layout: str = "stack") -> tuple[float, float]:
    """Vertical span (fraction of the frame height) where text can appear: the scene's elements plus the caption."""
    if layout == "upper":
        z = zones(aspect, layout)
        return z[0][0], z[-1][1]
    if aspect == "9:16":
        top = 760 / 1920 if layout == "lower" else 200 / 1920
        return top, 1 - 400 / 1920                          # captions sit 420 px up (phone-app safe area)
    if aspect == "1:1":
        top = 440 / 1080 if layout == "lower" else 80 / 1080
        return top, 1 - 110 / 1080
    top = 380 / 1080 if layout == "lower" else 70 / 1080
    return top, 1 - 58 / 1080


def blend(rgb: np.ndarray, alpha: np.ndarray, under: str) -> np.ndarray:
    """Composite a black (under light ink) or white (under dark ink) scrim of per-row opacity `alpha` onto the picture."""
    col = 0.0 if under == "light" else 255.0
    a = alpha[..., None]
    return rgb * (1 - a) + col * a


def decide(samples: list[np.ndarray], aspect: str = "9:16", layout: str = "stack", target: float = TARGET) -> Scrim:
    """samples: RGB arrays (H, W, 3) of the media as it will be framed (cover-cropped), one per sampled moment. The worst case over all moments is used."""
    rows = []
    for im in samples:
        h = im.shape[0]
        for zt, zb in zones(aspect, layout):
            r0, r1 = int(zt * h), max(int(zt * h) + 2, int(zb * h))
            rows.append((im[r0:r1], np.linspace(zt, zb, r1 - r0)))

    def ratio(ink: str, a: float, edge: str) -> float:
        ink_l = 1.0 if ink == "light" else 0.0
        worst = 99.0
        for reg, ys in rows:
            alpha = alpha_profile(ys, a, edge)[:, None] * np.ones((1, reg.shape[1]))
            lum = luminance(blend(reg, alpha, ink)) if a > 0 else luminance(reg)
            worst = min(worst, worst_ratio(lum, ink_l))
        return worst

    raw = {ink: ratio(ink, 0.0, "full") for ink in ("light", "dark")}
    ink = max(raw, key=raw.get)
    if raw[ink] >= target:
        return Scrim(ink=ink, kind="none", strength=0.0, edge="bottom", ratio=round(raw[ink], 2))
    best: Optional[Scrim] = None
    for edge in ("bottom", "full"):                      # lightest treatment first; each ink is tried, the one needing less scrim wins
        for a in ALPHAS:
            cands = []
            for k in ("light", "dark"):
                r = ratio(k, a, edge)
                if r >= target:
                    cands.append((a, k, r))
            if cands:
                a2, k2, r2 = min(cands, key=lambda c: (c[0], -c[2]))
                kind = "gradient" if edge == "bottom" else "panel"
                best = Scrim(ink=k2, kind=kind, strength=a2, edge=edge, ratio=round(r2, 2))
                break
        if best:
            break
    if best:
        return best
    k = "light" if raw["light"] >= raw["dark"] else "dark"      # even the strongest tint cannot reach the target (pathological picture)
    return Scrim(ink=k, kind="panel", strength=0.93, edge="full", ratio=round(ratio(k, 0.93, "full"), 2))


# --------------------------------------------------------------------------- sampling
def cover_crop(im: np.ndarray, aspect: str, fx: float = 0.5, fy: float = 0.5) -> np.ndarray:
    """Crop like CSS object-fit: cover with object-position (fx, fy) for the target aspect."""
    h, w = im.shape[:2]
    target = {"9:16": 9 / 16, "1:1": 1.0, "16:9": 16 / 9}[aspect]
    cur = w / h
    if cur > target:                                     # too wide: crop columns
        nw = int(round(h * target))
        x0 = int(round((w - nw) * fx))
        return im[:, x0:x0 + nw]
    nh = int(round(w / target))
    y0 = int(round((h - nh) * fy))
    return im[y0:y0 + nh]


def frames_of(path: Path, kind: str, duration: float = 0.0, n: int = 4, max_side: int = 360, start: float = 0.0) -> list[np.ndarray]:
    """RGB frames of an image (1) or video (n, spread over `duration` seconds from `start`)."""
    from PIL import Image

    if kind == "image":
        im = Image.open(path).convert("RGB")
        im.thumbnail((max_side, max_side))
        return [np.asarray(im)]
    out = []
    ffmpeg = find_tool("ffmpeg")
    with tempfile.TemporaryDirectory() as d:
        for i in range(n):
            t = max(0.0, start + duration * (i + 0.5) / n) if duration else start
            f = Path(d) / f"f{i}.png"
            subprocess.run([ffmpeg, "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf", f"scale={max_side}:-2", str(f)],
                           capture_output=True, creationflags=CREATE_NO_WINDOW)
            if f.exists():
                out.append(np.asarray(Image.open(f).convert("RGB")))
    return out


def decide_for_media(project, media_id: str, aspect: str, layout: str = "stack", t0: float = 0.0, t1: Optional[float] = None, media_start: float = 0.0) -> Scrim:
    """Scrim for a media item used as the backdrop of one scene (video: only the part of the clip that scene actually shows)."""
    m = next((x for x in project.meta().media if x.id == media_id), None)
    if not m:
        return Scrim()
    path = project.dir / m.file
    if m.kind == "image":
        fr = frames_of(path, "image")
    else:
        shown = min(m.duration or 0.0, max(0.5, (t1 - t0) if t1 else (m.duration or 1)))
        fr = frames_of(path, "video", shown or m.duration, 4, start=min(media_start, max(0.0, (m.duration or 0.0) - 0.2)))
    if not fr:
        return Scrim()
    return decide([cover_crop(f, aspect, m.fx, m.fy) for f in fr], aspect, layout)
