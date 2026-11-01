"""Spike: can Concat's headless engine (`concat --mcp headless`, MCP over stdio) be driven from Python to composite what Video Tool makes?

It creates a project, imports a video and a transparent PNG, puts the video on the base lane, the PNG on a lane above it and a title over both, exports an MP4 and checks the result
with ffprobe and by looking at pixels. Nothing is installed: the MSI is unpacked into a folder (`msiexec /a`) and the exe is run from there.

    python scripts/spike_concat.py --exe <concat.exe> --video <video> --out qa_out10
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vt.util import find_tool  # noqa: E402


from vt.concat_client import Concat  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", default="qa_out10")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="concat-spike-"))
    png = work / "badge.png"
    im = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((20, 20, 380, 380), fill=(230, 40, 40, 255))             # a red disc, transparent corners
    im.save(png)
    problems: list[str] = []
    c = Concat(a.exe)
    try:
        v = c.call("concat_version")
        print("concat:", json.dumps(v)[:200])
        t0 = time.time()
        proj = c.call("project_create", location=str(work), name="spike")
        folder = str(work / "spike")
        mv = c.call("media_import", path=folder, file=str(Path(a.video).resolve()))
        mp = c.call("media_import", path=folder, file=str(png))
        print("imported:", json.dumps(mv)[:160], "|", json.dumps(mp)[:160])
        vid_id = mv.get("createdId") or mv.get("summary", {}).get("createdId")
        png_id = mp.get("createdId") or mp.get("summary", {}).get("createdId")
        tl = c.call("timeline_read", path=folder)
        tracks = [t["id"] for t in (tl.get("tracks") or tl.get("timeline", {}).get("tracks") or [])]
        print("tracks:", tracks)
        base = tracks[0] if tracks else None
        up = c.call("track_add", path=folder)
        up_id = up.get("createdId") or up.get("summary", {}).get("createdId")
        c.call("clip_add", path=folder, mediaId=vid_id, trackId=base, start=0.0)
        pc = c.call("clip_add", path=folder, mediaId=png_id, trackId=up_id, start=3.0)
        clip_id = pc.get("createdId") or pc.get("summary", {}).get("createdId")
        c.call("clip_transform", path=folder, clipId=clip_id, scale=0.35, offsetX=0.32, offsetY=-0.28)
        c.call("title_add", path=folder, start=1.0, duration=4.0, style={"content": "Hello from Concat", "fontSize": 0.08})
        print(f"project built in {time.time() - t0:.1f} s")
        res = out / "concat_spike.mp4"
        res.unlink(missing_ok=True)
        t1 = time.time()
        job = c.call("export_start", path=folder, output=str(res.resolve()))
        jid = job.get("job") or job.get("jobId")
        st = c.call("export_wait", job=jid, timeoutSeconds=600)
        print(f"export {st.get('state')} in {time.time() - t1:.1f} s:", json.dumps(st)[:200])
        if st.get("state") != "done" or not res.exists():
            problems.append(f"the export did not finish: {st}")
        else:
            ff = find_tool("ffprobe")
            info = json.loads(subprocess.run([ff, "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,duration", "-of", "json", str(res)], capture_output=True, text=True).stdout)
            print("output streams:", [(s["codec_type"], s.get("codec_name"), s.get("width"), s.get("height"), s.get("duration")) for s in info["streams"]])

            def frame(t):
                f = out / f"concat_{t}.png"
                subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-ss", str(t), "-i", str(res), "-frames:v", "1", str(f)], check=True)
                return np.asarray(Image.open(f).convert("RGB")).astype(int)
            f2, f6 = frame(2.0), frame(6.0)
            h, w = f6.shape[:2]
            cx, cy = int(w * (0.5 + 0.32)), int(h * (0.5 - 0.28))
            patch = f6[cy - 8:cy + 8, cx - 8:cx + 8].reshape(-1, 3).mean(axis=0)
            before = f2[cy - 8:cy + 8, cx - 8:cx + 8].reshape(-1, 3).mean(axis=0)
            print(f"badge position at 6 s {patch.round()}, same place at 2 s {before.round()}")
            if not (patch[0] > 180 and patch[1] < 90 and patch[2] < 90):
                problems.append("the transparent PNG is not composited (red disc missing where it was placed)")
            if abs(before - patch).sum() < 120:
                problems.append("the PNG is also there before its start time")
            title = f2[int(h * 0.35):int(h * 0.65), int(w * 0.2):int(w * 0.8)]
            if title.std() < 8:
                problems.append("no title could be seen at 2 s")
    except Exception as e:
        problems.append(f"{type(e).__name__}: {str(e)[:300]}")
    finally:
        c.close()
    print("\nPROBLEMS:" if problems else "\nno problems found")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
