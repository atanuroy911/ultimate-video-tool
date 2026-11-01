"""Who is speaking? A lightweight, model-free guess for recordings with two voices (interview, podcast, debate).

Each sentence gets a voice signature: its typical pitch (median of the voiced frames) and the shape of its long-term spectrum (energy in 16 bands,
the same for the same vocal tract). The signatures are split into two groups by 2-means clustering, and the split is ACCEPTED only when it is
clearly real:
  * the two group centres are far apart compared with the spread inside each group (Fisher ratio),
  * pitch differs by at least 18% between the groups, or the spectral shape differs by a wide margin,
  * both groups have several sentences and each takes at least 15% of the speech,
  * the voices take turns (the speaker changes at least twice).
A single speaker, whose pitch and tone wander naturally, fails these tests and is left as one speaker. Two people with very similar voices may also
be missed: this is a helper, not a diarisation model. Speakers are named "Speaker 1" and "Speaker 2" in order of appearance.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..schema import Beats, Transcript
from ..visuals.emphasis import F0_MAX, F0_MIN, FRAME, HOP, SR, _f0_frames

BANDS = 16
MIN_SENTENCES = 4
FISHER_MIN = 2.6
PITCH_RATIO_MIN = 1.18
MIN_SHARE = 0.15


def _signature(seg: np.ndarray) -> Optional[np.ndarray]:
    """[log pitch, 16 normalised log band energies] of a stretch of speech, or None if there is too little voiced sound."""
    if len(seg) < SR * 0.8:
        return None
    f0 = _f0_frames(seg)
    if len(f0) < 12:
        return None
    # long-term average spectrum of the louder frames, in 16 log-spaced bands from 100 Hz to 6 kHz
    frames = []
    for i in range(0, len(seg) - FRAME, HOP):
        fr = seg[i: i + FRAME]
        if 20 * np.log10(np.sqrt(np.mean(fr * fr)) + 1e-9) > -42:
            frames.append(np.abs(np.fft.rfft(fr * np.hanning(FRAME), 1024)) ** 2)
    if len(frames) < 12:
        return None
    spec = np.mean(frames, axis=0)
    freqs = np.fft.rfftfreq(1024, 1 / SR)
    edges = np.geomspace(100, 6000, BANDS + 1)
    bands = np.array([spec[(freqs >= a) & (freqs < b)].sum() + 1e-12 for a, b in zip(edges[:-1], edges[1:])])
    lb = np.log(bands)
    lb = lb - lb.mean()                                    # the shape of the spectrum, not how loud the sentence was
    return np.concatenate([[np.log(np.median(f0))], lb])


def _kmeans2(X: np.ndarray, iters: int = 30) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(X[:, 0])
    c = np.stack([X[order[: max(1, len(X) // 4)]].mean(axis=0), X[order[-max(1, len(X) // 4):]].mean(axis=0)])
    lab = np.zeros(len(X), dtype=int)
    for _ in range(iters):
        d = ((X[:, None, :] - c[None, :, :]) ** 2).sum(axis=2)
        new = d.argmin(axis=1)
        if (new == lab).all() and _ > 0:
            break
        lab = new
        for k in (0, 1):
            if (lab == k).any():
                c[k] = X[lab == k].mean(axis=0)
    return lab, c


def assign(audio: np.ndarray, tr: Transcript, beats: Beats) -> Optional[dict[str, str]]:
    """{beat_id: "Speaker 1" | "Speaker 2"} when two distinct voices are clearly present, otherwise None."""
    sigs, ids, durs = [], [], []
    for b in beats.beats:
        s = _signature(audio[int(b.start * SR): int(b.end * SR)])
        if s is not None:
            sigs.append(s)
            ids.append(b.id)
            durs.append(b.end - b.start)
    if len(sigs) < MIN_SENTENCES:
        return None
    X = np.array(sigs)
    pitch = X[:, 0]
    Z = X.copy()
    Z[:, 0] = (pitch - pitch.mean()) / (pitch.std() + 1e-6) * 2.0                 # pitch counts double: it is the most reliable cue
    Z[:, 1:] = (X[:, 1:] - X[:, 1:].mean(axis=0)) / (X[:, 1:].std(axis=0) + 1e-6) * 0.5
    lab, c = _kmeans2(Z)
    if len(set(lab)) < 2:
        return None
    share = [sum(d for d, l in zip(durs, lab) if l == k) / sum(durs) for k in (0, 1)]
    if min(share) < MIN_SHARE or min((lab == 0).sum(), (lab == 1).sum()) < 2:
        return None
    within = np.sqrt(np.mean([((Z[lab == k] - c[k]) ** 2).sum(axis=1).mean() for k in (0, 1)]))
    between = float(np.linalg.norm(c[0] - c[1]))
    if between / (within + 1e-6) < FISHER_MIN:
        return None
    p0, p1 = np.exp(pitch[lab == 0].mean()), np.exp(pitch[lab == 1].mean())
    if max(p0, p1) / min(p0, p1) < PITCH_RATIO_MIN:
        return None
    # the speaker must change at least twice, in order of the sentences (a long monologue followed by another is not a conversation)
    order = [lab[ids.index(b.id)] for b in beats.beats if b.id in ids]
    if sum(1 for a, b in zip(order, order[1:]) if a != b) < 2:
        return None
    first = lab[0]
    names = {first: "Speaker 1", 1 - first: "Speaker 2"}
    out: dict[str, str] = {}
    last = names[first]
    by = dict(zip(ids, lab))
    for b in beats.beats:                                   # sentences without a signature (too short) follow the previous speaker
        last = names[by[b.id]] if b.id in by else last
        out[b.id] = last
    return out


def label_words(tr: Transcript, beats: Beats, who: dict[str, str]) -> Transcript:
    """Copy of the transcript with `speaker` set on every word of every sentence."""
    spk = {wid: who[b.id] for b in beats.beats if b.id in who for wid in b.word_ids}
    return tr.model_copy(update={"words": [w.model_copy(update={"speaker": spk.get(w.id)}) for w in tr.words]})
