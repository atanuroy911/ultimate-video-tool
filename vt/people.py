"""Where the people are in a picture, and where there is room for text and stickers that is not on a person.

Digital image processing, in four steps:
  1. a matte of the main subject (the IS-Net model, the same one that removes backgrounds; without it, a body shape estimated from the face box);
  2. clean-up with morphology: small specks go, holes close, and only the part that touches the face (or, with no face, the biggest part) is kept: that is the person;
  3. the mask is grown by a safety margin and kept as a coarse grid (48 x 27 cells) so it can be stored in the plan;
  4. for a given output shape (9:16, 1:1, 16:9) the grid is mapped through the same crop the picture really gets (object-fit: cover around the subject position, plus the slow punch-in),
     and the largest empty rectangle outside the caption zone is the only place elements may go. No room for anything useful: the elements are dropped and the person stays clear.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

GW, GH = 48, 27
MARGIN = 0.035                 # fraction of the picture added around the person (hair, hands, movement between the frames that were looked at)
ZOOM = 1.16                    # the slowest punch-in the renderer applies (kenburns): the person is looked for at this zoom too


def _ndi():
    import scipy.ndimage as ndi

    return ndi


def face_body_mask(face: list[float], h: int, w: int) -> np.ndarray:
    """A person's shape from a face box [x, y, w, h] (fractions): head, shoulders and the body below it. Used when no matte is available."""
    fx, fy, fw, fh = face
    yy, xx = np.mgrid[0:h, 0:w]
    px, py = (xx + 0.5) / w, (yy + 0.5) / h
    cx, cy = fx + fw / 2, fy + fh / 2
    head = ((px - cx) / (fw * 0.75)) ** 2 + ((py - cy) / (fh * 0.85)) ** 2 <= 1.0
    neck = (np.abs(px - cx) <= fw * 0.45) & (py >= cy) & (py <= fy + fh * 1.6)
    body = (np.abs(px - cx) <= fw * 1.6) & (py >= fy + fh * 1.35)           # shoulders are about three face widths across
    return head | neck | body


def person_mask(frame_rgb: np.ndarray, face: Optional[list[float]] = None, use_model: bool = True) -> np.ndarray:
    """Boolean mask (frame's size, reduced to at most 160 px) of the person in the picture."""
    from PIL import Image

    h0, w0 = frame_rgb.shape[:2]
    k = 160 / max(h0, w0)
    small = np.asarray(Image.fromarray(frame_rgb).resize((max(8, int(w0 * k)), max(8, int(h0 * k))), Image.BILINEAR))
    h, w = small.shape[:2]
    mask = None
    if use_model:
        try:
            from . import cutout

            if cutout.available():
                a = cutout.matte(Image.fromarray(frame_rgb))
                mask = np.asarray(Image.fromarray((a * 255).astype("uint8")).resize((w, h), Image.BILINEAR)) > 110
        except Exception:
            mask = None
    if mask is None or mask.sum() < 0.01 * h * w:
        if not face:
            return np.zeros((h, w), dtype=bool)
        return face_body_mask(face, h, w)
    ndi = _ndi()
    mask = ndi.binary_opening(mask, iterations=1)                        # specks and thin strands that are not the person
    mask = ndi.binary_closing(mask, iterations=2)                        # gaps between the arm and the body
    lab, n = ndi.label(mask)
    if n == 0:
        return face_body_mask(face, h, w) if face else mask
    keep = set()
    if face:
        fx, fy, fw, fh = face
        box = lab[int(fy * h):max(int(fy * h) + 1, int((fy + fh) * h)), int(fx * w):max(int(fx * w) + 1, int((fx + fw) * w))]
        keep = {int(v) for v in np.unique(box) if v}
    if not keep:
        sizes = ndi.sum(mask, lab, index=range(1, n + 1))
        keep = {int(np.argmax(sizes)) + 1}
    person = np.isin(lab, list(keep))
    person = ndi.binary_fill_holes(person)
    if face:                                                             # the matte can lose a dark head against a dark wall: the face box is part of the person, always
        person |= face_body_mask(face, h, w) & (np.arange(h)[:, None] <= int((face[1] + face[3] * 1.6) * h))
    return person


