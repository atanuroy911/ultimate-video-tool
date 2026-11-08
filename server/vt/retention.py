"""Retention scorecard: numbers that predict whether a viewer stays, measured on the frames of a rendered video (and the composition it came from).

What the big platforms reward is public: viewers who are still there after the first seconds, long average view duration, finishing, rewatching. A video loses people when nothing
new happens for a while, when most of the screen is empty, when there is too much to read, or when there is dead air. Each of those is measured here, with a target and a plain-words
message; nothing is a black box. The targets are defaults from short-video practice (labelled as such in the UI) until the owner's own retention curves can replace them.

Measured from the rendered MP4 (4 frames a second, small, in colour):
  * hook time        - when something meaningful is first on screen (target <= 1.0 s);
  * change gaps      - the time between visible changes (a new picture, a scene cut, text appearing, a camera move): longest gap and the share of gaps over the target (3 s, in every shape: something must change on screen at least every 3 s);
  * empty stretches  - how long four fifths of the safe area (everything above the caption zone) shows only plain background (target: never more than 1.5 s);
  * dead air         - silence inside the voice track longer than 0.7 s;
  * reading speed    - captions faster than about 4.5 words a second (from the composition);
  * motion           - the average amount of change per second (a very still video loses people, a very busy one tires them);
  * picture hold     - the time between *picture* changes: a change over at least 8 % of the screen (a new picture, a big word, a cut). A caption
                       swapping words covers about 3 % and does not count. Target 3 s: the high-retention reels change the picture every 2.3 s (about
                       one picture per 7 spoken words, docs/research/REELS-ANALYSIS.md);
  * fill             - how much of the height above the caption zone holds something (top of the highest thing to the bottom of the lowest):
                       a tall video with everything in its top third reads as half empty even when the empty-area check passes.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .util import CREATE_NO_WINDOW, find_tool, read_json, write_json

FPS = 4                                  # frames looked at per second
TARGETS = {
    "hook_s": 1.0,
    "gap_s": {"tall": 3.0, "wide": 3.0},
    "empty_s": 1.5,
    "empty_share": 0.80,                  # calibrated on frames judged by eye on 2026-10-23: the owner's "half empty" scene measured 0.88-0.89, the re-flowed version 0.76
    "dead_air_s": 0.7,
    "wps": 4.5,
    "cps": 25.0,                          # characters a second, the same speed as 4.5 words a second at ~5.5 characters a word: captions in step with the voice are read at its pace (17 and 20 flagged ordinary narration, 2026-11-08)
    "motion_low": 0.8,
    "motion_high": 14.0,
    "picture_hold_s": 3.0,
    "picture_share": 0.08,                # share of the screen that must change for a *picture* change
    "fill": 0.60,                         # share of the safe height in use (tall); wide frames are judged at 0.45
}
WEIGHTS = {"hook": 15, "gaps": 12, "picture": 20, "empty": 25, "dead_air": 10, "reading": 8, "motion": 10}  # points lost at the very worst; they add up to 100
CAPTION_ZONE = {"tall": 0.30, "wide": 0.22}                                                  # the bottom part where captions and the platforms' own buttons live


def _frames(video: Path, width: int = 160) -> tuple[np.ndarray, float]:
    """All sampled frames as (n, h, w, 3) uint8 and the fps actually used."""
    info = subprocess.run([find_tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video)],
                          capture_output=True, text=True, creationflags=CREATE_NO_WINDOW).stdout.strip().split(",")
    w0, h0 = int(info[0]), int(info[1])
    h = max(8, int(round(width * h0 / w0 / 2)) * 2)
    raw = subprocess.run([find_tool("ffmpeg"), "-v", "error", "-i", str(video), "-vf", f"fps={FPS},scale={width}:{h}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, creationflags=CREATE_NO_WINDOW).stdout
    n = len(raw) // (width * h * 3)
    return np.frombuffer(raw[: n * width * h * 3], dtype=np.uint8).reshape(n, h, width, 3), float(FPS)


def plain_share(frame: np.ndarray, zone: float, block: int = 8) -> float:
    return float(plain_mask(frame, zone, block).mean())


def fill(frame: np.ndarray, zone: float, block: int = 8) -> float:
    """Share of the safe height between the top of the highest thing and the bottom of the lowest (rows with at least 5 % detail)."""
    m = plain_mask(frame, zone, block)
    if m.size == 0:
        return 0.0
    used = np.nonzero((~m).mean(axis=1) >= 0.05)[0]
    return float((used[-1] - used[0] + 1) / m.shape[0]) if len(used) else 0.0


def plain_mask(frame: np.ndarray, zone: float, block: int = 8) -> np.ndarray:
    """Share of the safe area (everything above the caption zone) that is plain background: blocks with almost no detail whose colour is the frame's usual background colour.
    A flat-coloured emoji or an area of a photo is not plain: its colour differs from the background's, or it has detail."""
    h, w = frame.shape[:2]
    top = int(h * (1 - zone))
    area = frame[:top].astype("float32")
    gray = area.mean(axis=2)
    bh, bw = top // block, w // block
    if bh == 0 or bw == 0:
        return np.zeros((0, 0), dtype=bool)
    g = gray[: bh * block, : bw * block].reshape(bh, block, bw, block)
    c = area[: bh * block, : bw * block].reshape(bh, block, bw, block, 3)
    std = g.std(axis=(1, 3))
    mean = c.mean(axis=(1, 3))                                          # (bh, bw, 3)
    flat = mean.reshape(-1, 3)
    bg = np.median(flat, axis=0)                                        # the usual colour of the frame
    near = np.abs(mean - bg).max(axis=2) < 14
    return (std < 5.0) & near


