"""Beat sync: pictures land on the music's beat, the way an editor cuts to music.

The voice decides when things happen (a picture appears when its word is said); the music decides the rhythm. An editor nudges
each cut a few frames so it lands on a beat. Here every element's appearance and every sound cue moves to the nearest beat when
it is at most TOLERANCE s away (about 3-4 frames: nobody sees a picture 0.1 s early, everybody feels it land on the beat), and
never out of its scene or before the scene starts. The very first picture stays on frame 1.

The beat grid: the track's tempo from the music index when it is known, otherwise estimated (onset strength from spectral flux,
autocorrelation over 70-180 BPM), and the phase found by lining the grid up with the onsets. Music starts at 0 s in the mix
(vt/render/mux.py), loops, so the grid simply continues.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import numpy as np

from .util import read_json, write_json

TOLERANCE = 0.12
SR, HOP, WIN = 11025, 256, 1024
LATENCY = (WIN / 2 + HOP) / SR       # an onset shows up in the flux of the frame whose window centre has just passed it


def _decode(path: Path, seconds: float = 60.0) -> np.ndarray:
    out = subprocess.run(["ffmpeg", "-v", "error", "-t", f"{seconds}", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    return np.frombuffer(out, dtype=np.float32)


def onset_envelope(x: np.ndarray) -> np.ndarray:
    if len(x) < WIN * 4:
        return np.zeros(1, dtype=np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(x, WIN)[::HOP] * np.hanning(WIN)
    mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1)))
    flux = np.maximum(0.0, np.diff(mag, axis=0)).sum(axis=1)
    flux -= np.convolve(flux, np.ones(16) / 16, mode="same")          # local mean removed: onsets, not loudness
    return np.maximum(flux, 0.0).astype(np.float32)


def estimate(x: np.ndarray, bpm: Optional[float] = None) -> tuple[float, float]:
    """(bpm, offset of the first beat in s) for mono audio at SR."""
    env = onset_envelope(x)
    fps = SR / HOP
    if bpm is None:
        ac = np.correlate(env, env, mode="full")[len(env) - 1:]
        lags = np.arange(len(ac))
        ok = (lags >= fps * 60 / 180) & (lags <= fps * 60 / 70)
        if not ok.any() or ac[ok].max() <= 0:
            return 120.0, 0.0
        cand = lags[ok]
        score = ac[ok] * np.exp(-0.5 * (np.log2((60 * fps / cand) / 120) / 0.9) ** 2)     # a soft preference for tempos near 120, like listeners have
        coarse = float(60 * fps / cand[int(np.argmax(score))])
        # a tempo off by 1 BPM drifts half a beat over a minute: refine tempo and phase together on the whole envelope
        best = max(((_grid_strength(env, 60.0 / b * fps), b) for b in np.arange(coarse - 4.0, coarse + 4.0, 0.05)), key=lambda x: x[0][0])
        (_, ph), bpm = best
        return round(float(bpm), 2), round((ph / fps + LATENCY) % (60.0 / bpm), 3)
    _, ph = _grid_strength(env, 60.0 / bpm * fps)
    return round(bpm, 2), round((ph / fps + LATENCY) % (60.0 / bpm), 3)


def _grid_strength(env: np.ndarray, period: float) -> tuple[float, float]:
    """(onset strength on the best grid, its phase in frames) for a beat period in frames."""
    best = (-1.0, 0.0)
    for ph in np.arange(0, period, 1.0):
        idx = np.round(np.arange(ph, len(env), period)).astype(int)
        s = float(env[idx[idx < len(env)]].sum())
        if s > best[0]:
            best = (s, float(ph))
    return best


def grid_for(music: Path, bpm: Optional[float] = None) -> tuple[float, float]:
    """(bpm, offset), measured once per file (cached in the data folder, keyed by name, size and date)."""
    from . import paths

    st = music.stat()
    cache = paths.DATA / "beat_cache" / f"{music.stem}-{st.st_size}-{int(st.st_mtime)}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    got = read_json(cache, None)
    if got and (bpm is None or abs(got["bpm"] - bpm) < 0.01):
        return got["bpm"], got["offset"]
    b, off = estimate(_decode(music), bpm)
    try:
        write_json(cache, {"bpm": b, "offset": off})
    except OSError:
        pass
    return b, off


def beat_times(bpm: float, offset: float, duration: float) -> np.ndarray:
    step = 60.0 / bpm
    return np.arange(offset % step, duration + step, step)


def snap(t: float, beats: np.ndarray, lo: float, hi: float) -> float:
    i = int(np.searchsorted(beats, t))
    best = min((beats[j] for j in (i - 1, i) if 0 <= j < len(beats)), key=lambda b: abs(b - t), default=t)
    return round(float(best), 3) if abs(best - t) <= TOLERANCE and lo <= best <= hi else t


def apply(data: dict, bpm: float, offset: float) -> int:
    """Move element appearances and sound cues of a composition (composer.build_data) onto the beat. Returns how many moved."""
    beats = beat_times(bpm, offset, float(data.get("duration", 0)) + 1)
    moved = 0
    for i, sc in enumerate(data.get("scenes", [])):
        lo, hi = float(sc["start"]), max(float(sc["start"]), float(sc["end"]) - 0.3)
        for el in sc.get("elements", []):
            if "at" not in el or (i == 0 and el["at"] <= sc["start"] + 1e-6):        # the opening picture stays on frame 1
                continue
            new = snap(float(el["at"]), beats, lo, hi)
            moved += new != el["at"]
            el["at"] = new
        for c in sc.get("sfx", []):
            new = snap(float(c["t"]), beats, lo, float(sc["end"]))
            moved += new != c["t"]
            c["t"] = new
    data["beat_sync"] = {"bpm": bpm, "offset": offset, "moved": moved}
    return moved