def to_grid(mask: np.ndarray, margin: float = MARGIN) -> np.ndarray:
    """Coarse GH x GW boolean grid, grown by the safety margin."""
    h, w = mask.shape
    ndi = _ndi()
    r = max(1, int(round(margin * max(h, w))))
    grown = ndi.binary_dilation(mask, structure=np.ones((3, 3), bool), iterations=r)
    ys = np.minimum((np.arange(h) * GH) // h, GH - 1)
    xs = np.minimum((np.arange(w) * GW) // w, GW - 1)
    grid = np.zeros((GH, GW), dtype=bool)
    yy, xx = np.nonzero(grown)
    grid[ys[yy], xs[xx]] = True
    return grid


def pack(grid: np.ndarray) -> list[str]:
    return ["".join("1" if v else "0" for v in row) for row in grid]


def unpack(rows: list[str]) -> np.ndarray:
    g = np.zeros((GH, GW), dtype=bool)
    for y, r in enumerate(rows[:GH]):
        for x, c in enumerate(r[:GW]):
            g[y, x] = c == "1"
    return g


def union(grids: list[np.ndarray]) -> np.ndarray:
    out = np.zeros((GH, GW), dtype=bool)
    for g in grids:
        out |= g
    return out


def window(src_aspect: float, out_aspect: float, fx: float, fy: float, zoom: float = 1.0) -> tuple[float, float, float, float]:
    """The part of the source picture (x0, y0, x1, y1 as fractions) that an 'object-fit: cover' box of the output shape shows, with the subject position (fx, fy) as the CSS object-position
    and an optional punch-in towards that position."""
    if src_aspect > out_aspect:
        vw, vh = out_aspect / src_aspect, 1.0
    else:
        vw, vh = 1.0, src_aspect / out_aspect
    x0, y0 = fx * (1 - vw), fy * (1 - vh)
    if zoom > 1.0:
        nw, nh = vw / zoom, vh / zoom
        cx, cy = x0 + vw * fx, y0 + vh * fy                      # the point that stays still
        x0, y0 = cx - nw * fx, cy - nh * fy
        vw, vh = nw, nh
    return x0, y0, x0 + vw, y0 + vh


def to_output(grid: np.ndarray, src_aspect: float, out_aspect: float, fx: float, fy: float, motion: str = "none", cells: int = 48) -> np.ndarray:
    """The person grid as it appears in the output frame (cells x cells*h/w), for a picture shown with the given crop and camera motion."""
    oh = max(8, int(round(cells / out_aspect)))
    out = np.zeros((oh, cells), dtype=bool)
    for z in ((1.0, ZOOM) if motion != "none" else (1.0,)):
        x0, y0, x1, y1 = window(src_aspect, out_aspect, fx, fy, z)
        xs = x0 + (np.arange(cells) + 0.5) / cells * (x1 - x0)
        ys = y0 + (np.arange(oh) + 0.5) / oh * (y1 - y0)
        gx = np.clip((xs * GW).astype(int), 0, GW - 1)
        gy = np.clip((ys * GH).astype(int), 0, GH - 1)
        inside = ((xs >= 0) & (xs <= 1))[None, :] & ((ys >= 0) & (ys <= 1))[:, None]
        out |= grid[gy][:, gx] & inside
    return out


def largest_free_rect(occupied: np.ndarray, y_lo: float, y_hi: float, min_w: float, min_h: float) -> Optional[tuple[float, float, float, float]]:
    """The largest empty rectangle (x, y, w, h as fractions of the output) between y_lo and y_hi that is at least min_w wide and min_h tall, or None."""
    h, w = occupied.shape
    r0, r1 = int(round(y_lo * h)), int(round(y_hi * h))
    free = ~occupied[r0:r1]
    if free.size == 0:
        return None
    heights = np.zeros(free.shape[1], dtype=int)
    best, best_area = None, 0
    for r in range(free.shape[0]):
        heights = np.where(free[r], heights + 1, 0)
        stack: list[tuple[int, int]] = []                         # (start column, height): the classic largest rectangle in a histogram
        for c in range(len(heights) + 1):
            cur = heights[c] if c < len(heights) else 0
            start = c
            while stack and stack[-1][1] >= cur:
                s, hh = stack.pop()
                width = c - s
                if hh * width > best_area and width / w >= min_w and hh / h >= min_h:
                    best_area, best = hh * width, (s, r - hh + 1, width, hh)
                start = s
            stack.append((start, cur))
    if best is None:
        return None
    s, top, width, hh = best
    return (s / w, (r0 + top) / h, width / w, hh / h)