def analyze_frames(frames: np.ndarray, aspect_kind: str) -> dict[str, Any]:
    n = len(frames)
    zone = CAPTION_ZONE[aspect_kind]
    empty = np.array([plain_share(f, zone) for f in frames])
    fills = np.array([fill(f, zone) for f in frames])
    gray = frames.astype("float32").mean(axis=3)
    diffs = np.zeros(n)
    big = np.zeros(n)                                   # share of 8x8 blocks that changed clearly: a picture change, not a caption swap
    if n > 1:
        small = gray[:, ::2, ::2]
        diffs[1:] = np.abs(small[1:] - small[:-1]).mean(axis=(1, 2))
        h, w = gray.shape[1] // 8 * 8, gray.shape[2] // 8 * 8
        blocks = gray[:, :h, :w].reshape(n, h // 8, 8, w // 8, 8).mean(axis=(2, 4))
        big[1:] = (np.abs(blocks[1:] - blocks[:-1]) > 18).mean(axis=(1, 2))
    return {"empty": empty, "diff": diffs, "big": big, "fill": fills}


def picture_times(big: np.ndarray, fps: float) -> list[float]:
    """Moments of a picture change (over TARGETS["picture_share"] of the screen); a change spread over neighbouring frames (a fade) counts once."""
    out: list[float] = []
    for i in range(1, len(big)):
        if big[i] >= TARGETS["picture_share"] and (not out or i / fps - out[-1] > 0.6):
            out.append(i / fps)
    return out


def stretches(mask: np.ndarray, fps: float) -> list[tuple[float, float]]:
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start / fps, i / fps))
            start = None
    if start is not None:
        out.append((start / fps, len(mask) / fps))
    return out


def change_times(diff: np.ndarray, fps: float, thr: float = 3.0) -> list[float]:
    """Moments of a visible change: the frame differs from the one before by more than `thr` grey levels on average; neighbouring detections count once."""
    t = [i / fps for i in range(1, len(diff)) if diff[i] > thr]
    out: list[float] = []
    for x in t:
        if not out or x - out[-1] > 0.5:
            out.append(x)
    return out


