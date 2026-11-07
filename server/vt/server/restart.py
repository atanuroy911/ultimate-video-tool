"""Restart only this process's verified systemd user service, after jobs drain."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

last_error = ""


def _cgroup() -> str:
    return Path("/proc/self/cgroup").read_text(encoding="utf-8")


def describe() -> dict:
    note = "Restart the server from its server manager. This process has no verified automatic restart service."
    if sys.platform != "linux":
        return {"available":False,"note":note}
    try:
        paths = [line.split(":",2)[-1].split("/") for line in _cgroup().splitlines()]
        units = [parts[-1] for parts in paths if "user.slice" in parts and f"user@{os.getuid()}.service" in parts and parts[-1].endswith(".service")]
        if not units or not re.fullmatch(r"[A-Za-z0-9_.@-]+\.service",units[0]) or units[0].startswith("user@"):
            return {"available":False,"note":note}
        unit = units[0]
        result = subprocess.run(["systemctl","--user","show","--property=MainPID","--value",unit],capture_output=True,text=True,timeout=5)
        if result.returncode or int(result.stdout.strip()) != os.getpid():
            return {"available":False,"note":note}
        return {"available":True,"unit":unit,"note":"Restart this server when no jobs are running. Connected apps reconnect automatically."}
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return {"available":False,"note":note}


def execute(manager, unit: str) -> None:
    global last_error
    try:
        result = subprocess.run(["systemctl","--user","restart","--no-block",unit],capture_output=True,text=True,timeout=8)
        if result.returncode:
            raise RuntimeError("The server manager did not accept the restart. Use the server manager to try again.")
    except (OSError,RuntimeError,subprocess.TimeoutExpired):
        last_error = "The server could not restart. Use its server manager to try again."
        manager.resume_submissions()
        raise


def request(manager, background) -> dict:
    global last_error
    from fastapi import HTTPException

    state = describe()
    if not state["available"]:
        raise HTTPException(409,state["note"])
    if not manager.pause_submissions():
        raise HTTPException(409,"Wait for running and queued jobs to finish before restarting the server.")
    last_error = ""
    background.add_task(execute,manager,state["unit"])
    return {"restarting":True}
