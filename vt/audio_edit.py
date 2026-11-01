"""Hand editing of the voice track: cut (ripple delete), trim, split, mute and volume, with undo and redo.

Everything is stored in source time (seconds of the original recording) in `audio_edits.json`, so edits survive re-cutting of silences and a new pace:
  cuts   [[s, e]]            removed for good (the rest closes up: ripple)
  mutes  [[s, e]]            kept, but silent
  gains  [{s, e, db}]        louder or quieter
  splits [t]                 only a boundary between two clips (nothing changes in the sound)
The pipeline's cut stage adds `cuts` to the silences it removes and applies mutes and gains to the cut audio. The Studio talks in OUTPUT time (what you
see on the timeline); the functions here convert.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
import soundfile as sf

from .schema import Cuts
from .util import read_json, write_json

EMPTY: dict[str, Any] = {"cuts": [], "mutes": [], "gains": [], "splits": []}
MIN_LEN = 0.02
RAMP = 0.012                      # seconds of fade at the edge of a mute or gain change, so edits never click
HISTORY = 50


# --------------------------------------------------------------------------- storage with history
def _path(p) -> Path:
    return p.dir / "audio_edits.json"


def _hist(p) -> Path:
    return p.dir / "audio_hist.json"


def load(p) -> dict:
    d = read_json(_path(p), None)
    return {**json.loads(json.dumps(EMPTY)), **(d or {})}


def history(p) -> dict:
    return read_json(_hist(p), {"past": [], "future": []}) or {"past": [], "future": []}


def save(p, edits: dict, record: bool = True) -> None:
    """Write the new state; `record` pushes the old one on the undo stack (and clears redo)."""
    if record:
        h = history(p)
        h["past"] = (h["past"] + [load(p)])[-HISTORY:]
        h["future"] = []
        write_json(_hist(p), h)
    write_json(_path(p), edits)


def undo(p) -> bool:
    h = history(p)
    if not h["past"]:
        return False
    h["future"] = h["future"] + [load(p)]
    prev = h["past"].pop()
    write_json(_hist(p), h)
    write_json(_path(p), prev)
    return True


def redo(p) -> bool:
    h = history(p)
    if not h["future"]:
        return False
    h["past"] = h["past"] + [load(p)]
    nxt = h["future"].pop()
    write_json(_hist(p), h)
    write_json(_path(p), nxt)
    return True


# --------------------------------------------------------------------------- time maps
def out_to_src(cuts: Cuts, t: float) -> Optional[float]:
    """Output time -> source time (None past the end)."""
    acc = 0.0
    for s, e in cuts.keep:
        if t <= acc + (e - s) + 1e-9:
            return s + max(0.0, t - acc)
        acc += e - s
    return None


def src_ranges(cuts: Cuts, t0: float, t1: float) -> list[tuple[float, float]]:
    """The pieces of the original recording that play between output times t0 and t1."""
    out = []
    acc = 0.0
    for s, e in cuts.keep:
        a, b = max(t0, acc), min(t1, acc + (e - s))
        if b - a > 1e-6:
            out.append((round(s + (a - acc), 4), round(s + (b - acc), 4)))
        acc += e - s
    return out


def src_to_out(cuts: Cuts, t: float) -> float:
    return cuts.map_time_nearest(t)


def _merge(rs: list[list[float]]) -> list[list[float]]:
    rs = sorted([min(a, b), max(a, b)] for a, b in rs if abs(b - a) > 1e-6)
    out: list[list[float]] = []
    for a, b in rs:
        if out and a <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [[round(a, 4), round(b, 4)] for a, b in out]


def _subtract(rs: list[list[float]], cut: list[list[float]]) -> list[list[float]]:
    out = [list(r) for r in rs]
    for ca, cb in cut:
        nxt = []
        for a, b in out:
            if cb <= a or ca >= b:
                nxt.append([a, b])
                continue
            if ca - a > MIN_LEN:
                nxt.append([a, ca])
            if b - cb > MIN_LEN:
                nxt.append([cb, b])
        out = nxt
    return [[round(a, 4), round(b, 4)] for a, b in out]


# --------------------------------------------------------------------------- operations (output-time arguments)
def add_cut(edits: dict, cuts: Cuts, t0: float, t1: float) -> dict:
    """Ripple delete: remove what plays between output times t0 and t1."""
    new = src_ranges(cuts, min(t0, t1), max(t0, t1))
    if not new:
        raise ValueError("nothing to cut there")
    e = dict(edits)
    e["cuts"] = _merge(edits["cuts"] + [list(r) for r in new])
    e["splits"] = [s for s in edits["splits"] if not any(a < s < b for a, b in e["cuts"])]
    return e


def restore(edits: dict, index: int, side: str = "all", amount: float = 0.0) -> dict:
    """Bring back a manual cut (or part of it: `amount` seconds from its `start` or `end` side: a trim dragged outward)."""
    if not 0 <= index < len(edits["cuts"]):
        raise ValueError("no such cut")
    e = dict(edits)
    cuts = [list(c) for c in edits["cuts"]]
    a, b = cuts[index]
    if side == "all" or amount >= (b - a) - MIN_LEN:
        cuts.pop(index)
    elif side == "start":
        cuts[index] = [round(a + amount, 4), b]
    elif side == "end":
        cuts[index] = [a, round(b - amount, 4)]
    else:
        raise ValueError("side must be start, end or all")
    e["cuts"] = cuts
    return e


def set_mute(edits: dict, cuts: Cuts, t0: float, t1: float, on: bool) -> dict:
    rs = [list(r) for r in src_ranges(cuts, min(t0, t1), max(t0, t1))]
    if not rs:
        raise ValueError("nothing there")
    e = dict(edits)
    e["mutes"] = _merge(edits["mutes"] + rs) if on else _subtract(edits["mutes"], rs)
    return e


def set_gain(edits: dict, cuts: Cuts, t0: float, t1: float, db: float) -> dict:
    rs = [list(r) for r in src_ranges(cuts, min(t0, t1), max(t0, t1))]
    if not rs:
        raise ValueError("nothing there")
    db = max(-40.0, min(18.0, float(db)))
    kept: list[dict] = []
    for g in edits["gains"]:                           # cut the new range out of the older ones
        for a, b in _subtract([[g["s"], g["e"]]], rs):
            kept.append({"s": a, "e": b, "db": g["db"]})
    if abs(db) > 0.05:
        kept += [{"s": a, "e": b, "db": round(db, 2)} for a, b in rs]
    e = dict(edits)
    e["gains"] = sorted(kept, key=lambda g: g["s"])
    return e


def add_split(edits: dict, cuts: Cuts, t: float) -> dict:
    s = out_to_src(cuts, t)
    if s is None:
        raise ValueError("past the end")
    if any(abs(s - x) < 0.05 for x in edits["splits"]) or any(abs(s - k0) < 0.05 or abs(s - k1) < 0.05 for k0, k1 in cuts.keep):
        raise ValueError("there is already an edge here")
    e = dict(edits)
    e["splits"] = sorted(edits["splits"] + [round(s, 4)])
    return e


def remove_split(edits: dict, src_t: float) -> dict:
    e = dict(edits)
    e["splits"] = [s for s in edits["splits"] if abs(s - src_t) > 0.02]
    return e


# --------------------------------------------------------------------------- the sound
def apply_to_cut_audio(wav: Path, cuts: Cuts, edits: dict) -> None:
    """Mutes and volume changes, applied to the already cut voice (so they follow the cuts)."""
    if not edits["mutes"] and not edits["gains"]:
        return
    x, sr = sf.read(str(wav), dtype="float32", always_2d=True)
    gain = np.ones(len(x), dtype=np.float32)

    def paint(ranges: list[tuple[float, float]], factor: float) -> None:
        for s, e in ranges:
            acc = 0.0
            for ks, ke in cuts.keep:
                a, b = max(s, ks), min(e, ke)
                if b - a > 1e-6:
                    i0, i1 = int(round((acc + a - ks) * sr)), int(round((acc + b - ks) * sr))
                    i0, i1 = max(0, i0), min(len(x), i1)
                    if i1 > i0:
                        gain[i0:i1] = factor if factor == 0.0 else gain[i0:i1] * factor
                acc += ke - ks

    for g in edits["gains"]:
        paint([(g["s"], g["e"])], 10 ** (g["db"] / 20))
    paint([tuple(m) for m in edits["mutes"]], 0.0)
    # smooth every step in the gain curve over RAMP seconds so edits never click
    k = max(2, int(RAMP * sr))
    if k > 2:
        kernel = np.ones(k, dtype=np.float32) / k
        gain = np.convolve(np.pad(gain, (k // 2, k - k // 2 - 1), mode="edge"), kernel, mode="valid")[: len(x)]
    sf.write(str(wav), x * gain[:, None], sr, subtype="PCM_16")


# --------------------------------------------------------------------------- what the Studio shows
def peaks(p, n: int = 3000) -> dict:
    """Loudness of the original recording in `n` slices (0-1), cached next to the project."""
    f = p.dir / "audio_peaks.json"
    src = p.master if p.master.exists() else p.input_audio
    if f.exists() and src.exists() and f.stat().st_mtime >= src.stat().st_mtime:
        d = read_json(f)
        if d and d.get("n") == n:
            return d
    x, sr = sf.read(str(src), dtype="float32", always_2d=True)
    m = np.abs(x).max(axis=1)
    per = max(1, len(m) // n)
    v = m[: per * (len(m) // per)].reshape(-1, per).max(axis=1)
    top = float(np.percentile(v, 99.5)) or 1.0
    d = {"n": len(v), "duration": round(len(x) / sr, 4), "v": [round(float(a), 3) for a in np.clip(v / top, 0, 1)]}
    write_json(f, d)
    return d


def view(p) -> dict:
    """Everything the timeline needs, in output time."""
    cuts = p.cuts()
    ed = load(p)
    h = history(p)
    keep, acc = [], 0.0
    for s, e in cuts.keep:
        keep.append({"s": s, "e": e, "o0": round(acc, 4), "o1": round(acc + (e - s), 4)})
        acc += e - s
    out_ranges = lambda rs: [{"o0": round(src_to_out(cuts, a), 4), "o1": round(src_to_out(cuts, b), 4), "s": a, "e": b} for a, b in rs]
    return {
        "duration": round(acc, 4), "source_duration": cuts.source_duration, "keep": keep, "edits": ed,
        "cuts": [{"index": i, "s": a, "e": b, "o": round(src_to_out(cuts, a), 4), "len": round(b - a, 4)} for i, (a, b) in enumerate(ed["cuts"])],
        "mutes": out_ranges(ed["mutes"]),
        "gains": [{**r, "db": g["db"]} for r, g in zip(out_ranges([[g["s"], g["e"]] for g in ed["gains"]]), ed["gains"])],
        "splits": [{"s": s, "o": round(src_to_out(cuts, s), 4)} for s in ed["splits"]],
        "can_undo": bool(h["past"]), "can_redo": bool(h["future"]),
        "peaks": peaks(p),
    }
