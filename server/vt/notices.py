"""What the person is told when an optional extra was skipped (docs/plans/PLAN-WORKBENCH.MD W4.3): a missing model, an engine that did not
answer, a check that failed. The video is still made; the project says what was left out and why, in plain words, and the technical log keeps
the traceback. Stored as `notices.json` in the project (newest last, at most 50); the Studio shows them on the video's page.
"""
from __future__ import annotations

import logging
from typing import Optional

from .util import now_iso, read_json, write_json

FILE = "notices.json"
MAX = 50
log = logging.getLogger("vt.notices")


def record(project, stage: str, message: str, error: Optional[BaseException] = None) -> dict:
    """Say that something optional was skipped. `message` is for the person ("The sound check was skipped, so no sound stickers were added.")."""
    if error is not None:
        log.warning("%s: %s (%s: %s)", stage, message, type(error).__name__, error, exc_info=error)
    else:
        log.warning("%s: %s", stage, message)
    item = {"at": now_iso(), "stage": stage, "message": message[:300], "error": f"{type(error).__name__}: {str(error)[:200]}" if error else ""}
    try:
        path = project.dir / FILE
        items = [i for i in (read_json(path, []) or []) if not (i.get("stage") == stage and i.get("message") == item["message"])]
        write_json(path, (items + [item])[-MAX:])
    except Exception as e:                                                     # noqa: BLE001 — telling the person must never stop the video
        log.warning("could not record a notice: %s", e)
    return item


def load(project) -> list[dict]:
    return read_json(project.dir / FILE, []) or []


def clear(project, stage: str) -> None:
    """A stage that ran cleanly again: its old notices are no longer true."""
    path = project.dir / FILE
    items = read_json(path, []) or []
    keep = [i for i in items if i.get("stage") != stage]
    if len(keep) != len(items):
        write_json(path, keep)
