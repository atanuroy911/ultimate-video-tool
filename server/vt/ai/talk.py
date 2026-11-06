"""What was said to the AI and what it answered, for each video: ai_talk.jsonl in the project folder, shown in the Studio's Details sheet.

Every road to a model passes through here (providers.complete_json, llm.chat_json, the director broker, the MCP tools an outside director calls), so
the person can always read which AI was asked what, and judge the direction themselves.
"""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from ..util import now_iso

FILE = "ai_talk.jsonl"
MAX_TEXT = 200_000                  # a whole script task is a few tens of KB; a runaway answer must not fill the disk
_lock = threading.Lock()
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
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=1, default=str)
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + f"\n... ({len(text) - MAX_TEXT} more characters not kept)"


def record(who: str, model: str, *, system: Any = "", prompt: Any = "", answer: Any = "", seconds: float = 0.0, error: str = "", kind: str = "ask",
           cached: bool = False, images: int = 0, folder: Optional[Path] = None) -> None:
    """Never raises: a log must not stop a video."""
    try:
        with _lock:
            slot = _active[-1] if _active else None
        where = Path(folder) if folder else (slot["dir"] if slot else None)
        if where is None or not where.is_dir():
            return
        row = {"at": now_iso(), "stage": slot["stage"] if slot else "", "who": who, "model": model, "kind": kind, "system": _text(system), "prompt": _text(prompt),
               "answer": _text(answer), "seconds": round(seconds, 1), "error": error[:1000], "cached": cached, "images": images}
        with _lock, (where / FILE).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load(folder: Path) -> list[dict]:
    f = Path(folder) / FILE
    if not f.exists():
        return []
    rows = []
    for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            rows.append({"seq": i, **json.loads(line)})
        except ValueError:
            continue
    return rows
