"""Storage bounds for replaceable generated files. User assets and exports are excluded."""
from __future__ import annotations

import re
import stat
import threading
from pathlib import Path

_lock = threading.RLock()


def generated_files(folder: Path, pattern: str) -> list[Path]:
    """Direct regular files with a known generated name, without following links."""
    folder = Path(folder)
    try:
        info = folder.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            return []
        root = folder.resolve()
        files = []
        for file in folder.iterdir():
            if not re.fullmatch(pattern, file.name):
                continue
            try:
                info = file.lstat()
                if stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400 and file.resolve().parent == root:
                    files.append(file)
            except (FileNotFoundError, OSError):
                continue
        return files
    except (FileNotFoundError, OSError):
        return []


def prune_generated(folder: Path, pattern: str, *, max_bytes: int, max_files: int,
                    keep: set[str] | None = None) -> set[str]:
    """Remove oldest disposable files until both limits hold. Protected names survive."""
    removed = set()
    keep = keep or set()
    with _lock:
        entries = []
        for file in generated_files(folder, pattern):
            try:
                info = file.stat()
                entries.append((info.st_mtime_ns, file.name, file, info.st_size))
            except OSError:
                continue
        total = sum(entry[3] for entry in entries)
        count = len(entries)
        for _, name, file, size in sorted(entries):
            if total <= max_bytes and count <= max_files:
                break
            if name in keep:
                continue
            try:
                # Validate again after enumeration. A replaced link is never removed.
                info = file.lstat()
                if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400 or file.resolve().parent != folder.resolve():
                    continue
                file.unlink()
            except OSError:
                continue
            removed.add(name)
            total -= size
            count -= 1
    return removed


def clear_generated(folder: Path, pattern: str) -> None:
    """Replace a generated snapshot batch while preserving unrelated files."""
    prune_generated(folder, pattern, max_bytes=0, max_files=0)
