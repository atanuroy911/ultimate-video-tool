"""Studio API for the director's call log: the plain-words list, one call, cancel, and a zip of both logs."""
from __future__ import annotations

import io
import time
import zipfile
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..modules.calls import read_calls, read_technical
from .modules_routes import RUNNING, project_or_404

router = APIRouter(prefix="/api/projects/{pid}", tags=["log"])


def _running(pid: str) -> list[dict[str, Any]]:
    now = time.time()
    return [{"id": cid, "module": info["module"], "plain": info["plain_name"] + "...", "caller": info["caller"],
             "elapsed": round(now - info["started"], 1), "estimate": info["estimate"], "status": "running"}
            for cid, info in list(RUNNING.items()) if info["project"] == pid]


@router.get("/calls")
def calls(pid: str, after: int = 0, level: str = "", group: str = "", q: str = "", limit: int = 1000) -> dict[str, Any]:
    project = project_or_404(pid)
    return {"entries": read_calls(project.dir, after=after, level=level, group=group, q=q, limit=max(1, min(limit, 5000))),
            "running": _running(pid)}


@router.get("/calls/technical")
def technical(pid: str, lines: int = 2000) -> dict[str, str]:
    return {"text": read_technical(project_or_404(pid).dir, max_lines=max(1, min(lines, 2000)))}


@router.get("/calls/download")
def download(pid: str) -> Response:
    project = project_or_404(pid)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("calls.jsonl", "technical.log"):
            path = project.dir / name
            archive.writestr(name, path.read_text(encoding="utf-8") if path.exists() else "")
    return Response(buffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{pid}-director-log.zip"'})


@router.get("/calls/{call_id}")
def one_call(pid: str, call_id: str) -> dict[str, Any]:
    project = project_or_404(pid)
    for entry in read_calls(project.dir):
        if entry.get("id") == call_id:
            return entry
    running = [r for r in _running(pid) if r["id"] == call_id]
    if running:
        return running[0]
    raise HTTPException(404, "No such call in this project's log.")


@router.post("/calls/{call_id}/cancel")
def cancel(pid: str, call_id: str) -> dict[str, Any]:
    project_or_404(pid)
    info = RUNNING.get(call_id)
    if not info or info["project"] != pid:
        raise HTTPException(404, "That step is not running.")
    info["cancel"].set()
    return {"ok": True, "summary": f"Asked {info['plain_name'].lower()} to stop."}
