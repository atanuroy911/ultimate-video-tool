"""A vision model describes the user's own pictures, GIFs and clips: a caption and tags (so the planner can match them to sentences by meaning),
and where the subject is (so crops keep it in frame). Existing captions and tags written by the user are never overwritten."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image

from . import AIUnavailable, complete_json, vision_provider
from ..util import ProgressFn, find_tool, noop_progress

SCHEMA = {
    "type": "object",
    "properties": {
        "caption": {"type": "string", "maxLength": 80},
        "tags": {"type": "array", "items": {"type": "string", "maxLength": 24}, "maxItems": 8},
        "has_text": {"type": "boolean"},
        "subject_x": {"type": "number", "minimum": 0, "maximum": 1},
        "subject_y": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["caption", "tags"],
}

PROMPT = """Describe this picture for a video editor who must match it to spoken sentences.
caption: what is in it, at most 12 words, plain English.
tags: 3-8 single-word or two-word subjects (objects, people, place, activity, mood).
has_text: true if readable text is visible.
subject_x / subject_y: where the main subject is, 0 = left/top, 1 = right/bottom.
Describe only what you can see."""


def frame_of(project, item) -> Path:
    """A PNG to show the model: the picture itself, or the middle frame of a clip."""
    src = project.dir / item.file
    out = project.dir / "media" / f"_describe_{item.id}.png"
    if item.kind == "image":
        im = Image.open(src).convert("RGB")
        im.thumbnail((896, 896))
        im.save(out)
        return out
    from ..director.media import _run

    _run([find_tool("ffmpeg"), "-y", "-v", "error", "-ss", str(max(0.0, (item.duration or 1.0) / 2)), "-i", str(src), "-frames:v", "1", "-vf", "scale=896:-2", str(out)])
    return out


def describe_item(project, item, provider=None) -> dict:
    f = frame_of(project, item)
    try:
        with open(f, "rb") as fh:
            return complete_json(PROMPT, SCHEMA, [fh.read()], provider=provider or vision_provider(), max_tokens=300, timeout=180, temperature=0.0)
    finally:
        f.unlink(missing_ok=True)


def describe_project(project, progress: ProgressFn = noop_progress, provider=None, only_missing: bool = True) -> dict:
    """Fill in caption/tags/subject position for media that have none. Returns {described: [ids], skipped: n, error: str|None}."""
    meta = project.meta()
    done, skipped, error = [], 0, None
    todo = [m for m in meta.media if not only_missing or not (m.caption and m.tags)]
    for i, m in enumerate(todo):
        progress("media", i / max(1, len(todo)), f"Looking at {m.id}")
        try:
            r = describe_item(project, m, provider)
        except AIUnavailable as e:
            error = str(e)
            break
        except Exception as e:                       # a broken file must not stop the others
            skipped += 1
            error = f"{type(e).__name__}: {str(e)[:100]}"
            continue
        if not m.caption:
            m.caption = r["caption"].strip()[:80]
        if not m.tags:
            m.tags = [t.strip().lower() for t in r["tags"] if t.strip()][:8]
        if not m.faces and "subject_x" in r and "subject_y" in r:       # faces, when found, are the better focus
            m.fx, m.fy = float(r["subject_x"]), float(r["subject_y"])
        done.append(m.id)
    if done:
        project.save_meta(meta)
    progress("media", 1.0, f"{len(done)} described")
    return {"described": done, "skipped": skipped, "error": error}
