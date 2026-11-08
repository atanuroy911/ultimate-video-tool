"""What was said to the AI and what it answered, for each video: ai_talk.jsonl in the project folder, shown in the Studio's Details sheet.

Every road to a model passes through here (providers.complete_json, llm.chat_json, the director broker, the MCP tools an outside director calls), so
the person can always read which AI was asked what, and judge the direction themselves.
"""
from __future__ import annotations

import json
import hashlib
import threading
import os
import re
import tempfile
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from ..util import now_iso
from ..modules.calls import redact
from ..secure_paths import project_file
from ..storage_bounds import generated_files, prune_generated

FILE = "ai_talk.jsonl"
MAX_TEXT = 200_000                  # a whole script task is a few tens of KB; a runaway answer must not fill the disk
MAX_ROWS = 500
MAX_LOG_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGES_BYTES = 64 * 1024 * 1024
MAX_IMAGES = 1000
MAX_ROW_IMAGES = 24
IMAGE_PATTERN = r"[a-f0-9]{64}\.(?:png|jpg|webp)"
_lock = threading.RLock()
_active: list[dict] = []            # the job queue runs one job at a time, and a stage's helper threads belong to that same job


@contextmanager
def for_project(folder: Path) -> Iterator[dict]:
    """AI calls inside the block belong to this video."""
    slot = {"dir": Path(folder), "stage": ""}
    with _lock:
        _active.append(slot)
    try:
        yield slot
    finally:
        with _lock:
            _active.remove(slot)


def set_stage(stage: str) -> None:
    with _lock:
        if _active:
            _active[-1]["stage"] = stage


def _text(value: Any) -> str:
    value = redact(value)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=1, default=str)
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + f"\n... ({len(text) - MAX_TEXT} more characters not kept)"


def _encoded(row: dict) -> bytes:
    return (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _read_rows(file: Path) -> tuple[list[dict], int, bool]:
    """Bound memory even while migrating an old, unbounded log."""
    kept = deque()
    total, next_seq, compact = 0, 0, False
    if not file.exists():
        return [], next_seq, compact
    with file.open("rb") as stream:
        index = 0
        while line := stream.readline(MAX_LOG_BYTES + 1):
            if len(line) > MAX_LOG_BYTES:
                while line and not line.endswith(b"\n"):
                    line = stream.readline(MAX_LOG_BYTES + 1)
                next_seq = max(next_seq, index + 1)
                index += 1
                compact = True
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("not a conversation row")
                seq = row.get("seq", index)
                if not isinstance(seq, int) or isinstance(seq, bool) or seq < next_seq:
                    seq = next_seq
                row["seq"] = seq
                next_seq = seq + 1
                size = len(_encoded(row))
                kept.append((row, size))
                total += size
                while len(kept) > MAX_ROWS or total > MAX_LOG_BYTES:
                    total -= kept.popleft()[1]
                    compact = True
            except (ValueError, TypeError, UnicodeDecodeError):
                next_seq = max(next_seq, index + 1)
                compact = True
            index += 1
    return [row for row, _ in kept], next_seq, compact


def _replace(file: Path, rows: list[dict]) -> None:
    # A failed compaction keeps the old record intact. The temporary filename is
    # exclusive and lives beside the log so replacing it is atomic.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=file.parent, prefix=".ai-talk-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            for row in rows:
                stream.write(_encoded(row))
        os.replace(temporary, file)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _bound_images(where: Path, rows: list[dict]) -> bool:
    folder = project_file(where, "ai-talk-images")
    referenced = {name for row in rows for name in row.get("image_files", []) if re.fullmatch(IMAGE_PATTERN, name)}
    changed = False
    for file in generated_files(folder, IMAGE_PATTERN):
        if file.name not in referenced:
            file.unlink(missing_ok=True)
    removed = prune_generated(folder, IMAGE_PATTERN, max_bytes=MAX_IMAGES_BYTES, max_files=MAX_IMAGES)
    for row in rows:
        names = row.get("image_files", [])
        expired = [name for name in names if name in removed]
        if expired:
            row["image_files"] = [name for name in names if name not in removed]
            row["image_retention_notice"] = "Older pictures were removed to keep this video's conversation storage within its limit."
            changed = True
    return changed


def record(who: str, model: str, *, system: Any = "", prompt: Any = "", answer: Any = "", seconds: float = 0.0, error: str = "", kind: str = "ask",
           cached: bool = False, images: int = 0, folder: Optional[Path] = None, image_data: Optional[list[bytes]] = None) -> None:
    """Never raises: a log must not stop a video."""
    try:
        with _lock:
            slot = _active[-1] if _active else None
        where = Path(folder) if folder else (slot["dir"] if slot else None)
        if where is None or not where.is_dir():
            return
        row = redact({"at": now_iso(), "stage": str(slot["stage"] if slot else "")[:200], "who": str(who)[:200], "model": str(model)[:200], "kind": str(kind)[:50], "system": _text(system), "prompt": _text(prompt),
                      "answer": _text(answer), "seconds": round(seconds, 1), "error": redact(error)[:1000], "cached": cached, "images": images})
        with _lock:
            file = project_file(where, FILE)
            rows, next_seq, compact = _read_rows(file)
            row["seq"] = next_seq
            names = []
            for index, data in enumerate(image_data or []):
                if index >= MAX_ROW_IMAGES or len(data) > MAX_IMAGE_BYTES:
                    row["image_retention_notice"] = "Some pictures exceeded the conversation storage limit and were not retained."
                    continue
                ext = "png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "jpg" if data.startswith(b"\xff\xd8\xff") else "webp" if data[:4]==b"RIFF" and data[8:12]==b"WEBP" else None
                if ext is None:
                    continue
                name = hashlib.sha256(data).hexdigest()+"."+ext
                try:
                    target = project_file(where, "ai-talk-images/" + name)
                    target.parent.mkdir(exist_ok=True)
                    if not target.exists():
                        target.write_bytes(data)
                    target.touch()  # reuse keeps a picture recent when its row is recent
                    names.append(name)
                except (OSError, ValueError):
                    row["image_save_error"] = "Some pictures could not be saved. Check the server's available storage."
            if names:
                row["image_files"] = names
            rows.append(row)
            total = sum(len(_encoded(item)) for item in rows)
            while len(rows) > MAX_ROWS or total > MAX_LOG_BYTES:
                total -= len(_encoded(rows.pop(0)))
                compact = True
            if compact:
                _replace(file, rows)
            else:
                with file.open("ab") as stream:
                    stream.write(_encoded(row))
            try:
                if _bound_images(where, rows):
                    _replace(file, rows)
            except (OSError, ValueError):
                pass  # text survives an image cleanup failure
    except Exception:
        pass


def load(folder: Path) -> list[dict]:
    try:
        f = project_file(Path(folder), FILE)
    except ValueError:
        return []
    with _lock:
        rows, _, _ = _read_rows(f)
    return [redact(row) for row in rows]


def retention_info(rows: list[dict]) -> dict:
    """The list view can explain when earlier conversations have been removed."""
    omitted = rows[0]["seq"] if rows else 0
    return {"omitted_before": omitted, "message":
            "Earlier conversations were removed to keep this video's record within its storage limit." if omitted else ""}
