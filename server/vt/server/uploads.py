"""Uploads that survive a dropped connection (docs/plans/PLAN-CLIENT-SERVER.MD CS5).

The Studio sends a big file in chunks: `POST /api/uploads` {name, size} -> {id}; then `PUT /api/uploads/{id}?offset=N` with the raw bytes of each
chunk. After a drop it asks `GET /api/uploads/{id}` where to carry on. A finished upload is used by its id in place of the file
(`audio_upload` on `POST /api/projects`, `file_upload` on `POST /api/inspect`).
"""
from __future__ import annotations

import os
import errno
import re
import secrets
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.requests import ClientDisconnect

from .. import paths
from ..util import read_json, write_json

MAX_CHUNK = 64 * 1024 * 1024
MAX_SIZE = 64 * 1024 ** 3
KEEP_SECONDS = 2 * 24 * 3600            # an upload nobody finished or used is thrown away after two days

router = APIRouter()


def _dir() -> Path:
    d = paths.DATA / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta(uid: str) -> dict:
    if not uid.isalnum() or len(uid) > 40:
        raise HTTPException(404, "That upload is not known here (it may have been cleaned up). Start it again.")
    m = read_json(_dir() / f"{uid}.json", None)
    if not m:
        raise HTTPException(404, "That upload is not known here (it may have been cleaned up). Start it again.")
    return m


def _part(uid: str) -> Path:
    return _dir() / f"{uid}.part"


def _storage_error(error: OSError, path: Path) -> HTTPException:
    full = error.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)) or getattr(error, "winerror", None) in (39, 112)
    message = "The server needs more disk space. Free some space, then resume this upload." if full else "The server could not save this upload. Check its storage, then try again."
    try:
        offset = path.stat().st_size
    except OSError:
        offset = 0
    return HTTPException(507 if full else 500, {"errors": [message], "offset": offset})


async def _receive(path: Path, mode: str, request: Request, have: int, size: int, limit: int) -> None:
    """Keep bytes that arrived, including a partial write when the disk fills."""
    written = 0
    try:
        with path.open(mode, buffering=0) as file:
            try:
                async for piece in request.stream():
                    written += len(piece)
                    if written > limit or have + written > size:
                        file.truncate(have)
                        raise HTTPException(413, "That chunk is too big for this upload.")
                    pending = memoryview(piece)
                    while pending:
                        count = file.write(pending)
                        if not count:
                            raise OSError(errno.EIO, "The storage did not accept the upload.")
                        pending = pending[count:]
            except ClientDisconnect:
                pass  # the next request resumes from the actual file size
    except OSError as error:
        raise _storage_error(error, path) from error


def _status(uid: str, m: dict) -> dict[str, Any]:
    p = _part(uid)
    offset = p.stat().st_size if p.exists() else 0
    return {"id": uid, "offset": offset, "size": m["size"], "done": offset == m["size"]}


def _sweep() -> None:
    now = time.time()
    for f in _dir().iterdir():
        try:
            if now - f.stat().st_mtime > KEEP_SECONDS:
                f.unlink()
        except OSError:
            pass


class NewUpload(BaseModel):
    name: str = Field("upload", max_length=300)
    size: int = Field(..., ge=0, le=MAX_SIZE)


@router.post("/api/uploads")
def start(body: NewUpload) -> dict[str, Any]:
    _sweep()
    uid = secrets.token_hex(12)
    suffix = Path(body.name).suffix.lower()[:10]
    m = {"name": body.name, "suffix": suffix if suffix[1:].isalnum() else "", "size": body.size, "created": int(time.time())}
    try:
        write_json(_dir() / f"{uid}.json", m)
        _part(uid).touch()
    except OSError as error:
        raise _storage_error(error, _part(uid)) from error
    return _status(uid, m)


@router.get("/api/uploads/{uid}")
def status(uid: str) -> dict[str, Any]:
    return _status(uid, _meta(uid))


@router.put("/api/uploads/{uid}")
async def chunk(uid: str, offset: int, request: Request) -> dict[str, Any]:
    """Append one chunk. A chunk for the wrong place (a retry of one that did arrive) gets 409 with where to carry on."""
    m = _meta(uid)
    p = _part(uid)
    have = p.stat().st_size if p.exists() else 0
    if offset != have:
        raise HTTPException(409, {"errors": [f"Expected the chunk at {have}."], "offset": have})
    await _receive(p, "ab", request, have, m["size"], MAX_CHUNK)
    return _status(uid, m)


@router.put("/api/uploads/{uid}/file")
async def whole(uid: str, request: Request, ticket: str = "") -> dict[str, Any]:
    """The whole file in one request (`curl -T file <url>`): how an assistant on another computer hands a local file to the server.
    Allowed with the upload's one-time ticket instead of a key (vt/server/serve.py Guard); a retry starts the file again."""
    m = _meta(uid)
    p = _part(uid)
    await _receive(p, "wb", request, 0, m["size"], m["size"])
    return _status(uid, m)


def new_ticketed(name: str, size: int) -> dict[str, Any]:
    """An upload that can be sent with a one-time ticket in its address (no key): for prepare_upload (MCP)."""
    st = start(NewUpload(name=name, size=size))
    m = _meta(st["id"])
    m["ticket"] = secrets.token_urlsafe(18)
    write_json(_dir() / f"{st['id']}.json", m)
    return {**st, "ticket": m["ticket"]}


def ticket_ok(path: str, query: str) -> bool:
    """For the guard: PUT /api/uploads/<id>/file?ticket=<its ticket> needs no key."""
    import hmac
    from urllib.parse import parse_qs

    mm = re.fullmatch(r"/api/uploads/([0-9a-f]{1,40})/file", path)
    if not mm:
        return False
    meta = read_json(_dir() / f"{mm.group(1)}.json", None) or {}
    got = (parse_qs(query).get("ticket") or [""])[0]
    return bool(meta.get("ticket")) and bool(got) and hmac.compare_digest(got, meta["ticket"])


def resolve(ref: str) -> Path:
    """'upload:<id>' -> the finished file (moved out of the upload store, keeping its name and type); any other text is a path."""
    if not ref.startswith("upload:"):
        return Path(ref)
    tmp, name = take(ref[7:].strip())
    named = tmp.parent / (Path(name).name or tmp.name)
    tmp.rename(named)
    return named


def path_of(uid: str) -> tuple[Path, str]:
    """A finished upload, left in place (for a look before the project is made). Returns (file, the original name)."""
    m = _meta(uid)
    st = _status(uid, m)
    if not st["done"]:
        raise HTTPException(409, f"That upload is not finished ({st['offset']} of {st['size']} bytes arrived).")
    return _part(uid), m["name"]


def take(uid: str) -> tuple[Path, str]:
    """A finished upload, moved into a temporary folder of its own and forgotten here. The caller removes the folder."""
    src, name = path_of(uid)
    tmp = Path(tempfile.mkdtemp()) / f"upload{_meta(uid)['suffix']}"
    shutil.move(str(src), tmp)
    os.remove(_dir() / f"{uid}.json")
    return tmp, name
