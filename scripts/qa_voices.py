"""Real check of voice cloning and the offline Kokoro voices through the running Studio: a script becomes a video in a cloned voice and in a Kokoro voice, the words that were
spoken are checked with speech recognition, and the speaker is compared with the reference voice (WavLM speaker verification).

Any running Studio will do (cloning runs inside the app's own Python; the model is fetched on first use):  uvicorn vt.server.app:app --port 8771
    python scripts/qa_voices.py --url http://127.0.0.1:8771 --reference <a wav of 10+ s of a voice you may use> --out qa_out7
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vt.util import find_tool  # noqa: E402

SCRIPT = "Good morning everyone. Today we will talk about saving money. Small habits make a big difference over a year."


def wait(c, jid, timeout=1800):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "error", "cancelled"):
            if j["status"] != "done":
                raise RuntimeError(f"{j['status']} {j.get('error', '')[:300]}")
            return j
        time.sleep(2)
    raise TimeoutError


def words_of(path: Path) -> str:
    from faster_whisper import WhisperModel

    m = WhisperModel("base.en", device="cpu", compute_type="int8")
    seg, _ = m.transcribe(str(path), language="en")
    return " ".join(s.text.strip() for s in seg).lower()


def embed(path: Path, seconds=10):
    import torch
    from transformers import AutoFeatureExtractor, WavLMForXVector

    fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
    m = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").eval()
    tmp = path.with_suffix(".16k.wav")
    subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", str(tmp)], check=True)
    x, _ = sf.read(str(tmp), dtype="float32")
    tmp.unlink(missing_ok=True)
    with torch.no_grad():
        e = m(**fe(x[:16000 * seconds], sampling_rate=16000, return_tensors="pt")).embeddings
    return torch.nn.functional.normalize(e, dim=-1)[0]


def project_audio(c, pid, out: Path) -> Path:
    j = c.post(f"/api/projects/{pid}/export", json={"aspects": ["9:16"], "quality": "draft", "gpu": True, "music": "none", "captions": True, "sfx_level": "off", "fps": 30})
    j.raise_for_status()
    wait(c, j.json()["id"])
    v = Path(c.get(f"/api/projects/{pid}/exports").json()[0]["path"])
    out.write_bytes(v.read_bytes())
    wav = out.with_suffix(".wav")
    subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(out), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    return wav


def make(c, engine, voice, title):
    r = c.post("/api/projects/from-script", json={"script": SCRIPT, "title": title, "language": "en", "engine": engine, "voice": voice, "rate": 1.0, "aspect": "9:16", "theme": "auto", "pace": "normal"})
    r.raise_for_status()
    j = r.json()
    wait(c, j["job"]["id"])
    return j["project"]["id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8771")
    ap.add_argument("--reference", required=True)
    ap.add_argument("--out", default="qa_out7")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    c = httpx.Client(base_url=a.url, timeout=300)
    problems: list[str] = []
    ref = Path(a.reference)
    st = c.get("/api/my-voices").json()
    print("cloning available:", st["available"])
    if not st["available"]:
        print("voice cloning is not available in this server (is onnxruntime installed?)")
        return 2
    r = c.post("/api/my-voices", files={"file": (ref.name, ref.read_bytes(), "audio/wav")}, data={"name": "QA reference", "consent": "false"})
    if r.status_code != 422:
        problems.append("a voice was accepted without consent")
    r = c.post("/api/my-voices", files={"file": (ref.name, ref.read_bytes(), "audio/wav")}, data={"name": "QA reference", "consent": "true"})
    r.raise_for_status()
    vid = r.json()["id"]
    print("voice", vid, r.json()["seconds"], "s")
    engines = {e["id"]: e for e in c.get("/api/voices").json()}
    if not engines["clone"]["available"] or not any(v["id"] == vid for v in engines["clone"]["voices"]):
        problems.append("the engine list does not offer the new voice")
    ref_e = embed(ref)
    results = {}
    for label, engine, voice in (("clone", "clone", vid), ("kokoro", "kokoro", "af_heart")):
        t0 = time.time()
        try:
            pid = make(c, engine, voice, f"QA voice {label}")
        except Exception as e:
            problems.append(f"{label}: could not make the video: {str(e)[:200]}")
            continue
        wav = project_audio(c, pid, out / f"voice_{label}.mp4")
        said = words_of(wav)
        sim = float(__import__("torch").dot(ref_e, embed(wav)))
        results[label] = (said, sim)
        print(f"{label}: made in {time.time() - t0:.0f} s; said: {said!r}; similarity to the reference voice {sim:.2f}")
        for key in ("good morning", "saving money", "big difference"):
            if key not in said:
                problems.append(f"{label}: the spoken audio does not contain '{key}'")
    if "clone" in results and "kokoro" in results and not results["clone"][1] > results["kokoro"][1] + 0.05:
        problems.append("the cloned voice is not clearly closer to the reference than another voice")
    if "clone" in results and results["clone"][1] < 0.8:
        problems.append(f"the cloned voice is not close to the reference ({results['clone'][1]:.2f})")
    c.delete(f"/api/my-voices/{vid}")
    print("\nPROBLEMS:" if problems else "\nno problems found")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
