"""Real end-to-end generation through the running Studio API: upload a recording, process it, pick a mode, render the MP4, then inspect the file
(container, codecs, size, duration, loudness, frames per scene) and write a contact sheet per output.

    python scripts/qa_generate.py --url http://127.0.0.1:8771 --out qa_out --audio samples/audio/bn_plain.mp3 --lang bn

It never mocks anything: every number in the report comes from ffprobe / ffmpeg on the file the Studio produced.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vt.util import find_tool  # noqa: E402

MODES = [("pictures", "explainer", "general"), ("story", "explainer", "story"), ("product", "explainer", "product"), ("stick", "stick", "auto"), ("emoji", "emoji", "auto")]


def wait(c: httpx.Client, job_id: str, label: str, timeout: float = 900) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "error", "cancelled"):
            if j["status"] != "done":
                raise RuntimeError(f"{label}: {j['status']} {j.get('error', '')[:300]}")
            return j
        time.sleep(1.5)
    raise TimeoutError(label)


def probe(path: Path) -> dict:
    r = subprocess.run([find_tool("ffprobe"), "-v", "error", "-show_entries",
                        "format=format_name,duration,size,bit_rate:stream=codec_type,codec_name,profile,level,width,height,r_frame_rate,pix_fmt,sample_rate,channels",
                        "-of", "json", str(path)], capture_output=True, text=True)
    j = json.loads(r.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), {})
    return {"container": j["format"]["format_name"], "duration": float(j["format"]["duration"]), "mb": round(int(j["format"]["size"]) / 1e6, 2),
            "video": f"{v.get('codec_name')} {v.get('profile')} {v.get('width')}x{v.get('height')} {v.get('r_frame_rate')} {v.get('pix_fmt')}", "audio": f"{a.get('codec_name')} {a.get('sample_rate')}Hz x{a.get('channels')}" if a else "NONE",
            "_v": v, "_a": a}


def loudness(path: Path) -> dict:
    r = subprocess.run([find_tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    import re

    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    try:
        j = json.loads(m.group(0))
        return {"lufs": float(j["input_i"]), "peak_db": float(j["input_tp"])}
    except Exception:
        return {}


def silence_gaps(path: Path) -> int:
    r = subprocess.run([find_tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-af", "silencedetect=noise=-50dB:d=1.5", "-f", "null", "-"], capture_output=True, text=True)
    return r.stderr.count("silence_start")


def sheet(video: Path, out: Path, n: int = 6) -> None:
    dur = probe(video)["duration"]
    ff = find_tool("ffmpeg")
    parts = []
    tmp = out.parent / f"_{out.stem}"
    tmp.mkdir(exist_ok=True)
    for i in range(n):
        f = tmp / f"{i}.png"
        subprocess.run([ff, "-y", "-v", "error", "-ss", f"{dur * (i + 0.5) / n:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=-2:480", str(f)], check=True)
        parts.append(f)
    from PIL import Image

    ims = [Image.open(p) for p in parts]
    w, h = ims[0].size
    sh = Image.new("RGB", (w * n, h), "white")
    for i, im in enumerate(ims):
        sh.paste(im, (i * w, 0))
    sh.save(out)
    for p in parts:
        p.unlink()
    tmp.rmdir()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8771")
    ap.add_argument("--out", default="qa_out")
    ap.add_argument("--audio", default="samples/audio/bn_plain.mp3")
    ap.add_argument("--lang", default="bn")
    ap.add_argument("--aspects", default="9:16,16:9")
    ap.add_argument("--music", default="calm-01")
    ap.add_argument("--modes", default=",".join(m[0] for m in MODES))
    ap.add_argument("--quality", default="draft")
    ap.add_argument("--catalog-speech", default="", help="catalogue id of a free speech recording to make the project from (downloaded for real)")
    ap.add_argument("--catalog-music", default="", help="catalogue id of a free music track to install and use")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    c = httpx.Client(base_url=a.url, timeout=120)
    results = []
    # one project per recording; modes are applied to copies so each output is independent
    if a.catalog_music:
        r = c.post(f"/api/catalog/{a.catalog_music}/music")
        r.raise_for_status()
        a.music = r.json()["music"]
        print("installed music", a.music)
    if a.catalog_speech:
        r = c.post(f"/api/catalog/{a.catalog_speech}/project", json={"language": a.lang, "aspect": "9:16", "seconds": 60})
        r.raise_for_status()
        j = wait(c, r.json()["id"], "download the sample", 600)
        pid = j["result"]["project"]
        for _ in range(600):
            st = c.get(f"/api/projects/{pid}").json()
            if not st.get("active_job") and st["status"] != "processing":
                break
            time.sleep(2)
    else:
        with open(a.audio, "rb") as f:
            r = c.post("/api/projects", files={"audio": (Path(a.audio).name, f, "audio/mpeg")}, data={"title": f"QA {Path(a.audio).stem}", "language": a.lang, "aspect": "9:16", "theme": "auto", "pace": "normal"})
        r.raise_for_status()
        base = r.json()
        pid = base["project"]["id"]
        wait(c, base["job"]["id"], "process the audio")
    print("processed", pid)
    for name, kind, usecase in [m for m in MODES if m[0] in a.modes.split(",")]:
        d = c.post(f"/api/projects/{pid}/duplicate").json()
        did = d["id"]
        c.patch(f"/api/projects/{did}", json={"usecase": usecase})
        job = c.post(f"/api/projects/{did}/script/generate?kind={kind}").json() if kind != "explainer" else None
        if job:
            wait(c, job["id"], f"{name}: direct")
        else:
            wait(c, c.post(f"/api/projects/{did}/replan").json()["id"], f"{name}: replan")
        plan = c.get(f"/api/projects/{did}/scenes").json()["plan"]["scenes"]
        for asp in a.aspects.split(","):
            for music in (a.music, "none"):
                body = {"aspects": [asp], "quality": a.quality, "gpu": True, "music": music, "music_volume": 0.14, "sfx_level": "normal", "fps": 30, "captions": True}
                j = c.post(f"/api/projects/{did}/export", json=body)
                j.raise_for_status()
                res = wait(c, j.json()["id"], f"{name} {asp} music={music}: render", 1500)
                files = c.get(f"/api/projects/{did}/exports").json()
                mp4 = Path(files[0]["path"])
                dest = out / f"{name}_{asp.replace(':', 'x')}_{'music' if music != 'none' else 'nomusic'}.mp4"
                dest.write_bytes(mp4.read_bytes())
                info = probe(dest)
                row = {"mode": name, "aspect": asp, "music": music, "file": str(dest), "scenes": len(plan), "kinds": sorted({s.get("archetype") or "-" for s in plan}),
                       "elements": sorted({e["type"] for s in plan for e in s["elements"]}), "stick": any(s.get("stick") for s in plan), **{k: v for k, v in info.items() if not k.startswith("_")},
                       **loudness(dest), "silent_gaps": silence_gaps(dest)}
                sheet(dest, dest.with_suffix(".png"))
                results.append(row)
                print(json.dumps({k: row.get(k) for k in ("mode", "aspect", "music", "scenes", "duration", "mb", "video", "audio", "lufs", "peak_db", "silent_gaps", "kinds")}, ensure_ascii=False), flush=True)
    (out / "report.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
