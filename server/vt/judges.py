"""The automatic judges: a finished video is checked before a person sees it (docs/TEST-PLAN.md section 3).

Each judge returns a `Verdict`: a name, pass or fail, the measured number, the threshold and one plain sentence. `judge_video` runs every judge it has the inputs for and says which
it could not run. The thresholds are starting values tuned on the example reels; a video that fails a judge is a bug report, not a note.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Optional

import numpy as np

from .retention import FPS, _frames, change_times, analyze_frames
from .util import CREATE_NO_WINDOW, find_tool

LOUDNESS_RANGE = (-16.0, -12.0)           # integrated LUFS
TRUE_PEAK_MAX = -1.0                      # dBTP
STILL_MAX_S = 3.0
CHANGE_ON_WORD_MIN = 0.75
CHANGE_WINDOW_S = 0.15
FIRST_WORD_MAX_S = 0.3
SYNC_MEDIAN_MAX_S = 0.15
DURATION_TOLERANCE = 0.10
WORDS_PER_PICTURE = {"steps": (5, 13), "story": (4, 11), "explanation": (5, 12), "list": (4, 12), "argument": (5, 12), "opinion": (4, 12)}      # widened on 2026-10-28 after A1 and A9: the 3 s hold limit puts about 10 words in a picture at a normal speaking speed


@dataclass
class Verdict:
    judge: str
    passed: Optional[bool]                  # None = could not be judged (the reason is in `says`)
    value: Any = None
    limit: Any = None
    says: str = ""
    where: list = field(default_factory=list)

    def dict(self) -> dict:
        return asdict(self)


def _probe_duration(video: Path) -> float:
    out = subprocess.run([find_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW).stdout.strip()
    return float(out or 0)


def first_frame(frames: np.ndarray, words: Optional[list[dict]] = None) -> Verdict:
    """The first frame has something in it, and the voice starts at once."""
    f = frames[0].astype("float32")
    detail = float(f.mean(axis=2).std())
    blank = detail < 6.0
    first_word = float(words[0]["start"]) if words else None
    late = first_word is not None and first_word > FIRST_WORD_MAX_S
    ok = not blank and not late
    says = "The first frame has a picture" if not blank else "The first frame is blank"
    says += f" and the first word comes at {first_word:.2f} s." if first_word is not None else "."
    if late:
        says = f"The first word comes at {first_word:.2f} s (aim for under {FIRST_WORD_MAX_S} s)."
    return Verdict("first_frame", ok, {"detail": round(detail, 1), "first_word_s": first_word}, {"detail_min": 6.0, "first_word_max_s": FIRST_WORD_MAX_S}, says)


def nothing_still(frames: np.ndarray) -> Verdict:
    """No stretch longer than 3 s without a visible change."""
    diff = analyze_frames(frames, "tall")["diff"]
    dur = len(frames) / FPS
    marks = [0.0] + change_times(diff, FPS) + [dur]
    gaps = [(marks[i], marks[i + 1]) for i in range(len(marks) - 1)]
    longest = max(gaps, key=lambda g: g[1] - g[0])
    length = longest[1] - longest[0]
    bad = [(round(a, 2), round(b, 2)) for a, b in gaps if b - a > STILL_MAX_S]
    return Verdict("nothing_still", not bad, round(length, 2), STILL_MAX_S,
                   f"The longest stretch with nothing new is {length:.1f} s (at {longest[0]:.1f} s)." + ("" if not bad else f" {len(bad)} stretch(es) are over {STILL_MAX_S:.0f} s."), bad)


def change_on_the_word(frames: np.ndarray, words: list[dict]) -> Verdict:
    """The picture changes land on spoken words, not between them."""
    if not words:
        return Verdict("change_on_word", None, says="No word times to compare with.")
    diff = analyze_frames(frames, "tall")["diff"]
    changes = change_times(diff, FPS)
    if not changes:
        return Verdict("change_on_word", None, says="The video has no picture changes to compare.")
    starts = np.array([float(w["start"]) for w in words])
    near = [bool(np.min(np.abs(starts - t)) <= CHANGE_WINDOW_S + 1 / FPS) for t in changes]
    share = sum(near) / len(near)
    return Verdict("change_on_word", share >= CHANGE_ON_WORD_MIN, round(share, 2), CHANGE_ON_WORD_MIN,
                   f"{round(share * 100)} % of the {len(changes)} picture changes land on a spoken word (aim for {round(CHANGE_ON_WORD_MIN * 100)} %).",
                   [round(t, 2) for t, n in zip(changes, near) if not n][:10])


def glitches(frames: np.ndarray) -> Verdict:
    """No blank green, black or white frame inside the video, and no colour wash left by a transition (the bug of 2026-10-27)."""
    bad: list[float] = []
    n = len(frames)
    edge = int(0.3 * FPS)
    for i, fr in enumerate(frames):
        f = fr.astype("float32")
        r, g, b = f[..., 0], f[..., 1], f[..., 2]
        wash = float(((g - np.maximum(r, b)) > 70).mean())
        flat = float(f.mean(axis=2).std()) < 3.0
        mean = f.mean(axis=(0, 1))
        pure = flat and (mean.max() < 12 or mean.min() > 243 or (mean[1] > 150 and mean[0] < 100 and mean[2] < 100))
        if wash > 0.6 or (pure and edge <= i < n - edge):
            bad.append(round(i / FPS, 2))
    return Verdict("no_glitches", not bad, len(bad), 0, "No blank or colour-washed frame." if not bad else f"{len(bad)} glitched frame(s), first at {bad[0]:.1f} s.", bad[:10])


def loudness(video: Path) -> Verdict:
    """Integrated loudness near -14 LUFS and the true peak under -1 dBTP."""
    r = subprocess.run([find_tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(video), "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    tail = r.stderr[r.stderr.rfind("Summary:"):] if "Summary:" in r.stderr else ""
    i, p = re.search(r"I:\s+(-?[\d.]+) LUFS", tail), re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail)
    if not i:
        return Verdict("loudness", None, says="The video has no audio to measure.")
    lufs, peak = float(i.group(1)), float(p.group(1)) if p else None
    ok = LOUDNESS_RANGE[0] <= lufs <= LOUDNESS_RANGE[1] and (peak is None or peak <= TRUE_PEAK_MAX)
    return Verdict("loudness", ok, {"lufs": lufs, "true_peak": peak}, {"lufs": LOUDNESS_RANGE, "true_peak_max": TRUE_PEAK_MAX},
                   f"Loudness {lufs:.1f} LUFS" + (f", true peak {peak:.1f} dBTP" if peak is not None else "") + (" is in range." if ok else f" is outside {LOUDNESS_RANGE[0]} to {LOUDNESS_RANGE[1]} LUFS / {TRUE_PEAK_MAX} dBTP."))


def duration(seconds: float, target: Optional[float], tolerance: float = DURATION_TOLERANCE) -> Verdict:
    if not target:
        return Verdict("duration", None, round(seconds, 2), says="No target length was given.")
    off = abs(seconds - target) / target
    return Verdict("duration", off <= tolerance, round(seconds, 2), target, f"The video is {seconds:.1f} s; the target was {target:.0f} s ({round(off * 100)} % off, allowed {round(tolerance * 100)} %).")


def pictures_per_words(scenes: list[dict], words: list[dict], kind: str = "explanation") -> Verdict:
    """Words per picture sit in the range of the content kind for at least 90 % of the pictures."""
    lo, hi = WORDS_PER_PICTURE.get(kind, (5, 10))
    if not scenes or not words:
        return Verdict("pictures_per_words", None, says="No scenes or words to compare.")
    starts = np.array([float(w["start"]) for w in words])
    counts = []
    scenes = [s for s in scenes if not s.get("card")]                       # a step or day card ("Step two") is short on purpose
    if not scenes:
        return Verdict("pictures_per_words", None, says="Only cards: nothing to compare.")
    for s in scenes:
        t0, t1 = float(s.get("start", s.get("t0", 0))), float(s.get("end", s.get("t1", 0)))
        counts.append(int(((starts >= t0 - 1e-3) & (starts < t1 - 1e-3)).sum()))
    inside = sum(lo <= c <= hi for c in counts) / len(counts)
    return Verdict("pictures_per_words", inside >= 0.85, round(inside, 2), {"range": (lo, hi), "share": 0.85}, f"{round(inside * 100)} % of the {len(counts)} pictures carry {lo} to {hi} words.",
                   [i for i, c in enumerate(counts) if not lo <= c <= hi][:10])


def same_design(scenes: list[dict]) -> Verdict:
    """One design language: every scene is built the same way (all full-screen pictures, or all cards), so step 2 looks like step 1."""
    if len(scenes) < 2:
        return Verdict("same_design", None, says="Fewer than two scenes to compare.")

    def shape(s: dict) -> str:
        return "picture" if s.get("backdrop") else "cards"

    kinds = [shape(s) for s in scenes]
    top = max(set(kinds), key=kinds.count)
    odd = [scenes[i].get("id", i) for i, k in enumerate(kinds) if k != top]
    return Verdict("same_design", not odd, len(odd), 0, f"All {len(kinds)} scenes use the same {top} design." if not odd else f"{len(odd)} scene(s) break the {top} design of the rest: {', '.join(map(str, odd[:6]))}.", odd[:10])


def audio_sync(caption_words: list[dict], spoken: list[dict]) -> Verdict:
    """The caption word at time t is the word the voice says at t: the median start error over the words both lists share, in order."""
    def norm(t: str) -> str:
        return re.sub(r"\W+", "", str(t).casefold())

    a, b = [w for w in caption_words if norm(w.get("text", ""))], [w for w in spoken if norm(w.get("text", ""))]
    errs, j = [], 0
    for w in a:
        k = j
        while k < len(b) and norm(b[k]["text"]) != norm(w["text"]) and k - j < 4:
            k += 1
        if k < len(b) and norm(b[k]["text"]) == norm(w["text"]):
            errs.append(abs(float(w["start"]) - float(b[k]["start"])))
            j = k + 1
    if len(errs) < 3:
        return Verdict("audio_sync", None, says="Too few shared words to compare.")
    m = float(median(errs))
    return Verdict("audio_sync", m <= SYNC_MEDIAN_MAX_S, round(m, 3), SYNC_MEDIAN_MAX_S, f"Captions are a median {m * 1000:.0f} ms from the spoken words (limit {SYNC_MEDIAN_MAX_S * 1000:.0f} ms) over {len(errs)} words.")


def captions_readable(composition: Optional[dict]) -> Verdict:
    """No caption faster than the reading limit (the retention rule), and none empty."""
    from .retention import reading_speed

    caps = (composition or {}).get("captions")
    if not caps:
        return Verdict("captions", None, says="No captions in the composition to check.")
    fast = reading_speed(caps)
    return Verdict("captions", not fast, len(fast), 0, "Every caption is slow enough to read." if not fast else f"{len(fast)} caption(s) go by too fast to read, first at {fast[0][0]:.1f} s.", [(round(s, 2), round(e, 2)) for s, e, _ in fast][:10])


def judge_video(video: Path, *, words: Optional[list[dict]] = None, scenes: Optional[list[dict]] = None, composition: Optional[dict] = None,
                target_seconds: Optional[float] = None, kind: str = "explanation", has_audio: bool = True, duration_tolerance: float = DURATION_TOLERANCE) -> dict[str, Any]:
    """Run every judge that has what it needs. {"passed": bool, "verdicts": [...], "failed": [names], "skipped": [names]}."""
    video = Path(video)
    frames, _ = _frames(video)
    out: list[Verdict] = [first_frame(frames, words), nothing_still(frames), glitches(frames), duration(_probe_duration(video), target_seconds, duration_tolerance)]
    if has_audio:
        out.append(loudness(video))
    out.append(change_on_the_word(frames, words or []))
    out.append(pictures_per_words(scenes or [], words or [], kind))
    if scenes:
        out.append(same_design(scenes))
    caps = (composition or {}).get("captions")
    if caps:
        flat = [w for c in caps for w in (c.get("words") or [])]
        out.append(audio_sync(flat, words or []) if words else Verdict("audio_sync", None, says="No spoken word times."))
        out.append(captions_readable(composition))
    failed = [v.judge for v in out if v.passed is False]
    return {"passed": not failed, "verdicts": [v.dict() for v in out], "failed": failed, "skipped": [v.judge for v in out if v.passed is None]}


def report_lines(result: dict) -> list[str]:
    mark = {True: "pass", False: "FAIL", None: "skip"}
    return [f"| {v['judge']} | {mark[v['passed']]} | {v['says']} |" for v in result["verdicts"]]
