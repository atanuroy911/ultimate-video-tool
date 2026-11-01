"""Local Studio API for connected accounts, groups and publishing tasks."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import httpx

from ..project import Project
from ..social import core

router = APIRouter(prefix="/api", tags=["social"])


class AccountInput(BaseModel):
    platform: str
    name: str
    handle: str = ""
    credentials: dict = Field(default_factory=dict)


class GroupInput(BaseModel):
    name: str
    description: str = ""
    account_ids: list[str] = Field(default_factory=list)


class MetaExchangeInput(BaseModel):
    app_id: str
    app_secret: str
    user_token: str


class DispatchInput(BaseModel):
    group_id: str
    video_filename: str = ""
    title: str
    description: str = ""
    hashtags: list[str] = Field(default_factory=list)
    scheduled_for: str | None = None
    platform_overrides: dict[str, dict] = Field(default_factory=dict)


@router.get("/social/accounts")
def accounts():
    return core.accounts()


@router.post("/social/accounts/connect/{platform}")
def add_account(platform: str, body: AccountInput):
    if platform not in core.PLATFORMS or body.platform != platform:
        raise HTTPException(400, "Unsupported platform")
    if not body.name.strip(): raise HTTPException(400, "Account name is required")
    if platform != "mock" and not body.credentials.get("access_token"):
        raise HTTPException(400, "An access token is required")
    account_id = core.new_id("acct")
    with core.connect() as db:
        db.execute("INSERT INTO account(id,platform,name,handle,credentials) VALUES(?,?,?,?,?)", (account_id, platform, body.name.strip(), body.handle.strip(), json.dumps(body.credentials)))
    return {"id": account_id, "platform": platform, "name": body.name}


@router.post("/social/accounts/meta/exchange")
def exchange_meta(body: MetaExchangeInput):
    """Exchange a short-lived user token and add managed Pages and linked Instagram accounts."""
    if not all((body.app_id, body.app_secret, body.user_token)):
        raise HTTPException(400, "App ID, app secret, and user token are required")
    try:
        with httpx.Client(timeout=30) as client:
            exchange = client.get("https://graph.facebook.com/v22.0/oauth/access_token", params={"grant_type":"fb_exchange_token","client_id":body.app_id,"client_secret":body.app_secret,"fb_exchange_token":body.user_token})
            exchange.raise_for_status()
            long_token = exchange.json()["access_token"]
            page_response = client.get("https://graph.facebook.com/v22.0/me/accounts", params={"fields":"id,name,access_token,instagram_business_account{id,username}","access_token":long_token})
            page_response.raise_for_status()
            pages = page_response.json().get("data", [])
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(400, "Meta token exchange failed. Check app permissions and token validity.")
    added = []
    with core.connect() as db:
        for page in pages:
            if not page.get("id") or not page.get("access_token"): continue
            page_id = core.new_id("acct")
            db.execute("INSERT INTO account(id,platform,name,handle,credentials) VALUES(?,?,?,?,?)", (page_id,"facebook",page.get("name") or page["id"],"",json.dumps({"access_token":page["access_token"],"page_id":page["id"]})))
            added.append({"id":page_id,"platform":"facebook","name":page.get("name") or page["id"]})
            ig = page.get("instagram_business_account") or {}
            if ig.get("id"):
                ig_id = core.new_id("acct")
                db.execute("INSERT INTO account(id,platform,name,handle,credentials) VALUES(?,?,?,?,?)", (ig_id,"instagram",ig.get("username") or ig["id"],ig.get("username") or "",json.dumps({"access_token":page["access_token"],"ig_user_id":ig["id"]})))
                added.append({"id":ig_id,"platform":"instagram","name":ig.get("username") or ig["id"]})
    return {"accounts": added}


@router.delete("/social/accounts/{account_id}")
def delete_account(account_id: str):
    with core.connect() as db:
        db.execute("UPDATE account SET active=0 WHERE id=?", (account_id,))
        db.execute("DELETE FROM member WHERE account_id=?", (account_id,))
    return {"ok": True}


@router.get("/social/groups")
def groups():
    return core.groups()


@router.post("/social/groups")
def add_group(body: GroupInput):
    if not body.name.strip(): raise HTTPException(400, "Group name is required")
    group_id = core.new_id("grp")
    with core.connect() as db:
        valid = {r[0] for r in db.execute("SELECT id FROM account WHERE active=1")}
        if not set(body.account_ids) <= valid: raise HTTPException(400, "Group includes an unknown account")
        db.execute("INSERT INTO grp(id,name,description) VALUES(?,?,?)", (group_id, body.name.strip(), body.description))
        db.executemany("INSERT INTO member(group_id,account_id) VALUES(?,?)", [(group_id, aid) for aid in set(body.account_ids)])
    return {"id": group_id}


@router.delete("/social/groups/{group_id}")
def delete_group(group_id: str):
    with core.connect() as db:
        db.execute("DELETE FROM grp WHERE id=?", (group_id,))
    return {"ok": True}


@router.post("/projects/{pid}/social/dispatch")
def dispatch(pid: str, body: DispatchInput):
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", pid) or pid in (".", ".."):
        raise HTTPException(400, "Invalid project ID")
    project = Project(pid)
    if not project.exists(): raise HTTPException(404, "Project not found")
    group = core.one("SELECT * FROM grp WHERE id=?", (body.group_id,))
    if not group: raise HTTPException(404, "Group not found")
    members = core.rows("SELECT a.* FROM account a JOIN member m ON m.account_id=a.id WHERE m.group_id=? AND a.active=1", (body.group_id,))
    if not members: raise HTTPException(400, "Group has no active accounts")
    scheduled_for = None
    if body.scheduled_for:
        try:
            dt = datetime.fromisoformat(body.scheduled_for.replace("Z", "+00:00"))
            if dt.tzinfo is None: raise ValueError("Schedule needs a time zone")
            scheduled_for = dt.astimezone(timezone.utc).isoformat()
        except ValueError: raise HTTPException(400, "Invalid schedule timestamp")
    video = project.exports_dir / body.video_filename if body.video_filename else next(iter(sorted(project.exports_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)), None)
    if video is None or video.resolve().parent != project.exports_dir.resolve() or video.suffix.lower() != ".mp4" or not video.is_file():
        raise HTTPException(400, "Choose an exported MP4 from this project")
    if not body.title.strip(): raise HTTPException(400, "Post title is required")
    batch_id = core.new_id("batch")
    with core.connect() as db:
        db.execute("INSERT INTO batch(id,project_id,group_id,group_name,title,description,tags) VALUES(?,?,?,?,?,?,?)", (batch_id, pid, group["id"], group["name"], body.title.strip(), body.description, json.dumps(body.hashtags)))
        for account in members:
            task_id = core.new_id("task")
            override = body.platform_overrides.get(account["platform"], {})
            task_title = str(override.get("title") or body.title).strip()
            task_description = str(override.get("description") if override.get("description") is not None else body.description)
            task_tags = override.get("hashtags") if isinstance(override.get("hashtags"), list) else body.hashtags
            db.execute("INSERT INTO task(id,batch_id,project_id,video_path,account_id,platform,account_name,title,description,tags,scheduled_for) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (task_id, batch_id, pid, str(video), account["id"], account["platform"], account["name"], task_title, task_description, json.dumps(task_tags), scheduled_for))
            core.event(db, task_id, "queued", "Queued for publishing")
    core.start_worker()
    return {"batch_id": batch_id, "total_tasks": len(members)}


@router.get("/social/tasks")
def tasks():
    return core.tasks()


@router.get("/social/logs")
def logs():
    return core.rows("SELECT l.*,t.platform,t.account_name,t.project_id,t.permalink FROM log l LEFT JOIN task t ON t.id=l.task_id ORDER BY l.id DESC LIMIT 1000")


@router.post("/social/tasks/{task_id}/retry")
def retry(task_id: str):
    task = core.one("SELECT status FROM task WHERE id=?", (task_id,))
    if not task: raise HTTPException(404, "Task not found")
    if task["status"] != "failed": raise HTTPException(409, "Only failed tasks can be retried")
    with core.connect() as db:
        db.execute("UPDATE task SET status='queued',progress=0,error=NULL,message='Retry queued',retries=retries+1,completed_at=NULL WHERE id=?", (task_id,))
        core.event(db, task_id, "queued", "Retry queued")
    core.start_worker()
    return {"ok": True}


@router.post("/social/tasks/{task_id}/cancel")
def cancel(task_id: str):
    task = core.one("SELECT status FROM task WHERE id=?", (task_id,))
    if not task: raise HTTPException(404, "Task not found")
    if task["status"] not in ("queued", "uploading"): raise HTTPException(409, "Task cannot be cancelled")
    core.set_task(task_id, "cancelled", "Cancelled", completed_at=core.now())
    return {"ok": True}
