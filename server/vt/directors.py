"""Available video directors and the small broker for client-PC Claude runs.

The WebSocket transport lives in :mod:`vt.server.app`; this module owns the
state and policy so selection and timeout fallback can be tested without a
server or an Electron process.
"""
from __future__ import annotations

import base64
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from . import llm, paths
from .ai.providers import ClaudeCLIProvider, usage_today
from .util import now_iso, read_json, write_json

DEFAULT_ORDER = ["claude-client", "codex-client", "claude-server", "local"]
DEFAULT_MODEL = "sonnet"                       # what Claude on the person's computer runs, unless Settings says otherwise
WORK_LIMIT = 1800                              # a director that has started is working, not busy: it gets this long to finish the whole video
ASK_EXTRA_WAIT = 60                            # a question may wait behind another one at the helper before its own time starts
MAX_ANSWER = 2_000_000
GRACE_SECONDS = 90                             # how long a task waits for its computer to come back after the connection drops
BOOT = uuid.uuid4().hex[:12]                   # told to every helper that connects: a different one next time means the server restarted, and what it was waiting for is gone
SEEN_FILE = "directors-seen.json"              # computers that have been connected, kept in the data folder
SEEN_KEEP_DAYS = 60


def _seen_path():
    return paths.DATA / SEEN_FILE


def _recent_seen(now: float) -> dict[str, dict]:
    """Recent connection history, newest first, even if nobody has connected since it expired."""
    try:
        seen = read_json(_seen_path(), {})
    except (OSError, ValueError):
        return {}
    if not isinstance(seen, dict):
        return {}
    cutoff = now - SEEN_KEEP_DAYS * 86400
    recent = []
    for key, row in seen.items():
        if not isinstance(row, dict) or not isinstance(row.get("device"), str) or not row["device"]:
            continue
        try:
            stamp = datetime.fromisoformat(row.get("last_seen", "")).timestamp()
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        if stamp >= cutoff:
            recent.append((stamp, key, row))
    return {key: row for _, key, row in sorted(recent, key=lambda entry: entry[0], reverse=True)}


def who_asked(assistant: str) -> str:
    """The one name a video's conversations carry for a director on the person's computer (vt/ai/talk.py)."""
    return f"{assistant}-pc"


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
    kind: str = "direct"                       # a whole planning session, or one question
    assistant: str = "claude"
    event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] = field(default_factory=dict)
    message: dict[str, Any] = field(default_factory=dict, repr=False)          # what was sent, to send again when the computer comes back
    resend: bool = False
    mcp_token: str = field(default="", repr=False)
    started: float = 0.0                       # when the assistant began this task on its computer (its first line of progress); 0 while it still waits there


