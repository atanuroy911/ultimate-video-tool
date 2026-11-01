"""Real check of the sound-aware pipeline on real recordings (public domain / CC0 from Wikimedia Commons, downloaded once into $TEMP/snd by this script):

  A) speech with a baby laughing and applause mixed in: the events must be found at the right times and the plan must show a matching emoji there;
  B) a recording with NO speech (baby laughing, applause, rain): the project must still be made, with sound captions, and render.

    python scripts/qa_sounds.py --url http://127.0.0.1:8771 --out qa_out6
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vt.util import find_tool  # noqa: E402

FF = find_tool("ffmpeg")
UA = {"User-Agent": "VideoTool-catalog/1.0 (https://github.com/video-tool/video-tool; local desktop app)"}
FILES = {"laugh": "File:72844 lonemonk approx-800-laughter-and-clapter-1.wav", "baby": "File:Baby 5 months old gabbling laughing practising voice.ogg", "applause": "File:277021 sandermotions applause-2.wav", "rain": "File:Rain (1).ogg"}


def fetch_clips(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for k, title in FILES.items():
        if (d / f"{k}.wav").exists():
            continue
        r = httpx.get("https://commons.wikimedia.org/w/api.php", params={"action": "query", "titles": title, "prop": "imageinfo", "iiprop": "url", "format": "json"}, headers=UA, timeout=30).json()
        ii = list(r["query"]["pages"].values())[0]["imageinfo"][0]
        raw = d / f"{k}.src"
        raw.write_bytes(httpx.get(ii["url"], headers=UA, timeout=180, follow_redirects=True).content)
        subprocess.run([FF, "-y", "-v", "error", "-i", str(raw), "-ac", "1", "-ar", "16000", str(d / f"{k}.wav")], check=True)


def seg(path: Path, a: float, b: float) -> np.ndarray:
    x, sr = sf.read(str(path), dtype="float32")
    return x[int(a * sr):int(b * sr)]


def wait(c, jid, timeout=1500):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "error", "cancelled"):
            if j["status"] != "done":
                raise RuntimeError(f"{j['status']} {j.get('error', '')[:300]}")
            return j
        time.sleep(2)
    raise TimeoutError


def make_project(c, wav: Path, title: str, lang="en") -> str:
    with wav.open("rb") as f:
        r = c.post("/api/projects", files={"audio": (wav.name, f, "audio/wav")}, data={"title": title, "language": lang, "aspect": "9:16", "theme": "auto", "pace": "normal", "kind": "explainer"})
    r.raise_for_status()
    jid, pid = (r.json().get("job") or {}).get("id"), r.json()["project"]["id"]
    if jid:
        try:
            wait(c, jid)
        except RuntimeError as e:
            return pid + "|" + str(e)
    return pid


def render(c, pid, out: Path) -> Path:
    j = c.post(f"/api/projects/{pid}/export", json={"aspects": ["9:16"], "quality": "draft", "gpu": True, "music": "none", "captions": True, "sfx_level": "off", "fps": 30})
    j.raise_for_status()
    wait(c, j.json()["id"])
    v = Path(c.get(f"/api/projects/{pid}/exports").json()[0]["path"])
    out.write_bytes(v.read_bytes())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8771")
    ap.add_argument("--out", default="qa_out6")
    ap.add_argument("--speech", default="samples/audio/long_48s.mp3")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    snd = Path(os.environ.get("TEMP", ".")) / "snd"
    fetch_clips(snd)
    c = httpx.Client(base_url=a.url, timeout=300)
    problems: list[str] = []

    # ---------------- A: speech + laughter + applause
    sp = out / "_speech.wav"
    subprocess.run([FF, "-y", "-v", "error", "-i", a.speech, "-ac", "1", "-ar", "16000", str(sp)], check=True)
    s1, s2 = seg(sp, 0, 14), seg(sp, 14, 26)
    laugh = seg(snd / "baby.wav", 107, 117)
    clap = seg(snd / "applause.wav", 0, 6)
    t_laugh = len(s1) / 16000
    t_clap = (len(s1) + len(laugh) + len(s2)) / 16000
    to_out = None
    mix = np.concatenate([s1, laugh * 0.9, s2, clap * 0.8]).astype("float32")
    wa = out / "mix_speech_laugh_applause.wav"
    sf.write(str(wa), mix, 16000)
    print(f"A: speech 0-{t_laugh:.0f}s, baby laughter {t_laugh:.0f}-{t_laugh + 10:.0f}s, speech, applause {t_clap:.0f}-{t_clap + 6:.0f}s")
    pid = make_project(c, wa, "QA sounds speech")
    if "|" in pid:
        problems.append("A: project failed: " + pid.split("|", 1)[1][:200])
    else:
        ev = c.get(f"/api/projects/{pid}/sound-events").json()
        keep = c.get(f"/api/projects/{pid}/audio").json()["keep"]

        def out_t(t):                                    # source time -> output time (the silence cutter shortens the recording)
            for k in keep:
                if k["s"] - 0.01 <= t <= k["e"] + 0.01:
                    return k["o0"] + (t - k["s"])
            return min(keep, key=lambda k: min(abs(k["s"] - t), abs(k["e"] - t)))["o0"]
        lo, hi = out_t(t_laugh), out_t(t_laugh + 10)
        co, ce = out_t(t_clap), out_t(t_clap + 5.9)
        print(f"A events: {[(e['concept'], e['start'], e['end'], e['score']) for e in ev['events']]}   (laughter at {lo:.1f}-{hi:.1f} s, applause at {co:.1f}-{ce:.1f} s in the output)")
        if not ev["analyzed"]:
            problems.append("A: the sounds stage did not run")
        laughs = [e for e in ev["events"] if e["concept"] in ("laughter", "baby_laughter")]
        claps = [e for e in ev["events"] if e["concept"] == "applause"]
        if not any(e["start"] < hi and e["end"] > lo for e in laughs):
            problems.append(f"A: no laughter event around {lo:.0f}-{hi:.0f} s")
        if not any(e["end"] > co and e["start"] < ce for e in claps):
            problems.append(f"A: no applause event around {co:.0f}-{ce:.0f} s")
        plan = c.get(f"/api/projects/{pid}/scenes").json()["plan"]["scenes"]
        stick = [(s["id"], e["emoji"], e.get("label")) for s in plan for e in s["elements"] if e["type"] == "sticker"]
        print("A stickers:", stick)
        if not any(em == "1f44f" for _, em, _ in stick):
            problems.append("A: the plan has no applause emoji")
        if not any(em in ("1f602", "1f476") for _, em, _ in stick):
            problems.append("A: the plan has no laughing / baby emoji")
        v = render(c, pid, out / "A_speech_sounds.mp4")
        print("A rendered", v.name)

    # ---------------- B: no speech at all
    nb = np.concatenate([seg(snd / "baby.wav", 106, 118), np.zeros(8000, dtype="float32"), seg(snd / "applause.wav", 0, 6), seg(snd / "rain.wav", 28, 40)]).astype("float32")
    wb = out / "sounds_only.wav"
    sf.write(str(wb), nb, 16000)
    pid2 = make_project(c, wb, "QA sounds only")
    if "|" in pid2:
        problems.append("B: project failed: " + pid2.split("|", 1)[1][:200])
    else:
        words = [w["text"] for w in c.get(f"/api/projects/{pid2}/transcript").json()["transcript"]["words"]]
        print("B captions:", " ".join(words))
        if not any("laugh" in w.lower() or "baby" in w.lower() for w in words) or not any("applaud" in w.lower() for w in words):
            problems.append("B: the sound captions do not name the laughter and the applause")
        v = render(c, pid2, out / "B_sounds_only.mp4")
        subprocess.run([FF, "-y", "-v", "error", "-ss", "20", "-i", str(v), "-frames:v", "1", str(out / "B_frame.png")], check=True)
        print("B rendered", v.name)
    print("\nPROBLEMS:" if problems else "\nno problems found")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
