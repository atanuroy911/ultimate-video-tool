"""Real checks of the media bin and the voice editor through the running Studio: free catalogue clips become scene backdrops with readable captions, and cut / mute / volume
edits of the voice really change the exported file (shorter by the cut, silent where muted, quieter where lowered).

    python scripts/qa_media_audio.py --url http://127.0.0.1:8771 --out qa_out3
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vt.util import find_tool  # noqa: E402

FF = find_tool("ffmpeg")


def wait(c, jid, label, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "error", "cancelled"):
            if j["status"] != "done":
                raise RuntimeError(f"{label}: {j['status']} {j.get('error', '')[:300]}")
            return j
        time.sleep(1.5)
    raise TimeoutError(label)


def pcm(path: Path) -> np.ndarray:
    r = subprocess.run([FF, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def dur(path: Path) -> float:
    return float(subprocess.run([find_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout)


def render(c, pid, out: Path, music="none", aspect="9:16") -> Path:
    j = c.post(f"/api/projects/{pid}/export", json={"aspects": [aspect], "quality": "draft", "gpu": True, "music": music, "captions": True, "sfx_level": "off", "fps": 30})
    j.raise_for_status()
    wait(c, j.json()["id"], "render", 1500)
    f = Path(c.get(f"/api/projects/{pid}/exports").json()[0]["path"])
    out.write_bytes(f.read_bytes())
    return out


def frame(video: Path, t: float, png: Path) -> None:
    subprocess.run([FF, "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", str(png)], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8771")
    ap.add_argument("--out", default="qa_out3")
    ap.add_argument("--speech", default="ia-evelina-0812-librivox")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    c = httpx.Client(base_url=a.url, timeout=180)
    problems: list[str] = []
    r = c.post(f"/api/catalog/{a.speech}/project", json={"language": "en", "aspect": "9:16", "seconds": 45, "title": "QA media and audio"})
    r.raise_for_status()
    pid = wait(c, r.json()["id"], "sample")["result"]["project"]
    for _ in range(600):
        st = c.get(f"/api/projects/{pid}").json()
        if not st.get("active_job") and st["status"] != "processing":
            break
        time.sleep(2)
    print("project", pid, st["status"])

    # ---- media: two free clips become part of the video
    for cid in ("ia-videoplayback-22-20260326", "ia-tadano-le-dice-linda-a-komi-san-komi-san-komyshou-"):
        ents = [e["id"] for e in c.get("/api/catalog?kind=video").json()["entries"] if e["id"].startswith(cid[:30])]
        if not ents:
            problems.append(f"catalogue entry {cid} not found")
            continue
        rr = c.post(f"/api/projects/{pid}/catalog/{ents[0]}/add")
        print("add media", ents[0], rr.status_code, rr.text[:80])
        if rr.status_code != 200:
            problems.append(f"adding {ents[0]} failed: {rr.status_code} {rr.text[:100]}")
    media = c.get(f"/api/projects/{pid}/media").json()
    print("media bin:", [(m["id"], m["kind"], m["width"], m["height"]) for m in media])
    wait(c, c.post(f"/api/projects/{pid}/replan").json()["id"], "replan")
    plan = c.get(f"/api/projects/{pid}/scenes").json()["plan"]["scenes"]
    uses = [s["id"] for s in plan if s.get("backdrop") or any(e["type"] in ("media_frame", "device") for e in s["elements"])]
    print("scenes using media:", uses, "of", len(plan))
    if not uses:
        # show the first scene as a picture scene explicitly
        for m in media:
            rr = c.post(f"/api/projects/{pid}/scenes/{plan[0]['id']}/reshow", json={"scene_type": "media_hero", "media": m["id"]})
            print("reshow", rr.status_code, rr.text[:120])
            if rr.status_code == 200:
                break
        plan = c.get(f"/api/projects/{pid}/scenes").json()["plan"]["scenes"]
        uses = [s["id"] for s in plan if s.get("backdrop") or any(e["type"] in ("media_frame", "device") for e in s["elements"])]
    if not uses:
        problems.append("no scene used the added media")
    v1 = render(c, pid, out / "media_video.mp4", music="none")
    print("rendered", v1.name, round(dur(v1), 2), "s")
    timing = c.get(f"/api/projects/{pid}/scenes").json()["timing"]["scenes"]
    for s in plan:
        if s["id"] in uses:
            t = next(x for x in timing if x["id"] == s["id"])
            frame(v1, (t["start"] + t["end"]) / 2, out / f"media_scene_{s['id']}.png")
            print("frame of", s["id"], "->", out / f"media_scene_{s['id']}.png", "backdrop:", bool(s.get("backdrop")))
            break

    # ---- voice edits change the exported file
    base_audio = pcm(v1)
    d0 = dur(v1)
    av = c.get(f"/api/projects/{pid}/audio").json()
    d_src = av["duration"]
    c.post(f"/api/projects/{pid}/audio/cut", json={"start": 5.0, "end": 7.0}).raise_for_status()
    c.post(f"/api/projects/{pid}/audio/mute", json={"start": 10.0, "end": 12.0, "on": True}).raise_for_status()
    c.post(f"/api/projects/{pid}/audio/gain", json={"start": 14.0, "end": 16.0, "db": -12}).raise_for_status()
    v2 = render(c, pid, out / "voice_edited.mp4", music="none")
    d2 = dur(v2)
    a2 = pcm(v2)
    rms = lambda x: float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0  # noqa: E731
    seg = lambda x, t0, t1: x[int(t0 * 16000): int(t1 * 16000)]  # noqa: E731
    print(f"duration {d0:.2f} -> {d2:.2f} (cut 2.00 s)")
    if abs((d0 - d2) - 2.0) > 0.35:
        problems.append(f"the 2 s cut changed the length by {d0 - d2:.2f} s")
    # edits are in output time as they were when asked: the cut (5-7) happened first, so later windows are 2 s earlier in the edited file than in the first render
    ref_after, ref_before = rms(seg(a2, 20.0, 24.0)), rms(seg(base_audio, 22.0, 26.0))       # an untouched stretch: the loudness normaliser moves everything by this much
    offset_db = 20 * np.log10(max(ref_after, 1e-6) / max(ref_before, 1e-6))
    m_after, m_before = rms(seg(a2, 10.0, 12.0)), rms(seg(base_audio, 12.0, 14.0))
    print(f"muted window rms {m_after:.4f} (before {m_before:.4f})")
    if m_before > 0.01 and m_after > m_before * 0.1:
        problems.append("the muted range is not silent in the export")
    g_after, g_before = rms(seg(a2, 14.0, 16.0)), rms(seg(base_audio, 16.0, 18.0))
    ratio_db = 20 * np.log10(max(g_after, 1e-6) / max(g_before, 1e-6)) - offset_db
    print(f"gain window: {ratio_db:.1f} dB vs unedited after normaliser offset {offset_db:.1f} dB (asked -12)")
    if g_before > 0.01 and not (-15 <= ratio_db <= -9):
        problems.append(f"the -12 dB range came out {ratio_db:.1f} dB")
    # undo everything: the project returns to its first state
    for _ in range(3):
        c.post(f"/api/projects/{pid}/audio/undo").raise_for_status()
    back = c.get(f"/api/projects/{pid}/audio").json()
    if abs(back["duration"] - d_src) > 0.05:
        problems.append("undo did not restore the voice")
    (out / "report3.json").write_text(json.dumps({"problems": problems, "d0": d0, "d2": d2}, indent=2), encoding="utf-8")
    print("\nPROBLEMS:" if problems else "\nno problems found")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