class DirectorBroker:
    def __init__(self, grace: float = GRACE_SECONDS) -> None:
        self._lock = threading.RLock()
        self._devices: dict[str, ConnectedDirector] = {}
        self._runs: dict[str, PendingRun] = {}
        self.grace = grace
        self._abandoned: dict[str, list[str]] = {}         # device key -> requests the server gave up on while it was away: cancelled when it returns
        self._noted: dict[str, float] = {}

    def connect(self, device_id: str, device_name: str, *, version: str = "", logged_in: bool = False,
                send: Optional[Callable[[dict[str, Any]], None]] = None, assistant: str = 'claude') -> ConnectedDirector:
        rec = ConnectedDirector(device_id=device_id, device_name=device_name or "This PC", version=version,
                                logged_in=bool(logged_in), send=send, assistant=assistant)
        key = self._key(device_id, assistant)
        with self._lock:
            before = self._devices.get(key)
            self._devices[key] = rec
            if before is not None and before.send is not send:          # a new connection replaced the old one: whatever went down the old one may never have arrived
                for run in self._runs.values():
                    if self._key(run.device_id, run.assistant) == key:
                        run.resend = True
            if send is not None:
                for request in self._abandoned.pop(key, []):            # the server gave up on these while the computer was away: stop them there too
                    self._safely(send, {"type": "cancel", "request": request})
                for run in list(self._runs.values()):
                    if run.resend and run.message and self._key(run.device_id, run.assistant) == key:
                        run.resend = not self._safely(send, run.message)      # the helper ignores a task it already has
        self._note(rec)
        return rec

    @staticmethod
    def _safely(send: Callable[[dict[str, Any]], None], message: dict[str, Any]) -> bool:
        try:
            send(message)
            return True
        except Exception:
            return False

    def _note(self, rec: ConnectedDirector, *, gone: bool = False) -> None:
        """Remember a computer that was connected, so the list can still show it, as not connected, after it goes (and after a restart of the server)."""
        key = f"{rec.assistant}:{rec.device_id}"
        now = time.time()
        with self._lock:
            if not gone and now - self._noted.get(key, 0) < 60:
                return
            self._noted[key] = now
            try:
                seen = _recent_seen(now)
                seen[key] = {"device": rec.device_id, "assistant": rec.assistant, "name": rec.device_name, "version": rec.version, "last_seen": now_iso()}
                write_json(_seen_path(), seen)
            except Exception:
                pass                                                     # a list of old computers must never stop a connection

    def disconnect(self, device_id: str, send: Optional[Callable[[dict[str, Any]], None]] = None) -> None:
        """The connection to a computer ended. Its tasks are kept for `grace` seconds: they go again when it comes back, and only fail if it does not."""
        gone: list[str] = []
        with self._lock:
            for key, current in list(self._devices.items()):
                if current.device_id == device_id and (send is None or current.send is send):
                    self._devices.pop(key, None)
                    gone.append(key)
                    self._note(current, gone=True)
            for run in self._runs.values():
                if self._key(run.device_id, run.assistant) in gone:
                    run.resend = True
        for key in gone:
            if self.grace <= 0:
                self._expire(key)
            else:
                timer = threading.Timer(self.grace, self._expire, (key,))
                timer.daemon = True
                timer.start()

    def _expire(self, key: str) -> None:
        """The grace period is over: a computer that has not come back fails the tasks it still owed, with a reason a person can act on."""
        with self._lock:
            if key in self._devices:
                return
            for run in list(self._runs.values()):
                if self._key(run.device_id, run.assistant) == key and run.resend and not run.event.is_set():
                    who = "Codex" if run.assistant == "codex" else "Claude"
                    why = (f"{who} on that computer lost its connection to this server and did not come back within {int(self.grace)} seconds. "
                           "Open Video Tool there (its helper starts with the computer), or use a director on the server.")
                    run.result = {"ok": False, "error_kind": "other", "reason": why, "error": why[:500]}
                    from .mcp.scope import revoke

                    revoke(run.mcp_token)
                    run.event.set()
                    self._abandoned.setdefault(key, []).append(run.id)

    def devices(self) -> list[ConnectedDirector]:
        with self._lock:
            return list(self._devices.values())

    @staticmethod
    def _key(device_id: str, assistant: str) -> str:
        return device_id if assistant == 'claude' else f'{assistant}:{device_id}'

    def ready(self, device_id: str, assistant: str = 'claude') -> bool:
        """Connected and signed in, so a task can be sent."""
        with self._lock:
            d = self._devices.get(self._key(device_id, assistant))
            return bool(d and d.logged_in and d.send is not None)

    def who_directing(self, project: str) -> str:
        """The conversation name of the director now running a planning session for this project (the tools it calls are recorded under it), or ''."""
        with self._lock:
            return next((who_asked(r.assistant) for r in self._runs.values() if r.kind == "direct" and r.project == project), "")

    def _cancel(self, device_id: str, assistant: str, request: str) -> None:
        """Tell the helper this task is no longer wanted, so it stops spending the person's Claude or Codex on it."""
        with self._lock:
            d = self._devices.get(self._key(device_id, assistant))
        try:
            if d is not None and d.send is not None:
                d.send({"type": "cancel", "request": request})
        except Exception:
            pass

    def request(self, device_id: str, project: str, prompt: str, timeout: Optional[float], assistant: str = 'claude') -> dict[str, Any]:
        from .mcp.scope import issue, revoke

        with self._lock:
            device = self._devices.get(self._key(device_id, assistant))
            if not device or not device.logged_in or device.send is None:
                return {"ok": False, "reason": "Claude on that device is not connected and logged in."}
            run = PendingRun(uuid.uuid4().hex[:12], device_id, project, "direct", assistant)
            run.mcp_token = issue(project, ttl=86400 if timeout is None else timeout + WORK_LIMIT + ASK_EXTRA_WAIT + self.grace)
            run.message = {"type": "direct", "request": run.id, "project": project, "task": "plan", "prompt": prompt, 'assistant': assistant,
                           "model": task_model(assistant), "director_token": run.mcp_token}
            self._runs[run.id] = run
            try:
                device.send(run.message)
            except Exception as e:
                self._runs.pop(run.id, None)
                revoke(run.mcp_token)
                return {"ok": False, "reason": f"The director request could not be sent ({type(e).__name__})."}
        from . import paths
        from .ai import talk

        began = time.time()
        folder = paths.PROJECTS / project
        who = who_asked(assistant)
        talk.record(who, "", prompt=prompt, kind="sent", folder=folder)
        # `timeout` is how long the person waits for a computer that is busy with something else (Settings, Directors). Once the assistant has
        # begun this video it is not busy, it is directing: reading the task, writing the script and looking at its frames takes minutes.
        answered = False
        try:
            while not answered:
                now = time.time()
                left = (run.started + WORK_LIMIT - now) if run.started else (None if timeout is None else began + timeout - now)
                if left is not None and left <= 0:
                    break
                answered = run.event.wait(1.0 if left is None else min(1.0, left))
        finally:
            revoke(run.mcp_token)
        with self._lock:
            self._runs.pop(run.id, None)
        if not answered:
            self._cancel(device_id, assistant, run.id)
            name = assistant.capitalize()
            why = (f"{name} on the client PC worked for {WORK_LIMIT // 60} minutes without finishing." if run.started
                   else f"{name} on the client PC did not answer in time.")
            talk.record(who, "", kind="finished", seconds=time.time() - began, error="It did not finish in time." if run.started else "It did not answer in time.", folder=folder)
            return {"ok": False, "timeout": True, "reason": why}
        talk.record(who, "", kind="finished", answer=run.result, seconds=time.time() - began, error=str(run.result.get("error") or ""), folder=folder)
        return run.result

    def working(self, request_id: str) -> None:
        """The assistant's computer reported progress on this task: it has begun, so the wait for a busy computer is over."""
        with self._lock:
            run = self._runs.get(request_id)
            if run is not None and run.kind == "direct" and not run.started:
                run.started = time.time()

    def ask(self, device_id: str, assistant: str, *, system: str, prompt: str, schema: dict, images: list[bytes], model: str, timeout: float) -> dict[str, Any]:
        """One question to Claude or Codex on the person's computer, answered as JSON text. Blocks like `request`. The conversation row is written by
        `complete_json`, which is the only caller (ClientProvider), so it is not written here."""
        with self._lock:
            device = self._devices.get(self._key(device_id, assistant))
            if not device or not device.logged_in or device.send is None:
                return {"ok": False, "reason": f"{assistant.capitalize()} on that computer is not connected and signed in.", "error_kind": "login"}
            run = PendingRun(uuid.uuid4().hex[:12], device_id, "", "ask", assistant)
            run.message = {"type": "ask", "request": run.id, "assistant": assistant, "model": model, "system": system, "prompt": prompt, "schema": schema,
                           "images": [base64.b64encode(i).decode("ascii") for i in images], "timeout": timeout}
            self._runs[run.id] = run
            try:
                device.send(run.message)
            except Exception as e:
                self._runs.pop(run.id, None)
                return {"ok": False, "reason": f"The question could not be sent ({type(e).__name__}).", "error_kind": "other"}
        answered = run.event.wait(timeout + ASK_EXTRA_WAIT)
        with self._lock:
            self._runs.pop(run.id, None)
        if not answered:
            self._cancel(device_id, assistant, run.id)
            return {"ok": False, "timeout": True, "reason": f"{assistant.capitalize()} on your computer did not answer in time."}
        return run.result

    def finish(self, request_id: str, *, ok: bool, error: str = "", detail: Optional[dict] = None, device_id: Optional[str] = None) -> bool:
        with self._lock:
            run = self._runs.get(request_id)
            if run is None or (device_id is not None and run.device_id!=device_id):
                return False
            run.result = {"ok": bool(ok), "error": error[:500], **(detail or {})}
            from .mcp.scope import revoke

            revoke(run.mcp_token)
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
    return {"order": order, "wait_seconds": wait_seconds, "director_model": model_name(raw.get("director_model"))}


