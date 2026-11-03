"""Where the sentences end when the recogniser gives no punctuation (Bangla often arrives as one long stream).

Pause length at a word boundary is the single strongest cue to a sentence boundary in speech, ahead of the words
themselves (Shriberg, Stolcke, Hakkani-Tür & Tür, "Prosody-based automatic segmentation of speech into sentences and
topics", Speech Communication 2000; Kolář, Shriberg & Liu 2006 on meetings: the pause at the boundary and at the
neighbouring boundaries matter most). A fixed threshold fails across speakers, so the threshold is set from the speaker's
own pause distribution: a pause is a boundary when it is well above the typical between-word gap (median + k·MAD, a robust
z-score), with an absolute floor so a fast talker's commas are not sentences, and a ceiling so a slow talker still gets split.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

FLOOR = 0.35      # s: never a sentence boundary below this
CEILING = 0.90    # s: always one above this
K = 2.5           # robust z threshold
MIN_WORDS = 3     # a sentence shorter than this joins its neighbour


def pause_threshold(gaps: Sequence[float]) -> float:
    g = np.asarray([x for x in gaps if x >= 0], dtype=float)
    if len(g) < 8:
        return 0.45
    median = float(np.median(g))
    mad = float(np.median(np.abs(g - median))) or 0.05
    return float(min(CEILING, max(FLOOR, median + K * 1.4826 * mad)))


def boundaries(words: Sequence[dict], punctuation: str = ".!?।") -> list[int]:
    """Indices i such that a sentence ends after words[i]: at sentence punctuation, or at a pause above the speaker's threshold.
    Very short sentences are merged into the previous one."""
    n = len(words)
    if n == 0:
        return []
    gaps = [max(0.0, float(words[i + 1].get("start", 0)) - float(words[i].get("end", 0))) for i in range(n - 1)]
    threshold = pause_threshold(gaps)
    ends = []
    for i in range(n - 1):
        text = str(words[i].get("text", "")).rstrip()
        if text.endswith(tuple(punctuation)) or gaps[i] >= threshold:
            ends.append(i)
    ends.append(n - 1)
    merged, last = [], -1
    for e in ends:
        if e - last < MIN_WORDS:
            if merged:                      # too short: joins the sentence before it
                merged[-1] = e
                last = e
            continue                        # too short at the very start: joins the sentence after it
        merged.append(e)
        last = e
    if not merged or merged[-1] != n - 1:
        merged.append(n - 1)
    return merged
