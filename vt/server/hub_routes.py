"""Studio API for sharing THIS computer's engines with other computers (the Engine hub, vt/engines/hub.py): start, stop, a new pairing code, start at login.

The hub is a separate process (`vt engine run`), so closing the Studio window does not have to stop it once it is set to start at login.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import paths
from ..engines import hub
from ..util import CREATE_NO_WINDOW

router = APIRouter(prefix="/api/hub", tags=["hub"])
DEFAULT_PORT = 8790
_proc: Optional[subprocess.Popen] = None


class StartBody(BaseModel):
    port: int = Field(default=DEFAULT_PORT, ge=1024, le=65535)
    engines: list[str] = Field(default_factory=lambda: list(hub.DEFAULT_ENGINES), max_length=3)
    name: str = Field(default="", max_length=60)


def _answers(port: int, timeout: float = 1.0) -> bool:
    try:
        return httpx.get(f"http://127.0.0.1:{port}/.well-known/vt-engine", timeout=timeout).status_code == 200
    except Exception:                                                                   # noqa: BLE001
        return False


def _busy_by_someone_else(port: int) -> bool:
    if _answers(port):
        return False
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _status(port: int) -> dict[str, Any]:
    running = _answers(port)
    out: dict[str, Any] = {"running": running, "port": port, "addresses": hub.address_hints(port) if running else [], "mine": bool(_proc and _proc.poll() is None)}
    if running:
        out["services"] = {n: u for n, u in hub.status()["services"].items()}
        try:
            out["offers"] = httpx.get(f"http://127.0.0.1:{port}/.well-known/vt-engine", timeout=2).json().get("services", [])
        except Exception:                                                               # noqa: BLE001
            out["offers"] = []
    return out


@router.get("")
def hub_status(port: int = DEFAULT_PORT) -> dict[str, Any]:
    return _status(port)


@router.post("/start")
def hub_start(body: Optional[StartBody] = None) -> dict[str, Any]:
    """Start sharing. Returns the addresses and a pairing code that works once."""
    global _proc
    body = body or StartBody()
    bad = [e for e in body.engines if e not in ("ollama", "comfy", "voicestudio")]
    if bad:
        raise HTTPException(422, f"unknown engine(s): {', '.join(bad)}")
    if not _answers(body.port):
        if _busy_by_someone_else(body.port):
            raise HTTPException(409, f"Port {body.port} is used by another program. Choose another port.")
        cmd = [sys.executable, "-m", "vt.cli", "engine", "run", "--port", str(body.port), "--engines", ",".join(body.engines)]
        if body.name:
            cmd += ["--name", body.name]
        log = open(paths.DATA / "engine-hub.log", "ab")                                  # what the hub says, for the person who asks why it did not start
        _proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=CREATE_NO_WINDOW, cwd=str(paths.ROOT))
        deadline = time.time() + 45
        while time.time() < deadline and not _answers(body.port):
            if _proc.poll() is not None:
                raise HTTPException(500, "The engine stopped right after starting. See engine-hub.log in the data folder.")
            time.sleep(0.5)
        if not _answers(body.port):
            raise HTTPException(504, "The engine did not answer in time. See engine-hub.log in the data folder.")
    return {**_status(body.port), **_code(body.port)}


def _code(port: int) -> dict[str, str]:
    try:
        r = httpx.post(f"http://127.0.0.1:{port}/v1/admin/new-code", timeout=5)
        r.raise_for_status()
        return {"code": r.json()["code"]}
    except Exception as e:                                                              # noqa: BLE001
        raise HTTPException(502, f"Could not get a pairing code ({type(e).__name__}). Is the engine running?")


@router.post("/code")
def hub_code(port: int = DEFAULT_PORT) -> dict[str, str]:
    """A new one-time pairing code for another computer."""
    return _code(port)


@router.post("/stop")
def hub_stop(port: int = DEFAULT_PORT) -> dict[str, Any]:
    global _proc
    if _proc and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(10)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = None
    return _status(port)


@router.post("/service")
def hub_service(port: int = DEFAULT_PORT, remove: bool = False) -> dict[str, Any]:
    """Start the engine at every login (or stop doing that). No administrator rights."""
    spec = hub.service_files(port=port)
    if remove:
        done = []
        for cmd in spec.get("remove", []):
            r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW, stdin=subprocess.DEVNULL)
            done.append(f"{' '.join(cmd[:3])}: {'ok' if r.returncode == 0 else 'not set'}")
        return {"done": done, "note": "It will no longer start by itself."}
    return {"done": hub.apply_service(spec), "note": spec["note"]}