def dead_air(voice: Optional[Path], min_len: float = 0.7) -> list[tuple[float, float]]:
    if not voice or not Path(voice).exists():
        return []
    r = subprocess.run([find_tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(voice), "-af", f"silencedetect=noise=-45dB:d={min_len}", "-f", "null", "-"],
                       capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    import re

    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [(a, ends[i] if i < len(ends) else a + min_len) for i, a in enumerate(starts)]


def reading_speed(captions: list[dict]) -> list[tuple[float, float, float]]:
    """Captions that go by faster than the target words a second: [(start, end, wps)]. Measured over the captions read one after another
    (at least READ_WINDOW seconds, no pause between them): a three-word chunk shown exactly while it is said is read at the speed of the
    speech, not at three words over its own 0.6 s (D8: every normal video was warned about, 2026-11-08)."""
    caps = sorted(captions or [], key=lambda c: float(c.get("start", 0)))
    out = []
    for i, c in enumerate(caps):
        words = c.get("words") or []
        if len(words) < 3:
            continue
        start, end, j = float(c.get("start", 0)), float(c.get("end", 0)), i
        n = len(words)
        chars = sum(len(str(w.get("text", ""))) for w in words) + max(0, len(words) - 1)
        while end - start < READ_WINDOW and j + 1 < len(caps) and float(caps[j + 1].get("start", 0)) - float(caps[j].get("end", 0)) < 0.3:
            j += 1
            more = caps[j].get("words") or []
            n += len(more)
            chars += sum(len(str(w.get("text", ""))) for w in more) + len(more)
            end = float(caps[j].get("end", 0))
        dur = max(0.2, end - start)
        if n / dur > TARGETS["wps"] or chars / dur > TARGETS["cps"]:
            out.append((start, float(c.get("end", 0)), round(n / dur, 1)))
    return out


READ_WINDOW = 2.0                     # seconds of captions read in one go: long enough that the chunking does not decide the measure


def scorecard(video: Path, aspect: str, composition: Optional[dict] = None, voice: Optional[Path] = None) -> dict[str, Any]:
    kind = "tall" if aspect in ("9:16",) else "wide"
    frames, fps = _frames(Path(video))
    n = len(frames)
    dur = n / fps
    a = analyze_frames(frames, kind)
    empty, diff = a["empty"], a["diff"]

    # hook: the first moment something is on screen (a clearly non-plain frame) -------------------------------------------------------
    on = np.nonzero(empty < 0.85)[0]
    hook = float(on[0] / fps) if len(on) else dur
    # change gaps ---------------------------------------------------------------------------------------------------------------------
    ch = [0.0] + change_times(diff, fps) + [dur]
    gaps = [(ch[i], ch[i + 1], ch[i + 1] - ch[i]) for i in range(len(ch) - 1)]
    limit = TARGETS["gap_s"][kind]
    long_gaps = [(round(s, 2), round(e, 2)) for s, e, g in gaps if g > limit]
    longest = max(gaps, key=lambda g: g[2]) if gaps else (0, 0, 0)
    # empty stretches -------------------------------------------------------------------------------------------------------------------
    emp = [(round(s, 2), round(e, 2)) for s, e in stretches(empty > TARGETS["empty_share"], fps) if e - s > TARGETS["empty_s"]]
    emp_all = stretches(empty > TARGETS["empty_share"], fps)
    emp_longest = max(((e - s) for s, e in emp_all), default=0.0)
    # dead air, reading, motion --------------------------------------------------------------------------------------------------------
    dead = [(round(s, 2), round(e, 2)) for s, e in dead_air(voice)]
    fast = reading_speed((composition or {}).get("captions", []))
    motion = float(diff[1:].mean()) if n > 1 else 0.0
    pics = [0.0] + picture_times(a["big"], fps) + [dur]
    holds = [(pics[i], pics[i + 1] - pics[i]) for i in range(len(pics) - 1)]
    pic_longest = max(holds, key=lambda x: x[1]) if holds else (0.0, 0.0)
    pic_limit = TARGETS["picture_hold_s"]
    pic_long = [(round(s, 2), round(s + g, 2)) for s, g in holds if g > pic_limit + 0.5]
    pic_median = float(np.median([g for _, g in holds])) if holds else 0.0
    fill_target = TARGETS["fill"] if kind == "tall" else 0.45
    shown = ~(empty > 0.97)
    fill_mean = float(a["fill"][shown].mean()) if shown.any() else 0.0

    # points lost ---------------------------------------------------------------------------------------------------------------------
    lost = {
        "hook": WEIGHTS["hook"] * min(1.0, max(0.0, (hook - TARGETS["hook_s"]) / 3.0)),
        "gaps": WEIGHTS["gaps"] * min(1.0, max(0.0, (longest[2] - limit) / (2.0 * limit))) * 0.6 + WEIGHTS["gaps"] * 0.4 * min(1.0, sum(g for _, _, g in gaps if g > limit) / max(dur, 1) * 3),
        "picture": WEIGHTS["picture"] * (0.5 * min(1.0, max(0.0, (pic_longest[1] - pic_limit) / (2.0 * pic_limit)))
                                         + 0.5 * min(1.0, max(0.0, (pic_median - 2.3) / 2.0))),
        "empty": WEIGHTS["empty"] * (0.55 * min(1.0, max(0.0, (emp_longest - TARGETS["empty_s"]) / 4.0))
                                     + 0.25 * min(1.0, sum(e - s for s, e in emp_all if e - s > TARGETS["empty_s"]) / max(dur, 1) * 4)
                                     + 0.20 * min(1.0, max(0.0, (fill_target - fill_mean) / 0.3))),
        "dead_air": WEIGHTS["dead_air"] * min(1.0, sum(e - s for s, e in dead) / max(dur, 1) * 8),
        "reading": WEIGHTS["reading"] * min(1.0, len(fast) / 4),
        "motion": WEIGHTS["motion"] * (1.0 if motion < TARGETS["motion_low"] else 0.0 if motion < TARGETS["motion_high"] else 0.7),
    }
    risk = int(round(sum(lost.values())))
    moments: list[dict] = []
    for s, e in emp:
        moments.append({"t0": s, "t1": e, "kind": "empty", "severity": round(e - s, 2), "message": f"Most of the screen is empty for {e - s:.1f} s. Add the next picture sooner or fill the space."})
    for s, e in pic_long:
        moments.append({"t0": s, "t1": e, "kind": "picture", "severity": round(e - s, 2),
                        "message": f"The same picture for {e - s:.1f} s (aim for a new one every {pic_limit:.0f} s or sooner)."})
    for s, e in long_gaps:
        moments.append({"t0": s, "t1": e, "kind": "still", "severity": round(e - s, 2), "message": f"Nothing new for {e - s:.1f} s (aim for under {limit:.0f} s). Add a change here."})
    if hook > TARGETS["hook_s"]:
        moments.append({"t0": 0.0, "t1": round(hook, 2), "kind": "hook", "severity": round(hook, 2), "message": f"Nothing meaningful is on screen until {hook:.1f} s. Show the key picture and topic from the first frame."})
    for s, e in dead:
        moments.append({"t0": s, "t1": e, "kind": "dead_air", "severity": round(e - s, 2), "message": f"Silence for {e - s:.1f} s."})
    for s, e, w in fast:
        moments.append({"t0": round(s, 2), "t1": round(e, 2), "kind": "reading", "severity": w, "message": f"Captions go by at {w} words a second: hard to read."})
    moments.sort(key=lambda m: -m["severity"])
    return {
        "aspect": aspect, "duration": round(dur, 2), "risk": risk, "score": 100 - risk,
        "hook_s": round(hook, 2), "longest_gap_s": round(longest[2], 2), "longest_gap_at": round(longest[0], 2), "gaps_over_target": len(long_gaps),
        "empty_longest_s": round(emp_longest, 2), "empty_stretches": emp, "dead_air": dead, "fast_captions": len(fast), "motion": round(motion, 2),
        "picture_hold_longest_s": round(pic_longest[1], 2), "picture_hold_at": round(pic_longest[0], 2), "picture_hold_median_s": round(pic_median, 2),
        "picture_changes_per_min": round((len(pics) - 2) / max(dur, 1) * 60, 1), "fill": round(fill_mean, 2),
        "targets": {"hook_s": TARGETS["hook_s"], "gap_s": limit, "picture_hold_s": pic_limit, "fill": fill_target, "empty_s": TARGETS["empty_s"], "dead_air_s": TARGETS["dead_air_s"], "wps": TARGETS["wps"]},
        "points_lost": {k: round(v, 1) for k, v in lost.items()},
        "worst": moments[:5],
        "note": "Targets are defaults from short-video practice, not measurements of your audience.",
    }


def verdict(card: dict) -> str:
    r = card["risk"]
    if r <= 15:
        return "Strong: a quick start and something new all the time."
    if r <= 35:
        return f"Good, with {len(card['worst'])} moment(s) to look at."
    return f"Risky: {len(card['worst'])} moment(s) where viewers may leave. Fix the first ones listed."


def save(path: Path, card: dict) -> None:
    write_json(path, card)


def load(path: Path) -> Optional[dict]:
    return read_json(path)
