"""Parity check of the ONNX voice cloning against the PyTorch reference outputs kept in tests/fixtures/clone_ref (docs/history/plan-2026-10.md, Phase 7 step 3.6).

For each of the three sentences: (a) speech recognition hears the key phrases, (b) the WavLM speaker similarity to the 12 s reference voice is >= 0.95 (and above Kokoro's, measured by
qa_voices.py), (c) the length is within 25 % of the PyTorch output, (d) no clipping and loudness at the app's speech level (-19 dB RMS; the PyTorch output peaked at 0.99-1.0, so it is not a loudness reference), (e) the real-time factor is printed per device.

    python scripts/qa_clone_onnx.py [--device auto|cpu|cuda] [--out DIR]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from vt import clone_onnx as C  # noqa: E402
from vt import voices as V  # noqa: E402
from vt.util import find_tool  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "clone_ref"
KEYS = {1: ["good morning", "saving money"], 2: ["small habits", "big difference"], 3: ["check the price", "before you buy"]}


def load24(path: Path) -> np.ndarray:
    tmp = path.with_suffix(".24k.wav")
    subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "24000", str(tmp)], check=True)
    x, _ = sf.read(str(tmp), dtype="float32")
    tmp.unlink(missing_ok=True)
    return x


def words_of(x: np.ndarray, sr: int) -> str:
    from faster_whisper import WhisperModel

    tmp = FIX.parent / "_tmp16.wav"
    sf.write(str(tmp), x, sr)
    out = tmp.with_suffix(".16.wav")
    subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(tmp), "-ac", "1", "-ar", "16000", str(out)], check=True)
    m = WhisperModel("base.en", device="cpu", compute_type="int8")
    seg, _ = m.transcribe(str(out), language="en")
    text = " ".join(s.text.strip() for s in seg).lower()
    tmp.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    return text.replace(",", "").replace(".", "")


_wl = {}


def embed(x24: np.ndarray):
    import torch
    from transformers import AutoFeatureExtractor, WavLMForXVector

    if not _wl:
        _wl["fe"] = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
        _wl["m"] = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").eval()
    tmp = FIX.parent / "_e24.wav"
    sf.write(str(tmp), x24, 24000)
    out = tmp.with_suffix(".16.wav")
    subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(tmp), "-ac", "1", "-ar", "16000", str(out)], check=True)
    x, _ = sf.read(str(out), dtype="float32")
    tmp.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    with torch.no_grad():
        e = _wl["m"](**_wl["fe"](x[:160000], sampling_rate=16000, return_tensors="pt")).embeddings
    return torch.nn.functional.normalize(e, dim=-1)[0]


def loud(x):
    return 20 * np.log10(max(float(np.sqrt(np.mean(x * x))), 1e-9))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="auto")
    ap.add_argument("--out", default=str(ROOT / "qa_out_clone"))
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ref = load24(FIX / "reference_12s.wav")
    t = time.time()
    eng = C.Engine.load(device=a.device)
    print(f"loaded in {time.time() - t:.1f} s; providers {eng.providers}")
    problems = []
    ref_e = embed(ref)
    sims = []
    rtfs = []
    for i in (1, 2, 3):
        text = (FIX / f"{i}.txt").read_text(encoding="utf-8")
        old, sr_old = sf.read(str(FIX / f"{i}.wav"), dtype="float32")
        if old.ndim > 1:
            old = old.mean(axis=1)
        t = time.time()
        y = eng.speak(text, ref, seed=a.seed + i)
        took = time.time() - t
        y = V.level(y)                                                       # as the app does before saving
        sf.write(str(out / f"{i}.wav"), y, C.SAMPLE_RATE)
        dur = len(y) / C.SAMPLE_RATE
        said = words_of(y, C.SAMPLE_RATE)
        sim = float(embed(y) @ ref_e)
        sims.append(sim)
        rtfs.append(took / dur)
        old_dur = len(old) / sr_old
        peak = float(np.abs(y).max())
        d_loud = loud(y) - V.SPEECH_DB
        print(f"{i}: {dur:.1f} s of audio in {took:.1f} s (x{took / dur:.2f} real time); old {old_dur:.1f} s; peak {peak:.2f}; loudness {loud(y):.1f} dB (old {loud(old):.1f}); similarity {sim:.2f}; said {said!r}")
        for k in KEYS[i]:
            if k not in said:
                problems.append(f"{i}: speech recognition did not hear '{k}'")
        if abs(dur - old_dur) > 0.25 * old_dur:
            problems.append(f"{i}: length {dur:.1f} s vs {old_dur:.1f} s (more than 25 % apart)")
        if peak >= 0.99:
            problems.append(f"{i}: clipping (peak {peak:.2f})")
        if abs(d_loud) > 2.0:
            problems.append(f"{i}: loudness {loud(y):.1f} dB, not {V.SPEECH_DB:.0f} dB")
    print(f"mean speaker similarity {np.mean(sims):.2f}; mean real-time factor {np.mean(rtfs):.2f}")
    if np.mean(sims) < 0.95:
        problems.append(f"speaker similarity {np.mean(sims):.2f} < 0.95")
    print("no problems found" if not problems else "\n".join("PROBLEM: " + p for p in problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
