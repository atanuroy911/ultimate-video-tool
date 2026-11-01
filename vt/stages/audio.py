"""Audio stages: normalise, find silences, build/apply the cut list."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from ..schema import Cuts
from ..util import find_tool, run

PACE = {
    # pad = audio kept on each side of a removed silence; min_silence = shortest silence that gets cut
    "calm": {"pad": 0.22, "min_silence": 0.60},
    "normal": {"pad": 0.10, "min_silence": 0.35},
    "fast": {"pad": 0.05, "min_silence": 0.22},
}
LEAD_KEEP = 0.12   # silence kept before the first word
TAIL_KEEP = 0.45   # silence kept after the last word
CROSSFADE = 0.010  # seconds, avoids clicks at joins


# --------------------------------------------------------------------------- preprocess


def _loudnorm_params(src: Path, pre_filters: str) -> Optional[dict]:
    """First pass of two-pass loudnorm; returns measured values or None if it could not be parsed."""
    ff = find_tool("ffmpeg")
    out = run([ff, "-hide_banner", "-nostats", "-i", str(src), "-vn", "-af",
               f"{pre_filters}loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], check=False)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", out, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        if d.get("input_i") in ("-inf", "inf"):
            return None
        return d
    except json.JSONDecodeError:
        return None


def preprocess(src: Path, master: Path, asr_wav: Path, denoise: bool = True) -> None:
    """Any input -> 48 kHz stereo master (-16 LUFS) plus a 16 kHz mono copy for speech recognition."""
    ff = find_tool("ffmpeg")
    pre = "highpass=f=80," + ("afftdn=nr=10:nf=-40," if denoise else "")
    m = _loudnorm_params(src, pre)
    if m:
        ln = (f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    else:
        ln = "loudnorm=I=-16:TP=-1.5:LRA=11"
    run([ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vn", "-af", pre + ln,
         "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(master)])
    run([ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(master), "-ar", "16000", "-ac", "1",
         "-c:a", "pcm_s16le", str(asr_wav)])


# --------------------------------------------------------------------------- silence / cuts


def _frame_db(x: np.ndarray, sr: int, hop_s: float = 0.01) -> np.ndarray:
    hop = int(sr * hop_s)
    n = len(x) // hop
    if n == 0:
        return np.array([-90.0])
    frames = x[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms)


def estimate_threshold(db: np.ndarray) -> float:
    """Adaptive silence threshold between the noise floor and speech level, clamped to a sane range."""
    floor = float(np.percentile(db, 10))
    speech = float(np.percentile(db, 90))
    thr = floor + 0.25 * (speech - floor)
    return float(min(max(thr, -52.0), -30.0))


def find_silences(wav16: Path, min_silence: float, threshold_db: Optional[float] = None, return_db: bool = False):
    """Return ([(start, end)] silences >= min_silence, duration, threshold_db used) and, if asked, the 10 ms energy frames."""
    x, sr = sf.read(str(wav16), dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    hop_s = 0.01
    db = _frame_db(x, sr, hop_s)
    thr = threshold_db if threshold_db is not None else estimate_threshold(db)
    quiet = db < thr
    # smooth: a single loud frame (click) should not break a silence; a single quiet frame should not start one
    k = 3
    if len(quiet) > k:
        kernel = np.ones(k) / k
        quiet = np.convolve(quiet.astype(float), kernel, mode="same") > 0.5
    silences: list[tuple[float, float]] = []
    start = None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) * hop_s >= min_silence:
                silences.append((start * hop_s, i * hop_s))
            start = None
    if start is not None and (len(quiet) - start) * hop_s >= min_silence:
        silences.append((start * hop_s, len(quiet) * hop_s))
    if return_db:
        return silences, len(x) / sr, thr, db
    return silences, len(x) / sr, thr


def silence_cuts(duration: float, silences: list[tuple[float, float]], pace: str = "normal") -> Cuts:
    """Turn silences into kept ranges. Leading/trailing silence is trimmed harder than inner pauses."""
    cfg = PACE.get(pace, PACE["normal"])
    pad = cfg["pad"]
    removed: list[tuple[float, float]] = []
    for s, e in silences:
        if s <= 0.01:                      # leading silence
            a, b = 0.0, e - LEAD_KEEP
        elif e >= duration - 0.02:         # trailing silence
            a, b = s + TAIL_KEEP, duration
        else:
            a, b = s + pad, e - pad
        if b - a >= 0.08:
            removed.append((a, b))
    return cuts_from_removed(duration, removed)


def cuts_from_removed(duration: float, removed: list[tuple[float, float]]) -> Cuts:
    removed = sorted((max(0.0, a), min(duration, b)) for a, b in removed if b > a)
    merged: list[list[float]] = []
    for a, b in removed:
        if merged and a <= merged[-1][1] + 1e-6:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    keep: list[tuple[float, float]] = []
    pos = 0.0
    for a, b in merged:
        if a - pos > 0.05:
            keep.append((round(pos, 4), round(a, 4)))
        pos = b
    if duration - pos > 0.05:
        keep.append((round(pos, 4), round(duration, 4)))
    if not keep:
        keep = [(0.0, round(duration, 4))]
    return Cuts(source_duration=round(duration, 4), keep=keep)


def removed_from_cuts(cuts: Cuts) -> list[tuple[float, float]]:
    out = []
    pos = 0.0
    for s, e in cuts.keep:
        if s > pos:
            out.append((pos, s))
        pos = e
    if cuts.source_duration > pos:
        out.append((pos, cuts.source_duration))
    return out


def apply_cuts(master: Path, cuts: Cuts, out: Path) -> float:
    """Assemble the kept ranges with tiny crossfades. Returns the output duration (seconds)."""
    x, sr = sf.read(str(master), dtype="float32", always_2d=True)
    fade = max(1, int(CROSSFADE * sr))
    pieces = []
    for i, (s, e) in enumerate(cuts.keep):
        seg = x[int(round(s * sr)): int(round(e * sr))].copy()
        if len(seg) == 0:
            continue
        f = min(fade, len(seg) // 2)
        if f > 1:
            ramp = np.linspace(0.0, 1.0, f, dtype=np.float32)[:, None]
            if i > 0:
                seg[:f] *= ramp
            if i < len(cuts.keep) - 1:
                seg[-f:] *= ramp[::-1]
        pieces.append(seg)
    y = np.concatenate(pieces, axis=0) if pieces else x
    sf.write(str(out), y, sr, subtype="PCM_16")
    return len(y) / sr
