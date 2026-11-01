"""Which word did the speaker stress? Measured from the audio, not guessed from the text.

For every spoken word: peak loudness, pitch (F0 by autocorrelation) and how long it is held per letter. Each is compared with
the speaker's own typical values (robust z-score over the whole recording), then combined. People emphasise by getting louder,
higher and slower, so a word that is all three is the one the sentence is about.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from ..schema import Word

SR = 16000
FRAME = int(0.040 * SR)
HOP = int(0.020 * SR)
F0_MIN, F0_MAX = 70.0, 400.0


def load_mono16k(path: Path) -> np.ndarray:
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if sr % SR == 0:
        k = sr // SR
        x = x[: len(x) // k * k].reshape(-1, k).mean(axis=1)         # box filter + decimate: enough for voice energy and pitch
    elif sr != SR:
        x = np.interp(np.arange(0, len(x), sr / SR), np.arange(len(x)), x).astype(np.float32)
    return x


def _f0_frames(seg: np.ndarray) -> list[float]:
    """Pitch (Hz) of each voiced frame in a word, by normalised autocorrelation."""
    out: list[float] = []
    lo, hi = int(SR / F0_MAX), int(SR / F0_MIN)
    win = np.hanning(FRAME)
    for i in range(0, max(1, len(seg) - FRAME), HOP):
        fr = seg[i: i + FRAME]
        if len(fr) < FRAME:
            break
        e = float(np.sqrt(np.mean(fr * fr)) + 1e-9)
        if 20 * np.log10(e) < -45:
            continue
        f = (fr - fr.mean()) * win
        spec = np.fft.rfft(f, 2 * FRAME)
        ac = np.fft.irfft(spec * np.conj(spec))[: hi + 1]
        if ac[0] <= 0:
            continue
        ac = ac / ac[0]
        lag = lo + int(np.argmax(ac[lo: hi + 1]))
        if ac[lag] > 0.35:
            out.append(SR / lag)
    return out


def word_features(audio: np.ndarray, words: list[Word]) -> list[dict]:
    feats = []
    for w in words:
        a, b = int(w.start * SR), int(w.end * SR)
        seg = audio[a:b]
        if len(seg) < FRAME:
            feats.append({"db": -90.0, "f0": 0.0, "dur_per_char": (w.end - w.start) / max(len(w.text.strip()), 1)})
            continue
        n = max(1, (len(seg) - FRAME) // HOP)
        rms = [np.sqrt(np.mean(seg[i * HOP: i * HOP + FRAME] ** 2) + 1e-12) for i in range(n)]
        f0 = _f0_frames(seg)
        feats.append({"db": float(20 * np.log10(max(rms))), "f0": float(np.percentile(f0, 80)) if f0 else 0.0,
                      "dur_per_char": (w.end - w.start) / max(len(w.text.strip(" ,.।?!")), 1)})
    return feats


def _robust_z(v: np.ndarray, valid: np.ndarray) -> np.ndarray:
    x = v[valid]
    if len(x) < 5:
        return np.zeros_like(v)
    med = np.median(x)
    mad = np.median(np.abs(x - med)) * 1.4826 + 1e-6
    z = (v - med) / mad
    z[~valid] = 0.0
    return np.clip(z, -3, 4)


def emphasis_scores(audio_path: Optional[Path], words: list[Word]) -> dict[str, float]:
    """word id -> emphasis in 0..1 (0.5 = typical). Without audio, everything is neutral."""
    if not words or audio_path is None or not Path(audio_path).exists():
        return {w.id: 0.5 for w in words}
    feats = word_features(load_mono16k(Path(audio_path)), words)
    db = np.array([f["db"] for f in feats])
    f0 = np.array([f["f0"] for f in feats])
    dpc = np.array([f["dur_per_char"] for f in feats])
    z_db = _robust_z(db, db > -80)
    semis = np.where(f0 > 0, 12 * np.log2(np.maximum(f0, 1.0) / (np.median(f0[f0 > 0]) if (f0 > 0).any() else 1.0)), 0.0)
    z_f0 = _robust_z(semis, f0 > 0)
    z_d = _robust_z(dpc, np.ones_like(dpc, dtype=bool))
    z = 0.40 * z_db + 0.35 * z_f0 + 0.25 * z_d
    return {w.id: float(1 / (1 + np.exp(-1.3 * z[i]))) for i, w in enumerate(words)}
