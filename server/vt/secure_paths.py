"""A file inside a project's folder, or an error: a log or picture path that is a link, or that leads out of the folder, is never read or written (plan step F8)."""
from __future__ import annotations

import stat
from pathlib import Path


def project_file(project_dir: Path, name: str) -> Path:
    """`project_dir / name` when it stays inside the project: not a symbolic link or a Windows reparse point, and resolving inside the folder. ValueError otherwise."""
    root = Path(project_dir).resolve()
    path = Path(project_dir) / name
    try:
        info = path.lstat()
    except FileNotFoundError:
        info = None
    if info is not None and (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400):
        raise ValueError(f"{name} is a link, so it is not a file of this project")
    if root != path.resolve().parent and root not in path.resolve().parents:
        raise ValueError(f"{name} leads out of the project folder")
    return path
