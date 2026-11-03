"""Append-only, plain-word director call log with secret redaction."""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LOG_LOCK = threading.RLock()
_SECRET_PARTS = ("password", "secret", "token", "api_key", "credential")
_SECRET_ASSIGNMENT = re.compile(r"(?i)\b(password|secret|token|api[_-]?key|credential)\b\s*[:=]\s*\S+")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[redacted]" if any(part in key.lower() for part in _SECRET_PARTS) else redact(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _SECRET_ASSIGNMENT.sub(r"\1=[redacted]", value)
    return value


def append_call(project_dir: Path, entry: dict[str, Any]) -> dict[str, Any]:
    path = project_dir / "calls.jsonl"
    with _LOG_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        seq = 1
        if path.exists():
            with path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        seq += 1
        record = {"seq": seq, "t": datetime.now(timezone.utc).isoformat(), **redact(entry)}
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        return record


def append_technical(project_dir: Path, lines: str, *, max_lines: int = 2000) -> None:
    """Keep a bounded diagnostic tail without recording common secret assignments."""
    path = project_dir / "technical.log"
    with _LOG_LOCK:
        existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        incoming = [redact(line) for line in lines.splitlines()]
        path.write_text("\n".join((existing + incoming)[-max_lines:]) + "\n", encoding="utf-8")


def read_calls(project_dir: Path, *, after: int = 0, level: str = "", group: str = "", q: str = "",
               limit: int = 1000) -> list[dict[str, Any]]:
    """The recorded calls in order, optionally after a sequence number, of one level or group, or containing text."""
    path = project_dir / "calls.jsonl"
    if not path.exists():
        return []
    needle = q.strip().lower()
    wanted = {part for part in level.split(",") if part}
    found: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue                    # a half-written last line is not an error
            if entry.get("seq", 0) <= after:
                continue
            if wanted and entry.get("level") not in wanted:
                continue
            if group and not str(entry.get("module", "")).startswith(group + "."):
                continue
            if needle and needle not in json.dumps(entry, ensure_ascii=False).lower():
                continue
            found.append(entry)
            if len(found) >= limit:
                break
    return found


def read_technical(project_dir: Path, *, max_lines: int = 2000) -> str:
    path = project_dir / "technical.log"
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8").splitlines()[-max_lines:])


class capture_technical:
    """While a module runs, keep the warnings and errors any library logs in the project's bounded technical.log."""

    def __init__(self, project_dir: Path, label: str):
        import logging

        self.dir, self.label, self.logging = project_dir, label, logging
        self.lines: list[str] = []
        outer = self

        class Handler(logging.Handler):
            def emit(self, record):
                outer.lines.append(f"{outer.label}: {record.name}: {record.getMessage()}")
        self.handler = Handler(level=logging.WARNING)

    def __enter__(self):
        self.logging.getLogger().addHandler(self.handler)
        return self

    def __exit__(self, *exc):
        self.logging.getLogger().removeHandler(self.handler)
        if self.lines:
            append_technical(self.dir, "\n".join(self.lines))
        return False
