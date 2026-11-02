"""Available video directors and the small broker for client-PC Claude runs.

The WebSocket transport lives in :mod:`vt.server.app`; this module owns the
state and policy so selection and timeout fallback can be tested without a
server or an Electron process.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from . import llm, paths
from .ai.providers import ClaudeCLIProvider, usage_today
from .util import now_iso, read_json, write_json

DEFAULT_ORDER = ["claude-client", "claude-server", "local"]


@dataclass
class ConnectedDirector:
    device_id: str
    device_name: str
    version: str = ""
    logged_in: bool = False
    send: Optional[Callable[[dict[str, Any]], None]] = field(default=None, repr=False)
    connected_at: float = field(default_factory=time.time)

    @property
    def id(self) -> str:
        return f"claude@{self.device_id}"


@dataclass
class PendingRun:
    id: str
    device_id: str
    project: str
    event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] = field(default_factory=dict)


class DirectorBroker:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._devices: dict[str, ConnectedDirector] = {}
        self._runs: dict[str, PendingRun] = {}

    def connect(self, device_id: str, device_name: str, *, version: str = "", logged_in: bool = False,
                send: Optional[Callable[[dict[str, Any]], None]] = None) -> ConnectedDirector:
        rec = ConnectedDirector(device_id=device_id, device_name=device_name or "This PC", version=version,
                                logged_in=bool(logged_in), send=send)
        with self._lock:
            self._devices[device_id] = rec
        return rec

    def disconnect(self, device_id: str) -> None:
        with self._lock:
            self._devices.pop(device_id, None)

    def devices(self) -> list[ConnectedDirector]:
        with self._lock:
            return list(self._devices.values())

    def request(self, device_id: str, project: str, prompt: str, timeout: Optional[float]) -> dict[str, Any]:
        with self._lock:
            device = self._devices.get(device_id)
            if not device or not device.logged_in or device.send is None:
                return {"ok": False, "reason": "Claude on that device is not connected and logged in."}
            run = PendingRun(uuid.uuid4().hex[:12], device_id, project)
            self._runs[run.id] = run
            device.send({"type": "direct", "request": run.id, "project": project, "task": "plan", "prompt": prompt})
        answered = run.event.wait(timeout)
        with self._lock:
            self._runs.pop(run.id, None)
        if not answered:
            return {"ok": False, "timeout": True, "reason": "Claude on the client PC did not answer in time."}
        return run.result

    def finish(self, request_id: str, *, ok: bool, error: str = "", detail: Optional[dict] = None) -> bool:
        with self._lock:
            run = self._runs.get(request_id)
            if run is None:
                return False
            run.result = {"ok": bool(ok), "error": error[:500], **(detail or {})}
            run.event.set()
            return True


broker = DirectorBroker()


def settings() -> dict[str, Any]:
    raw = read_json(paths.SETTINGS, {}) or {}
    order = [str(x) for x in raw.get("director_order", DEFAULT_ORDER) if isinstance(x, str)]
    if not order:
        order = list(DEFAULT_ORDER)
    wait = raw.get("director_wait_seconds", 120)
    wait_seconds = None if wait in (None, "wait") else max(5, min(3600, int(wait)))
    return {"order": order, "wait_seconds": wait_seconds}


def save_settings(*, order: Optional[list[str]] = None, wait_seconds: Any = ...) -> dict[str, Any]:
    raw = read_json(paths.SETTINGS, {}) or {}
    if order is not None:
        raw["director_order"] = [str(x) for x in order]
    if wait_seconds is not ...:
        raw["director_wait_seconds"] = wait_seconds
    write_json(paths.SETTINGS, raw)
    return settings()


def _local_ready() -> tuple[bool, str]:
    try:
        s = llm.settings()
        if s.get("llm_mode") == "off":
            return False, "The local AI is turned off in Settings."
        return True, "Runs on this server."
    except Exception as e:  # status must never make the New page fail
        return False, str(e)[:160]


def listing() -> dict[str, Any]:
    local_ok, local_note = _local_ready()
    claude = ClaudeCLIProvider()
    try:
        server_ok = claude.available()
    except Exception:
        server_ok = False
    items: list[dict[str, Any]] = [
        {"id": "best", "kind": "best", "label": "Best available", "available": True,
         "note": "Uses your fallback order."},
        {"id": "local", "kind": "local", "label": "Local AI", "available": local_ok, "note": local_note},
        {"id": "claude-server", "kind": "claude-server", "label": "Claude on the server", "available": server_ok,
         "note": "Uses Claude Code logged in on the server." if server_ok else "Claude Code is not logged in on the server."},
    ]
    for d in sorted(broker.devices(), key=lambda x: x.device_name.lower()):
        items.append({"id": d.id, "kind": "claude-client", "device": d.device_id,
                      "label": f"Claude on {d.device_name}", "available": d.logged_in,
                      "version": d.version,
                      "note": "Ready on this device." if d.logged_in else "Open Claude Code and log in on this device."})
    cfg = settings()
    return {"directors": items, **cfg, "claude_usage_today": usage_today()}


def candidates(choice: str) -> list[str]:
    available = {d["id"]: d for d in listing()["directors"]}
    if choice and choice != "best":
        result = [choice]
    else:
        result = []
        for item in settings()["order"]:
            if item == "claude-client":
                result.extend(d["id"] for d in available.values() if d["kind"] == "claude-client")
            else:
                result.append(item)
    if "local" not in result:
        result.append("local")
    return list(dict.fromkeys(result))


def record(project, who: str, *, requested: str, fallback_reason: str = "") -> None:
    project.update_meta(director={"who": who, "requested": requested or "best", "at": now_iso(),
                                  **({"fallback_reason": fallback_reason} if fallback_reason else {})})


def client_prompt(project_id: str) -> str:
    return (
        f"Direct Video Tool project {project_id}. Use only the Video Tool MCP tools. "
        "Read the script and current plan, improve the plan with plan.edit so every made picture is self-contained: name its place, "
        "visible scale, and every recurring person's fixed appearance; describe only visible things and put no writing in pictures. "
        "Run craft.check, fix critical and major picture.place and picture.drawable problems, then call plan.approve with by set to Claude. "
        "Do not render or start the plan."
    )
