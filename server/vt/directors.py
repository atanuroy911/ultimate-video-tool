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

DEFAULT_ORDER = ["claude-client", "codex-client", "claude-server", "local"]


@dataclass
class ConnectedDirector:
    device_id: str
    device_name: str
    version: str = ""
    logged_in: bool = False
    send: Optional[Callable[[dict[str, Any]], None]] = field(default=None, repr=False)
    connected_at: float = field(default_factory=time.time)
    assistant: str = 'claude'

    @property
    def id(self) -> str:
        return f"{self.assistant}@{self.device_id}"


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
                send: Optional[Callable[[dict[str, Any]], None]] = None, assistant: str = 'claude') -> ConnectedDirector:
        rec = ConnectedDirector(device_id=device_id, device_name=device_name or "This PC", version=version,
                                logged_in=bool(logged_in), send=send, assistant=assistant)
        with self._lock:
            self._devices[device_id if assistant=='claude' else f'{assistant}:{device_id}'] = rec
        return rec

    def disconnect(self, device_id: str, send: Optional[Callable[[dict[str, Any]], None]] = None) -> None:
        with self._lock:
            removed=False
            for key,current in list(self._devices.items()):
                if current.device_id==device_id and (send is None or current.send is send):
                    self._devices.pop(key, None)
                    removed=True
            if removed:
                for run in self._runs.values():
                    if run.device_id==device_id:
                        run.result={'ok':False,'reason':'The client companion disconnected. Reconnect it or use a server-side director.'}
                        run.event.set()

    def devices(self) -> list[ConnectedDirector]:
        with self._lock:
            return list(self._devices.values())

    def request(self, device_id: str, project: str, prompt: str, timeout: Optional[float], assistant: str = 'claude') -> dict[str, Any]:
        with self._lock:
            device = self._devices.get(device_id if assistant=='claude' else f'{assistant}:{device_id}')
            if not device or not device.logged_in or device.send is None:
                return {"ok": False, "reason": "Claude on that device is not connected and logged in."}
            run = PendingRun(uuid.uuid4().hex[:12], device_id, project)
            self._runs[run.id] = run
            try:
                device.send({"type": "direct", "request": run.id, "project": project, "task": "plan", "prompt": prompt, 'assistant':assistant})
            except Exception as e:
                self._runs.pop(run.id, None)
                return {"ok": False, "reason": f"The director request could not be sent ({type(e).__name__})."}
        answered = run.event.wait(timeout)
        with self._lock:
            self._runs.pop(run.id, None)
        if not answered:
            return {"ok": False, "timeout": True, "reason": "Claude on the client PC did not answer in time."}
        return run.result

    def finish(self, request_id: str, *, ok: bool, error: str = "", detail: Optional[dict] = None, device_id: Optional[str] = None) -> bool:
        with self._lock:
            run = self._runs.get(request_id)
            if run is None or (device_id is not None and run.device_id!=device_id):
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
        items.append({"id": d.id, "kind": f"{d.assistant}-client", "device": d.device_id,
                      "label": f"{'Codex' if d.assistant=='codex' else 'Claude'} on {d.device_name}", "available": d.logged_in,
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
            if item in ("claude-client", "codex-client"):
                result.extend(d["id"] for d in available.values() if d["kind"] == item)
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
        f"Direct Video Tool project {project_id}. Use only the Video Tool MCP tools. First call module_catalog_tool to discover the system's capabilities; use module_describe_tool for exact inputs instead of guessing. Call get_reel_plan and read the script, moments, "
        "places, cast, rules and current checks. Improve it by calling module_call_tool with module_id plan.edit once per operation and a "
        "specific why. Every made picture must be self-contained: set its place, visible scale and every recurring person's fixed appearance; "
        "describe only visible things and put no writing in pictures. Call check_reel_plan, fix every picture.place and picture.drawable "
        "problem, then call module_call_tool with module_id plan.approve and inputs {\"by\":\"Claude\"}. Do not call plan.start or render."
    )


def client_scene_prompt(project_id: str) -> str:
    return (
        f"Direct Video Tool project {project_id}. Use only the Video Tool MCP tools. First call module_catalog_tool to discover the system's capabilities; use module_describe_tool for exact inputs instead of guessing. Call get_script_task for this project, read its "
        "timed transcript, craft rules, style and schema, then write and submit a complete Video Script with submit_script. Cover every "
        "beat, use only facts from the source, keep every picture drawable, and fix every validation error. Then call module_call_tool with "
        "module_id craft.check and inputs {}, and fix every critical and major violation it reports. Do not render or publish."
    )
