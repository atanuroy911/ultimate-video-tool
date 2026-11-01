"""Your own voices: a few seconds of a voice you are allowed to use, kept in `voices/<id>/`, and the Chatterbox Turbo engine (ONNX, `vt.clone_onnx`) that speaks new sentences in it.

Consent is part of the data: a voice can only be added with `consent=True` (the person recording it is the one who says yes, or you have their permission), the name and the time are
stored with it, and nothing is ever taken from a project's media or a download automatically. The engine runs inside the app's own Python (GPU when there is one); its model (about 1.1 GB)
is downloaded the first time a voice is used.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from . import paths
from .util import CREATE_NO_WINDOW, find_tool, now_iso, read_json, write_json

MIN_SECONDS, MAX_SECONDS = 5.0, 60.0
REF_SECONDS = 20.0                                         # the model needs no more than this much of a voice
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")


def voices_dir() -> Path:
    d = paths.DATA / "voices"
    d.mkdir(parents=True, exist_ok=True)
    return d


class VoiceError(RuntimeError):
    pass


def list_voices() -> list[dict]:
    out = []
    for d in sorted(voices_dir().iterdir()):
        meta = read_json(d / "voice.json")
        if meta and (d / "ref.wav").exists():
            out.append({"id": d.name, "name": meta.get("name", d.name), "seconds": meta.get("seconds"), "created": meta.get("created"), "consent": bool(meta.get("consent"))})
    return out


def ref_path(voice_id: str) -> Path:
    if not _ID.match(voice_id or ""):
        raise VoiceError("unknown voice")
    p = voices_dir() / voice_id / "ref.wav"
    if not p.exists():
        raise VoiceError("unknown voice")
    return p


def ref_text(voice_id: str) -> str:
    """The exact words spoken in a saved voice's recording: the models that clone from a recording (Breeze TTS 2, OmniVoice) need them. Written once, by the speech recogniser, then kept."""
    ref = ref_path(voice_id)
    meta_path = voices_dir() / voice_id / "voice.json"
    meta = read_json(meta_path, {}) or {}
    if meta.get("ref_text"):
        return meta["ref_text"]
    try:
        from .stages.asr import model_for_language, transcribe

        wav16 = ref.with_name("ref16k.wav")
        subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(ref), "-ac", "1", "-ar", "16000", str(wav16)], check=True, creationflags=CREATE_NO_WINDOW)
        words = transcribe(wav16, model=model_for_language("large-v3", "en"), language="en").get("words", [])
        wav16.unlink(missing_ok=True)
    except Exception as e:                                          # noqa: BLE001
        raise VoiceError(f"The words in this voice's recording could not be read ({type(e).__name__}); type them in the voice's settings.") from e
    meta["ref_text"] = " ".join(w["text"].strip() for w in words).strip()
    write_json(meta_path, meta)
    return meta["ref_text"]


def add_voice(src: Path, name: str, consent: bool) -> dict:
    """Keep a voice sample. The recording is converted to mono 24 kHz WAV, trimmed to its best 20 s, and refused when it is too short, silent or clipped."""
    if not consent:
        raise VoiceError("Say that this is your own voice, or that you have the speaker's permission. A voice is never added without it.")
    name = re.sub(r"\s+", " ", (name or "").strip())[:40]
    if not name:
        raise VoiceError("give the voice a name")
    tmp = src.with_suffix(".conv.wav")
    r = subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "24000", str(tmp)], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0 or not tmp.exists():
        raise VoiceError("this file could not be read as audio")
    try:
        x, sr = sf.read(str(tmp), dtype="float32")
    finally:
        tmp.unlink(missing_ok=True)
    secs = len(x) / sr
    if secs < MIN_SECONDS:
        raise VoiceError(f"the recording is {secs:.1f} s long; record at least {MIN_SECONDS:.0f} seconds of clear speech")
    if secs > MAX_SECONDS * 5:
        raise VoiceError("that is a very long recording; use a minute or less of clear speech")
    if float(np.abs(x).max()) < 0.02:
        raise VoiceError("the recording is almost silent")
    if float((np.abs(x) > 0.99).mean()) > 0.01:
        raise VoiceError("the recording is distorted (clipped); record again a bit quieter")
    x = _best_window(x, sr, REF_SECONDS)
    x = x / max(1e-6, float(np.abs(x).max())) * 0.9
    vid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "voice"
    base, n = vid, 2
    while (voices_dir() / vid).exists():
        vid, n = f"{base}-{n}", n + 1
    d = voices_dir() / vid
    d.mkdir(parents=True)
    sf.write(str(d / "ref.wav"), x, sr)
    write_json(d / "voice.json", {"name": name, "seconds": round(len(x) / sr, 1), "created": now_iso(), "consent": True, "consent_text": "the person recording, or their permission, was confirmed"})
    return {"id": vid, "name": name, "seconds": round(len(x) / sr, 1)}


