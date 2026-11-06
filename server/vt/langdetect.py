"""Which language is this? So the person starting a video does not have to say.

* `from_text`: by the writing system of the letters (Bengali script -> bn, Devanagari -> hi, Arabic -> ar ...), Latin letters -> en.
* `from_audio`: the speech model's own language detection on 30 s of the first speech in the recording, restricted to languages the app handles. Bangla gets a head start because
  Banglish (Bangla with English words) is often called English by a language detector: Bangla wins when it is at least a quarter likely and half as likely as the best guess.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Callable, Optional

SUPPORTED = ["bn", "en", "hi", "ur", "ar", "es", "fr", "de", "pt", "id", "tr", "ru", "ja", "ko", "zh", "it", "nl", "fa", "ta", "te"]
NAMES = {"bn": "Bangla", "en": "English", "hi": "Hindi", "ur": "Urdu", "ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese", "id": "Indonesian",
         "tr": "Turkish", "ru": "Russian", "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "it": "Italian", "nl": "Dutch", "fa": "Persian", "ta": "Tamil", "te": "Telugu"}
_BLOCKS = [("bn", 0x0980, 0x09FF), ("hi", 0x0900, 0x097F), ("ta", 0x0B80, 0x0BFF), ("te", 0x0C00, 0x0C7F), ("ar", 0x0600, 0x06FF), ("ru", 0x0400, 0x04FF),
           ("ja", 0x3040, 0x30FF), ("ko", 0xAC00, 0xD7AF), ("zh", 0x4E00, 0x9FFF)]


def from_text(text: str, default: str = "en") -> str:
    counts: dict[str, int] = {}
    for ch in text:
        if not ch.isalpha():
            continue
        o = ord(ch)
        for lang, a, b in _BLOCKS:
            if a <= o <= b:
                counts[lang] = counts.get(lang, 0) + 1
                break
        else:
            if "LATIN" in unicodedata.name(ch, ""):
                counts["latin"] = counts.get("latin", 0) + 1
    if not counts:
        return default
    best = max(counts, key=counts.get)
    if best == "latin":
        return default
    return best


def pick(probs: list[tuple[str, float]], allowed: Optional[list[str]] = None) -> tuple[str, float]:
    """The language to use from the detector's (language, probability) list, among `allowed` (default: every supported language)."""
    ok = sorted(((l, p) for l, p in probs if l in (allowed or SUPPORTED)), key=lambda x: -x[1])
    if not ok:
        return "en", 0.0
    top, ptop = ok[0]
    bn = dict(ok).get("bn", 0.0)
    if top != "bn" and bn >= 0.25 and bn >= 0.5 * ptop:
        return "bn", bn
    return top, ptop


def from_audio(wav: Path, progress: Optional[Callable[[str, float, str], None]] = None, allowed: Optional[list[str]] = None) -> tuple[str, float]:
    """(language code, probability) for a 16 kHz mono wav."""
    from . import gpu

    gpu.prepare()            # before faster_whisper: torch's CUDA libraries must be the ones loaded, or torch models crash the process later
    import numpy as np
    import soundfile as sf
    from faster_whisper import WhisperModel
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    from .stages import asr
    x, sr = sf.read(str(wav), dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != 16000:
        raise ValueError("language detection expects a 16 kHz mono wav")
    ts = get_speech_timestamps(x, VadOptions(threshold=0.5, min_speech_duration_ms=250))
    start = int(ts[0]["start"]) if ts else 0
    seg = x[start:start + 30 * sr]
    key = "large-v3" if (asr.model_dir("large-v3") / "model.bin").exists() else "small"
    noop = progress or (lambda *a: None)
    path = asr.ensure_model(key, noop)
    cuda = asr.cuda_available()
    try:
        from . import gpuassign

        wm = WhisperModel(str(path), device="cuda" if cuda else "cpu", device_index=gpuassign.cuda_index("speech") if cuda else 0, compute_type="float16" if cuda else "int8")
    except Exception:
        wm = WhisperModel(str(path), device="cpu", compute_type="int8")
    _, _, probs = wm.detect_language(audio=seg, vad_filter=False)
    del wm
    return pick(list(probs), allowed)
