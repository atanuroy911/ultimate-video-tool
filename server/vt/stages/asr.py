"""Speech recognition with faster-whisper (CTranslate2). Runs on the GPU when available.

Models live in models/ (never inside a project). The Bangla fine-tune is converted to CTranslate2 on first use.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Callable, Optional

from .. import paths
from ..util import noop_progress

# The Xet transfer backend stalled at 0 bytes on Windows during testing; plain HTTP downloads work.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

MODEL_SPECS: dict[str, dict] = {
    # Bangla fine-tune of Whisper medium; lowest WER among open models in a 2026 Bengali long-form study.
    # This fine-tune was trained WITHOUT timestamp tokens: enabling them clips the first word and invites a hallucinated tail
    # (verified against the original model), so it decodes without them; word times come from attention alignment instead.
    "bn-medium": {"hf": "bengaliAI/tugstugi_bengaliai-asr_whisper-medium", "convert": True, "timestamp_tokens": False, "languages": ["bn"], "download_gb": 3.06,
                  "note": "Bangla fine-tune (converted locally to CTranslate2, ~1.5 GB)"},
    # General multilingual model; better for English words, weaker for Bangla.
    "large-v3": {"hf": "Systran/faster-whisper-large-v3", "download_gb": 3.09, "convert": False, "timestamp_tokens": True, "note": "multilingual, ~3 GB"},
    "medium": {"hf": "Systran/faster-whisper-medium", "download_gb": 1.53, "convert": False, "timestamp_tokens": True, "note": "multilingual, ~1.5 GB"},
    "small": {"hf": "Systran/faster-whisper-small", "download_gb": 0.48, "convert": False, "timestamp_tokens": True, "note": "fast, lower accuracy, ~480 MB"},
}


def _prepare_cuda() -> None:
    from .. import gpu
    gpu.prepare()


def cuda_available() -> bool:
    _prepare_cuda()
    from .. import gpu

    if not gpu.usable():                                                # the person allowed no graphics card: the processor listens
        return False
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def model_for_language(key: str, language: str) -> str:
    """The Bangla fine-tune only knows Bangla; any other language falls back to a multilingual model."""
    langs = MODEL_SPECS[key].get("languages")
    if langs and language not in langs:
        # large-v3 is the multilingual model that reads English well. With a GPU it is the default and downloads itself on first use (~3 GB);
        # on the processor the smaller medium is used unless large-v3 is already there.
        return "large-v3" if ((model_dir("large-v3") / "model.bin").exists() or cuda_available()) else "medium"
    return key


def model_dir(key: str) -> Path:
    """Converted models live in models/<key>/; ready-made ones stay in the Hugging Face cache and models/<key>.json points there."""
    ptr = paths.MODELS / f"{key}.json"
    if ptr.exists():
        try:
            return Path(json.loads(ptr.read_text(encoding="utf-8"))["path"])
        except (ValueError, KeyError, OSError):
            pass
    return paths.MODELS / key


def list_models() -> list[dict]:
    out = []
    for k, spec in MODEL_SPECS.items():
        out.append({"key": k, "hf": spec["hf"], "note": spec["note"], "installed": (model_dir(k) / "model.bin").exists()})
    return out


def ensure_model(key: str, progress: Callable[[str, float, str], None] = noop_progress) -> Path:
    """Download (and convert, if needed) a model. Returns the local directory."""
    if key not in MODEL_SPECS:
        raise ValueError(f"unknown ASR model '{key}', choose one of {list(MODEL_SPECS)}")
    dest = model_dir(key)
    if (dest / "model.bin").exists():
        return dest
    spec = MODEL_SPECS[key]
    dest.parent.mkdir(parents=True, exist_ok=True)
    progress("asr", 0.0, f"Downloading the speech model {key} (first run only)")
    stop = _watch_download(spec, progress)
    try:
        return _fetch(key, spec, dest, progress)
    finally:
        stop()


def _watch_download(spec: dict, progress: Callable[[str, float, str], None]) -> Callable[[], None]:
    """A first download is gigabytes: say how far it is every few seconds (it showed 0 % for minutes and looked frozen, 2026-11-05)."""
    import threading
    import time

    from huggingface_hub.constants import HF_HUB_CACHE

    folder = Path(HF_HUB_CACHE) / ("models--" + spec["hf"].replace("/", "--"))
    total = float(spec.get("download_gb") or 0) * 1e9
    done = threading.Event()

    def loop():
        last, t_last = 0, time.time()
        while not done.wait(3):
            have = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file() and not f.is_symlink()) if folder.exists() else 0
            now = time.time()
            speed = (have - last) / max(0.1, now - t_last) / 1e6
            last, t_last = have, now
            if total and have < total * 0.995:
                left = (total - have) / 1e6 / speed if speed > 0.05 else 0
                progress("asr", min(0.5, 0.5 * have / total), f"Downloading the speech model (first run only): {have / 1e9:.1f} of {total / 1e9:.1f} GB"
                         + (f", about {max(1, round(left / 60))} min left" if left else ""))
            elif have:
                progress("asr", 0.5, "Preparing the speech model (first run only, a minute or two)")

    threading.Thread(target=loop, daemon=True).start()
    return done.set


def _fetch(key: str, spec: dict, dest: Path, progress: Callable[[str, float, str], None]) -> Path:
    if spec["convert"]:
        from ctranslate2.converters import TransformersConverter

        conv = TransformersConverter(spec["hf"], copy_files=["tokenizer.json", "preprocessor_config.json"], load_as_float16=True)
        try:
            conv.convert(str(dest), quantization="float16", force=True)
        except Exception:
            # some repos have no tokenizer.json; the multilingual tokenizer is identical, faster-whisper falls back to it
            conv = TransformersConverter(spec["hf"], copy_files=["preprocessor_config.json"], load_as_float16=True)
            conv.convert(str(dest), quantization="float16", force=True)
    else:
        from huggingface_hub import snapshot_download

        # the cache-based download is the reliable one here (local_dir downloads stalled at 0 bytes during testing)
        snap = Path(snapshot_download(spec["hf"]))
        (paths.MODELS / f"{key}.json").write_text(json.dumps({"path": str(snap), "hf": spec["hf"]}), encoding="utf-8")
        dest = snap
    if not (dest / "model.bin").exists():
        raise RuntimeError(f"model {key} could not be prepared")
    return dest


MIN_SPEECH = 0.35   # a chunk needs at least this much voiced audio (Silero VAD) to be transcribed


JUNK_CONF = 0.7          # a word below this confidence that the model also invented elsewhere on the recording is dropped


def _norm(t: str) -> str:
    return re.sub(r"[^\wঀ-৿]+", "", t.lower())


def looped(words: list[str], run: int = 3) -> bool:
    """A segment that says the same word `run` times in a row ("প্রেসিডেন্ট প্রেসিডেন্ট প্রেসিডেন্ট") is the model looping, not speech."""
    n = [_norm(w) for w in words]
    return any(n[i] and n[i] == n[i + 1] == n[i + 2] for i in range(len(n) - run + 1))


def free_card() -> list[str]:
    """Before speech recognition loads on the card: a picture engine (ComfyUI) or the local AI (Ollama) on this same computer may hold most of it,
    and the model would then fall back to the processor (16 minutes of talk took over 40 minutes that way, 2026-11-22). Ask both to let go;
    they load again on their next job. Best effort; returns who was asked."""
    asked: list[str] = []
    try:
        import httpx

        from .. import llm
        from ..server.comfy_routes import comfy_url

        url = comfy_url()
        if url and llm.is_local(url):
            httpx.post(url.rstrip("/") + "/free", json={"unload_models": True, "free_memory": True}, timeout=10)
            asked.append("comfyui")
        if llm.is_local(llm.settings()["ollama_url"]) and llm.release():
            asked.append("ollama")
    except Exception:                                                                      # noqa: BLE001
        pass
    return asked


def transcribe(wav: Path, *, model: str = "bn-medium", language: str = "bn",
               progress: Callable[[str, float, str], None] = noop_progress, device: Optional[str] = None,
               chunks: Optional[list[tuple[float, float]]] = None) -> dict:
    """Retry on CPU when CUDA fails lazily during decoding, not just model loading."""
    try:
        return _transcribe(wav,model=model,language=language,progress=progress,device=device,chunks=chunks)
    except RuntimeError as error:
        reason=str(error).lower()
        if device=='cpu' or not any(token in reason for token in ('libcublas','libcudnn','cublas64','cudnn64','cuda failed','cuda error')):
            raise
        progress('asr',.02,'GPU libraries could not be loaded; continuing speech recognition on the CPU')
        return _transcribe(wav,model=model,language=language,progress=progress,device='cpu',chunks=chunks)


def _transcribe(wav: Path, *, model: str = "bn-medium", language: str = "bn",
               progress: Callable[[str, float, str], None] = noop_progress, device: Optional[str] = None,
               chunks: Optional[list[tuple[float, float]]] = None) -> dict:
    """Return {"language", "model", "words": [{"text","start","end","conf"}]} in source time.

    `chunks` are (start, end) pieces cut at pauses (see stages/chunks.py); each is transcribed on its own because the Bangla
    model ends early on long windows. No initial prompt is used: priming it with glossary words made it drop sentences and
    loop. The glossary is applied afterwards, word by word.
    """
    _prepare_cuda()
    import numpy as np
    import soundfile as sf
    from faster_whisper import WhisperModel

    path = ensure_model(model, progress)
    use_cuda = (device == "cuda") or (device is None and cuda_available())
    if use_cuda:
        free_card()
    progress("asr", 0.02, "loading model on " + ("GPU" if use_cuda else "CPU"))
    try:
        from .. import gpuassign

        index = gpuassign.cuda_index("speech") if use_cuda else 0                # the card chosen for speech recognition (Server page, `vt gpu`)
        wm = WhisperModel(str(path), device="cuda" if use_cuda else "cpu", device_index=index, compute_type="float16" if use_cuda else "int8")
        if use_cuda:
            progress("asr", 0.03, f"speech recognition runs on GPU {index}")
    except Exception as e:                                                                  # a GPU that cannot be used (driver, memory): say so and go on with the CPU
        if not use_cuda:
            raise
        progress("asr", 0.02, f"GPU not usable ({str(e)[:80]}); using the CPU")
        wm = WhisperModel(str(path), device="cpu", compute_type="int8")
    x, sr = sf.read(str(wav), dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != 16000:
        raise ValueError("speech recognition expects a 16 kHz mono wav")
    duration = len(x) / sr
    chunks = chunks or [(0.0, duration)]
    ts_tokens = MODEL_SPECS[model].get("timestamp_tokens", True)
    words: list[dict] = []
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    skipped = 0
    junk: set[str] = set()
    for ci, (cs, ce) in enumerate(chunks):
        piece = x[int(cs * sr): int(ce * sr)]
        # neural speech gate: Whisper-style models invent text from noise, so chunks without real speech are not transcribed
        speech = sum(t["end"] - t["start"] for t in get_speech_timestamps(piece, VadOptions(threshold=0.5, min_speech_duration_ms=250))) / sr
        if speech < MIN_SPEECH:
            skipped += 1
            continue
        # no artificial lead-in: the aligner anchors the first word to the clip start, so padding would be swallowed into its timing
        segments, _ = wm.transcribe(
            piece, language=language, word_timestamps=True, beam_size=5, condition_on_previous_text=False,
            without_timestamps=not ts_tokens, vad_filter=False, temperature=0.0,
            no_speech_threshold=0.6, compression_ratio_threshold=2.4,
        )
        for seg in segments:
            progress("asr", min(0.98, 0.05 + 0.93 * (cs + seg.end) / max(duration, 0.1)), f"{cs + seg.end:.0f}s/{duration:.0f}s  {seg.text.strip()[:70]}")
            seg_words = [w.word.strip() for w in seg.words or [] if w.word.strip()]
            if (seg.no_speech_prob > 0.7 and seg.avg_logprob < -1.2) or looped(seg_words):
                junk.update(_norm(t) for t in seg_words)          # what this model invents on this recording
                continue
            for w in seg.words or []:
                t = w.word.strip()
                if t:
                    words.append({"text": t, "start": cs + float(w.start), "end": cs + float(w.end), "conf": float(w.probability)})
    before = len(words)
    words = [w for w in words if not (w["conf"] < JUNK_CONF and _norm(w["text"]) in junk)]       # a stray invented word next to real speech
    progress("asr", 1.0, f"{len(words)} words" + (f" ({before - len(words)} invented dropped)" if before > len(words) else ""))
    del wm
    return {"language": language, "model": model, "duration": duration, "chunks": [[round(a, 2), round(b, 2)] for a, b in chunks], "chunks_without_speech": skipped, "words": words}