def _best_window(x: np.ndarray, sr: int, seconds: float) -> np.ndarray:
    """The stretch of `seconds` that is loudest and speech-like all the way through (not a pause, not a cough)."""
    n = int(seconds * sr)
    if len(x) <= n:
        return x
    hop = sr // 2
    best, at = -1.0, 0
    for a in range(0, len(x) - n + 1, hop):
        seg = x[a:a + n]
        frames = seg[: len(seg) // 480 * 480].reshape(-1, 480)
        rms = np.sqrt((frames ** 2).mean(axis=1))
        level = float(rms.clip(0, 1).mean() * (rms > 0.01).mean())
        if level > best:
            best, at = level, a
    return x[at:at + n]


def remove_voice(voice_id: str) -> bool:
    import shutil

    if not _ID.match(voice_id or ""):
        return False
    d = voices_dir() / voice_id
    if not d.is_dir():
        return False
    shutil.rmtree(d, ignore_errors=True)
    return True


# --------------------------------------------------------------------------- the engine
SPEECH_DB = -19.0                                          # the level a cloned voice is brought to (RMS); the model itself writes about -26 dB
PEAK = 0.95

_engine = None
_lock = threading.Lock()


def available() -> bool:
    """Voice cloning works wherever ONNX Runtime does; the model is fetched on first use."""
    import importlib.util                     # look, do not load: importing it here would load GPU libraries before torch's (vt/gpu.py)

    try:
        return all(importlib.util.find_spec(m) is not None for m in ("onnxruntime", "tokenizers"))
    except Exception:
        return False


def ready() -> bool:
    from . import models

    return models.ready("chatterbox-turbo")


def _load(progress=None):
    global _engine
    if _engine is None:
        from . import clone_onnx, models

        try:
            models.ensure("chatterbox-turbo", progress)
            _engine = clone_onnx.Engine.load(device=os.environ.get("VT_CLONE_DEVICE", "auto"))
        except models.ModelError as e:
            raise VoiceError(str(e)) from e
    return _engine


def stop() -> None:
    """Let go of the engine (and the GPU memory it holds)."""
    global _engine
    with _lock:
        _engine = None


def level(y: np.ndarray) -> np.ndarray:
    """Bring a cloned voice to a normal speech level without clipping."""
    rms = float(np.sqrt(np.mean(y * y))) if len(y) else 0.0
    if rms <= 1e-6:
        return y
    g = 10 ** ((SPEECH_DB - 20 * np.log10(rms)) / 20)
    y = y * g
    peak = float(np.abs(y).max())
    return (y * (PEAK / peak) if peak > PEAK else y).astype("float32")


def say(text: str, voice_id: str, out_wav: Path, *, exaggeration: float = 0.5, timeout: float = 900.0, progress=None, cancel=None) -> float:
    """Speak `text` in the saved voice into out_wav (24 kHz mono). Returns the length in seconds. (`exaggeration` and `timeout` are kept for old callers; the Turbo model has neither.)"""
    from . import clone_onnx

    ref, sr = sf.read(str(ref_path(voice_id)), dtype="float32")
    if ref.ndim > 1:
        ref = ref.mean(axis=1)
    if sr != clone_onnx.SAMPLE_RATE:
        raise VoiceError("the saved voice is not at 24 kHz; add it again")
    with _lock:
        eng = _load()
        try:
            y = eng.speak(text, ref, cancel=cancel, progress=progress)
        except clone_onnx.CloneError as e:
            raise VoiceError(str(e)) from e
    y = level(y)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), y, clone_onnx.SAMPLE_RATE)
    return len(y) / clone_onnx.SAMPLE_RATE
