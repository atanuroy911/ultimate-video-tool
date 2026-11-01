"""A real export with layers: a text clip, a picture, a video clip with its own sound and an audio clip are put on extra tracks, the video is rendered, and the pictures
and the sound are checked at the places the clips were put.

    python scripts/qa_layers.py --url http://127.0.0.1:8771 --project <id with a video in its media bin> --out qa_out5
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
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vt.util import find_tool  # noqa: E402

FF = find_tool("ffmpeg")


def wait(c, jid, timeout=1500):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "error", "cancelled"):
            if j["status"] != "done":
                raise RuntimeError(f"{j['status']} {j.get('error', '')[:300]}")
            return j
        time.sleep(1.5)
    raise TimeoutError


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8771")
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", default="qa_out5")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    c = httpx.Client(base_url=a.url, timeout=300)
    pid = a.project
    problems: list[str] = []
    media = c.get(f"/api/projects/{pid}/media").json()
    video = next((m for m in media if m["kind"] == "video"), None)
    if not video:
        print("the project needs a video in its media bin")
        return 2
    pic = out / "qa_layer_pic.png"
    Image.new("RGB", (640, 360), (30, 120, 220)).save(pic)
    up = c.post(f"/api/projects/{pid}/media", files={"file": ("qa_layer_pic.png", pic.read_bytes(), "image/png")})
    up.raise_for_status()
    pic_id = up.json()["id"]
    beep = out / "qa_beep.wav"
    t = np.arange(2 * 48000) / 48000
    sf.write(str(beep), (0.6 * np.sin(2 * np.pi * 880 * t)).astype("float32"), 48000)
    s = c.post(f"/api/projects/{pid}/sounds", files={"file": ("qa_beep.wav", beep.read_bytes(), "audio/wav")})
    s.raise_for_status()
    snd = s.json()["id"]
    dur = c.get(f"/api/projects/{pid}/layers").json()["duration"]
    print("project", pid, "duration", dur, "video", video["id"], "pic", pic_id, "sound", snd)
    doc = {"v": 1,
           "tracks": [{"id": "t1", "name": "Overlay", "kind": "visual"}, {"id": "t2", "name": "B-roll", "kind": "visual"}, {"id": "a1", "name": "Sound", "kind": "audio"}],
           "clips": [
               {"id": "c1", "type": "text", "track": "t1", "start": 2.0, "dur": 3.0, "text": "A title of my own", "x": 0.5, "y": 0.2, "w": 0.8, "fade_in": 0.3, "fade_out": 0.3,
                "style": {"size": 0.07, "color": "#ffffff", "bg": "#1b1b1b", "weight": 800}},
               {"id": "c2", "type": "media", "track": "t2", "start": 6.0, "dur": 3.0, "media": pic_id, "x": 0.5, "y": 0.45, "w": 0.7},
               {"id": "c3", "type": "media", "track": "t2", "start": 10.0, "dur": 4.0, "media": video["id"], "x": 0.5, "y": 0.5, "w": 1.0, "h": 0.5, "fit": "cover", "volume": 0.0},
               {"id": "c4", "type": "audio", "track": "a1", "start": 7.0, "dur": 1.5, "media": snd, "volume": 1.0}]}
    r = c.put(f"/api/projects/{pid}/layers", json={"doc": doc})
    print("saved layers:", r.status_code, r.text[:160])
    if r.status_code != 200:
        return 1
    j = c.post(f"/api/projects/{pid}/export", json={"aspects": ["9:16"], "quality": "draft", "gpu": True, "music": "none", "captions": True, "sfx_level": "off", "fps": 30})
    j.raise_for_status()
    wait(c, j.json()["id"])
    v = Path(c.get(f"/api/projects/{pid}/exports").json()[0]["path"])
    final = out / "layers_video.mp4"
    final.write_bytes(v.read_bytes())
    for name, tt in (("title", 3.5), ("picture", 7.5), ("video", 12.0), ("plain", 1.0)):
        subprocess.run([FF, "-y", "-v", "error", "-ss", str(tt), "-i", str(final), "-frames:v", "1", str(out / f"layer_{name}.png")], check=True)
    px = lambda n: np.asarray(Image.open(out / f"layer_{n}.png").convert("RGB")).astype(float)       # noqa: E731
    h, w = px("plain").shape[:2]
    # the picture clip is blue (30,120,220) in the middle of the frame at 7.5 s and not at 1 s
    mid = lambda a_: a_[int(h * 0.40):int(h * 0.50), int(w * 0.35):int(w * 0.65)].mean(axis=(0, 1))     # noqa: E731
    blue = np.array([30, 120, 220], dtype=float)
    d_in, d_out = np.abs(mid(px("picture")) - blue).sum(), np.abs(mid(px("plain")) - blue).sum()
    print(f"picture clip: distance to its colour {d_in:.0f} inside the clip, {d_out:.0f} outside")
    if not (d_in < 60 and d_out > 120):
        problems.append("the picture layer is not drawn where it was placed")
    top = lambda a_: a_[int(h * 0.15):int(h * 0.25), int(w * 0.1):int(w * 0.9)]                       # noqa: E731
    dark_in = (top(px("title")).mean(axis=2) < 50).mean()
    dark_out = (top(px("plain")).mean(axis=2) < 50).mean()
    print(f"title plate: dark share {dark_in:.2f} at 3.5 s, {dark_out:.2f} at 1 s")
    if not (dark_in > 0.15 and dark_in > dark_out + 0.1):
        problems.append("the text layer's plate is not visible at its time")
    raw = subprocess.run([FF, "-v", "error", "-i", str(final), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    rms = lambda a_, b_: float(np.sqrt(np.mean(x[int(a_ * 16000):int(b_ * 16000)] ** 2)))             # noqa: E731
    # the beep is a pure 880 Hz tone: look for energy at that frequency in its window against the same window one second earlier
    def tone(a_, b_):
        seg = x[int(a_ * 16000):int(b_ * 16000)]
        if len(seg) < 1000:
            return 0.0
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f = np.fft.rfftfreq(len(seg), 1 / 16000)
        return float(spec[(f > 860) & (f < 900)].sum() / (spec.sum() + 1e-9))
    t_in, t_out = tone(7.2, 8.3), tone(5.5, 6.6)
    print(f"880 Hz share: {t_in:.2f} inside the sound clip, {t_out:.2f} before it")
    if not (t_in > 0.1 and t_in > 3 * t_out):              # the voice is also speaking there, so the tone is a share of a mix
        problems.append("the audio layer is not heard at its time")
    print("\nPROBLEMS:" if problems else "\nno problems found")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