def task_model(assistant: str) -> str:
    """The model a task asks for. The setting names a Claude model (Sonnet, Opus): Codex has models of its own, so it is asked for none and uses the one it is set up with."""
    return "" if assistant == "codex" else str(settings().get("director_model") or DEFAULT_MODEL)


def model_name(value: Any) -> str:
    """A model name for Claude on the person's computer: letters, digits, dots and dashes only (the helper accepts nothing else)."""
    text = str(value or "")
    return text if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.\-]*", text) else DEFAULT_MODEL


def save_settings(*, order: Optional[list[str]] = None, wait_seconds: Any = ..., model: Optional[str] = None) -> dict[str, Any]:
    raw = read_json(paths.SETTINGS, {}) or {}
    if order is not None:
        raw["director_order"] = [str(x) for x in order]
    if model is not None:
        raw["director_model"] = model_name(model)
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
    live = sorted(broker.devices(), key=lambda d: d.device_name.casefold())
    for d in live:
        items.append({"id": d.id, "kind": f"{d.assistant}-client", "device": d.device_id, "device_name": d.device_name,
                      "label": f"{'Codex' if d.assistant=='codex' else 'Claude'} on {d.device_name}", "available": d.logged_in,
                      "version": d.version,
                      "note": "Ready on this device." if d.logged_in else f"Open {'Codex' if d.assistant == 'codex' else 'Claude Code'} on this device and sign in."})
    here = {d.id for d in live}
    displayed = {(d.assistant, d.device_name.strip().casefold()) for d in live}
    offline = []
    for seen in _recent_seen(time.time()).values():
        assistant = seen.get("assistant", "claude")
        name = str(seen.get("name") or "").strip()
        did = f"{assistant}@{seen['device']}"
        if did in here:
            continue
        if name.casefold() not in ("", "this pc"):
            # A reinstall can leave a new ID under the same computer name.
            # Keep every live connection and only the newest offline alias.
            alias = (assistant, name.casefold())
            if alias in displayed:
                continue
            displayed.add(alias)
        who = "Codex" if assistant == "codex" else "Claude"
        offline.append({"id": did, "kind": f"{assistant}-client", "device": seen["device"], "device_name": name,
                        "label": f"{who} on {name or 'another computer'}", "available": False,
                        "version": seen.get("version", ""), "last_seen": seen["last_seen"],
                        "note": "Not connected. Open Video Tool on that computer; its helper starts with it and reconnects by itself."})
    items.extend(sorted(offline, key=lambda d: d["device_name"].casefold()))
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


