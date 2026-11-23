"""The whole video in the HyperFrames Studio (docs/plans/PLAN-OPENMOTION.MD, O4).

"Edit in Studio" bakes the video's current composition (vt/bake.py) into `<project>/studio-<shape>/` and opens the Studio on that folder, so every scene
is a clip on its timeline and every part on the picture can be selected, moved, retyped and re-animated. The Studio saves into that folder itself.
The export draws from it when it holds edits and was baked from the composition the export is about to draw; when the video changed since (a new plan,
a re-timed cut), the edits no longer fit it: the export uses the new video and says so, and the next "Edit in Studio" bakes afresh.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Optional

from . import shot_studio as ST
from .bake import bake

BASELINE = ".baked.html"           # the page as baked, to tell edits from no edits
STAMP = ".baked.json"              # what it was baked from


def folder(project, tag: str) -> Path:
    return project.dir / f"studio-{tag}"


def fingerprint(comp_dir: Path) -> str:
    """What the video is, from its data. Captions on or off is not part of it: the baked captions are their own composition, left out when not wanted."""
    try:
        data = json.loads((comp_dir / "data.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    data.pop("captions_enabled", None)
    return hashlib.sha1(b"v2" + json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


HOST = re.compile(r'<div id="captions"[^>]*data-composition-src="captions\.html"[^>]*></div>')


def without_captions(src: Path, dst: Path) -> Path:
    """The edited video with its captions composition left out (an export without captions)."""
    from .bake import _link_or_copy

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, copy_function=_link_or_copy, ignore=shutil.ignore_patterns(BASELINE, STAMP, "captions.html"))
    page = dst / "index.html"
    page.write_text(HOST.sub("", page.read_text(encoding="utf-8")), encoding="utf-8")
    return dst


def info(project, tag: str, comp_dir: Optional[Path] = None) -> dict:
    """Whether this shape has Studio edits, and whether they still fit the current composition."""
    d = folder(project, tag)
    if not (d / "index.html").exists() or not (d / BASELINE).exists():
        return {"baked": False, "edited": False, "current": False}
    edited = (d / "index.html").read_bytes() != (d / BASELINE).read_bytes()
    try:
        stamp = json.loads((d / STAMP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stamp = {}
    current = comp_dir is not None and stamp.get("from") == fingerprint(comp_dir)
    return {"baked": True, "edited": edited, "current": current, "dir": str(d)}


def prepare(project, tag: str, comp_dir: Path, *, fresh: bool = False) -> dict:
    """Bake the composition into the Studio folder, unless edits made on this same composition are already there (they are kept)."""
    d = folder(project, tag)
    have = info(project, tag, comp_dir)
    if have["baked"] and have["current"] and not fresh:
        return {**have, "kept": True}
    if have["edited"] and not have["current"]:                     # older edits: kept beside, never thrown away silently
        old = project.dir / f"studio-{tag}.old"
        shutil.rmtree(old, ignore_errors=True)
        shutil.move(str(d), str(old))
    got = bake(comp_dir, d)
    shutil.copy(d / "index.html", d / BASELINE)
    (d / STAMP).write_text(json.dumps({"from": fingerprint(comp_dir), "lost": got["lost"][:20], "lost_count": got["lost_count"]}, indent=1), encoding="utf-8")
    return {**info(project, tag, comp_dir), "kept": False, "lost_count": got["lost_count"]}


def open_video(project, tag: str, comp_dir: Path, *, fresh: bool = False) -> dict:
    """Bake (or keep) and start the Studio on the whole video. The Studio writes into the folder itself, so saving only reports."""
    ready = prepare(project, tag, comp_dir, fresh=fresh)
    d = folder(project, tag)

    def saver() -> dict:
        now = info(project, tag, comp_dir)
        return {"saved": True, "changed": now["edited"], "assets": []}

    out = ST.start(f"{project.id}/video/{tag}", d, saver, project.dir)
    return {**out, **{k: ready[k] for k in ("kept", "edited") if k in ready}, "lost_count": ready.get("lost_count", 0)}


def for_render(project, tag: str, comp_dir: Path, captions: bool = True) -> tuple[Path, Optional[str]]:
    """The folder the export should draw, and a sentence for the person when their Studio edits are not used."""
    have = info(project, tag, comp_dir)
    if not have["edited"]:
        return comp_dir, None
    if have["current"]:
        if not captions:
            return without_captions(Path(have["dir"]), project.dir / f".studio-{tag}-nocaptions"), None
        return Path(have["dir"]), None
    return comp_dir, ("The video changed after it was edited in the Studio, so those Studio edits are not in this export. "
                      "Open the Studio again to edit the new version (the old edits are kept in the project folder).")
