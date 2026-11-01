"""Word-timing clean-up: snap word boundaries to the audio's real speech/silence and drop words recognised in silence.

Attention-based word timestamps place boundaries contiguously, so the last word before a pause 'absorbs' the pause, and
Whisper-style models sometimes add a low-confidence word after the speech has ended. The energy-based silence list (same
signal the cutter uses) fixes both.
"""
from __future__ import annotations

TAIL = 0.05          # a word keeps this much time after the speech energy drops
MIN_WORD = 0.06
HALLUCINATION_CONF = 0.6
HALLUCINATION_MAX_LEN = 0.25  # seconds of real speech a low-confidence word must have to survive
SEC_PER_CHAR = 0.03           # a spoken character takes at least this long; far less means it was not really said
IMPLAUSIBLE = 0.35            # ...a word shorter than this fraction of that is dropped
SOLID_CONF = 0.95            # such words are never dropped for being 'in silence'
SOLID_LEN = 0.25
LEAD_CONF, LEAD_REACH, LEAD_GAP, LEAD_LEN = 0.5, 0.06, 0.25, 0.14   # a confident word that ends where the next speech begins is kept, not dropped
EDGE_TOL = 0.08               # a word that starts this close before a pause is treated as part of the pause


def snap_words(words: list[dict], silences: list[tuple[float, float]], duration: float | None = None) -> tuple[list[dict], int]:
    """words: [{"text","start","end","conf"}] in source time. Returns (cleaned words, number dropped)."""
    out: list[dict] = []
    dropped = 0
    for wi, w in enumerate(words):
        s, e = float(w["start"]), float(w["end"])
        conf = float(w.get("conf", 1.0))
        nxt = float(words[wi + 1]["start"]) if wi + 1 < len(words) else None
        touched = False                                    # did the word overlap a pause? Only such words can be junk; inside speech every word is kept
        # a long, fully confident word is real speech even if the energy threshold calls the span "silence" (noisy rooms)
        solid = conf >= SOLID_CONF and (e - s) >= SOLID_LEN
        for a, b in silences:
            if e <= a or s >= b:
                continue                                   # no overlap with this silence
            touched = True
            if a - EDGE_TOL <= s and e <= b + EDGE_TOL:    # nothing was said here (also catches junk placed right at the speech end)
                if solid:
                    break                                  # keep the word untouched
                if conf >= LEAD_CONF and e >= b - LEAD_REACH and nxt is not None and nxt - b <= LEAD_GAP:
                    s, e = max(s, b - LEAD_LEN), max(e, b + 0.02)      # the soft first word of the next utterance ("It is..."): its onset is below the energy gate
                    break
                s = e = -1.0
                break
            if s < a:                                      # starts in speech, runs into the pause -> end where the speech ends
                e = min(e, a + TAIL)
            elif e > b:                                    # starts inside the pause, ends in speech -> begin at speech onset
                s = max(s, b - 0.02)
            else:                                          # entirely inside a pause: nothing was said here
                s = e = -1.0
                break
        if e < 0 or e - s < MIN_WORD * 0.5:
            dropped += 1
            continue
        suspect = touched or (e - s) <= 0.08             # overlapped a pause, or squeezed into almost no time: the two signs of invented words
        if suspect and conf < HALLUCINATION_CONF and (e - s) < HALLUCINATION_MAX_LEN:
            dropped += 1                                   # tiny, unsure, left over after clipping: a trailing hallucination
            continue
        if suspect and (e - s) < IMPLAUSIBLE * SEC_PER_CHAR * len(str(w["text"]).strip()):
            dropped += 1                                   # e.g. a 16-letter word squeezed into 60 ms after the speech ended
            continue
        if duration is not None:
            e = min(e, duration)
        nw = dict(w)
        nw["start"], nw["end"] = round(s, 3), round(max(e, s + MIN_WORD), 3)
        out.append(nw)
    # keep order and prevent overlaps created by the snapping
    for i in range(1, len(out)):
        if out[i]["start"] < out[i - 1]["end"]:
            mid = (out[i]["start"] + out[i - 1]["end"]) / 2
            out[i - 1]["end"] = round(max(out[i - 1]["start"] + MIN_WORD, min(out[i - 1]["end"], mid)), 3)
            out[i]["start"] = round(max(out[i]["start"], out[i - 1]["end"]), 3)
    return out, dropped
