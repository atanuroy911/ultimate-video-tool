"""Take one recording through the whole pipeline on the GPU server with music, as a client on its network would, and fetch the result safely.

    python scripts/lab/run_recording.py "<recording.mp4>" [--out DIR] [--music auto] [--edit auto]

Steps: resumable upload (a computer on the server's network needs no key; --key is for one outside it) -> create the project with the full pipeline -> wait for the plan -> export with the music
(GPU render on the server) -> download to a .part file, check the size, then rename. Prints what the server reports at each step.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

BASE = "http://192.168.123.47:8790"
CHUNK = 32 * 1024 * 1024


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--key", default=os.environ.get("VT_KEY", ""))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "dist/recording-run"))
    ap.add_argument("--music", default="auto")
    ap.add_argument("--edit", default="auto", choices=["auto", "subtitles", "screen"])
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--title", default="")
    ap.add_argument("--project", default="", help="use this existing project instead of uploading")
    a = ap.parse_args()
    src = Path(a.file)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    c = httpx.Client(base_url=BASE, timeout=httpx.Timeout(120, connect=15))

    if a.key:
        c.headers["Authorization"] = f"Bearer {a.key}"

    pid = a.project
    if not pid:
        size = src.stat().st_size
        u = c.post("/api/uploads", json={"name": src.name, "size": size}).json()
        uid, sent, t0 = u["id"] if "id" in u else u["upload"], 0, time.time()
        with src.open("rb") as f:
            while sent < size:
                piece = f.read(CHUNK)
                r = c.put(f"/api/uploads/{uid}", params={"offset": sent}, content=piece, timeout=300)
                r.raise_for_status()
                sent += len(piece)
                print(f"upload {sent / 1e6:.0f}/{size / 1e6:.0f} MB", flush=True)
        print(f"uploaded in {time.time() - t0:.0f} s", flush=True)
        opts = {"recording_edit": a.edit, "music": a.music, "music_volume": 0.12}
        r = c.post("/api/projects", data={"audio_upload": uid, "title": a.title or src.stem, "language": "en", "aspect": a.aspect, "theme": "auto",
                                          "options": json.dumps(opts), "start": "true", "usecase": "auto", "kind": "explainer"})
        r.raise_for_status()
        body = r.json()
        pid, job = body["project"]["id"], (body.get("job") or {}).get("id")
        print("project", pid, "job", job, flush=True)
        (out / "project.txt").write_text(pid, encoding="utf-8")
        t = time.time()
        last = ""
        while job:
            j = c.get(f"/api/jobs/{job}").json()
            line = f"{j['status']} {j.get('stage', '')} {int(j.get('frac', 0) * 100)}% {j.get('msg', '')[:90]}"
            if line != last:
                print(f"[{time.time() - t:5.0f}s] {line}", flush=True)
                last = line
            if j["status"] in ("done", "error", "cancelled"):
                if j["status"] != "done":
                    print("JOB FAILED:", j.get("error", "")[:600])
                    return 1
                break
            time.sleep(10)

    r = c.post(f"/api/projects/{pid}/export", json={"aspects": [a.aspect], "quality": "delivery", "gpu": True, "music": "project", "captions": True})
    r.raise_for_status()
    job = r.json()["id"]
    t = time.time()
    last = ""
    while True:
        j = c.get(f"/api/jobs/{job}").json()
        line = f"{j['status']} {int(j.get('frac', 0) * 100)}% {j.get('msg', '')[:90]}"
        if line != last:
            print(f"[export {time.time() - t:5.0f}s] {line}", flush=True)
            last = line
        if j["status"] in ("done", "error", "cancelled"):
            if j["status"] != "done":
                print("EXPORT FAILED:", j.get("error", "")[:600])
                return 1
            break
        time.sleep(10)

    files = c.get(f"/api/projects/{pid}/exports").json()
    f = files[0]
    print(json.dumps({k: f[k] for k in ("name", "size", "retention", "judges", "acceleration")}, indent=1, default=str)[:2500])
    dest = out / f["name"]
    part = dest.with_name(dest.name + ".part")
    with c.stream("GET", f["url"], timeout=600) as resp:
        resp.raise_for_status()
        with part.open("wb") as fh:
            for chunk in resp.iter_bytes(1 << 20):
                fh.write(chunk)
    if part.stat().st_size != f["size"]:
        raise SystemExit(f"download incomplete: {part.stat().st_size} of {f['size']} bytes (kept as {part.name}; nothing replaced)")
    part.replace(dest)
    if f.get("srt"):
        s = c.get(f["srt"])
        if s.status_code == 200:
            dest.with_suffix(".srt").write_bytes(s.content)
    print("DOWNLOADED", dest, dest.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
