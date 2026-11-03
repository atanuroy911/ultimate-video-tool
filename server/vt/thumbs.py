"""Scene thumbnails for the Studio scene list (one HyperFrames snapshot call for all scenes)."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from .compose import FORMATS, compose_project
from .project import Project
from .render.hyperframes import snapshot
from .util import read_json, write_json


def thumbs_dir(project: Project, aspect: str) -> Path:
    return project.dir / "thumbs" / FORMATS[aspect]["tag"]


def make_thumbnails(project: Project, aspect: str) -> dict:
    """Return {"hash": str, "scenes": {scene_id: filename}}. Skips work when scenes/theme/transcript are unchanged."""
    index = compose_project(project, aspect)
    data = read_json(index.parent / "data.json")
    sig = hashlib.sha1((index.parent / "data.json").read_bytes()).hexdigest()[:12]
    out = thumbs_dir(project, aspect)
    manifest = read_json(out / "manifest.json")
    if manifest and manifest.get("hash") == sig:
        return manifest
    times = []
    for sc in data["scenes"]:
        span = sc["end"] - sc["start"]
        last = max((e["at"] for e in sc["elements"]), default=sc["start"])
        times.append(round(min(sc["end"] - 0.05, max(sc["start"] + 0.9, last + 0.9, sc["start"] + span * 0.5)), 3))
    tmp = out / "_tmp"
    files = snapshot(index.parent, tmp, times)
    out.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    for sc, f in zip(data["scenes"], files):
        name = f"{sc['id']}-{sig}.png"
        shutil.move(str(f), out / name)
        mapping[sc["id"]] = name
    shutil.rmtree(tmp, ignore_errors=True)
    for old in out.glob("*.png"):
        if old.name not in mapping.values():
            old.unlink()
    manifest = {"hash": sig, "scenes": mapping}
    write_json(out / "manifest.json", manifest)
    return manifest
