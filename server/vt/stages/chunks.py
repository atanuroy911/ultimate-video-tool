"""Split a recording into speech chunks for recognition.

The Bangla fine-tune handles utterances up to ~17 s well but ends early on long merged windows (verified: a 20 s window
lost its last 12 words and the next window's first 11). So we cut at real pauses into pieces of at most `max_len` seconds,
transcribe each on its own, and offset the timings back.
"""
from __future__ import annotations

import numpy as np

HOP = 0.01  # seconds per energy frame (matches audio._frame_db)


def plan_chunks(duration: float, silences: list[tuple[float, float]], db: np.ndarray | None = None, *,
                max_len: float = 15.0, pad: float = 0.15, min_len: float = 0.3) -> list[tuple[float, float]]:
    """Return [(start, end)] chunk boundaries in source seconds. Chunks end inside pauses; each is <= max_len + 2*pad."""
    # speech runs = everything between silences
    runs: list[tuple[float, float]] = []
    pos = 0.0
    for a, b in sorted(silences):
        if a - pos >= min_len:
            runs.append((pos, a))
        pos = max(pos, b)
    if duration - pos >= min_len:
        runs.append((pos, duration))

    # a single run longer than max_len is split at its quietest frame in the last third of the allowed span
    pieces: list[tuple[float, float]] = []
    for s, e in runs:
        while e - s > max_len:
            lo, hi = s + max_len * 0.6, s + max_len
            cut = hi
            if db is not None and len(db):
                i0, i1 = int(lo / HOP), min(len(db), int(hi / HOP))
                if i1 > i0:
                    cut = (i0 + int(np.argmin(db[i0:i1]))) * HOP
            pieces.append((s, cut))
            s = cut
        pieces.append((s, e))

    # greedily pack neighbouring pieces while the chunk stays within max_len
    chunks: list[list[float]] = []
    for s, e in pieces:
        if chunks and e - chunks[-1][0] <= max_len:
            chunks[-1][1] = e
        else:
            chunks.append([s, e])
    return [(max(0.0, s - pad), min(duration, e + pad)) for s, e in chunks if e - s >= min_len]
