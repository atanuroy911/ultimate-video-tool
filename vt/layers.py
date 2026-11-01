"""Layers: extra tracks the owner (or an AI) puts on top of the generated video: text, pictures, video clips and audio, each with its own time, place and fades.

`layers.json` is one document: {"v": 1, "tracks": [...], "clips": [...]}. Tracks are listed top layer first. A clip belongs to one track and the clips of a track never overlap.
The whole document is saved at once (the editor edits it locally while dragging and saves when the pointer is released), every save keeps one step of history.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any, Optional

from .util import read_json, write_json

MAX_TRACKS = 24
MAX_CLIPS = 600
VISUAL_TYPES = ("text", "media")
EMPTY: dict[str, Any] = {"v": 1, "tracks": [], "clips": []}
_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
MIN_DUR = 0.1
ANIMS = ("none", "zoom_in", "zoom_out", "slide_left", "slide_right", "slide_up", "slide_down", "pulse")


def load(project) -> dict:
    doc = read_json(project.dir / "layers.json")
    if not isinstance(doc, dict):
        return copy.deepcopy(EMPTY)
    return {"v": 1, "tracks": list(doc.get("tracks") or []), "clips": list(doc.get("clips") or [])}


def _num(v: Any, default: float, lo: float, hi: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(f):
        return default
    return min(hi, max(lo, f))


def validate(doc: Any, duration: float, media: dict[str, str]) -> tuple[dict, list[str]]:
    """Clean the document and list what is wrong. `media` maps media id -> kind ("image" | "video" | "gif" | "audio").
    Returns (clean document, errors). Errors mean the document must not be saved; the clean copy is only for showing what was understood."""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return copy.deepcopy(EMPTY), ["the layers must be an object with tracks and clips"]
    tracks_in, clips_in = doc.get("tracks") or [], doc.get("clips") or []
    if not isinstance(tracks_in, list) or not isinstance(clips_in, list):
        return copy.deepcopy(EMPTY), ["tracks and clips must be lists"]
    if len(tracks_in) > MAX_TRACKS:
        errors.append(f"at most {MAX_TRACKS} tracks")
    if len(clips_in) > MAX_CLIPS:
        errors.append(f"at most {MAX_CLIPS} clips")
    tracks: list[dict] = []
    seen: set[str] = set()
    for i, t in enumerate(tracks_in[:MAX_TRACKS]):
        tid = str(t.get("id", "")) if isinstance(t, dict) else ""
        if not _ID.match(tid) or tid in seen:
            errors.append(f"track {i + 1}: the id is missing, odd or repeated")
            continue
        seen.add(tid)
        kind = t.get("kind") if t.get("kind") in ("visual", "audio") else "visual"
        tracks.append({"id": tid, "name": str(t.get("name") or f"Track {i + 1}")[:40], "kind": kind,
                       "hidden": bool(t.get("hidden")), "muted": bool(t.get("muted")), "locked": bool(t.get("locked"))})
    kinds = {t["id"]: t["kind"] for t in tracks}
    clips: list[dict] = []
    ids: set[str] = set()
    for c in clips_in[:MAX_CLIPS]:
        if not isinstance(c, dict):
            errors.append("a clip is not an object")
            continue
        cid = str(c.get("id", ""))
        if not _ID.match(cid) or cid in ids:
            errors.append("a clip has a missing, odd or repeated id")
            continue
        ids.add(cid)
        tid = c.get("track")
        if tid not in kinds:
            errors.append(f"clip {cid}: it is on a track that does not exist")
            continue
        ctype = c.get("type")
        if ctype not in ("text", "media", "audio"):
            errors.append(f"clip {cid}: unknown type {ctype!r}")
            continue
        if (ctype == "audio") != (kinds[tid] == "audio"):
            errors.append(f"clip {cid}: {ctype} clips do not belong on a {kinds[tid]} track")
            continue
        if _num(c.get("start"), 0.0, -1e9, 1e9) > duration - MIN_DUR / 2:
            errors.append(f"clip {cid}: it starts after the end of the video")
            continue
        start = _num(c.get("start"), 0.0, 0.0, max(0.0, duration - MIN_DUR))
        end = min(duration, start + _num(c.get("dur"), 3.0, MIN_DUR, 3600.0))
        if end - start < MIN_DUR:
            errors.append(f"clip {cid}: it starts after the end of the video")
            continue
        out: dict[str, Any] = {"id": cid, "track": tid, "type": ctype, "start": round(start, 3), "dur": round(end - start, 3),
                               "fade_in": round(_num(c.get("fade_in"), 0.0, 0.0, 5.0), 2), "fade_out": round(_num(c.get("fade_out"), 0.0, 0.0, 5.0), 2)}
        if ctype in ("media", "audio"):
            mid = c.get("media")
            kind = media.get(mid) if isinstance(mid, str) else None
            if kind is None:
                errors.append(f"clip {cid}: its media is not in the project")
                continue
            if (ctype == "audio") != (kind == "audio"):
                errors.append(f"clip {cid}: a {kind} file cannot be used as {ctype}")
                continue
            out["media"] = mid
            out["in"] = round(_num(c.get("in"), 0.0, 0.0, 36000.0), 3)
        if ctype == "text":
            text = str(c.get("text") or "").strip()
            if not text:
                errors.append(f"clip {cid}: the text is empty")
                continue
            st = c.get("style") if isinstance(c.get("style"), dict) else {}
            out["text"] = text[:400]
            out["style"] = {"size": round(_num(st.get("size"), 0.06, 0.015, 0.4), 3), "color": _color(st.get("color"), "#ffffff"),
                            "bg": _color(st.get("bg"), "") or None, "weight": int(_num(st.get("weight"), 800, 300, 900)), "align": st.get("align") if st.get("align") in ("left", "center", "right") else "center"}
        if ctype in ("text", "media"):
            out["x"] = round(_num(c.get("x"), 0.5, -0.5, 1.5), 4)            # the centre of the clip, as a fraction of the frame
            out["y"] = round(_num(c.get("y"), 0.5, -0.5, 1.5), 4)
            out["w"] = round(_num(c.get("w"), 0.6 if ctype == "text" else 1.0, 0.02, 3.0), 4)
            out["h"] = None if c.get("h") in (None, "") else round(_num(c.get("h"), 1.0, 0.02, 3.0), 4)
            out["opacity"] = round(_num(c.get("opacity"), 1.0, 0.0, 1.0), 3)
            out["anim"] = c.get("anim") if c.get("anim") in ANIMS else "none"                  # a motion over the clip's time: see ANIMS
            out["fit"] = c.get("fit") if c.get("fit") in ("cover", "contain") else "cover"
        if ctype == "audio" or (ctype == "media" and media.get(c.get("media")) == "video"):
            out["volume"] = round(_num(c.get("volume"), 0.0 if ctype == "media" else 1.0, 0.0, 4.0), 3)      # a video's own sound is off unless asked for
        clips.append(out)
    # clips of one track never overlap
    by_track: dict[str, list[dict]] = {}
    for c in clips:
        by_track.setdefault(c["track"], []).append(c)
    for tid, lst in by_track.items():
        lst.sort(key=lambda c: c["start"])
        for a, b in zip(lst, lst[1:]):
            if b["start"] < a["start"] + a["dur"] - 0.001:
                errors.append(f"clips {a['id']} and {b['id']} overlap on the same track")
    return {"v": 1, "tracks": tracks, "clips": clips}, errors


def _color(v: Any, default: str) -> str:
    return v if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v) else default


# ---------------------------------------------------------------- history (one step back and forward, kept next to the document)
def _hist_path(project):
    return project.dir / "layers.history.json"


def save(project, doc: dict) -> None:
    cur = load(project)
    if cur == doc:
        return
    h = read_json(_hist_path(project), {"past": [], "future": []}) or {"past": [], "future": []}
    h["past"] = (h.get("past") or [])[-49:] + [cur]
    h["future"] = []
    write_json(_hist_path(project), h)
    write_json(project.dir / "layers.json", doc)


def history(project) -> dict:
    h = read_json(_hist_path(project), {"past": [], "future": []}) or {}
    return {"can_undo": bool(h.get("past")), "can_redo": bool(h.get("future"))}


def step(project, direction: str) -> Optional[dict]:
    h = read_json(_hist_path(project), {"past": [], "future": []}) or {"past": [], "future": []}
    src, dst = ("past", "future") if direction == "undo" else ("future", "past")
    if not h.get(src):
        return None
    cur = load(project)
    doc = h[src].pop()
    h[dst] = (h.get(dst) or []) + [cur]
    write_json(_hist_path(project), h)
    write_json(project.dir / "layers.json", doc)
    return doc


def audio_clips(project, doc: Optional[dict] = None) -> list[dict]:
    """What the final mix needs: [{path, start, dur, in, volume, fade_in, fade_out}] for every audible audio clip and every video clip that keeps its sound."""
    doc = doc or load(project)
    tracks = {t["id"]: t for t in doc["tracks"]}
    meta = project.meta()
    items = {m.id: m for m in [*meta.media, *meta.sounds]}
    out = []
    for c in doc["clips"]:
        t = tracks.get(c["track"])
        m = items.get(c.get("media", ""))
        if not t or not m or t.get("muted") or (t.get("hidden") and c["type"] != "audio"):
            continue
        vol = c.get("volume", 0.0)
        if vol <= 0 or c["type"] == "text":
            continue
        p = project.dir / (m.audio_file if m.kind in ("video", "gif") else m.file)
        if (m.kind == "audio" or m.audio_file) and p.is_file():
            out.append({"path": str(p), "start": c["start"], "dur": c["dur"], "in": c.get("in", 0.0), "volume": vol, "fade_in": c.get("fade_in", 0.0), "fade_out": c.get("fade_out", 0.0)})
    return out


def media_kinds(project) -> dict[str, str]:
    meta = project.meta()
    return {m.id: m.kind for m in [*meta.media, *meta.sounds]}
