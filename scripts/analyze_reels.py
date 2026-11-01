"""Measure what high-retention reels do: cut times, cut rhythm, first change, loudness, and a contact sheet of each.

    python scripts/analyze_reels.py fb-shorts-example docs/research/reels

Writes <out>/<name>.json and <out>/<name>.png per video and <out>/summary.json. Reads the videos only.
"""
from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

THRESHOLD = 0.30        # ffmpeg scene score: 0.3 is a clear cut, not a pan or a zoom


def run(*args: str) -> str:
    done = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return done.stderr + done.stdout


def probe(path: Path) -> dict:
    out = json.loads(run("ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", str(path)))
    video = next(s for s in out["streams"] if s["codec_type"] == "video")
    return {"duration": float(out["format"]["duration"]), "width": video["width"], "height": video["height"],
            "has_audio": any(s["codec_type"] == "audio" for s in out["streams"])}


def cuts(path: Path) -> list[float]:
    text = run("ffmpeg", "-hide_banner", "-i", str(path), "-vf", f"select='gt(scene,{THRESHOLD})',showinfo", "-an", "-f", "null", "-")
    return [round(float(m), 2) for m in re.findall(r"pts_time:([0-9.]+)", text)]


def loudness(path: Path) -> dict:
    text = run("ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-vn", "-f", "null", "-")
    last = text[text.rfind("Summary:"):] if "Summary:" in text else ""
    pick = lambda key: (re.search(key + r":\s+(-?[0-9.]+)", last) or [None, None])[1]
    return {"lufs": pick("I"), "lra": pick("LRA")}


def sheet(path: Path, out: Path, duration: float) -> None:
    fps = min(1.0, 48 / duration)                                  # at most 48 frames: 8 across, 6 down
    run("ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf", f"fps={fps},scale=180:-1,tile=8x6", "-frames:v", "1", str(out))


def gaps(times: list[float], duration: float) -> list[float]:
    marks = [0.0] + times + [duration]
    return [round(b - a, 2) for a, b in zip(marks, marks[1:])]


def main(folder: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for path in sorted(Path(folder).glob("*.mp4")):
        info = probe(path)
        times = cuts(path)
        spans = gaps(times, info["duration"])
        info.update(name=path.name, cuts=times, cut_count=len(times), first_change=times[0] if times else None,
                    shots=len(spans), median_shot=round(statistics.median(spans), 2), mean_shot=round(statistics.mean(spans), 2),
                    longest_shot=max(spans), cuts_per_min=round(len(times) / info["duration"] * 60, 1),
                    **loudness(path))
        sheet(path, out / (path.stem.replace(" ", "-") + ".png"), info["duration"])
        (out / (path.stem.replace(" ", "-") + ".json")).write_text(json.dumps(info, indent=1), encoding="utf-8")
        summary[path.name] = {k: info[k] for k in ("duration", "width", "height", "cut_count", "first_change", "median_shot", "longest_shot", "cuts_per_min", "lufs")}
        print(path.name, summary[path.name])
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")


if __name__ == "__main__" and not (len(sys.argv) > 3 and sys.argv[3] == "deep"):
    main(*sys.argv[1:3])


# ---------------------------------------------------------------- second pass: what changes, and what is said
def change_series(path: Path, fps: int = 10):
    """Mean absolute difference between consecutive frames (0-255, 64 px wide, grey) at `fps`."""
    import numpy as np

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={fps},scale=64:-2,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    probe_h = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "scale=64:-2", "-frames:v", "1", "-f", "image2pipe", "-vcodec", "pgm", "-"],
                             capture_output=True).stdout
    header = probe_h.split(b"\n", 3)
    w, h = (int(v) for v in header[1].split())
    frames = np.frombuffer(raw, dtype=np.uint8)
    frames = frames[: len(frames) // (w * h) * w * h].reshape(-1, h, w).astype(np.int16)
    return np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2)), fps


def change_stats(diff, fps: int, swap: float = 14.0, active: float = 1.2) -> dict:
    import numpy as np

    times = (np.arange(len(diff)) + 1) / fps
    swaps = [round(float(t), 1) for t, d in zip(times, diff) if d > swap]
    merged = [t for i, t in enumerate(swaps) if i == 0 or t - swaps[i - 1] > 0.3]
    quiet, longest, start = 0.0, 0.0, None
    for t, d in zip(times, diff):
        if d < active:
            start = t if start is None else start
            longest = max(longest, t - start + 1 / fps)
        else:
            start = None
    return {"swap_events": merged, "swaps": len(merged), "longest_still_s": round(longest, 1),
            "moving_share": round(float((diff >= active).mean()), 2), "median_change": round(float(np.median(diff)), 2)}


def speech(path: Path, work: Path) -> dict:
    wav = work / (path.stem.replace(" ", "-") + ".wav")
    run("ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "16000", str(wav))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from vt.stages.asr import transcribe

    out = transcribe(wav, model="large-v3", language="en")
    words = out["words"]
    if not words:
        return {"words": 0}
    span = words[-1]["end"] - words[0]["start"]
    pauses = [round(b["start"] - a["end"], 2) for a, b in zip(words, words[1:]) if b["start"] - a["end"] > 0.25]
    return {"words": len(words), "first_word_at": round(words[0]["start"], 2), "wpm": round(len(words) / span * 60), "pauses_over_0.25s": len(pauses),
            "longest_pause": max(pauses) if pauses else 0, "text": " ".join(w["text"].strip() for w in words),
            "word_times": [[round(w["start"], 2), round(w["end"], 2), w["text"].strip()] for w in words]}


def deep(folder: str, out_dir: str) -> None:
    import tempfile

    out, work = Path(out_dir), Path(tempfile.mkdtemp())
    for path in sorted(Path(folder).glob("*.mp4")):
        slug = path.stem.replace(" ", "-")
        info = json.loads((out / (slug + ".json")).read_text(encoding="utf-8"))
        if "speech" in info:                                           # measured earlier; only new files cost time
            continue
        diff, fps = change_series(path)
        info["change"] = change_stats(diff, fps)
        info["speech"] = speech(path, work)
        (out / (slug + ".json")).write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")
        s = info["speech"]
        print(path.name, info["change"]["swaps"], "swaps; still", info["change"]["longest_still_s"], "s; words", s.get("words"), "wpm", s.get("wpm"), "first word", s.get("first_word_at"))


if __name__ == "__main__" and len(sys.argv) > 3 and sys.argv[3] == "deep":
    deep(sys.argv[1], sys.argv[2])
