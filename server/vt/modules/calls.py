"""Append-only, plain-word director call log with secret redaction."""
from __future__ import annotations

import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from collections.abc import Mapping
from pathlib import Path
from ..secure_paths import project_file
from typing import Any
from urllib.parse import quote, quote_plus


_LOG_LOCK = threading.RLock()
_SECRET_ASSIGNMENT = re.compile(
    r"""(?=(?P<prefix>\b(?P<name>[A-Za-z_][A-Za-z0-9_-]*)["']?\s*[:=]\s*)"""
    r"""(?P<value>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;&}\]"']+))"""
)
_AUTHORIZATION = re.compile(
    r"""(?i)(?P<prefix>\bauthorization["']?\s*[:=]\s*)(?P<quote>["']?)"""
    r"""(?:bearer|basic)\s+[^\s,"';}\]]+(?P=quote)"""
)
_URL_CREDENTIALS = re.compile(r"(?i)(https?://)[^/\s:@]+:[^/\s@]+@")
_DIRECTOR_TOKEN = re.compile(r"\bvtd_[A-Za-z0-9_-]{43}\b")


def is_secret_key(name: Any) -> bool:
    """Credential fields, including camelCase names; token usage and set flags are public metadata."""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name)).lower().replace("-", "_")
    if name.startswith("has_") or name.endswith("_set") or name in ("token_count", "token_usage", "token_budget", "token_limit"):
        return False
    return (name == "key" or name.endswith("_key") or name == "apikey"
            or bool(re.search(r"(?:^|_)(?:password|passwd|pass|secret|token|credential|credentials|authorization|cookie|auth)(?:_|$)", name)))


def _known_secrets() -> set[str]:
    """Read existing credentials only; logging must never create keys or import the server."""
    from .. import paths

    found = set()

    def visit(value, sensitive=False):
        if isinstance(value, Mapping):
            for name, item in value.items():
                visit(item, sensitive or is_secret_key(name))
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item, sensitive)
        elif sensitive and isinstance(value, str) and value:
            found.add(value)

    for file in (paths.SETTINGS, paths.DATA / "engine-hub.json"):
        try:
            visit(json.loads(file.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            pass
    visit(os.environ)
    serve = sys.modules.get("vt.server.serve")
    if serve is not None:
        visit({"key": serve.STATE.get("key", "")})
    return {variant for secret in found for variant in (secret, quote(secret, safe=""), quote_plus(secret, safe=""))}


def redact(value: Any) -> Any:
    """A copy safe for logs and diagnostic responses, without changing an AI's actual inputs."""
    secrets = sorted(_known_secrets(), key=len, reverse=True)

    def assignments(text):
        # Look ahead so a harmless outer field or URL does not swallow a token
        # assignment inside it. Keep the original offsets, even for nested text.
        chunks, end = [], 0
        for match in _SECRET_ASSIGNMENT.finditer(text):
            if match.start() < end or not is_secret_key(match["name"]):
                continue
            quote_char = match["value"][0] if match["value"].startswith(("'", '"')) else ""
            chunks.extend((text[end:match.start()], match["prefix"] + quote_char + "[redacted]" + quote_char))
            end = match.end("value")
        return "".join((*chunks, text[end:]))

    def clean(item):
        if isinstance(item, dict):
            return {key: "[redacted]" if is_secret_key(key) else clean(part) for key, part in item.items()}
        if isinstance(item, (list, tuple)):
            return [clean(part) for part in item]
        if isinstance(item, str):
            item = _AUTHORIZATION.sub(lambda m: m["prefix"] + m["quote"] + "[redacted]" + m["quote"], item)
            item = assignments(item)
            item = _URL_CREDENTIALS.sub(r"\1[redacted]@", item)
            item = _DIRECTOR_TOKEN.sub("[redacted]", item)
            for secret in secrets:
                item = item.replace(secret, "[redacted]")
        return item

    return clean(value)


def append_call(project_dir: Path, entry: dict[str, Any]) -> dict[str, Any]:
    path = project_file(project_dir, "calls.jsonl")
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
    path = project_file(project_dir, "technical.log")
    with _LOG_LOCK:
        existing = redact(path.read_text(encoding="utf-8")).splitlines() if path.exists() else []
        incoming = [redact(line) for line in lines.splitlines()]
        path.write_text("\n".join((existing + incoming)[-max_lines:]) + "\n", encoding="utf-8")


def read_calls(project_dir: Path, *, after: int = 0, level: str = "", group: str = "", q: str = "",
               limit: int = 1000) -> list[dict[str, Any]]:
    """The recorded calls in order, optionally after a sequence number, of one level or group, or containing text."""
    try:
        path = project_file(project_dir, "calls.jsonl")
    except ValueError:                                  # a link or a path out of the project: nothing is read
        return []
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
            if not isinstance(entry, dict):
                continue
            entry = redact(entry)
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
    try:
        path = project_file(project_dir, "technical.log")
    except ValueError:
        return ""
    if not path.exists():
        return ""
    return redact("\n".join(path.read_text(encoding="utf-8").splitlines()[-max_lines:]))


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
