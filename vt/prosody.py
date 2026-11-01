"""How worked up the speaker sounds, moment by moment: arousal from pitch, loudness, speed and pauses.

Listeners hear excitement before they understand the words, and highlight detection on podcasts improves when the speech
signal joins the transcript (Rhapsody, arXiv 2505.19429: audio emotion features raised the hit rate of every model). The
classic prosodic correlates of arousal are a higher and more varied pitch, more energy, faster speech and fewer pauses
(Shriberg, Bates & Stolcke 1997 on decision trees over prosody; IBM's call-centre study; the rule-based mapping in
arXiv 2307.02132 ties speech rate to arousal). Nothing here is learned: every feature is measured, normalised against the
speaker's own recording (a z-score), and averaged into one arousal number per window.

* pitch: a normalised autocorrelation pitch tracker (the core of YIN/RAPT) on 40 ms frames, voiced frames only;
* energy: RMS in dB;
* rate and pauses come from the transcript's word timings.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

SAMPLE_RATE = 16000
FRAME = int(0.040 * SAMPLE_RATE)
HOP = int(0.010 * SAMPLE_RATE)
F0_MIN, F0_MAX = 70.0, 400.0
VOICED_THRESHOLD = 0.55


def decode(path: Path) -> np.ndarray:
    """Mono float32 at SAMPLE_RATE, by ffmpeg."""
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"],
                         capture_output=True, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    return np.frombuffer(out, dtype=np.float32)


def frame_features(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per 10 ms frame: (time s, f0 Hz or NaN when unvoiced, energy dB)."""
    if len(x) < FRAME * 2:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    frames = np.lib.stride_tricks.sliding_window_view(x, FRAME)[::HOP].astype(np.float64)
    frames = frames - frames.mean(axis=1, keepdims=True)
    energy_db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-6)
    lag_min, lag_max = int(SAMPLE_RATE / F0_MAX), int(SAMPLE_RATE / F0_MIN)
    # normalised autocorrelation by FFT, one pass for all frames
    size = 1 << (2 * FRAME - 1).bit_length()
    spectrum = np.fft.rfft(frames, size, axis=1)
    acf = np.fft.irfft(spectrum * np.conj(spectrum), size, axis=1)[:, :FRAME]
    power = acf[:, :1] + 1e-9
    normalised = acf / power
    window = normalised[:, lag_min:lag_max + 1]
    best = window.argmax(axis=1)
    peak = window[np.arange(len(best)), best]
    f0 = SAMPLE_RATE / (best + lag_min)
    loud_enough = energy_db > (np.median(energy_db) - 12)
    f0 = np.where((peak > VOICED_THRESHOLD) & loud_enough, f0, np.nan)
    times = np.arange(len(frames)) * HOP / SAMPLE_RATE
    return times, f0, energy_db


def _zscore(values: np.ndarray) -> np.ndarray:
    ok = np.isfinite(values)
    if ok.sum() < 2:
        return np.zeros_like(values)
    mean, std = values[ok].mean(), values[ok].std()
    return np.where(ok, (values - mean) / (std if std > 1e-6 else 1.0), 0.0)


def arousal_per_window(times: np.ndarray, f0: np.ndarray, energy_db: np.ndarray, windows: Sequence[tuple[float, float]],
                       words: Optional[Sequence[dict]] = None) -> list[float]:
    """One arousal score per (start, end) window: the mean z-score of pitch level, pitch range, loudness, speech rate and
    (negatively) pause share, each normalised across all windows so the speaker is compared with themself.
    Returns 0.0 for every window when there is nothing to measure."""
    if len(windows) == 0:
        return []
    if len(times) == 0:
        return [0.0] * len(windows)
    pitch_level, pitch_range, loudness, rate, pause_share = [], [], [], [], []
    starts = np.asarray([w[0] for w in windows]); ends = np.asarray([w[1] for w in windows])
    word_starts = np.asarray([float(w.get("start", 0.0)) for w in words]) if words else None
    word_ends = np.asarray([float(w.get("end", 0.0)) for w in words]) if words else None
    for s, e in zip(starts, ends):
        sel = (times >= s) & (times < e)
        voiced = f0[sel][np.isfinite(f0[sel])]
        pitch_level.append(np.log(voiced).mean() if len(voiced) >= 5 else np.nan)       # log pitch: semitones, speaker-relative
        pitch_range.append(np.percentile(np.log(voiced), 90) - np.percentile(np.log(voiced), 10) if len(voiced) >= 5 else np.nan)
        loudness.append(np.percentile(energy_db[sel], 80) if sel.sum() >= 5 else np.nan)
        if word_starts is not None and e > s:
            inside = (word_starts >= s) & (word_ends <= e)
            n = int(inside.sum())
            rate.append(n / (e - s) if n else np.nan)
            spoken = float((word_ends[inside] - word_starts[inside]).sum()) if n else 0.0
            pause_share.append(1.0 - spoken / (e - s) if n else np.nan)
        else:
            rate.append(np.nan); pause_share.append(np.nan)
    parts = [_zscore(np.asarray(pitch_level, float)), _zscore(np.asarray(pitch_range, float)), _zscore(np.asarray(loudness, float)),
             _zscore(np.asarray(rate, float)), -_zscore(np.asarray(pause_share, float))]
    stacked = np.vstack(parts)
    return [float(v) for v in np.clip(stacked.mean(axis=0), -3, 3)]


def arousal_for(audio: Path, windows: Sequence[tuple[float, float]], words: Optional[Sequence[dict]] = None) -> list[float]:
    """Arousal per window straight from a file; silently 0.0 everywhere if the audio cannot be read."""
    try:
        times, f0, energy = frame_features(decode(audio))
    except Exception:
        return [0.0] * len(windows)
    return arousal_per_window(times, f0, energy, windows, words)
