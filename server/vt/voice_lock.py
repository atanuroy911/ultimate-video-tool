"""One voice for the whole script: the same person, the same level, checked sentence by sentence.

A script is spoken one sentence at a time (the audio-first plan needs each sentence's real length). Every sentence is then a separate request to a model
that never heard the one before it, and three things made a video sound like several narrators (owner, 2026-10-31):
  * a **designed** voice ("a calm woman, gentle and thoughtful") is sampled afresh by the model for every sentence: the description fits thousands of voices
    and the text changes which one comes out, whatever the seed;
  * sentences came back at different loudness, and only the whole file was normalised;
  * nothing listened to check that sentence seven was the same person as sentence one.

So, as an editor casting a narrator would:
  1. **Cast once.** A designed voice is spoken once, on the script's own opening (about ten seconds, so the language and the register are right). That take
     is the project's **reference**; every sentence is then *cloned* from it. The reference is cached by voice, language and text, so asking twice costs nothing.
  2. **Even the level.** Each sentence's speech (its loud frames, not its pauses) is brought to one level before the pieces are joined.
  3. **Check every take.** Each sentence's voice signature (median pitch and the shape of the long-term spectrum, `vt/stages/speakers.py::_signature`) is
     compared with the reference. A take far from the reference, and far from how the other sentences differ from it, is spoken again with another seed;
     the closest take is kept. The distances are returned so the Details log can say how steady the voice was.

The thresholds below are relative (an outlier among this script's own sentences) with an absolute floor; they are to be calibrated on real takes
(the gate in docs/plans/PLAN-VOICE-DIRECTION.MD, VD-7).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

ANCHOR_MIN_CHARS = 140              # about ten seconds of speech: enough for a clone to hold the voice
ANCHOR_MAX_CHARS = 320
SPEECH_DB = -20.0                   # the level every sentence's speech is brought to
MAX_GAIN_DB = 12.0                  # never lift a near-silent take into noise
PITCH_FLOOR = np.log(1.10)          # a take is never re-spoken for less than a 10% pitch change...
SHAPE_FLOOR = 0.45                  # ...or less than this RMS difference of the log band energies
ROBUST_Z = 3.5                      # and only when it stands out from the script's other sentences
RETRIES = 2                         # extra seeds tried for a take that drifted


@dataclass
class Anchor:
    """The reference take every sentence is cloned from."""
    path: Path
    text: str
    key: str


def locks(engine: str, voice: str) -> bool:
    """Does this voice need a reference? Only voices the model invents on every request: a designed ComfyUI voice."""
    return engine == "comfyvoice" and voice.partition(":")[0] not in ("me",)


def reseeds(engine: str) -> bool:
    """Engines whose take changes with the seed, so a drifted sentence can be asked for again."""
    return engine == "comfyvoice"


def anchor_text(sentences: list[str]) -> str:
    """The script's opening, whole sentences, about ten seconds long: the reference speaks the same language and register as the video."""
    out = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if out and len(out) + 1 + len(s) > ANCHOR_MAX_CHARS:
            break
        out = f"{out} {s}".strip()
        if len(out) >= ANCHOR_MIN_CHARS:
            break
    return out[:ANCHOR_MAX_CHARS]


def anchor_key(engine: str, voice: str, language: str, text: str) -> str:
    return hashlib.sha1(f"anchor-v1|{engine}|{voice}|{language}|{text}".encode("utf-8")).hexdigest()[:20]


def make_anchor(engine: str, voice: str, text: str, language: str, speak: Callable[[Path], None], cache_dir: Path) -> Anchor:
    """Speak the reference once with `speak(out_wav)` (the voice as designed); later calls with the same voice and text reuse it."""
    key = anchor_key(engine, voice, language, text)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"anchor_{key}.wav"
    if not path.exists():
        tmp = path.with_suffix(".part.wav")
        speak(tmp)
        tmp.replace(path)
    return Anchor(path=path, text=text, key=key)


# ------------------------------------------------------------------------------------------------------------------------------ level
def speech_db(x: np.ndarray, sr: int) -> Optional[float]:
    """The level of the speech itself: the RMS of the loudest half of the 10 ms frames, so pauses and breaths do not pull it down."""
    hop = max(1, sr // 100)
    n = len(x) // hop
    if n < 5:
        return None
    rms = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    loud = np.sort(rms)[n // 2:]
    level = float(np.sqrt((loud ** 2).mean()))
    return 20 * np.log10(level) if level > 1e-6 else None


def level(x: np.ndarray, sr: int, target_db: float = SPEECH_DB) -> np.ndarray:
    db = speech_db(x, sr)
    if db is None:
        return x
    gain = float(np.clip(target_db - db, -MAX_GAIN_DB, MAX_GAIN_DB))
    return (x * 10 ** (gain / 20)).astype("float32")


# ------------------------------------------------------------------------------------------------------------------------------ the check
def signature(x: np.ndarray, sr: int) -> Optional[np.ndarray]:
    """[log pitch, 16 log band shapes] of a take, at the 16 kHz the speaker signature is defined at; None for a take too short to judge."""
    from scipy.signal import resample_poly

    from .stages.speakers import SR as SIG_SR, _signature

    if sr != SIG_SR:
        g = np.gcd(sr, SIG_SR)
        x = resample_poly(x, SIG_SR // g, sr // g).astype("float32")
    return _signature(x)


def drift(sig: np.ndarray, ref: np.ndarray) -> tuple[float, float]:
    """(|pitch change| in log units, RMS change of the spectral shape) between a take and the reference."""
    return abs(float(sig[0] - ref[0])), float(np.sqrt(np.mean((sig[1:] - ref[1:]) ** 2)))


def score(sig: np.ndarray, ref: np.ndarray) -> float:
    """One number for "how far from the reference": each part measured in units of its floor."""
    p, s = drift(sig, ref)
    return max(p / PITCH_FLOOR, s / SHAPE_FLOOR)


def outliers(sigs: list[Optional[np.ndarray]], ref: Optional[np.ndarray]) -> list[int]:
    """Indexes of takes that sound like another person: beyond the floors AND a robust outlier among this script's takes.

    The reference is the anchor's signature when there is one, else the median of the takes (the voice most sentences agree on).
    """
    have = [(i, s) for i, s in enumerate(sigs) if s is not None]
    if len(have) < 2 and ref is None:
        return []
    if ref is None:
        ref = np.median(np.array([s for _, s in have]), axis=0)
    scores = np.array([score(s, ref) for _, s in have])
    med = float(np.median(scores))
    mad = float(np.median(np.abs(scores - med))) * 1.4826 or 1e-6
    return [i for (i, _), sc in zip(have, scores) if sc > 1.0 and (sc - med) / mad > ROBUST_Z]
