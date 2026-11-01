"""The publishing queue: one SQLite file, one background worker, one upload flow per platform.

A dispatch (vt/server/social_routes.py) writes a batch and one task per account of a group. The worker takes queued tasks whose time has come, one at a
time, uploads each through its platform's official API, and records every step in `log`. A failed channel never blocks the others: its task fails with
the platform's reason and can be retried; the batch ends `completed` when every task published, `partial_error` otherwise.

Rebuilt 2026-10-31 from the routes, the Studio pages and tests/test_social_flow.py after the original file was lost (an unanchored `social/` rule in
.gitignore had kept it out of git). Live posting on the owner's accounts has still never been verified (STATUS E5).
"""
from __future__ import annotations

import json
import math
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Optional

import httpx

from .. import paths

DB = paths.DATA / "social" / "social.db"
PLATFORMS = ("mock", "facebook", "instagram", "youtube", "tiktok")
GRAPH = "https://graph.facebook.com/v22.0"
POLL_SECONDS = 3.0
IDLE_SECONDS = 5.0                    # the worker looks again this often while a scheduled task waits
CHUNK = 8 * 1024 * 1024

SCHEMA = """
CREATE TABLE IF NOT EXISTS account (id TEXT PRIMARY KEY, platform TEXT NOT NULL, name TEXT NOT NULL, handle TEXT DEFAULT '', credentials TEXT DEFAULT '{}',
    active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS grp (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS member (group_id TEXT NOT NULL REFERENCES grp(id) ON DELETE CASCADE, account_id TEXT NOT NULL, PRIMARY KEY (group_id, account_id));
CREATE TABLE IF NOT EXISTS batch (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, group_id TEXT, group_name TEXT, title TEXT, description TEXT, tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'running', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS task (id TEXT PRIMARY KEY, batch_id TEXT REFERENCES batch(id), project_id TEXT, video_path TEXT, account_id TEXT, platform TEXT, account_name TEXT,
    title TEXT, description TEXT, tags TEXT DEFAULT '[]', scheduled_for TEXT, status TEXT DEFAULT 'queued', progress REAL DEFAULT 0, message TEXT DEFAULT '', error TEXT,
    remote_id TEXT, permalink TEXT, retries INTEGER DEFAULT 0, started_at TEXT, completed_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS log (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, status TEXT, message TEXT, at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_task_status ON task(status);
CREATE INDEX IF NOT EXISTS idx_task_batch ON task(batch_id);
"""


class Cancelled(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """A connection with the schema in place; committed on success. WAL lets the Studio read while the worker writes."""
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB), timeout=30)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        yield db
        db.commit()
    finally:
        db.close()


def rows(sql: str, params: tuple = ()) -> list[dict]:
    with connect() as db:
        return [dict(r) for r in db.execute(sql, params)]


def one(sql: str, params: tuple = ()) -> Optional[dict]:
    r = rows(sql, params)
    return r[0] if r else None


def event(db: sqlite3.Connection, task_id: str, status: str, message: str) -> None:
    db.execute("INSERT INTO log(task_id,status,message,at) VALUES(?,?,?,?)", (task_id, status, message, now()))


def set_task(task_id: str, status: str, message: str, *, log: bool = True, **fields) -> None:
    cols = {"status": status, "message": message, **fields}
    with connect() as db:
        db.execute(f"UPDATE task SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?", (*cols.values(), task_id))
        if log:
            event(db, task_id, status, message)


# ------------------------------------------------------------------------------------------------------------------------------ what the Studio lists
def accounts() -> list[dict]:
    """Every connected account, never its credentials."""
    return rows("SELECT id,platform,name,handle,active,created_at FROM account ORDER BY active DESC, created_at")


def groups() -> list[dict]:
    out = rows("SELECT * FROM grp ORDER BY created_at")
    for g in out:
        g["accounts"] = rows("SELECT a.id,a.platform,a.name,a.handle,a.active FROM account a JOIN member m ON m.account_id=a.id WHERE m.group_id=? ORDER BY a.platform", (g["id"],))
    return out


