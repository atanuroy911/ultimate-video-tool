"""The Engine hub: one computer that runs everything the app needs and offers it to the others (docs/plans/PLAN-PACKAGING.MD).

    vt engine setup      # install Ollama, ComfyUI (and the models) on this computer, once; resumable
    vt engine run        # start them, then the gateway; prints the address and a pairing code
    vt engine pair       # a new pairing code for another computer
    vt engine service    # start it at every login / boot

The hub is the same code the Studio uses to set engines up on its own computer (`vt.engines.setup`): "both on one PC" and "the server on another PC" differ only in who
asks. The gateway (`vt.engines.server`) keeps the services themselves on 127.0.0.1 and hands the paired computer one key that opens them all.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from .. import paths
from ..util import CREATE_NO_WINDOW, read_json, write_json

IDENTITY = "engine-hub.json"
# where each service listens ON THIS COMPUTER: never exposed except through the gateway and its key
LOCAL_URLS = {"ollama": "http://127.0.0.1:11434", "comfy": "http://127.0.0.1:8188", "voicestudio": "http://127.0.0.1:3900"}
DEFAULT_ENGINES = ("ollama", "comfy")


def identity_path() -> Path:
    return paths.DATA / IDENTITY


def identity() -> dict[str, Any]:
    """The key that opens this hub. Made once and kept, so a restart does not unpair the computers that already use it."""
    d = read_json(identity_path(), {}) or {}
    if not d.get("key"):
        d = {**d, "key": secrets.token_urlsafe(32)}
        identity_path().parent.mkdir(parents=True, exist_ok=True)
        write_json(identity_path(), d)
    return d


def new_code() -> str:
    """A pairing code short enough to read out. It works once."""
    return "-".join(secrets.token_hex(2) for _ in range(3))


def reset_key() -> str:
    """Throw the old key away: every paired computer must pair again."""
    d = read_json(identity_path(), {}) or {}
    d["key"] = secrets.token_urlsafe(32)
    write_json(identity_path(), d)
    return d["key"]


def service_urls(only: Optional[list[str]] = None) -> dict[str, str]:
    """The services the gateway should offer: environment overrides (VT_HUB_OLLAMA=http://...) on top of the local defaults, limited to `only` when given."""
    out = {}
    for name, url in LOCAL_URLS.items():
        if only is not None and name not in only:
            continue
        out[name] = os.environ.get(f"VT_HUB_{name.upper()}", url).rstrip("/")
    return out


def reachable(name: str, url: str, timeout: float = 1.5) -> bool:
    probe = {"ollama": "/api/version", "comfy": "/system_stats", "voicestudio": "/health"}.get(name, "/")
    try:
        return httpx.get(url + probe, timeout=timeout).status_code == 200
    except Exception:                                                                   # noqa: BLE001
        return False


# ----------------------------------------------------------------------------- setup
def plan(engines: list[str], bundles: list[str], models: str = "") -> list[dict[str, Any]]:
    from . import installers

    out = []
    for e in engines:
        kw: dict[str, Any] = {"bundles": tuple(bundles), "models": models} if e == "comfy" else {}
        out.append(installers.installer(e, **kw).plan().public())
    return out


def setup(engines: list[str], bundles: list[str], progress: Callable[[str, float, str], None], models: str = "") -> dict[str, Any]:
    """Install each engine that is not complete, in order. An engine that fails is reported and the next one still runs: a half set-up hub is better than none."""
    from . import installers

    result: dict[str, Any] = {}
    for i, e in enumerate(engines):
        kw: dict[str, Any] = {"bundles": tuple(bundles), "models": models} if e == "comfy" else {}
        base, span = i / max(1, len(engines)), 1 / max(1, len(engines))
        try:
            inst = installers.installer(e, **kw)
            if inst.verify() and e != "ollama":
                result[e] = {"ok": True, "note": "already in place"}
                continue
            inst.install(lambda stage, f, m="", b=base, s=span, name=e: progress(name, b + s * f, m))
            result[e] = {"ok": inst.verify() or e == "ollama", "note": "installed"}
        except Exception as ex:                                                          # noqa: BLE001
            result[e] = {"ok": False, "note": f"{type(ex).__name__}: {str(ex)[:300]}"}
    return result


# ----------------------------------------------------------------------------- run
def start_services(engines: list[str], say: Callable[[str], None] = print, wait: float = 60.0) -> dict[str, str]:
    """Start what is installed and not yet answering. Returns {engine: "running" | "started" | "missing" | "failed: why"}."""
    from . import installers

    status: dict[str, str] = {}
    urls = service_urls()
    for e in engines:
        if reachable(e, urls[e]):
            status[e] = "running"
            continue
        try:
            if e == "ollama":
                from .. import llm

                status[e] = "started" if llm.binary() and llm.start_server(urls[e], wait=min(wait, 40)) else "missing"
            elif e == "comfy":
                inst = installers.ComfyInstaller()
                if not (inst.root / "main.py").exists():
                    status[e] = "missing"
                    continue
                inst.start()
                status[e] = "started"
            elif e == "voicestudio":
                status[e] = _start_docker("voicestudio")
            else:
                status[e] = "missing"
        except Exception as ex:                                                          # noqa: BLE001
            status[e] = f"failed: {type(ex).__name__}: {str(ex)[:160]}"
        say(f"  {e}: {status[e]}")
    deadline = time.time() + wait
    pending = [e for e, s in status.items() if s == "started"]
    while pending and time.time() < deadline:
        pending = [e for e in pending if not reachable(e, urls[e], 2)]
        if pending:
            time.sleep(2)
    for e in pending:
        status[e] = "started, not answering yet"
    return status


def _start_docker(name: str) -> str:
    if not shutil.which("docker"):
        return "missing"
    r = subprocess.run(["docker", "start", name], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW, stdin=subprocess.DEVNULL)
    return "started" if r.returncode == 0 else "missing"


def status() -> dict[str, Any]:
    urls = service_urls()
    return {"services": {n: {"url": u, "up": reachable(n, u)} for n, u in urls.items()}, "identity": str(identity_path()), "data": str(paths.DATA)}


# ----------------------------------------------------------------------------- start at login / boot
def service_files(*, python: str = "", port: int = 8790, name: str = "", target: str = "", args: Optional[list[str]] = None,
                  service: str = "engine") -> dict[str, Any]:
    """What it takes to start Video Tool automatically, for this operating system: {"os", "files": {path: text}, "commands": [[...]], "note"}.
    Nothing is written here. `args` are the `vt` arguments (default: the engine hub); `service` names it ("engine" or "server")."""
    from xml.sax.saxutils import escape

    py = python or sys.executable
    argv = ["-m", "vt.cli"] + (args if args is not None else ["engine", "run", "--port", str(port)] + (["--name", name] if name else []))
    quote = lambda a: f'"{a}"' if (not a or any(c in a for c in ' "&|<>^')) else a      # noqa: E731
    run = f'"{py}" ' + " ".join(quote(a) for a in argv)
    data = str(paths.DATA)
    title = service.capitalize()
    now = service != "server"            # the server asks for this while it runs: starting a second copy now would only fight it for the port
    target = target or ("windows" if os.name == "nt" else "mac" if sys.platform == "darwin" else "linux")
    if target == "windows":
        task = f"VideoTool{title}"
        cmd_file = str(Path(data) / f"{service}-run.cmd")                 # a launcher file keeps the quoting out of the task definition
        body = f'@echo off\r\nset "VT_DATA={data}"\r\n{run}\r\n'
        return {"os": "windows", "files": {cmd_file: body}, "commands": [["schtasks", "/Create", "/F", "/TN", task, "/SC", "ONLOGON", "/RL", "LIMITED", "/TR", f'"{cmd_file}"']],
                "remove": [["schtasks", "/Delete", "/F", "/TN", task]], "installed": cmd_file,
                "note": "Starts when this user logs in. No administrator rights are needed."}
    if target == "mac":
        label = f"app.videotool.{service}"
        prog = "".join(f"<string>{escape(a)}</string>" for a in [py] + argv)
        plist = (f'<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict><key>Label</key><string>{label}</string><key>RunAtLoad</key><true/><key>KeepAlive</key><true/>'
                 f'<key>EnvironmentVariables</key><dict><key>VT_DATA</key><string>{escape(data)}</string></dict><key>ProgramArguments</key><array>{prog}</array></dict></plist>\n')
        dest = str(Path.home() / "Library" / "LaunchAgents" / f"{label}.plist")
        return {"os": "mac", "files": {dest: plist}, "commands": [["launchctl", "load", "-w", dest]] if now else [], "remove": [["launchctl", "unload", "-w", dest]],
                "installed": dest, "note": "Starts at login."}
    unit_name = f"video-tool-{service}"
    unit = (f"[Unit]\nDescription=Video Tool {title}\nAfter=network-online.target\nWants=network-online.target\n\n[Service]\nEnvironment=\"VT_DATA={data}\"\n"
            f"ExecStart={run}\nRestart=on-failure\nRestartSec=5\n\n[Install]\nWantedBy=default.target\n")
    dest = str(Path.home() / ".config" / "systemd" / "user" / f"{unit_name}.service")
    return {"os": "linux", "files": {dest: unit}, "commands": [["systemctl", "--user", "daemon-reload"], ["systemctl", "--user", "enable", *(["--now"] if now else []), unit_name]],
            "remove": [["systemctl", "--user", "disable", "--now", unit_name]], "installed": dest,
            "note": "Starts when you log in, and restarts if it stops. To start at boot with nobody logged in, the computer's owner turns on "
                    "lingering for this user once (`loginctl enable-linger`)."}


def apply_service(spec: dict[str, Any]) -> list[str]:
    done = []
    for path, text in spec["files"].items():
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        done.append(f"wrote {path}")
    for cmd in spec["commands"]:
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW, stdin=subprocess.DEVNULL)
        done.append(f"{' '.join(cmd[:3])}: " + ("ok" if r.returncode == 0 else f"failed ({(r.stderr or r.stdout).strip()[:160]})"))
    return done


def address_hints(port: int) -> list[str]:
    """The addresses another computer could use, best first (the LAN address, then the name)."""
    import socket

    out = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        out.append(f"http://{s.getsockname()[0]}:{port}")
        s.close()
    except Exception:                                                                   # noqa: BLE001
        pass
    out.append(f"http://{socket.gethostname()}:{port}")
    return list(dict.fromkeys(out))


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)
