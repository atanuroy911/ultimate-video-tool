"""Real check of the A-roll on a real talking-head video: it is imported as a video, the speaker's picture is kept and cut like the voice, the plan shows the speaker where nothing better
illustrates the words, and the rendered picture matches the right moment of the source with the face inside the frame - in 9:16 and 16:9.

    python scripts/qa_aroll.py --url http://127.0.0.1:8771 --video <a talking-head video> --out qa_out8
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vt.director.media import detect_faces  # noqa: E402
from vt.util import find_tool  # noqa: E402

FF = find_tool("ffmpeg")


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


def frame(video: Path, t: float, out: Path, scale: str = "") -> np.ndarray:
    subprocess.run([FF, "-y", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1"] + (["-vf", scale] if scale else []) + [str(out)], check=True)
    return np.asarray(Image.open(out).convert("RGB"))


def gray_small(im: np.ndarray, size=(48, 48)) -> np.ndarray:
    g = np.asarray(Image.fromarray(im).convert("L").resize(size, Image.BILINEAR), dtype="float32")
    return (g - g.mean()) / (g.std() + 1e-6)


def cover_crop(im: np.ndarray, aspect: float, fx: float) -> np.ndarray:
    h, w = im.shape[:2]
    if w / h > aspect:
        nw = int(round(h * aspect))
        x0 = int(round(min(max(0, fx * w - nw / 2), w - nw)))
        return im[:, x0:x0 + nw]
    nh = int(round(w / aspect))
    return im[(h - nh) // 2:(h - nh) // 2 + nh]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8771")
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", default="qa_out8")
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    src = Path(a.video)
    c = httpx.Client(base_url=a.url, timeout=600)
    problems: list[str] = []
    with src.open("rb") as f:
        r = c.post("/api/projects", files={"audio": (src.name, f, "video/webm")}, data={"title": "QA A-roll", "language": a.lang, "aspect": "9:16", "theme": "auto", "pace": "normal", "kind": "explainer"})
    r.raise_for_status()
    pid = r.json()["project"]["id"]
    try:
        wait(c, r.json()["job"]["id"])
    except RuntimeError as e:
        print("pipeline failed:", e)
        return 1
    media = c.get(f"/api/projects/{pid}/media").json()
    ar = next((m for m in media if m["id"] == "aroll"), None)
    if not ar:
        print("no A-roll in the media bin")
        return 1
    print(f"A-roll: {ar['width']}x{ar['height']} {ar['duration']} s role={ar['role']} face-focus=({ar['fx']:.2f},{ar['fy']:.2f}) faces={len(ar['faces'])}")
    if ar["role"] != "a_roll":
        problems.append("the A-roll is not marked as A-roll")
    if not ar["faces"]:
        problems.append("no face was found in the speaker's picture")
    audio = c.get(f"/api/projects/{pid}/audio").json()
    keep = audio["keep"]
    out_dur = keep[-1]["o1"]
    if abs(ar["duration"] - out_dur) > 0.5:
        problems.append(f"the A-roll is {ar['duration']} s but the edited voice is {out_dur:.1f} s")
    plan = c.get(f"/api/projects/{pid}/scenes").json()
    scenes, timing = plan["plan"]["scenes"], {t["id"]: t for t in plan["timing"]["scenes"]}
    speaker = [s for s in scenes if s.get("backdrop") and s["backdrop"]["media"] == "aroll"]
    print("scenes:", [(s["id"], "SPEAKER" if s in speaker else "graphic", s["backdrop"]["motion"] if s in speaker else "") for s in scenes])
    if not speaker or scenes[0] not in speaker:
        problems.append("the opening scene does not show the speaker")
    if len(speaker) == len(scenes) and len(scenes) > 2:
        problems.append("every scene shows the speaker: the plan has no graphics at all")

    def src_time(t):
        for k in keep:
            if k["o0"] - 1e-3 <= t <= k["o1"] + 1e-3:
                return k["s"] + (t - k["o0"])
        return keep[-1]["e"]

    for aspect, tag, wh in (("9:16", "9x16", 9 / 16), ("16:9", "16x9", 16 / 9)):
        j = c.post(f"/api/projects/{pid}/export", json={"aspects": [aspect], "quality": "draft", "gpu": True, "music": "none", "captions": True, "sfx_level": "off", "fps": 30})
        j.raise_for_status()
        wait(c, j.json()["id"])
        exp = [e for e in c.get(f"/api/projects/{pid}/exports").json() if tag in e["name"]]
        v = Path(exp[0]["path"])
        final = out / f"aroll_{tag}.mp4"
        final.write_bytes(v.read_bytes())
        hits, faces_ok, sheet = 0, 0, []
        for s in speaker[:4]:
            t = timing[s["id"]]
            tm = (t["start"] + t["end"]) / 2
            rendered = frame(final, tm, out / f"r_{tag}_{s['id']}.png")
            offsets = (0.0, -8.0, -4.0, -2.0, -1.0, 1.0, 2.0, 4.0, 8.0)
            sources = {d: gray_small(cover_crop(frame(src, src_time(tm) + d, out / "_s.png"), wh, s["backdrop"]["fx"])) for d in offsets}
            g = gray_small(rendered)
            corr = {d: float((g * sources[d]).mean()) for d in sources}
            still = s["backdrop"]["motion"] == "none"                # a punch-in zooms the crop, so only the unzoomed scenes can be matched to the source frame
            ok = (not still) or corr[0.0] >= max(corr.values()) - (0.03 if tag == "16x9" else 0.1)             # the right moment is the best match (a nearly still speaker matches the moments next to it just as well)
            hits += ok
            fc = detect_faces(np.asarray(Image.fromarray(rendered).resize((rendered.shape[1] // 2, rendered.shape[0] // 2))))
            inside = bool(fc) and all(0.02 < f[0] and f[0] + f[2] < 0.98 for f in fc[:1])
            faces_ok += inside
            print(f"  {aspect} {s['id']} at {tm:.1f}s: matches the source moment {ok if still else 'n/a (punch-in)'} (corr now {corr[0.0]:.2f}, best other {max(v for k, v in corr.items() if k):.2f} at {max((k for k in corr if k), key=lambda k: corr[k])} s); face inside frame {inside}")
            sheet.append(rendered)
        if speaker and hits < max(1, len(speaker[:4]) - 1):
            problems.append(f"{aspect}: the rendered picture does not match the right moment of the source")
        if speaker and faces_ok == 0:
            problems.append(f"{aspect}: no face stayed inside the frame")
        # nothing may sit on the speaker: an independent person mask from a fresh frame of each speaker scene against what the composer decided for this shape
        from vt import people as PE

        data = c.get(f"/media/{pid}/composition/{tag}/data.json").json()
        by_id = {x["id"]: x for x in data["scenes"]}
        for s in speaker:
            d = by_id[s["id"]]
            t = timing[s["id"]]
            tm = (t["start"] + t["end"]) / 2
            apath = out / "_aroll_media.mp4"
            if not apath.exists():
                apath.write_bytes(c.get(f"/media/{pid}/media/aroll.mp4").content)
            fr = frame(apath, tm, out / "_pf.png", "scale=640:-2")
            face = ar["faces"][0] if ar["faces"] else None
            person = PE.to_output(PE.to_grid(PE.person_mask(fr, face), margin=0.0), ar["width"] / ar["height"], wh, s["backdrop"]["fx"], s["backdrop"]["fy"], s["backdrop"]["motion"])
            if d.get("stage"):
                x, y, w, hh = d["stage"]
                H, W = person.shape
                sub = person[int(y * H):int(np.ceil((y + hh) * H)), int(x * W):int(np.ceil((x + w) * W))]
                share = float(sub.mean()) if sub.size else 0.0
                print(f"  {aspect} {s['id']}: elements in the free rectangle {[round(v, 2) for v in d['stage']]}, {share * 100:.1f}% of it is person")
                if share > 0.06:
                    problems.append(f"{aspect} {s['id']}: the elements' rectangle overlaps the speaker ({share * 100:.0f}%)")
            else:
                print(f"  {aspect} {s['id']}: {'elements dropped, the speaker has the whole picture' if not d['elements'] else 'no stage override (no person grid)'}")
                if d["elements"]:
                    problems.append(f"{aspect} {s['id']}: the scene still has elements but no free rectangle was chosen")
        ff = subprocess.run([find_tool("ffprobe"), "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0", str(final)], capture_output=True, text=True).stdout.split()
        durs = {x.split(",")[0]: float(x.split(",")[1]) for x in ff if "," in x and x.split(",")[1] not in ("N/A", "")}
        if abs(durs.get("video", 0) - durs.get("audio", 0)) > 0.3:
            problems.append(f"{aspect}: picture and sound end {abs(durs.get('video', 0) - durs.get('audio', 0)):.2f} s apart")
    print("\nPROBLEMS:" if problems else "\nno problems found")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