def failure_line(who: str, result: dict, label: str) -> str:
    """Why a director on the person's computer did not finish, in plain words and without a full stop: its usage limit, its sign-in, or what it said."""
    name = "Codex" if str(who).startswith("codex@") else "Claude"
    kind = result.get("error_kind")
    if kind == "limit":
        return f"{name}'s usage limit was reached"
    if kind == "login":
        return f"{name} is not signed in on that computer"
    said = str(result.get("reason") or result.get("error") or "it did not submit a valid plan").strip().rstrip(".")
    return f"{label} did not finish ({said[:120]})"


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


def client_story_prompt(project_id: str) -> str:
    return (
        f"Direct Video Tool project {project_id}, a Cartoon 2 story video. Use only the Video Tool MCP tools. Call get_story_task for this project: "
        "it has the designer rules, the catalog of everything that can be drawn, the timed captions, the cast and the current story (a rule draft). "
        "Improve every scene so it shows what its words say, keep times on the words, draw people kindly, then submit the whole story with "
        "submit_story. Nothing is changed behind your back: whatever the app would have had to drop or replace in what you wrote (an element type it cannot draw, a background it does not "
        "have, a speaker who is not in the cast, a sound it does not know) comes back as an error, so fix every error and submit again, and treat every warning as something to fix too. "
        "Then look at your cut with preview_frames, and submit again if a frame is unclear or a face is covered. Do not render or publish."
    )


def client_scene_prompt(project_id: str) -> str:
    return (
        f"Direct Video Tool project {project_id} using only the Video Tool MCP tools. First call get_script_task once for this project. "
        "It includes the timed words, schema and visual choices. Write the complete Video Script yourself and call submit_script immediately. "
        "Cover every beat using facts from the source. Fix any errors returned by submit_script. Do not call another module to plan the script for you. "
        "After a successful submission, call module_call with module_id craft.check and inputs {}. Look once using preview_frames and frame_facts "
        "at a moment in each scene. Apply one revision with update_scene for the problems you found, then finish. "
        "Elements take x, y, scale and rotation; cartoon characters take x, y and arrive. Do not render or publish."
    )
