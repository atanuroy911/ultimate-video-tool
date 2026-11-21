"""The programs of ours that keep running on their own (our own Ollama and our own ComfyUI), so that a change of graphics card can restart exactly them.

Starting one records its process number and port. A process is only ever stopped when it is still the program we started: its command line must name it (and, for ComfyUI,
the port we gave it). A number the computer has given to something else since, or an Ollama or ComfyUI the person runs themselves, is never touched.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from .. import paths
from ..util import CREATE_NO_WINDOW, read_json, write_json

FILE = "engine-pids.json"
MARKERS = {"ollama": ("ollama", "serve"), "comfy": ("main.py", "--port")}          # words that must be in the command line of the program we started


def _file() -> Path:
    return paths.DATA / FILE


def remember(engine: str, pid: int, port: int, **extra: str) -> None:
    """`extra`: what else to know about how it was started (for Ollama, the memory settings it was given: llm.TUNING)."""
    data = read_json(_file(), {}) or {}
    data[engine] = {"pid": int(pid), "port": int(port), "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **{k: str(v) for k, v in extra.items()}}
    _file().parent.mkdir(parents=True, exist_ok=True)
    write_json(_file(), data)
    _seen.pop(engine, None)


def recorded(engine: str) -> Optional[dict]:
    got = (read_json(_file(), {}) or {}).get(engine)
    return got if isinstance(got, dict) and isinstance(got.get("pid"), int) else None


def _cmdline(pid: int) -> str:
    """The command line of the running process with this number; empty when there is none (or it has ended and only waits to be collected)."""
    try:
        if sys.platform.startswith("linux"):
            return Path(f"/proc/{int(pid)}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        if os.name == "nt":
            cmd = f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"
            return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=15, creationflags=CREATE_NO_WINDOW).stdout.strip()
        return subprocess.run(["ps", "-p", str(int(pid)), "-o", "command="], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""


_seen: dict[str, tuple[float, Optional[int]]] = {}


def running(engine: str, fresh: bool = False) -> Optional[int]:
    """The process number of our running copy of this engine, or None: nothing recorded, it has ended, or the number now belongs to another program.
    The answer is kept for 5 seconds (the Server page asks all the time); `fresh` asks again."""
    at, got = _seen.get(engine, (0.0, None))
    if not fresh and time.monotonic() - at < 5.0:
        return got
    info = recorded(engine)
    line = _cmdline(info["pid"]).lower() if info else ""
    ok = bool(line) and all(word in line for word in MARKERS.get(engine, ("\0",))) and (engine != "comfy" or f"--port {info.get('port')}" in line)
    got = info["pid"] if ok and info else None
    _seen[engine] = (time.monotonic(), got)
    return got


def stop(engine: str, wait: float = 15.0) -> bool:
    """Stop our own copy of the engine if it is running and is the one we started. True when something was stopped."""
    pid = running(engine, fresh=True)
    _seen.pop(engine, None)
    if pid is None:
        return False
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW)
        return True
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    t0 = time.time()
    while time.time() - t0 < wait and _cmdline(pid):
        time.sleep(0.2)
    if _cmdline(pid) and running(engine, fresh=True) == pid:            # still there after the polite request, and still the program we started
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    return True