def tasks() -> list[dict]:
    return rows("SELECT * FROM task ORDER BY created_at DESC, rowid DESC LIMIT 500")


# ------------------------------------------------------------------------------------------------------------------------------ the worker
_lock = threading.Lock()
_thread: Optional[threading.Thread] = None


def start_worker() -> None:
    """Start the background worker if it is not running. Safe to call after every dispatch and at startup."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _thread = threading.Thread(target=_run, name="social-worker", daemon=True)
        _thread.start()


def _due() -> Optional[dict]:
    return one("SELECT * FROM task WHERE status='queued' AND (scheduled_for IS NULL OR scheduled_for<=?) ORDER BY created_at, rowid LIMIT 1", (now(),))


def _run() -> None:
    while True:
        task = _due()
        if task is None:
            if one("SELECT id FROM task WHERE status='queued'") is None:
                return                                                    # nothing waits: the next dispatch starts the worker again
            time.sleep(IDLE_SECONDS)
            continue
        _process(task)


def _process(task: dict) -> None:
    acct = one("SELECT * FROM account WHERE id=?", (task["account_id"],))
    set_task(task["id"], "uploading", f"Uploading to {task['platform']}", progress=0, started_at=now(), error=None)

    def progress(pct: float, message: str) -> None:
        state = one("SELECT status FROM task WHERE id=?", (task["id"],))
        if state and state["status"] == "cancelled":
            raise Cancelled()
        set_task(task["id"], "uploading", message, log=False, progress=round(max(0.0, min(100.0, pct)), 1))

    try:
        if acct is None or not acct["active"]:
            raise ValueError("The account was removed")
        remote_id, permalink = _upload(task, json.loads(acct["credentials"] or "{}"), progress)
        _finish(task, "published", "Published", progress=100, remote_id=remote_id, permalink=permalink, completed_at=now())
    except Cancelled:
        _finish(task, None, "")                                           # the cancel route already recorded the task; the batch still settles
    except Exception as e:                                                # noqa: BLE001 - one channel's failure is that task's, never the worker's
        _finish(task, "failed", f"Failed: {_reason(e)}", error=_reason(e), completed_at=now())


def _reason(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        try:
            body = e.response.json()
            msg = (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else body.get("error_description") or body.get("message")
        except ValueError:
            msg = ""
        return f"{e.response.status_code} {msg or e.response.reason_phrase}".strip()[:300]
    return str(e)[:300] or type(e).__name__


def _finish(task: dict, status: Optional[str], message: str, **fields) -> None:
    """The task's last state and its batch's state in one transaction, so nobody ever reads a published task in a batch still marked as failing."""
    with connect() as db:
        if status is not None:
            cols = {"status": status, "message": message, **fields}
            db.execute(f"UPDATE task SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?", (*cols.values(), task["id"]))
            event(db, task["id"], status, message)
        states = [r["status"] for r in db.execute("SELECT status FROM task WHERE batch_id=?", (task["batch_id"],))]
        if any(s in ("queued", "uploading") for s in states):
            batch = "running"
        else:
            batch = "completed" if all(s == "published" for s in states) else "partial_error"
        db.execute("UPDATE batch SET status=? WHERE id=?", (batch, task["batch_id"]))


# ------------------------------------------------------------------------------------------------------------------------------ the platforms
ProgressFn = Callable[[float, str], None]


def _upload(task: dict, credentials: dict, progress: ProgressFn) -> tuple[str, str]:
    """(the platform's id for the post, its public link). Raises with the platform's own reason."""
    fn = {"mock": _mock, "facebook": _facebook, "instagram": _instagram, "youtube": _youtube, "tiktok": _tiktok}.get(task["platform"])
    if fn is None:
        raise ValueError(f"{task['platform']} is not a supported platform")
    return fn(task, credentials, progress)


def _caption(task: dict) -> str:
    tags = " ".join(f"#{t.lstrip('#')}" for t in json.loads(task.get("tags") or "[]") if str(t).strip())
    return "\n\n".join(x for x in ((task.get("description") or task.get("title") or "").strip(), tags) if x)


def _mock(task: dict, credentials: dict, progress: ProgressFn) -> tuple[str, str]:
    progress(50, "Uploading (test channel)")
    return f"mock-{task['id']}", f"https://example.com/mock/{task['id']}"


def _facebook(task: dict, credentials: dict, progress: ProgressFn) -> tuple[str, str]:
    """A Page Reel: start, send the file to the upload address, finish with the caption (Graph API video_reels)."""
    page, token = credentials["page_id"], credentials["access_token"]
    data = Path(task["video_path"]).read_bytes()
    with httpx.Client(timeout=600) as c:
        start = c.post(f"{GRAPH}/{page}/video_reels", params={"upload_phase": "start", "access_token": token})
        start.raise_for_status()
        video_id, upload_url = start.json()["video_id"], start.json()["upload_url"]
        progress(10, "Sending the video")
        c.post(upload_url, headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data))}, content=data).raise_for_status()
        progress(80, "Publishing")
        c.post(f"{GRAPH}/{page}/video_reels", params={"upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED", "description": _caption(task),
                                                    "access_token": token}).raise_for_status()
    return video_id, f"https://www.facebook.com/reel/{video_id}"


def _instagram(task: dict, credentials: dict, progress: ProgressFn) -> tuple[str, str]:
    """A Reel through the two-step container flow; the local file is sent with the resumable upload, so no public address is needed."""
    ig, token = credentials["ig_user_id"], credentials["access_token"]
    data = Path(task["video_path"]).read_bytes()
    with httpx.Client(timeout=600) as c:
        made = c.post(f"{GRAPH}/{ig}/media", params={"media_type": "REELS", "upload_type": "resumable", "caption": _caption(task), "access_token": token})
        made.raise_for_status()
        container, uri = made.json()["id"], made.json()["uri"]
        progress(10, "Sending the video")
        c.post(uri, headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data))}, content=data).raise_for_status()
        progress(60, "Instagram is processing the video")
        for _ in range(200):
            st = c.get(f"{GRAPH}/{container}", params={"fields": "status_code,status", "access_token": token})
            st.raise_for_status()
            code = st.json().get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise ValueError(f"Instagram could not process the video: {st.json().get('status') or code}")
            progress(60, "Instagram is processing the video")
            time.sleep(POLL_SECONDS)
        else:
            raise TimeoutError("Instagram took too long to process the video")
        progress(90, "Publishing")
        pub = c.post(f"{GRAPH}/{ig}/media_publish", params={"creation_id": container, "access_token": token})
        pub.raise_for_status()
        post_id = pub.json()["id"]
        link = c.get(f"{GRAPH}/{post_id}", params={"fields": "permalink", "access_token": token})
        permalink = link.json().get("permalink", "") if link.status_code == 200 else ""
    return post_id, permalink or "https://www.instagram.com/"


def _youtube_token(credentials: dict, c: httpx.Client) -> str:
    """A fresh access token when a refresh token and its OAuth client are stored, else the stored token."""
    if credentials.get("refresh_token") and credentials.get("client_id") and credentials.get("client_secret"):
        r = c.post("https://oauth2.googleapis.com/token", data={"grant_type": "refresh_token", "refresh_token": credentials["refresh_token"],
                                                               "client_id": credentials["client_id"], "client_secret": credentials["client_secret"]})
        r.raise_for_status()
        return r.json()["access_token"]
    return credentials["access_token"]


def _youtube(task: dict, credentials: dict, progress: ProgressFn) -> tuple[str, str]:
    """The resumable upload of the Data API v3, in chunks; a vertical video under a minute becomes a Short by itself."""
    path = Path(task["video_path"])
    size = path.stat().st_size
    meta = {"snippet": {"title": (task.get("title") or "")[:100], "description": _caption(task), "tags": json.loads(task.get("tags") or "[]"), "categoryId": "22"},
            "status": {"privacyStatus": credentials.get("privacy", "public"), "selfDeclaredMadeForKids": False}}
    with httpx.Client(timeout=600) as c:
        token = _youtube_token(credentials, c)
        auth = {"Authorization": f"Bearer {token}"}
        init = c.post("https://www.googleapis.com/upload/youtube/v3/videos", params={"uploadType": "resumable", "part": "snippet,status"},
                      headers={**auth, "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)}, json=meta)
        init.raise_for_status()
        session = init.headers["Location"]
        sent, video_id = 0, ""
        with path.open("rb") as f:
            while sent < size:
                chunk = f.read(CHUNK)
                end = sent + len(chunk) - 1
                r = c.put(session, headers={**auth, "Content-Range": f"bytes {sent}-{end}/{size}"}, content=chunk)
                if r.status_code == 308:
                    rng = r.headers.get("Range")
                    sent = int(rng.split("-")[1]) + 1 if rng else end + 1
                    f.seek(sent)
                    progress(5 + 90 * sent / size, f"Uploading {round(100 * sent / size)}%")
                    continue
                r.raise_for_status()
                video_id = r.json()["id"]
                break
    if not video_id:
        raise ValueError("YouTube did not confirm the upload")
    return video_id, f"https://www.youtube.com/shorts/{video_id}"


def _tiktok_chunks(size: int) -> tuple[int, int]:
    """(chunk size, chunk count) within TikTok's rules: 5 to 64 MB chunks, the last one may be larger; a small file is one chunk."""
    if size <= 5 * 1024 * 1024:
        return size, 1
    chunk = min(CHUNK, 64 * 1024 * 1024)
    return chunk, max(1, math.floor(size / chunk))


def _tiktok(task: dict, credentials: dict, progress: ProgressFn) -> tuple[str, str]:
    """Content Posting API, direct post from a file: init, PUT the chunks, poll the status."""
    path = Path(task["video_path"])
    size = path.stat().st_size
    chunk, count = _tiktok_chunks(size)
    auth = {"Authorization": f"Bearer {credentials['access_token']}", "Content-Type": "application/json; charset=UTF-8"}
    with httpx.Client(timeout=600) as c:
        init = c.post("https://open.tiktokapis.com/v2/post/publish/video/init/", headers=auth, json={
            "post_info": {"title": _caption(task)[:2200] or task.get("title", ""), "privacy_level": credentials.get("privacy_level", "SELF_ONLY")},
            "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}})
        init.raise_for_status()
        data = init.json().get("data") or {}
        publish_id, upload_url = data["publish_id"], data["upload_url"]
        with path.open("rb") as f:
            for i in range(count):
                start = i * chunk
                body = f.read(chunk if i < count - 1 else size - start)
                c.put(upload_url, headers={"Content-Type": "video/mp4", "Content-Range": f"bytes {start}-{start + len(body) - 1}/{size}"}, content=body).raise_for_status()
                progress(5 + 80 * (i + 1) / count, f"Uploading part {i + 1} of {count}")
        for _ in range(200):
            st = c.post("https://open.tiktokapis.com/v2/post/publish/status_fetch/", headers=auth, json={"publish_id": publish_id})
            st.raise_for_status()
            d = st.json().get("data") or {}
            if d.get("status") == "PUBLISH_COMPLETE":
                post = (d.get("publicaly_available_post_id") or d.get("publicly_available_post_id") or [""])[0]
                handle = credentials.get("handle", "").lstrip("@")
                return str(post or publish_id), f"https://www.tiktok.com/@{handle}/video/{post}" if post and handle else "https://www.tiktok.com/"
            if d.get("status") == "FAILED":
                raise ValueError(f"TikTok refused the video: {d.get('fail_reason') or 'no reason given'}")
            progress(90, "TikTok is processing the video")
            time.sleep(POLL_SECONDS)
    raise TimeoutError("TikTok took too long to process the video")
