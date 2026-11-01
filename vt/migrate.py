"""One-time move of the user's data out of a developer checkout (where projects/, voices/, models/ and settings.json sit next to the code) into the per-user data folder
(`VT_DATA`, `%LOCALAPPDATA%\\VideoTool` in the installed product).

Nothing is ever deleted or moved: files are copied (models are hard-linked when both folders are on one disk, so a 6 GB model folder costs no space and no time), the old folder is left
as it was, and a file that already exists in the new place is never overwritten. `plan()` only looks; `run()` does it.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

ITEMS = [  # (name inside the old folder, what it is, link instead of copy)
    ("projects", "your projects", False),
    ("voices", "your saved voices", False),
    ("settings.json", "your settings and keys", False),
    ("glossary.json", "your glossary", False),
    ("translate_cache.json", "the translation cache", False),
    ("ai_cache", "the AI answer cache", False),
    ("assets/music/user", "your own music", False),
    ("models", "downloaded models", True),
]


@dataclass
class Item:
    name: str
    what: str
    bytes: int
    files: int
    link: bool


@dataclass
class Report:
    src: Path
    dst: Path
    items: list[Item] = field(default_factory=list)
    copied: int = 0
    linked: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _files(p: Path):
    if p.is_file():
        yield p
    elif p.is_dir():
        yield from (f for f in p.rglob("*") if f.is_file())


def _target(name: str, dst: Path) -> Path:
    return dst / ("user-music" if name == "assets/music/user" else name)


def plan(src: Path, dst: Path, models: bool = True) -> Report:
    src, dst = Path(src).resolve(), Path(dst).resolve()
    if src == dst:
        raise ValueError("the old and the new folder are the same")
    r = Report(src, dst)
    for name, what, link in ITEMS:
        if name == "models" and not models:
            continue
        p = src / name
        if not p.exists():
            continue
        fs = list(_files(p))
        if fs:
            r.items.append(Item(name, what, sum(f.stat().st_size for f in fs), len(fs), link))
    return r


def _same_disk(a: Path, b: Path) -> bool:
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def run(src: Path, dst: Path, models: bool = True) -> Report:
    r = plan(src, dst, models)
    dst.mkdir(parents=True, exist_ok=True)
    for it in r.items:
        base = r.src / it.name
        out = _target(it.name, r.dst)
        for f in _files(base):
            rel = f.relative_to(base) if base.is_dir() else Path(f.name)
            t = out / rel if base.is_dir() else out
            if t.exists():
                r.skipped += 1                                                       # never overwrite what is already in the new place
                continue
            try:
                t.parent.mkdir(parents=True, exist_ok=True)
                if it.link and _same_disk(f, t.parent):
                    try:
                        os.link(f, t)
                        r.linked += 1
                        continue
                    except OSError:
                        pass
                shutil.copy2(f, t)
                r.copied += 1
            except OSError as e:
                r.errors.append(f"{f}: {e}")
    return r


def describe(r: Report) -> str:
    lines = [f"from {r.src}", f"  to {r.dst}"]
    for it in r.items:
        lines.append(f"  {it.what}: {it.files} files, {it.bytes / 1e6:.0f} MB" + (" (linked, no extra space)" if it.link else ""))
    if r.copied or r.linked or r.skipped or r.errors:
        lines.append(f"copied {r.copied}, linked {r.linked}, already there {r.skipped}, problems {len(r.errors)}")
    return "\n".join(lines)
