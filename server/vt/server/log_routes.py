"""Studio API for the director's call log: the plain-words list, one call, cancel, and a zip of both logs."""
from __future__ import annotations

import io
import json
import re
import time
import zipfile
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from ..secure_paths import project_file
from ..modules.calls import read_calls, read_technical, redact
from .modules_routes import RUNNING, project_or_404

router = APIRouter(prefix="/api/projects/{pid}", tags=["log"])


def _running(pid: str) -> list[dict[str, Any]]:
    now = time.time()
    return redact([{"id": cid, "module": info["module"], "plain": info["plain_name"] + "...", "caller": info["caller"],
             "elapsed": round(now - info["started"], 1), "estimate": info["estimate"], "status": "running"}
            for cid, info in list(RUNNING.items()) if info["project"] == pid])


@router.get("/calls")
def calls(pid: str, after: int = 0, level: str = "", group: str = "", q: str = "", limit: int = 1000) -> dict[str, Any]:
    project = project_or_404(pid)
    return {"entries": read_calls(project.dir, after=after, level=level, group=group, q=q, limit=max(1, min(limit, 5000))),
            "running": _running(pid)}


@router.get("/ai-talk")
def ai_talk(pid: str) -> dict[str, Any]:
    """Every prompt and answer of this video, in order (vt/ai/talk.py): the list; one row's full text comes from /ai-talk/{seq}."""
    from ..ai import talk

    rows = []
    for row in talk.load(project_or_404(pid).dir):
        text = row.pop("prompt"), row.pop("system"), row.pop("answer")
        row["size"] = sum(len(t) for t in text)
        row["preview"] = " ".join(text[0].split())[:160]
        if row["kind"] == "tool":                       # the tool's name, for the list
            try:
                row["preview"] = json.loads(text[0]).get("tool",row["preview"])
            except (ValueError,AttributeError):
                pass
        rows.append(row)
    return {"rows": rows}


@router.get("/ai-talk/{seq}")
def ai_talk_row(pid: str, seq: int) -> dict[str, Any]:
    from ..ai import talk

    row = next((r for r in talk.load(project_or_404(pid).dir) if r["seq"] == seq), None)
    if row is None:
        raise HTTPException(404, "That conversation is not in this video's record.")
    return row


@router.get("/ai-talk-images/{name}")
def ai_talk_image(pid: str, name: str):
    project = project_or_404(pid)
    if not re.fullmatch(r"[a-f0-9]{64}\.(png|jpg|webp)",name):
        raise HTTPException(404,"That picture is not in this video's record.")
    file = project.dir / "ai-talk-images" / name
    if not file.is_file() or file.is_symlink() or file.parent.is_symlink() or not file.resolve().is_relative_to(project.dir.resolve()):
        raise HTTPException(404,"That picture is not in this video's record.")
    return FileResponse(file)


@router.get("/calls/technical")
def technical(pid: str, lines: int = 2000) -> dict[str, str]:
    return {"text": read_technical(project_or_404(pid).dir, max_lines=max(1, min(lines, 2000)))}


@router.get("/calls/download")
def download(pid: str) -> Response:
    project = project_or_404(pid)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("calls.jsonl", "technical.log"):
            try:
                path = project_file(project.dir, name)
            except ValueError:                           # a link, or a path out of the project: nothing of it goes in the archive
                path = None
            text = path.read_text(encoding="utf-8") if path is not None and path.exists() else ""
            if name.endswith(".jsonl"):
                rows = []
                for line in text.splitlines():
                    try:
                        rows.append(json.dumps(redact(json.loads(line)), ensure_ascii=False))
                    except ValueError:
                        rows.append("[Unreadable log record omitted]")
                text = "\n".join(rows)
            archive.writestr(name, redact(text))
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
