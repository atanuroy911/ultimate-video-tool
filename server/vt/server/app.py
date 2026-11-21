"""Studio backend: REST + WebSocket on localhost. Run with `vt studio`."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from .. import paths, planning, scene_ops
from ..compose import FORMATS, scene_timing
from ..compose.specimen import specimen_data, write_specimen
from ..doctor import run_checks
from ..pipeline import LABELS, ORDER, Pipeline, compose_all, export
from ..planner.catalogue import all_icon_names, catalogue_summary
from ..project import Project, list_themes, load_theme
from ..schema import ELEMENT_MODELS, ProjectMeta, Scene, ScenesFile, Theme, validate_scenes
from ..stages import asr as asr_mod
from ..thumbs import make_thumbnails, thumbs_dir
from ..util import now_iso, read_json, write_json
from .jobs import JobBusy, JobManager, ServerRestarting

ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
THEME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
SETTINGS_PATH = paths.SETTINGS

log = logging.getLogger(__name__)
app = FastAPI(title="Video Tool Studio", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
from .serve import Guard
app.add_middleware(Guard)                  # a token on every /api, /ws and /media request from another computer (serve.py)
paths.PROJECTS.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------ realtime
class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def _send_all(self, msg: dict) -> None:
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(json.dumps(msg, ensure_ascii=False))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def emit(self, msg: dict) -> None:
        """Thread-safe: callable from the job worker thread."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._send_all(msg), self.loop)

    def send(self, ws: WebSocket, msg: dict) -> None:
        """Thread-safe targeted send (director requests must reach one device, not every browser)."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(ws.send_text(json.dumps(msg, ensure_ascii=False)), self.loop)


hub = Hub()
jobs = JobManager(hub.emit, store=lambda: paths.PROJECTS / ".jobs")
app.state.jobs = jobs
app.state.hub = hub


@app.exception_handler(ServerRestarting)
async def server_restarting(request: Request, error: ServerRestarting):
    return JSONResponse(status_code=503,content={"detail":{"errors":[str(error)]}})


@app.on_event("startup")
async def _startup() -> None:
    hub.loop = asyncio.get_running_loop()
    jobs.recover()
    app.state.jobs = jobs
    app.state.hub = hub
    from ..social.core import start_worker
    start_worker()
    asyncio.create_task(_watch_files())



def scene_hashes(p: Project) -> dict[str, str]:
    import hashlib
    import json as _json
    sf = p.scenes()
    return {s.id: hashlib.sha1(_json.dumps(s.model_dump(exclude_none=True), sort_keys=True, default=str).encode()).hexdigest()[:12] for s in (sf.scenes if sf else [])}


def change_event(p: Project, state: dict[str, dict]) -> dict:
    """One 'changed' event: which scenes changed or went away, a number that grows with each change, and who did it when the MCP server just did
    (W14.1). `state` is the watcher's memory of each project's scenes."""
    import time as _time

    from .. import paths
    from ..util import read_json
    now = scene_hashes(p)
    before = state.get(p.id)
    state[p.id] = now
    rev = state.setdefault("_rev", {})
    rev[p.id] = rev.get(p.id, 0) + 1
    ev: dict = {"type": "changed", "project": p.id, "rev": rev[p.id], "scenes": [], "removed": [], "by": "", "what": ""}
    if before is not None:
        ev["scenes"] = sorted(i for i, h in now.items() if before.get(i) != h)
        ev["removed"] = sorted(i for i in before if i not in now)
    seen = read_json(paths.mcp_seen_path(), {}) or {}
    try:
        from datetime import datetime
        age = _time.time() - datetime.fromisoformat(str(seen.get("at", ""))).timestamp()
    except Exception:
        age = 999.0
    if age < 4:
        ev["by"] = f"mcp:{seen.get('client', 'assistant')}"
        ev["what"] = str(seen.get("tool", "")).replace("_", " ")
    return ev


async def _watch_files() -> None:
    """Tell the browser when something outside it (Claude via MCP, the CLI) changed a project."""
    seen: dict[str, tuple] = {}
    scene_state: dict[str, dict] = {}
    while True:
        try:
            for p in Project.list_all():
                sig = (
                    (p.scenes_path.stat().st_mtime if p.scenes_path.exists() else 0),
                    (p.meta_path.stat().st_mtime if p.meta_path.exists() else 0),
                    ((p.dir / "plan_doc.json").stat().st_mtime if (p.dir / "plan_doc.json").exists() else 0),
                    tuple(sorted((f.name, f.stat().st_mtime) for f in p.requests_dir.glob("*.json"))) if p.requests_dir.exists() else (),
                )
                if p.id not in seen:
                    scene_state[p.id] = scene_hashes(p)
                if p.id in seen and seen[p.id] != sig:
                    hub.emit(change_event(p, scene_state))
                seen[p.id] = sig
        except Exception:
            pass
        await asyncio.sleep(1.0)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    from .. import directors
    from .serve import is_local, named_device

    await ws.accept()
    hub.clients.add(ws)
    device_id = named_device(ws.scope) or ("local-app" if is_local(ws.scope) else "")      # a browser tab names no device: it watches, and cannot become a director
    device_name = "This computer"
    send_to_device = lambda m, sock=ws: hub.send(sock, m)
    try:
        await ws.send_text(json.dumps({"type": "hello", "boot": directors.BOOT, "jobs": [j.public() for j in jobs.snapshot()]}))
        while True:
            try:
                msg = json.loads(await ws.receive_text())
            except (ValueError, TypeError):
                continue
            if not isinstance(msg, dict) or not device_id:
                continue
            if msg.get("type") in ("director", "director_announce") and msg.get("director") in ('claude','codex'):
                directors.broker.connect(device_id, str(msg.get('device_name') or device_name)[:100], version=str(msg.get("version", ""))[:80],
                                         logged_in=bool(msg.get("logged_in")), send=send_to_device, assistant=msg['director'])
                hub.emit({"type": "directors_changed"})
            elif msg.get("type") == "director_done":
                directors.broker.finish(str(msg.get("request", "")), ok=bool(msg.get("ok")), error=str(msg.get("error", "")), device_id=device_id,
                                        detail={"result": msg.get("result"), "error_kind": str(msg.get("error_kind", ""))[:20], "model": str(msg.get("model", ""))[:80]})
            elif msg.get("type") == "ask_done":
                directors.broker.finish(str(msg.get("request", "")), ok=bool(msg.get("ok")), error=str(msg.get("error", "")), device_id=device_id,
                                        detail={"text": str(msg.get("text", ""))[:directors.MAX_ANSWER], "error_kind": str(msg.get("error_kind", ""))[:20],
                                                "models": [str(x)[:80] for x in (msg.get("models") or [])[:6]]})
            elif msg.get("type") == "director_log":
                hub.emit({"type": "director_log", "project": str(msg.get("project", "")), "message": str(msg.get("message", ""))[:500]})
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(ws)
        if device_id:
            directors.broker.disconnect(device_id, send_to_device)
            hub.emit({"type": "directors_changed"})


@app.exception_handler(JobBusy)
async def job_busy(_, e: JobBusy):
    return JSONResponse(status_code=409, content={"detail": {"errors": [f"{e.job.label} is already running. Wait for it to finish (or cancel it) before starting another."]}})


# ------------------------------------------------------------------ helpers
def proj(pid: str) -> Project:
    if not ID_RE.match(pid):
        raise HTTPException(400, "invalid project id")
    p = Project(pid)
    if not p.exists():
        raise HTTPException(404, f"project '{pid}' not found")
    return p


def changed(pid: str) -> None:
    hub.emit({"type": "changed", "project": pid})


def project_summary(p: Project) -> dict:
    m = p.meta()
    tr_exists = p.transcript_path.exists()
    sf = p.scenes()
    cuts = p.cuts()
    d = m.model_dump()
    if m.options.recording_edit != 'auto':
        from ..screen_recording import canvas
        d['canvas'] = canvas(m)
    d.update({
        "has_transcript": tr_exists, "scene_count": len(sf.scenes) if sf else 0, "planner": sf.planner if sf else None,
        "duration": round(cuts.output_duration, 2) if cuts else None,
        "pending_requests": len([r for r in p.requests() if r.status == "queued"]),
        "audio_url": (lambda a: f"/media/{p.id}/{a.name}" if a else None)(p.ensure_preview_audio()),
        "thumb": _first_thumb(p),
        "plan_notice": read_json(p.dir / "plan_notice.json"),
        "usecase_used": read_json(p.dir / "usecase.json"),
        "ai_notice": (lambda n: n if n and n.get("message") else None)(read_json(p.dir / "ai_notice.json")),
        "ai_brief": (read_json(p.dir / "ai_notice.json") or {}).get("brief"),
        "video_kind": (read_json(p.dir / "script_kind.json", {}) or {}).get("kind") or "explainer",
        "source_mode": (read_json(p.dir / "source.json", {}) or {}).get("mode") or "audio",
        "active_job": (jobs.active_for(p.id).public() if jobs.active_for(p.id) else None),
        **_activity(p),
    })
    return d


def _activity(p: Project) -> dict:
    """When the project last changed, and what has been exported from it (for the dashboard)."""
    stamps = [f.stat().st_mtime for f in (p.meta_path, p.dir / "scenes.json", p.dir / "transcript.json") if f.exists()]
    mp4 = sorted(p.exports_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True) if p.exports_dir.exists() else []
    cover = p.exports_dir / "cover.jpg"
    return {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(max(stamps))) if stamps else "",
        "export_count": len(mp4),
        "last_export": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mp4[0].stat().st_mtime)) if mp4 else None,
        "last_export_url": f"/media/{p.id}/exports/{mp4[0].name}" if mp4 else None,
        "cover_url": f"/media/{p.id}/exports/cover.jpg?v={int(cover.stat().st_mtime)}" if cover.exists() else None,
    }


def _first_thumb(p: Project) -> Optional[str]:
    for a in FORMATS.values():
        m = read_json(thumbs_dir(p, a["aspect"]) / "manifest.json")
        if m and m.get("scenes"):
            first = next(iter(m["scenes"].values()))
            return f"/media/{p.id}/thumbs/{a['tag']}/{first}"
    return None


def load_settings() -> dict:
    d = {"default_theme": "auto", "default_aspect": "9:16", "default_pace": "normal", "default_music": "auto", "autopilot": True, "plan_review": "when_expensive"}
    d.update(read_json(SETTINGS_PATH, {}) or {})
    return d


def save_and_compose(p: Project, sf: ScenesFile) -> None:
    errs = validate_scenes(sf, p.transcript(), p.beats(), all_icon_names(), {m.id for m in p.meta().media})
    if errs:
        raise HTTPException(422, {"errors": errs[:12]})
    with p.scenes_lock():
        cur = p.scenes()
        if cur:
            write_json(p.dir / "scenes.prev.json", cur.model_dump(exclude_none=True))
        p.save_scenes(sf)
        compose_all(p)
        changed(p.id)


def edit_scenes(p: Project, fn) -> ScenesFile:
    with p.scenes_lock():
        sf = p.scenes()
        if not sf:
            raise HTTPException(409, "no plan yet; process the audio first")
        try:
            new = fn(sf)
        except scene_ops.OpError as e:
            raise HTTPException(422, {"errors": [str(e)]})
        new = new.model_copy(update={"planner": "manual" if new.planner == "rules" else new.planner})
        save_and_compose(p, new)
        return new


# ------------------------------------------------------------------ meta / catalogue
API_VERSION = 8          # Free scene/visual/caption timing and component examples


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "time": now_iso(), "api_version": API_VERSION}


@app.get("/api/house-rules")
def house_rules_list() -> list[dict]:
    """Every lesson the app follows when it plans a video (vt/house_rules.py), with the incident behind it."""
    from .. import house_rules

    return house_rules.listing()


@app.get("/api/catalogue")
def catalogue() -> dict:
    cat = catalogue_summary()
    cat["stages"] = [{"key": k, "label": LABELS[k]} for k in ORDER]
    return cat


# Cartoon 1's character looks as a video made with each one shows them (vt/script/story_kit.py: the kit's drawn set; "illustrated" keeps the
# planner's own cartoon card)
_CAST = [{"who": "woman", "pose": "wave", "expression": "happy", "x": 0.32}, {"who": "man", "pose": "point", "expression": "happy", "x": 0.68, "flip": True}]
CARTOON_LOOKS = {
    "ink": {"character_style": "ink", "framing": "scene", "world": "3d", "set": "street", "cast": _CAST, "bubble": "We did it!", "props": []},
    "classic": {"character_style": "classic", "framing": "scene", "world": "3d", "set": "street", "cast": _CAST, "bubble": "We did it!", "props": []},
    "paper": {"character_style": "paper", "framing": "scene", "world": "3d", "set": "street", "cast": _CAST, "bubble": "We did it!", "props": []},
    "illustrated": {"cast": _CAST, "bubble": "We did it!", "props": []},
}


@app.get("/api/elements/{kind}/preview")
def element_preview(kind: str, variant: str = "", look: str = "") -> dict:
    """A real, silent component example using the same runtime as exported videos. `look` shows one of an element's looks the way a video
    made with it shows it (a Cartoon 1 character look: the New video page draws its choices with this, never with a made-up picture)."""
    from ..planner.catalogue import component_catalogue
    from ..schema import Beat, Beats, Scene, Transcript, Word
    from ..compose.composer import resolve_composition, write_composition
    spec = next((s for s in component_catalogue() if s["type"] == kind), None)
    if not spec:
        raise HTTPException(404, "Unknown element")
    if variant:
        from ..planner.visual_templates import templates
        spec=next((s for s in templates(component_catalogue()) if s['type']==kind and s['variant']==variant),None)
        if spec is None: raise HTTPException(404,"Unknown template")
    looks = CARTOON_LOOKS if kind == "cartoon" else {}
    if look and look not in looks:
        raise HTTPException(404, "Unknown look")
    sample_id=variant or kind
    if look:
        sample_id = f"{kind}-{look}"
    folder = paths.PROJECTS / ".elements" / sample_id
    folder.mkdir(parents=True, exist_ok=True)
    art = folder / "example.svg"
    art.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><rect width="800" height="600" fill="#dbeafe"/><circle cx="590" cy="150" r="65" fill="#fbbf24"/><path d="M0 600L270 240 440 460 600 300 800 600" fill="#60a5fa"/><text x="400" y="550" text-anchor="middle" font-family="sans-serif" font-size="36" fill="#172554">Your picture</text></svg>', encoding="utf-8")
    el = {**spec["starter"], "at_word": "w1", **looks.get(look, {})}
    if kind in ("media_frame", "device"):
        el["media"] = "example"
    theme = load_theme("paper")
    tr = Transcript(language="en", words=[Word(id="w1", text="Example", start=.3, end=3.5)])
    beats = Beats(beats=[Beat(id="b1", word_ids=["w1"], start=.3, end=3.5, text="Example")])
    sf = ScenesFile(scenes=[Scene(id="sample", beats=["b1"], elements=[el], layout="hero")])
    media = {"example": {"src":"example.svg", "kind":"image", "width":800, "height":600}}
    data = resolve_composition(sf, tr, beats, theme, "16:9" if look else "1:1", 4, media=media)
    data["captions_enabled"] = False
    write_composition(folder, data, theme, spec["name"])
    return {"url":f"/media/.elements/{sample_id}/index.html"}


@app.get("/api/icons/{name}")
def icon_svg(name: str) -> JSONResponse:
    icons = read_json(paths.ICONS / "lucide.json", {})
    if name not in icons:
        raise HTTPException(404)
    return JSONResponse({"name": name, "inner": icons[name]})


@app.get("/api/icon-pack")
def icon_pack() -> dict:
    """Inner SVG for the curated icon names (one request for the icon picker)."""
    icons = read_json(paths.ICONS / "lucide.json", {})
    names = read_json(paths.ICONS / "curated.json", [])
    return {n: icons[n] for n in names if n in icons}


@app.get("/api/visuals/search")
def visuals_search(q: str, kind: Optional[str] = None, limit: int = 12) -> list[dict]:
    """Icon/sticker picker: search by meaning in English, Bangla or other languages."""
    from ..visuals.search import search

    return search(q, kind if kind in ("icon", "sticker") else None, max(1, min(limit, 40)))


@app.get("/api/visuals/get")
def visuals_get(ids: str) -> dict:
    """Markup for the visuals currently used by a scene (comma separated ids; emoji characters are accepted)."""
    from ..visuals import emoji as emo
    from ..visuals.search import _describe, svg_for

    out = {}
    for v in [i for i in ids.split(",") if i][:40]:
        key = emo.emoji_key(v)
        vid = f"emoji:{key}" if key else v
        out[v] = {**_describe(vid), **svg_for(vid)}
    return out


@app.get("/api/doctor")
def doctor() -> list[dict]:
    return run_checks()


@app.get("/api/settings")
def get_settings() -> dict:
    return _public_settings(load_settings())


@app.get("/api/directors")
def get_directors() -> dict:
    from ..directors import listing

    return listing()


def _public_settings(s: dict) -> dict:
    """Settings for the browser: API keys never leave this computer's disk through the API (only whether they are set)."""
    from ..modules.calls import is_secret_key, redact

    def visible(value):
        if isinstance(value, dict):
            return {key: visible(item) for key, item in value.items() if not is_secret_key(key)}
        if isinstance(value, list):
            return [visible(item) for item in value]
        return redact(value)

    engines = {i: {"mode": e.get("mode"), "url": redact(e.get("url")), "has_key": bool(e.get("key"))} for i, e in (s.get("engines") or {}).items()}
    return visible({k: v for k, v in s.items() if k != "engines"}) | {"stock_keys": {k[:-4]: bool(v) for k, v in s.items() if k.endswith("_key")}, "engines": engines}


@app.put("/api/settings")
def put_settings(body: dict[str, Any]) -> dict:
    s = load_settings()
    for k in ("default_theme", "default_aspect", "default_pace", "default_music", "llm_mode", "ollama_url", "ollama_model", "llm_auto_download", "pexels_key", "pixabay_key",
              "ai_provider", "ai_script", "openai_url", "openai_model", "openai_key", "anthropic_model", "anthropic_key", "elevenlabs_key", "elevenlabs_model", "claude_cli_path", "claude_cli_model", "claude_cli_daily_cap", "autopilot", "comfy_url", "plan_review", "director_order", "director_wait_seconds"):
        if k in body:
            s[k] = body[k]
    if "director_model" in body:                                          # which Claude directs (Sonnet, Opus, ...): one name the helper accepts, never free text
        from ..directors import model_name

        s["director_model"] = model_name(body["director_model"])
    write_json(SETTINGS_PATH, s)
    return _public_settings(s)


# ------------------------------------------------------------------ scene types ("show as")
_director_args = planning.director_args


@app.get("/api/projects/{pid}/scenes/{sid}/shows")
def scene_options(pid: str, sid: str) -> list[dict]:
    from ..director.plan import options_for_scene

    p = proj(pid)
    sf = p.scenes()
    sc = next((s for s in (sf.scenes if sf else []) if s.id == sid), None)
    if not sc:
        raise HTTPException(404, "no such scene")
    return options_for_scene(p.transcript(), p.beats(), sc, **_director_args(p))


class ReshowBody(BaseModel):
    archetype: str
    media: Optional[str] = None       # a media-bin item to use in this scene (for the picture types)


@app.post("/api/projects/{pid}/scenes/{sid}/reshow")
def scene_reshow(pid: str, sid: str, body: ReshowBody) -> dict:
    """Show the same sentences as another kind of scene (chart, steps, cartoon...). Undoable like every edit."""
    from ..director.contrast import decide_for_media
    from ..director.plan import reshow

    p = proj(pid)
    meta = p.meta()

    def fn(sf: ScenesFile) -> ScenesFile:
        sc = next((s for s in sf.scenes if s.id == sid), None)
        if not sc:
            raise scene_ops.OpError(f"scene '{sid}' not found")
        try:
            new = reshow(p.transcript(), p.beats(), sc, body.archetype, aspect=meta.aspect, scrim_fn=lambda m, a, l, t0, t1: decide_for_media(p, m, a, l, t0, t1), media_id=body.media, **_director_args(p))
        except ValueError as e:
            raise scene_ops.OpError(str(e))
        return sf.model_copy(update={"scenes": [new if s.id == sid else s for s in sf.scenes]})

    sf = edit_scenes(p, fn)
    return {"plan": sf.model_dump(exclude_none=True)}


# ------------------------------------------------------------------ media bin
def _media_view(p: Project, m) -> dict:
    d = m.model_dump()
    d["url"] = f"/media/{p.id}/{m.file}"
    return d


@app.get("/api/projects/{pid}/media")
def list_media(pid: str) -> list[dict]:
    p = proj(pid)
    return [_media_view(p, m) for m in p.meta().media]


@app.post("/api/projects/{pid}/media")
async def upload_media(pid: str, file: UploadFile = File(...), caption: str = Form(""), tags: str = Form("")) -> dict:
    from ..director import media as M

    p = proj(pid)
    suffix = Path(file.filename or "x.jpg").suffix.lower()
    if suffix not in M.ALL_EXT:
        raise HTTPException(400, f"unsupported file type '{suffix}'. Use a picture, a GIF or a video clip.")
    tmp = Path(tempfile.mkdtemp()) / f"{re.sub(r'[^A-Za-z0-9._-]', '_', Path(file.filename or 'media').stem)}{suffix}"
    with tmp.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        item = await run_in_threadpool(M.add_media, p, tmp, caption=caption.strip()[:80], tags=[t.strip() for t in tags.split(",") if t.strip()][:8])
    except M.MediaError as e:
        raise HTTPException(422, str(e))
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
    changed(p.id)
    return _media_view(p, item)


class MediaPatch(BaseModel):
    caption: Optional[str] = None
    tags: Optional[list[str]] = None
    fx: Optional[float] = None
    fy: Optional[float] = None


@app.patch("/api/projects/{pid}/media/{mid}")
def patch_media(pid: str, mid: str, body: MediaPatch) -> dict:
    p = proj(pid)
    meta = p.meta()
    m = next((x for x in meta.media if x.id == mid), None)
    if not m:
        raise HTTPException(404, "no such media")
    if body.caption is not None:
        m.caption = body.caption.strip()[:80]
    if body.tags is not None:
        m.tags = [t.strip() for t in body.tags if t.strip()][:8]
    if body.fx is not None:
        m.fx = max(0.0, min(1.0, body.fx))
    if body.fy is not None:
        m.fy = max(0.0, min(1.0, body.fy))
    p.save_meta(meta)
    changed(p.id)
    return _media_view(p, m)



@app.post("/api/projects/{pid}/media/describe")
def describe_media(pid: str, all: bool = False) -> dict:
    """The vision model writes a caption and tags for media that have none (or all of them). Runs as a job."""
    from ..ai import media_tags

    p = proj(pid)

    def work(cb):
        res = media_tags.describe_project(p, lambda s, f, m: cb("media", f, m), only_missing=not all)
        changed(pid)
        return res
    return jobs.submit("media", pid, "Describe the pictures", work, when_busy="reuse").public()


@app.post("/api/projects/{pid}/aroll/apply")
def apply_aroll(pid: str, on: bool = True) -> dict:
    """Show the speaker (A-roll) on every scene where nothing better illustrates the words (the opening always), or put the graphics back with on=false. One undo step in the editor."""
    from .. import aroll as AR

    p = proj(pid)
    item = next((m for m in p.meta().media if m.id == "aroll" and m.role == "a_roll"), None)
    if item is None:
        raise HTTPException(409, "this project has no speaker's picture: make it from a video")
    beats, aspect = p.beats(), p.meta().aspect

    def fn(sf):
        sf = sf.model_copy(deep=True)
        if on:
            AR.apply_speaker(sf, p, beats, aspect, item)
        else:
            for sc in sf.scenes:
                if sc.backdrop and sc.backdrop.media == "aroll":
                    sc.backdrop = None
                    sc.archetype = None
        return sf
    sf = edit_scenes(p, fn)
    return {"scenes": sum(1 for s in sf.scenes if s.backdrop and s.backdrop.media == "aroll")}


@app.post("/api/projects/{pid}/media/{mid}/cutout")
def cutout_media(pid: str, mid: str) -> dict:
    """Remove the background of a picture in the media bin: a new picture '<id>-cutout' with a transparent background is added (the original stays). A job: the first use downloads a 180 MB model."""
    from .. import cutout as CO
    from ..director import media as M

    p = proj(pid)
    item = next((m for m in p.meta().media if m.id == mid), None)
    if not item:
        raise HTTPException(404, "no such media")
    if item.kind != "image":
        raise HTTPException(422, {"errors": ["background removal works on pictures (a video would need a mask for every frame)"]})
    if not CO.available():
        raise HTTPException(422, {"errors": ["background removal needs onnxruntime (pip install onnxruntime)"]})

    def work(cb):
        tmp = Path(tempfile.mkdtemp())
        try:
            CO.ensure_model(lambda f, m: cb("cutout", 0.05 + 0.5 * f, m))
            cb("cutout", 0.6, "Finding the subject")
            out = tmp / f"{mid[:30]}-cutout.png"
            info = CO.cut_out(p.dir / item.file, out)
            if info["kept"] < 0.005:
                raise RuntimeError("no clear subject was found in this picture")
            new = M.add_media(p, out, caption=(item.caption + " (cutout)").strip()[:80], tags=item.tags, source="cutout", credit=item.credit, licence=item.licence)
            changed(pid)
            return {"id": new.id, **info}
        except CO.CutoutError as e:
            raise RuntimeError(str(e))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return jobs.submit("cutout", pid, "Remove the background", work, when_busy="queue").public()


@app.delete("/api/projects/{pid}/media/{mid}")
def delete_media(pid: str, mid: str) -> dict:
    from ..director import media as M

    from .. import layers as L

    p = proj(pid)
    if any(c.get("media") == mid for c in L.load(p)["clips"]):
        raise HTTPException(409, "this file is used in the layers: remove those clips first")
    if not M.remove_media(p, mid):
        raise HTTPException(404, "no such media")
    sf = p.scenes()
    if sf and any((s.backdrop and s.backdrop.media == mid) or any(getattr(e, "media", None) == mid for e in s.elements) for s in sf.scenes):
        write_json(p.dir / "plan_notice.json", {"at": now_iso(), "planner": sf.planner, "message": f"The picture '{mid}' was removed but a scene still uses it. Press Auto-design to plan again."})
    changed(p.id)
    return {"ok": True}


# ------------------------------------------------------------------ stock media (optional, user's own keys)
@app.get("/api/stock/status")
def stock_status() -> dict:
    from ..director import stock

    return stock.status()                                   # which providers have a key; the keys themselves are never sent to the browser


@app.get("/api/projects/{pid}/stock/search")
async def stock_search(pid: str, q: str, kind: str = "image", provider: Optional[str] = None) -> list[dict]:
    from ..director import stock

    p = proj(pid)
    if kind not in ("image", "video", "clipart"):
        raise HTTPException(400, "kind must be image, video or clipart")
    try:
        return await run_in_threadpool(stock.search, q, kind=kind, aspect=p.meta().aspect, provider=provider)
    except stock.StockError as e:
        raise HTTPException(502, str(e))


@app.get("/api/projects/{pid}/stock/suggest")
def stock_suggest(pid: str) -> list[str]:
    from ..director import stock

    return stock.suggest(proj(pid))


class StockAdd(BaseModel):
    item: dict[str, Any]
    caption: str = ""


@app.post("/api/projects/{pid}/stock/add")
async def stock_add(pid: str, body: StockAdd) -> dict:
    from ..director import stock

    p = proj(pid)
    try:
        item = await run_in_threadpool(stock.add_to_project, p, body.item, body.caption)
    except stock.StockError as e:
        raise HTTPException(502, str(e))
    changed(p.id)
    return _media_view(p, item)


@app.get("/api/llm/status")
def llm_status() -> dict:
    from .. import llm

    return llm.status()


@app.post("/api/llm/test")
def llm_test() -> dict:
    """One tiny structured question, to show the user the model really answers (and how fast)."""
    import time as _t

    from .. import llm

    t0 = _t.time()
    try:
        r = llm.chat_json([{"role": "user", "content": "Which emoji fits the word 'lazy'? Answer as JSON."}],
                          {"type": "object", "properties": {"emoji": {"type": "string", "maxLength": 8}}, "required": ["emoji"]}, max_tokens=40, timeout=180)
    except llm.LLMUnavailable as e:
        return {"ok": False, "message": str(e)}
    return {"ok": True, "message": f"Answered in {_t.time() - t0:.1f} s", "sample": r.get("emoji", "")}


@app.post("/api/llm/setup")
def llm_setup() -> dict:
    """Install the portable local AI engine (when the address is this computer) and download the model. Runs as a background job."""
    from .. import llm

    def work(cb):
        model = llm.ensure_ready(lambda s, f, m: cb("llm", f, m), allow_download=True)
        return {"model": model}
    return jobs.submit("llm", None, "Set up the local AI", work).public()


@app.get("/api/mcp/status")
def mcp_status() -> dict:
    seen = read_json(paths.mcp_seen_path(), {}) or {}
    clients = read_json(paths.PROJECTS / ".mcp_clients.json", {}) or {}
    age = None
    if seen.get("at"):
        try:
            from datetime import datetime
            age = int((datetime.now().astimezone() - datetime.fromisoformat(seen["at"])).total_seconds())
        except Exception:
            age = None
    pend = planning.pending()
    py = str(Path(sys.executable))
    codex_seen = clients.get("codex", {})
    codex_age = None
    if codex_seen.get("at"):
        try:
            from datetime import datetime
            codex_age = int((datetime.now().astimezone() - datetime.fromisoformat(codex_seen["at"])).total_seconds())
        except Exception:
            pass
    return {"last_seen": seen.get("at"), "last_tool": seen.get("tool"), "seconds_ago": age,
            "connected": age is not None and age < 600, "pending": len(pend),
            "add_command": f'claude mcp add video-tool -- "{py}" -m vt.mcp.server',
            "codex_connected": codex_age is not None and codex_age < 600,
            "codex_seconds_ago": codex_age,
            "codex_add_command": f'codex mcp add video-tool --env VT_MCP_CLIENT=codex -- "{py}" -m vt.mcp.server',
            "say": "plan my pending videos"}



# ------------------------------------------------------------------ AI providers, video kind, scripts, assistants (MCP)
@app.get("/api/ai/status")
def ai_status() -> dict:
    from .. import ai

    s = load_settings()
    from ..ai import providers as _P

    st = _P.login_status()
    use = _P.usage_today()
    claude = {"found": st["found"], "logged_in": st["logged_in"], "plan": st["plan"], "reason": st["reason"], "model": s.get("claude_cli_model") or "sonnet",
              "daily_cap": int(s.get("claude_cli_daily_cap") or 200), "calls_today": use["calls"], "cost_usd_today": use["cost_usd"]}
    return {**ai.provider_status(), "claude": claude, "settings": {"ai_provider": s.get("ai_provider", "auto"), "ai_script": bool(s.get("ai_script")),
                                                   "openai_url": s.get("openai_url", ""), "openai_model": s.get("openai_model", ""),
                                                   "anthropic_model": s.get("anthropic_model", ""),
                                                   "openai_key_set": bool(s.get("openai_key")), "anthropic_key_set": bool(s.get("anthropic_key"))}}


@app.post("/api/ai/test")
def ai_test() -> dict:
    import time as _t

    from .. import ai

    t0 = _t.time()
    try:
        r = ai.complete_json("Which emoji fits the word 'lazy'? Answer as JSON.",
                             {"type": "object", "properties": {"emoji": {"type": "string", "maxLength": 8}}, "required": ["emoji"]}, max_tokens=60, timeout=180, cache=False)
    except ai.AIUnavailable as e:
        return {"ok": False, "message": str(e)}
    return {"ok": True, "message": f"Answered in {_t.time() - t0:.1f} s", "sample": r.get("emoji", "")}


class KindBody(BaseModel):
    kind: str


@app.put("/api/projects/{pid}/video-kind")
def put_video_kind(pid: str, body: KindBody) -> dict:
    from ..script import service

    if body.kind not in ("stick", "emoji", "explainer", "infographic", "cartoon", "mixed"):
        raise HTTPException(400, "unknown kind")
    p = proj(pid)
    service.set_script_kind(p, body.kind)
    changed(pid)
    return {"kind": body.kind}


@app.post("/api/projects/{pid}/script/generate")
def generate_script(pid: str, kind: str = "") -> dict:
    """Direct the whole video as a Video Script (the AI when one answers, else the rule director) and apply it. Runs as a job."""
    from ..script import service

    p = proj(pid)
    if kind:
        if kind not in ("stick", "emoji", "explainer", "infographic", "cartoon", "mixed"):
            raise HTTPException(400, "unknown kind")
        service.set_script_kind(p, kind)
    if not p.scenes():
        raise HTTPException(409, "Plan the video first.")

    def work(cb):
        from .. import ai
        from ..planner import plan_rules
        from ..pipeline import compose_all
        from ..script.planner import plan_script

        meta = p.meta()
        tr, beats = p.transcript(), p.beats()
        k = service.script_kind(p)
        draft = p.scenes()
        cb("plan", 0.05, "Directing the video")
        script, how = plan_script(tr, beats, draft=draft, use_ai=ai.provider_status().get("available", False), kind=k, language=meta.language,
                                  aspect=meta.aspect, media_ids={m.id for m in meta.planner_media()}, progress=lambda f, m: cb("plan", 0.1 + 0.8 * f, m))
        res = service.apply_script(p, script.model_dump(by_alias=True, exclude_none=True), planner=script.planner)
        if not res.get("ok"):
            raise RuntimeError("; ".join(res.get("errors", [])[:3]))
        changed(pid)
        return {"how": how, **res}
    return jobs.submit("plan", pid, "Direct the video", work, when_busy="reuse").public()


@app.get("/api/projects/{pid}/script")
def get_script(pid: str) -> dict:
    from ..script import service

    return {"script": service.current_script(proj(pid)), "kind": service.script_kind(proj(pid))}


@app.get("/api/projects/{pid}/script/task")
def script_task_text(pid: str, kind: str = "") -> dict:
    """For chat-only assistants (no MCP): one block of text to paste into the chat, plus the schema the answer must follow."""
    from ..script import service

    t = service.script_task(proj(pid), kind or None)
    return {"message": t["instructions"] + "\n\n" + t["task"] + "\n\nReply with ONLY the JSON object.", "schema": t["schema"]}


@app.post("/api/projects/{pid}/script/paste")
def script_paste(pid: str, body: dict[str, Any]) -> dict:
    from ..ai.providers import parse_json
    """The JSON a chat assistant answered with: repaired, validated, applied. Returns {ok, errors}."""
    from ..script import service

    raw = body.get("json", body)
    if isinstance(raw, str):
        try:
            raw = parse_json(raw)
        except ValueError:
            return {"ok": False, "errors": ["That is not valid JSON. Paste the assistant's whole answer."]}
    p = proj(pid)
    res = service.apply_script(p, raw, planner="manual")
    if res.get("ok"):
        changed(pid)
    return res



@app.post("/api/projects/{pid}/qa")
def run_qa(pid: str, fix: bool = False, pictures: bool = False) -> dict:
    """Look at one frame per scene (vision model, else pixel checks); optionally fix what is wrong and re-judge pictures. Runs as a job."""
    from ..ai import vision

    p = proj(pid)
    if not p.scenes():
        raise HTTPException(409, "Plan the video first.")

    def work(cb):
        res = vision.qa_project(p, lambda s, f, m: cb("qa", f * (0.6 if (fix or pictures) else 1.0), m))
        out: dict[str, Any] = {"bad": res["bad"], "model": res["model"]}
        if fix and res["bad"]:
            out["fixed"] = vision.fix_scenes(p, res)["changed"]
            changed(pid)
        if pictures:
            out["pictures"] = vision.improve_pictures(p, lambda s, f, m: cb("qa", 0.6 + 0.4 * f, m))["changed"]
            changed(pid)
        return out
    return jobs.submit("qa", pid, "Check the frames", work, when_busy="reuse").public()


@app.get("/api/projects/{pid}/qa")
def get_qa(pid: str) -> dict:
    return read_json(proj(pid).dir / "qa.json", {"scenes": [], "bad": []}) or {"scenes": [], "bad": []}


@app.get("/api/projects/{pid}/qa/frame/{name}")
def qa_frame(pid: str, name: str) -> FileResponse:
    f = proj(pid).dir / "qa_frames" / Path(name).name
    if not f.exists():
        raise HTTPException(404, "no such frame")
    return FileResponse(f)


@app.post("/api/projects/{pid}/autofix")
def autofix_project(pid: str) -> dict:
    """Automatically fix viewer test suggestions and frame issues: rebalances caption pacing,
    fixes empty/faint frames using rule planner visuals, re-composes, and renders an improved cut."""
    from ..ai import vision
    from ..pipeline import compose_all
    from .. import retention as RT

    p = proj(pid)
    if not p.scenes():
        raise HTTPException(409, "Plan the video first.")

    def work(cb):
        cb("autofix", 0.1, "Reading director notes & checking frames")
        qa = read_json(p.dir / "qa.json") or {"scenes": [], "bad": []}
        fixed = vision.fix_scenes(p, qa).get("changed", [])

        cb("autofix", 0.35, "Rebalancing caption pacing and composing")
        compose_all(p)
        changed(pid)

        a = p.meta().aspect
        old_card = None
        cards = sorted(p.exports_dir.glob("*.retention.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if cards:
            old_card = read_json(cards[0])
        old_risk = old_card.get("risk", 50) if old_card else 50

        cb("autofix", 0.5, "Rendering improved cut")
        r = export(p, a, quality="looks", gpu=True, music="__project__", fps=30, short_side=None, captions=True, clean_voice=False,
                   progress=lambda stage, f, msg="": cb("autofix", 0.5 + 0.4 * f, "Rendering improved cut"))
        f_vid = Path(r["video"])

        cb("autofix", 0.95, "Checking viewer retention metrics")
        comp = read_json(p.comp_dir / FORMATS[a]["tag"] / "data.json")
        card2 = RT.scorecard(f_vid, a, comp, p.cut_audio if p.cut_audio.exists() else None)
        RT.save(f_vid.with_suffix(".retention.json"), card2)

        write_json(p.dir / "revise.json", {
            "before": old_risk,
            "after": card2["risk"],
            "notes": "Auto-fixed caption pacing, contrast, and scene framing.",
            "kept": True
        })

        # update director chat
        chat_f = p.dir / "director_chat.json"
        cdata = read_json(chat_f, {"messages": []}) or {"messages": []}
        cdata["messages"].append({
            "from": "director",
            "text": "Fixed the things to look at: caption reading speed and scene framing. The new cut is easier to keep watching.",
            "at": now_iso(),
            "ok": True
        })
        write_json(chat_f, cdata)
        changed(pid)
        return {"ok": True, "before": old_risk, "after": card2["risk"], "fixed_scenes": fixed, "card": card2}

    return jobs.submit("autofix", pid, "Auto-fixing suggestions", work, when_busy="reuse").public()


@app.get("/api/mcp/connect")
def mcp_connect() -> dict:
    """Everything a user needs to connect an assistant: stdio command (Claude Code/Desktop, Cursor...), HTTP address + token (ChatGPT, others)."""
    from ..mcp import http as H

    py = str(Path(sys.executable))
    token = H.ensure_token()
    stdio = {"command": py, "args": ["-m", "vt.mcp.server"]}
    return {
        "token": token, "http_port": 8766, "http_url": "http://127.0.0.1:8766/mcp", "http_command": f'"{py}" -m vt.mcp.server --http --port 8766',
        "stdio": stdio,
        "claude_code": f'claude mcp add video-tool -- "{py}" -m vt.mcp.server',
        "codex": f'codex mcp add video-tool --env VT_MCP_CLIENT=codex -- "{py}" -m vt.mcp.server',
        "claude_desktop": {"mcpServers": {"video-tool": stdio}},
        "cursor": {"mcpServers": {"video-tool": stdio}},
        "gemini_cli": {"mcpServers": {"video-tool": {**stdio}}},
        "vscode": {"servers": {"video-tool": {"type": "stdio", **stdio}}},
        "chatgpt": "ChatGPT connectors need an HTTPS address. Start the HTTP server (command above), expose it with a tunnel you trust "
                   "(for example: cloudflared tunnel --url http://127.0.0.1:8766), then add the tunnel address + /mcp as a connector and send the token as a Bearer token. "
                   "A tunnel makes your local tools reachable from the internet: keep the token secret and revoke it when you are done.",
    }


# Connecting Claude Code, Codex or Claude Desktop is /api/assistants/{id}/connect (vt/assistants.py), the one implementation behind Settings and `vt assistants`.


@app.get("/api/assistants")
def assistants_list(request: Request) -> dict:
    """Claude Code, Codex and Claude Desktop on this computer: installed? connected? (vt/assistants.py). `here` is false on another computer:
    there the desktop app connects them on its own computer."""
    from .. import assistants
    from .serve import is_local

    return {"here": is_local(request.scope), "assistants": assistants.status() if is_local(request.scope) else []}


def _assistant_call(request: Request, aid: str, fn: str) -> dict:
    from .. import assistants
    from .serve import is_local

    if not is_local(request.scope):
        raise HTTPException(403, "This connects assistants on the server computer. On this device, use the Video Tool app: it connects them here in one click.")
    if aid not in assistants.IDS:
        raise HTTPException(404, "unknown assistant")
    try:
        return getattr(assistants, fn)(aid)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        raise HTTPException(409, str(e))


@app.post("/api/assistants/{aid}/connect")
def assistants_connect(aid: str, request: Request) -> dict:
    return _assistant_call(request, aid, "connect")


@app.post("/api/assistants/{aid}/disconnect")
def assistants_disconnect(aid: str, request: Request) -> dict:
    return _assistant_call(request, aid, "disconnect")


@app.post("/api/mcp/token/revoke")
def mcp_revoke() -> dict:
    from ..mcp import http as H

    return {"token": H.revoke_token()}


# ------------------------------------------------------------------ projects
@app.get("/api/projects")
def list_projects() -> list[dict]:
    out = [project_summary(p) for p in Project.list_all()]
    out.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return out


def _inspect(path: Path) -> dict:
    """The recording's mode (talking_head / video / audio); never fails the upload."""
    from ..source_inspect import inspect_source

    try:
        return inspect_source(path)
    except Exception:
        return {"mode": "audio" if path.suffix.lower() not in (".mp4", ".mov", ".mkv", ".webm") else "video"}


@app.post("/api/inspect")
async def inspect_upload(file: Optional[UploadFile] = File(None), file_upload: str = Form("")) -> dict:
    """Look at a recording before a project is made: is it a talking head, a video, or only audio? (for the New flow)
    The file comes in the request, or as a finished chunked upload (`file_upload`, vt/server/uploads.py), which stays for the project."""
    if file_upload:
        from .uploads import path_of

        src, name = path_of(file_upload)
        tmp = Path(tempfile.mkdtemp()) / f"inspect{Path(name).suffix.lower() or '.webm'}"
        try:
            os.link(src, tmp)                                    # same file, no copy (a 1 GB video); a copy where links are not allowed
        except OSError:
            shutil.copyfile(src, tmp)
        try:
            return await asyncio.to_thread(_inspect, tmp)
        finally:
            shutil.rmtree(tmp.parent, ignore_errors=True)
    if file is None:
        raise HTTPException(400, "No file was sent.")
    suffix = Path(file.filename or "rec.webm").suffix.lower() or ".webm"
    tmp = Path(tempfile.mkdtemp()) / f"inspect{suffix}"
    try:
        with tmp.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        return await asyncio.to_thread(_inspect, tmp)
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)


@app.post("/api/projects")
async def create_project(audio: Optional[UploadFile] = File(None), audio_upload: str = Form(""), title: str = Form(""), language: str = Form("en"),
                         aspect: str = Form("9:16"), theme: str = Form("paper"), pace: str = Form("normal"),
                         options: str = Form("{}"), start: Optional[str] = Form(None), usecase: str = Form("auto"), kind: str = Form("explainer"),
                         subtitles: Optional[UploadFile] = File(None)) -> dict:
    # NOTE: an omitted boolean form field arrives as False in recent FastAPI versions, so parse explicitly (default: start)
    start_now = start is None or start.strip().lower() in ("1", "true", "yes", "on")
    if aspect not in FORMATS:
        raise HTTPException(400, "aspect must be 9:16, 1:1 or 16:9")
    try:
        opts = json.loads(options or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "options must be JSON")
    allowed = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".opus", ".flac", ".aac", ".mp4", ".mov", ".mkv"}
    if audio_upload:                                             # sent before in chunks (vt/server/uploads.py)
        from .uploads import path_of, take

        filename = path_of(audio_upload)[1]
        if (Path(filename).suffix.lower() or ".webm") not in allowed:
            raise HTTPException(400, f"unsupported audio type '{Path(filename).suffix.lower()}'")
        tmp = take(audio_upload)[0]
    elif audio is not None:
        filename = audio.filename or ""
        suffix = Path(filename or "rec.webm").suffix.lower() or ".webm"
        if suffix not in allowed:
            raise HTTPException(400, f"unsupported audio type '{suffix}'")
        tmp = Path(tempfile.mkdtemp()) / f"upload{suffix}"
        with tmp.open("wb") as f:
            shutil.copyfileobj(audio.file, f)
    else:
        raise HTTPException(400, "No recording was sent.")
    try:
        sub = None
        if subtitles is not None and subtitles.filename:          # refuse bad subtitles before making a project or starting its job
            from ..ingest import read_subtitles

            sub = tmp.parent / ("subtitles" + (Path(subtitles.filename).suffix.lower() or ".srt"))
            with sub.open("wb") as f:
                shutil.copyfileobj(subtitles.file, f)
            read_subtitles(sub, language)
        name = title.strip() or (Path(filename).stem if filename and not filename.startswith("recording.") else f"Recording {time.strftime('%d %b %Y')}")
        p = Project.create(name, tmp, language=language, aspect=aspect, theme=theme, pace=pace,
                           options=ProjectMeta(id="x", options=opts).options.model_dump() if opts else None)
        info = _inspect(tmp)
        write_json(p.dir / "source.json", info)
        from ..source_inspect import default_recording_edit

        mode = default_recording_edit(info, p.meta().options.recording_edit)
        if mode != p.meta().options.recording_edit:               # a screen recording starts protected: its picture and pauses kept, captions added
            m = p.meta()
            m.options.recording_edit = mode
            p.save_meta(m)
        if sub is not None:                                     # the person's own timing replaces speech recognition
            from ..ingest import attach_subtitles

            attach_subtitles(p, sub, language)
    except ValidationError as e:
        raise HTTPException(422, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
    if not title.strip():
        p.update_meta(auto_title=True)
    p = _set_usecase(p, usecase)
    _set_kind(p, kind)
    job = start_pipeline(p, None, False) if start_now else None
    return {"project": project_summary(p), "job": job.public() if job else None}


class ScriptBody(BaseModel):
    title: str = "Untitled"
    script: str
    language: str = "auto"
    engine: str = "auto"
    voice: str = "en-US-AndrewNeural"
    rate: float = 1.0
    aspect: str = "9:16"
    theme: str = "paper"
    pace: str = "normal"
    options: dict[str, Any] = {}
    start: bool = True
    usecase: str = "auto"
    kind: str = "explainer"


class LinkBody(BaseModel):
    url: str
    title: str = ""
    language: str = "en"
    aspect: str = "9:16"
    theme: str = "paper"
    pace: str = "normal"
    options: dict[str, Any] = {}
    start: bool = True
    usecase: str = "auto"
    kind: str = "explainer"
    want_video: Optional[bool] = None


@app.post("/api/projects/from-link")
def create_from_link(body: LinkBody) -> dict:
    """A video from a link (YouTube or a direct audio/video file): download the audio and the subtitles, then the usual pipeline.
    Returns the download job; its result names the new project when it finishes."""
    from .. import ingest

    if body.aspect not in FORMATS:
        raise HTTPException(400, "aspect must be 9:16, 1:1 or 16:9")
    try:
        url = ingest.check_url(body.url)
        opts = ProjectMeta(id="x", options=body.options).options.model_dump() if body.options else None
    except ingest.IngestError as e:
        raise HTTPException(400, str(e))
    except ValidationError as e:
        raise HTTPException(422, str(e))

    def work(cb):
        want_vid = body.want_video if body.want_video is not None else (body.options.get("aroll", "auto") != "off")
        p = ingest.create_project(url, language=body.language, title=body.title, use_subs=body.options.get("use_subtitles", "auto"),
                                  want_video=want_vid,
                                  progress=lambda f, m: cb("download", f, m), aspect=body.aspect, theme=body.theme, pace=body.pace, options=opts)
        _set_usecase(p, body.usecase)
        _set_kind(p, body.kind)
        if body.start:
            start_pipeline(p, None, False)
        changed(p.id)
        return {"project": p.id}
    return jobs.submit("import", None, "Download from link", work).public()


@app.get("/api/voices")
def voices() -> list[dict]:
    from .. import tts

    return tts.voice_choices()


@app.post("/api/projects/from-script")
def create_from_script(body: ScriptBody) -> dict:
    """Typed script -> spoken voice -> the usual pipeline."""
    from .. import tts

    if body.aspect not in FORMATS:
        raise HTTPException(400, "aspect must be 9:16, 1:1 or 16:9")
    if not body.script.strip():
        raise HTTPException(400, "Write or paste the script first.")
    if len(tts.clean(body.script)) > tts.MAX_CHARS:
        raise HTTPException(400, f"The script is too long. Keep it under {tts.MAX_CHARS} characters.")
    if body.engine not in {e["id"] for e in tts.ENGINES} | {'auto'}:
        raise HTTPException(400, "unknown voice engine")
    if body.language == "auto":                   # decided by the letters; the voice follows the language when it was left at the other language's default
        from .. import langdetect

        body.language = langdetect.from_text(body.script, default="en")
        eng = next(e for e in tts.voice_choices() if e["id"] == body.engine)
        if not any(v["id"] == body.voice and v["lang"].startswith(body.language) for v in eng["voices"]):
            body.voice = next((v["id"] for v in eng["voices"] if v["lang"].startswith(body.language)), body.voice)
    try:
        first = re.split(r"[.?!।\n]", body.script.strip(), maxsplit=1)[0].split()
        p = Project.create_from_script(body.title.strip() or " ".join(first[:6]) or "Untitled", body.script, voice_engine=body.engine, voice=body.voice, rate=max(0.6, min(1.5, body.rate)),
                                       language=body.language, aspect=body.aspect, theme=body.theme, pace=body.pace,
                                       options=ProjectMeta(id="x", options=body.options).options.model_dump() if body.options else None)
    except ValidationError as e:
        raise HTTPException(422, str(e))
    if not body.title.strip():
        p.update_meta(auto_title=True)
    p = _set_usecase(p, body.usecase)
    _set_kind(p, body.kind)
    job = start_pipeline(p, None, False) if body.start else None
    return {"project": project_summary(p), "job": job.public() if job else None}


@app.post("/api/voices/preview")
def voice_preview(body: ScriptBody) -> FileResponse:
    """A short spoken sample so the user can pick a voice before making the video."""
    from .. import tts

    sample = (tts.clean(body.script) or "আমি এই ভিডিওটা বলব।")[:140]
    out = Path(tempfile.mkdtemp()) / "preview.wav"
    try:
        tts.synthesize(sample, out, engine=body.engine, voice=body.voice, rate=max(0.6, min(1.5, body.rate)))
    except tts.TTSError as e:
        raise HTTPException(502, str(e))
    return FileResponse(out, media_type="audio/wav")


def _set_kind(p: Project, kind: str) -> None:
    from ..script import service

    if kind in ("stick", "emoji", "explainer", "infographic", "cartoon", "mixed") and kind != "explainer":
        service.set_script_kind(p, kind)


def _set_usecase(p: Project, usecase: str) -> Project:
    from ..director.profiles import USECASES

    if usecase not in USECASES:
        raise HTTPException(400, f"use case must be one of {USECASES}")
    if usecase != "auto":
        p.update_meta(usecase=usecase)
    return p


@app.get("/api/scene-types")
def scene_types() -> list[dict]:
    from ..director.plan import ARCHETYPE_LABELS

    return [{"id": k, "label": v} for k, v in ARCHETYPE_LABELS.items()]


@app.get("/api/usecases")
def usecases() -> list[dict]:
    """The kinds of video the director knows (product, story, discussion, education...), for the picker."""
    from ..director import profiles

    return [{"id": "auto", "label": "Auto", "about": "Decided from what is said."}] + profiles.listing()


def start_pipeline(p: Project, from_stage: Optional[str], force: bool, rerender: bool = False):
    def work(cb):
        pl = Pipeline(p, cb)
        pl.run(from_stage, None, force)
        changed(p.id)
        if pl.pause_reason:                                          # the plan is waiting for the person: nothing more is made until they press Start
            return {"project": p.id, "waiting": pl.pause_reason}
        if rerender or (from_stage is None and load_settings().get("autopilot", True)):
            autopilot_finish(p, cb, again=rerender)
        return {"project": p.id}
    return jobs.submit("pipeline", p.id, p.meta().title, work, when_busy="reuse")


REVISE_OVER = 35          # retention risk above which the autopilot sends the worst moments back to the director (RT.verdict calls it "Risky")


def _remove(f: Path, tries: int = 20) -> bool:
    """Delete a file that Windows may still hold for a moment (an antivirus scan of a fresh video, a preview): retry for a few seconds, then leave it."""
    for _ in range(tries):
        try:
            f.unlink(missing_ok=True)
            return True
        except PermissionError:
            time.sleep(0.3)
    log.warning("could not delete %s (in use); left in place", f)
    return False


QA_WORDS = {"cut_off": "something is cut off at the screen edge", "overlap": "text and pictures cover each other", "unreadable": "text is too small or faint to read",
            "empty": "the screen is nearly empty", "unrelated": "the picture does not match what is said", "tiny_text": "text is too small"}


def watch_and_revise(p: Project, card: dict, first: Path, cb, qa: Optional[dict] = None) -> bool:
    """An editor watches the cut and fixes the moments where viewers would leave: the scorecard's worst moments go to the director as
    a note, the video is rendered and scored again, and the new cut is kept only when its risk is lower; otherwise the first plan
    and video come back. Needs an AI and a Video Script (the director's plan); one round. Returns True when the new cut was kept."""
    from .. import ai
    from .. import retention as RT
    from ..ai import providers as AIP
    from ..script import chat
    from ..script.service import current_script

    seen = [s for s in (qa or {}).get("scenes", []) if not s["ok"] and s.get("source") == "vlm"]
    if (card["risk"] <= REVISE_OVER and len(seen) < 2) or not AIP.ai_enabled() or not current_script(p) or not (card.get("worst") or seen):
        return False
    a = p.meta().aspect
    saved = {n: read_json(p.dir / n) for n in ("scenes.json", "video_script.json", "director.json")}
    notes = "; ".join([f"at {w['t0']:.1f}-{w['t1']:.1f} s: {w['message']}" for w in card["worst"][:4]]
                      + [f"scene {s['id']} (at {s['t']:.1f} s): " + ", ".join(QA_WORDS.get(x, x) for x in s["problems"]) + (f" ({s['fix_hint']})" if s.get("fix_hint") else "") for s in seen[:5]])
    cb("check", 0.3, "Fixing the slow moments")
    try:
        res = chat.talk(p, author="viewer test", message="A viewer test found moments where people would scroll away. Fix only these, keep everything else: " + notes)
    except ai.AIUnavailable:
        return False
    if not res["ok"]:
        return False
    r2 = export(p, a, quality="looks", gpu=True, music="__project__", fps=30, short_side=None, captions=True, clean_voice=False,
                progress=lambda stage, f, msg="": cb("render", f, "Rendering the improved cut"))
    f2 = Path(r2["video"])
    card2 = RT.scorecard(f2, a, read_json(p.comp_dir / FORMATS[a]["tag"] / "data.json"), p.cut_audio if p.cut_audio.exists() else None)
    if card2["risk"] < card["risk"] or (seen and card2["risk"] <= card["risk"] + 2):      # better, or the flagged frames fixed without losing viewers
        RT.save(f2.with_suffix(".retention.json"), card2)
        for f in (first, first.with_suffix(".retention.json"), first.with_suffix(".srt")):
            _remove(f)
        write_json(p.dir / "revise.json", {"before": card["risk"], "after": card2["risk"], "notes": notes, "kept": True})
        try:
            from ..director_review import remeasure

            remeasure(p)                                         # the cut changed after the director looked: list what is really left for the person
        except Exception as e:                                   # noqa: BLE001  a report, never a reason to lose the cut
            log.warning("could not re-measure %s: %s", p.id, e)
        return True
    for n, d in saved.items():                                   # worse or no better: the first cut stays
        if d is not None:
            write_json(p.dir / n, d)
    compose_all(p)
    for f in (f2, f2.with_suffix(".srt")):
        _remove(f)
    write_json(p.dir / "revise.json", {"before": card["risk"], "after": card2["risk"], "notes": notes, "kept": False})
    return False


def autopilot_finish(p: Project, cb, again: bool = False) -> None:
    """Checking and revising the cut is the video's own director's work, and its prompts stay on the video's record."""
    from ..pipeline import directing

    with directing(p):
        _autopilot_finish(p, cb, again)


def _autopilot_finish(p: Project, cb, again: bool = False) -> None:
    """Autopilot: the person only spoke, so the job does what an editor would do next: render the video, watch it back (retention
    scorecard) and write the title, description, hashtags and cover. Only for a project that was never exported, so re-running a
    stage from the editor does not render again. A failure here never fails the pipeline: the editable timeline is already made."""
    from .. import retention as RT

    if not again and p.exports_dir.exists() and any(p.exports_dir.glob("*.mp4")):
        return
    a = p.meta().aspect
    try:
        r = export(p, a, quality="looks", gpu=True, music="__project__", fps=30, short_side=None, captions=True, clean_voice=False,
                   progress=lambda stage, f, msg="": cb("render", f, "Rendering your video"))
        changed(p.id)
    except Exception as e:                                  # rendering can fail on a machine without Chrome/ffmpeg; the editor still works
        log.warning("autopilot render failed for %s: %s", p.id, e)
        cb("render", 1.0, f"Could not render: {e}")
        return
    card = None
    try:
        cb("check", 0.0, "Watching it back")
        comp = read_json(p.comp_dir / FORMATS[a]["tag"] / "data.json")
        f = Path(r["video"])
        card = RT.scorecard(f, a, comp, p.cut_audio if p.cut_audio.exists() else None)
        RT.save(f.with_suffix(".retention.json"), card)
    except Exception as e:
        log.warning("autopilot retention check failed for %s: %s", p.id, e)
    try:
        from .review_routes import judge_export

        cb("check", 0.3, "Running the quality checks")
        judge_export(p, Path(r["video"]))
    except Exception as e:                                  # a judge that cannot run never fails the video
        log.warning("autopilot judges failed for %s: %s", p.id, e)
    qa = None
    try:
        from ..ai import vision

        cb("check", 0.5, "Looking at every scene like an editor")
        qa = vision.qa_project(p, lambda s, f, m: cb("check", 0.5 + 0.3 * f, m), video=Path(r["video"]), max_scenes=20)
    except Exception as e:
        log.warning("autopilot frame check failed for %s: %s", p.id, e)
    if card and not again:
        try:
            watch_and_revise(p, card, Path(r["video"]), cb, qa)
        except Exception as e:                                   # the first cut is already good enough to keep
            log.warning("autopilot revise failed for %s: %s", p.id, e)
    try:
        from ..ai import publish

        publish.build_kit(p, lambda s, f, m: cb("publish", f, m or "Writing the title and hashtags"), cover=True)
        kit = read_json(p.dir / "publish.json") or {}
        if p.meta().auto_title and (kit.get("title") or "").strip():
            p.update_meta(title=kit["title"].strip()[:80], auto_title=False)
    except Exception as e:
        log.warning("autopilot publish kit failed for %s: %s", p.id, e)
    changed(p.id)


@app.get("/api/projects/{pid}/decisions")
def edit_decisions(pid: str) -> dict:
    """What the automatic editor cut, with its reasons: retakes and false starts (vt/retakes.py), sentences dropped to reach the target length (vt/tighten.py)."""
    p = proj(pid)
    tg = read_json(p.dir / "tighten.json") or {}
    return {"retakes": (read_json(p.dir / "retakes.json") or {}).get("cuts", []),
            "tighten": {"target": tg.get("target"), "cuts": [{k: v for k, v in d.items() if k != "src"} for d in tg.get("cuts", [])]},
            "revise": read_json(p.dir / "revise.json")}


class RestoreBody(BaseModel):
    kind: Literal["retakes", "tighten"]


@app.post("/api/projects/{pid}/decisions/restore")
def restore_decisions(pid: str, body: RestoreBody) -> dict:
    """Put back what the automatic editor cut (all retakes, or all dropped sentences), then rebuild and render again. Undo: turn the option back on."""
    p = proj(pid)
    if jobs.active_for(pid):
        raise HTTPException(409, "already running")
    m = p.meta()
    if body.kind == "retakes":
        m.options.remove_retakes = False
    else:
        m.options.target_length = "keep"
    p.save_meta(m)
    return start_pipeline(p, "cuts" if body.kind == "retakes" else "tighten", False, rerender=True).public()


class DirectorMessage(BaseModel):
    message: str


@app.get("/api/projects/{pid}/director")
def director_view(pid: str) -> dict:
    """The director's report (how the plan was made, the critic's notes) and the conversation with the person."""
    from ..script import chat

    p = proj(pid)
    return {"report": read_json(p.dir / "director.json"), "messages": chat.history(p)}


@app.post("/api/projects/{pid}/director/chat")
def director_chat(pid: str, body: DirectorMessage) -> dict:
    """Ask the director for a change in plain words. A job: the AI rewrites the script, the critic checks it, the plan is applied
    (undo keeps the previous one) and, when the video was already rendered, it is rendered again."""
    from .. import ai
    from ..script import chat

    p = proj(pid)
    if not body.message.strip():
        raise HTTPException(400, "Say what you would like to change.")
    if not p.scenes():
        raise HTTPException(409, "The video is not planned yet.")
    if jobs.active_for(pid):
        raise HTTPException(409, "already running")

    def work(cb):
        try:
            res = chat.talk(p, body.message, say=lambda f, m: cb("director", 0.6 * f, m))
        except ai.AIUnavailable as e:
            raise RuntimeError(f"No AI could answer ({e}). Choose one in Settings > AI.") from e
        changed(pid)
        if res["ok"] and p.exports_dir.exists() and any(p.exports_dir.glob("*.mp4")):
            autopilot_finish(p, lambda s, f, m="": cb(s, 0.6 + 0.4 * f, m), again=True)
        return res
    return jobs.submit("director", pid, "The director is working on your note", work, when_busy="refuse").public()


class DirectorStateBody(BaseModel):
    state: dict[str, Any]


@app.put("/api/projects/{pid}/director/state")
def put_director_state(pid: str, body: DirectorStateBody) -> dict:
    """Swap the whole state written by one Director turn. The returned prior state makes the same action a redo."""
    from ..script import chat

    p = proj(pid)
    with p.scenes_lock():
        before = chat.director_state(p)
        try:
            chat.restore_director_state(p, body.state)
        except (ValueError, ValidationError) as e:
            raise HTTPException(422, f"Could not restore the Director change: {e}") from e
        try:
            compose_all(p)
        except Exception as e:
            # The HTTP request must be all-or-nothing. Otherwise the client keeps its old history stacks while the files have already moved.
            chat.restore_director_state(p, before)
            try:
                compose_all(p)
            except Exception:
                pass
            raise HTTPException(500, f"Could not rebuild the restored Director change: {e}") from e
        if before.get("plan"):
            write_json(p.dir / "scenes.prev.json", before["plan"])
    changed(pid)
    return {"state": before}


@app.get("/api/projects/{pid}")
def get_project(pid: str) -> dict:
    return project_summary(proj(pid))


class MetaPatch(BaseModel):
    usecase: Optional[str] = None
    title: Optional[str] = None
    aspect: Optional[str] = None
    theme: Optional[str] = None
    pace: Optional[str] = None
    options: Optional[dict[str, Any]] = None


@app.patch("/api/projects/{pid}")
def patch_project(pid: str, body: MetaPatch) -> dict:
    p = proj(pid)
    m = p.meta()
    rerun_from = None
    if body.title is not None:
        m.title = body.title.strip() or m.title
        m.auto_title = False
    if body.aspect is not None:
        if body.aspect not in FORMATS:
            raise HTTPException(400, "bad aspect")
        m.aspect = body.aspect  # type: ignore[assignment]
    if body.theme is not None:
        if body.theme != "auto":
            try:
                load_theme(body.theme)
            except FileNotFoundError:
                raise HTTPException(404, "theme not found")
        m.theme = body.theme
        from .. import taste

        if taste.learn_choice("theme", body.theme):
            s = load_settings()
            if s.get("default_theme") != body.theme:
                s["default_theme"] = body.theme
                write_json(SETTINGS_PATH, s)
    if body.usecase is not None:
        from ..director.profiles import USECASES

        if body.usecase not in USECASES:
            raise HTTPException(400, f"use case must be one of {USECASES}")
        m.usecase = body.usecase  # type: ignore[assignment]
    if body.pace is not None and body.pace != m.pace:
        m.pace = body.pace  # type: ignore[assignment]
        rerun_from = "silence"
    if body.options:
        try:                                                 # validated: an unknown caption look or a wrong type is refused with the reason, never saved
            new_opts = type(m.options).model_validate({**m.options.model_dump(), **body.options})
        except ValidationError as e:
            raise HTTPException(422, {"errors": [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()][:6]})
        if (new_opts.remove_fillers != m.options.remove_fillers) and rerun_from is None:
            rerun_from = "cuts"
        if new_opts.asr_model != m.options.asr_model:
            rerun_from = "asr"
        m.options = new_opts
    p.save_meta(m)
    sf = p.scenes()
    if sf and body.theme and sf.theme != body.theme:
        p.save_scenes(sf.model_copy(update={"theme": body.theme}))
    visual = any(v is not None for v in (body.theme, body.aspect, body.pace, body.options, body.usecase))
    if visual and p.scenes():                                # a rename alone changes nothing on screen: no 0.5 s recompose, no loading layer
        compose_all(p)
    changed(pid)
    out = project_summary(p)
    out["needs_reprocess_from"] = rerun_from
    return out



@app.post("/api/projects/{pid}/duplicate")
def duplicate_project(pid: str) -> dict:
    """A copy to try another look on: everything except the exports and caches. Opens as '<title> (copy)'."""
    src = proj(pid)
    base = f"{src.id}-copy"
    new_id, n = base, 2
    while (paths.PROJECTS / new_id).exists():
        new_id, n = f"{base}-{n}", n + 1
    dst = paths.PROJECTS / new_id
    shutil.copytree(src.dir, dst, ignore=shutil.ignore_patterns("exports", "snapshots", "qa_frames", "cover_frames", "cover_comp", "*.tmp", "requests"))
    meta = read_json(dst / "project.json", {}) or {}
    meta.update(id=new_id, title=f"{meta.get('title') or src.id} (copy)", created_at=now_iso(), status="planned" if (dst / "scenes.json").exists() else "draft")
    write_json(dst / "project.json", meta)
    out = Project(new_id)
    changed(new_id)
    return project_summary(out)


@app.delete("/api/projects/{pid}")
def delete_project(pid: str) -> dict:
    p = proj(pid)
    if jobs.active_for(pid):
        raise HTTPException(409, "a job is running for this project")
    shutil.rmtree(p.dir)
    return {"ok": True}


class RunBody(BaseModel):
    director: Optional[str] = Field(default=None, max_length=80)
    from_stage: Optional[str] = None
    force: bool = False
    rerender: bool = False
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    video_kind: Optional[str] = None


@app.post("/api/projects/{pid}/run")
def run_project(pid: str, body: RunBody) -> dict:
    p = proj(pid)
    if body.from_stage and body.from_stage not in ORDER:
        raise HTTPException(400, f"stage must be one of {ORDER}")
    if jobs.active_for(pid):
        raise HTTPException(409, "already running")
    if body.video_kind:
        from ..script import service

        if body.video_kind not in ("auto", "story", "reel", "stick", "emoji", "explainer", "infographic", "cartoon", "mixed"):
            raise HTTPException(400, "Choose one of the available video styles.")
        service.set_script_kind(p, body.video_kind if body.video_kind not in ("auto", "story", "reel") else "explainer")
        meta = p.meta()
        meta.options.look = body.video_kind if body.video_kind in ("story", "reel") else "classic"
        p.save_meta(meta)
    if body.director is not None:
        meta = p.meta()
        meta.options.director = body.director or "best"
        p.save_meta(meta)
    if body.ai_provider or body.ai_model:
        s = load_settings()
        if body.ai_provider:
            s["ai_provider"] = body.ai_provider
        if body.ai_model:
            prov = s.get("ai_provider", "auto")
            if prov == "auto":
                s["ollama_model"] = body.ai_model
            elif prov in ("claude_cli", "best"):
                s["claude_cli_model"] = body.ai_model
            elif prov == "anthropic":
                s["anthropic_model"] = body.ai_model
            elif prov == "openai":
                s["openai_model"] = body.ai_model
        write_json(SETTINGS_PATH, s)
    return start_pipeline(p, body.from_stage, body.force, rerender=body.rerender).public()


@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    return [j.public() for j in jobs.snapshot()]


@app.get("/api/jobs/{jid}")
def get_job(jid: str) -> dict:
    j = jobs.jobs.get(jid)
    if not j:
        raise HTTPException(404)
    return j.public()


@app.get("/api/jobs/{jid}/log")
def job_log(jid: str, after: int = 0) -> dict:
    """The job's step-by-step log (verbose view): lines newer than `after`."""
    j = jobs.jobs.get(jid)
    if not j:
        raise HTTPException(404)
    return j.log_after(after)


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str) -> dict:
    return {"cancelled": jobs.cancel(jid)}


# ------------------------------------------------------------------ transcript
@app.get("/api/projects/{pid}/transcript")
def get_transcript(pid: str) -> dict:
    p = proj(pid)
    return {"transcript": p.transcript().model_dump(), "beats": p.beats().model_dump(),
            "glossary": p.glossary()}


class WordEdit(BaseModel):
    text: Optional[str] = None
    cut: Optional[bool] = None
    restore: bool = False
    start: Optional[float] = None
    end: Optional[float] = None
    reset_timing: bool = False


class SnippetBody(BaseModel):
    text: str
    beat: Optional[str] = None            # a sentence id; without it the text replaces the whole transcript
    dry: bool = False                     # only show what would change


@app.put("/api/projects/{pid}/transcript")
def correct_transcript(pid: str, body: SnippetBody) -> dict:
    """Paste the correct text of one sentence (or of everything): matching words keep their time, the rest is lined up around them."""
    from .. import transcript_edit as TE

    p = proj(pid)
    if not p.raw_transcript_path.exists():
        raise HTTPException(409, "this project has no transcript to edit yet; process the audio first")
    if not body.text.strip():
        raise HTTPException(422, "paste the text of the sentence")
    if len(body.text) > 200_000:
        raise HTTPException(400, "that text is too long")
    tr, beats = p.transcript(), p.beats()
    if body.beat:
        b = next((x for x in beats.beats if x.id == body.beat), None)
        if not b:
            raise HTTPException(404, f"no sentence {body.beat}")
        ids = set(b.word_ids)
        words = [w for w in tr.words if w.id in ids]
    else:
        words = list(tr.words)
    old = [(w.id, w.text) for w in words]
    changes = TE.align(old, body.text)
    names = dict(old)
    preview = [{"id": i, "from": names[i], "to": None if c.get("drop") else c["text"]} for i, c in changes.items()]
    if body.dry or not changes:
        return {"changed": len(changes), "changes": preview, "applied": False}
    path = p.dir / "edits.json"
    cur = read_json(path, {"words": {}}) or {"words": {}}
    write_json(p.dir / "edits.prev.json", cur)                       # one step back for "Undo the text change"
    write_json(path, TE.merge(cur, changes))
    _rebuild_words(p, pid)
    return {"changed": len(changes), "changes": preview, "applied": True}


@app.post("/api/projects/{pid}/transcript/undo")
def undo_transcript(pid: str) -> dict:
    p = proj(pid)
    prev = read_json(p.dir / "edits.prev.json")
    if prev is None:
        raise HTTPException(409, "there is no text change to undo")
    cur = read_json(p.dir / "edits.json", {"words": {}}) or {"words": {}}
    write_json(p.dir / "edits.json", prev)
    write_json(p.dir / "edits.prev.json", cur)                       # so a second press redoes it
    _rebuild_words(p, pid)
    return {"ok": True}


def _rebuild_words(p: Project, pid: str) -> None:
    pl = Pipeline(p)
    pl.stage_words()
    pl.stage_plan()
    compose_all(p)
    changed(pid)


@app.put("/api/projects/{pid}/words/{wid}")
def edit_word(pid: str, wid: str, body: WordEdit) -> dict:
    p = proj(pid)
    if not re.fullmatch(r"w\d+", wid):
        raise HTTPException(400, "bad word id")
    if not p.raw_transcript_path.exists():
        raise HTTPException(409, "this project has no transcript to edit yet; process the audio first")
    path = p.dir / "edits.json"
    edits = read_json(path, {"words": {}}) or {"words": {}}
    import copy
    before = copy.deepcopy(edits)
    cur = edits["words"].get(wid, {})
    if body.reset_timing:
        cur.pop("caption_start_src", None)
        cur.pop("caption_end_src", None)
    if body.start is not None or body.end is not None:
        from ..audio_edit import out_to_src
        from math import isfinite
        word = p.transcript().by_id().get(wid)
        if not word:
            raise HTTPException(404, "Word not found")
        a = body.start if body.start is not None else word.caption_start if word.caption_start is not None else word.start
        b = body.end if body.end is not None else word.caption_end if word.caption_end is not None else word.end
        if not isfinite(a) or not isfinite(b) or not 0 <= a < b <= p.cuts().output_duration:
            raise HTTPException(422, "Keep caption start and end inside the video, with end after start")
        cur.update(caption_start_src=out_to_src(p.cuts(), a), caption_end_src=out_to_src(p.cuts(), b))
    if body.text is not None and body.text.strip() and not body.restore:
        from .. import taste

        raw_words = (read_json(p.raw_transcript_path, {}) or {}).get("words", [])
        i = int(wid[1:]) - 1                                   # word ids are positions in the raw transcript (vt/stages/words.py)
        heard = raw_words[i].get("text", "") if 0 <= i < len(raw_words) else ""
        taste.learn_fix(heard, body.text, p.id)
    if body.restore:
        cur = {}
    else:
        if body.text is not None:
            if not body.text.strip():
                raise HTTPException(422, "word text cannot be empty; use cut to remove a word")
            cur["text"] = body.text.strip()
        if body.cut is not None:
            cur["cut"] = body.cut
    if cur:
        edits["words"][wid] = cur
    else:
        edits["words"].pop(wid, None)
    write_json(path, edits)
    if edits != before:
        history = read_json(p.dir / "word_history.json", {"past": [], "future": []})
        history["past"] = (history["past"] + [before])[-50:]
        history["future"] = []
        write_json(p.dir / "word_history.json", history)
    pl = Pipeline(p)
    pl.stage_words()
    pl.stage_plan()
    compose_all(p)
    changed(pid)
    return {"ok": True}



@app.post("/api/projects/{pid}/words/history/{direction}")
def word_history(pid: str, direction: str) -> dict:
    if direction not in ("undo", "redo"):
        raise HTTPException(404, "Unknown history action")
    p = proj(pid)
    path = p.dir / "word_history.json"
    history = read_json(path, {"past": [], "future": []})
    take, give = ("past", "future") if direction == "undo" else ("future", "past")
    if not history[take]:
        raise HTTPException(409, "No caption change to restore")
    history[give].append(read_json(p.dir / "edits.json", {"words": {}}))
    write_json(p.dir / "edits.json", history[take].pop())
    write_json(path, history)
    _rebuild_words(p, pid)
    return {"ok": True}


@app.post("/api/projects/{pid}/polish")
def run_polish(pid: str) -> dict:
    """The language model suggests fixes for recognition mistakes (never applied without the user's say-so). Runs as a job."""
    from .. import ai
    from ..ai import polish

    p = proj(pid)
    if not p.raw_transcript_path.exists():
        raise HTTPException(409, "process the audio first")

    def work(cb):
        res = polish.suggest(p, lambda s, f, m: cb("polish", f, m))
        changed(pid)
        return {"suggestions": len(res)}
    return jobs.submit("polish", pid, "Check the transcript", work, when_busy="reuse").public()


@app.get("/api/projects/{pid}/polish")
def get_polish(pid: str) -> dict:
    from ..ai import polish

    return {"suggestions": polish.load(proj(pid))}


class PolishDecision(BaseModel):
    accept: list[str] = []
    reject: list[str] = []


@app.post("/api/projects/{pid}/polish/decide")
def decide_polish(pid: str, body: PolishDecision) -> dict:
    from ..ai import polish

    p = proj(pid)
    res = polish.decide(p, body.accept, body.reject)
    if res["applied"]:
        pl = Pipeline(p)
        pl.stage_words()
        pl.stage_plan()
        compose_all(p)
    changed(pid)
    return res




# ------------------------------------------------------------------ free media catalogue (assets/media_catalog.json)
@app.get("/api/catalog")
def get_catalog(kind: str = "", role: str = "") -> dict:
    from ..director import catalog as CT

    es = CT.load()
    return {"entries": [CT.public(e) for e in es if (not kind or e["kind"] == kind) and (not role or e.get("role") == role)], "summary": CT.summary(es)}


@app.post("/api/catalog/refresh")
def refresh_catalog(discover: bool = True) -> dict:
    """Look for new free media and re-check every entry (downloads and decodes each one). Runs as a job."""
    from ..director import catalog as CT

    def work(cb):
        es = CT.refresh(lambda m: cb("catalog", 0.5, m), discover=discover)
        return CT.summary(es)
    return jobs.submit("catalog", None, "Update the free media catalogue", work, when_busy="reuse").public()


@app.post("/api/catalog/{eid}/check")
def check_catalog_entry(eid: str) -> dict:
    from ..director import catalog as CT

    try:
        e = CT.find(eid)
    except CT.CatalogError as ex:
        raise HTTPException(404, {"errors": [str(ex)]})
    new = CT.validate(e)
    CT.save([new if x["id"] == eid else x for x in CT.load()])
    return CT.public(new)


@app.post("/api/projects/{pid}/catalog/{eid}/add")
def add_catalog_media(pid: str, eid: str) -> dict:
    """Put a free clip or picture into the project's media bin (source, licence and credit are kept)."""
    from ..director import catalog as CT

    p = proj(pid)
    try:
        item = CT.install_media(p, eid)
    except CT.CatalogError as ex:
        raise HTTPException(502 if "download" in str(ex) else 422, {"errors": [str(ex)]})
    except Exception as ex:                                          # a file the media code cannot use
        raise HTTPException(422, {"errors": [f"The file could not be used: {str(ex)[:160]}"]})
    changed(pid)
    return {"id": item.id, "kind": item.kind}


@app.post("/api/catalog/{eid}/music")
def install_catalog_music(eid: str) -> dict:
    """Download a free track into your music folder: it then appears in the Export music list (with its credit)."""
    from ..director import catalog as CT

    try:
        return {"music": CT.install_music(eid)}
    except CT.CatalogError as ex:
        raise HTTPException(502 if "download" in str(ex) else 422, {"errors": [str(ex)]})


@app.post("/api/catalog/{eid}/project")
def project_from_catalog(eid: str, body: dict[str, Any] = {}) -> dict:
    """Make a video from a free speech recording (a quick way to try the app). Returns the download job."""
    from .. import ingest
    from ..director import catalog as CT

    try:
        e = CT.find(eid)
    except CT.CatalogError as ex:
        raise HTTPException(404, {"errors": [str(ex)]})
    if e["kind"] != "audio" or e.get("status") != "ok":
        raise HTTPException(422, {"errors": ["Choose a working audio entry."]})

    seconds = max(15, min(180, int(body.get("seconds", 75))))

    def work(cb):
        import subprocess
        import tempfile

        from ..director import catalog as CT2
        from ..util import find_tool

        with tempfile.TemporaryDirectory() as d:
            raw, cut = Path(d) / "full.mp3", Path(d) / "sample.wav"
            cb("download", 0.05, "Downloading the sample")
            try:
                CT2.download(e["url"], raw, CT2.MAX_MB["audio"])
            except CT2.CatalogError as ex:
                raise RuntimeError(f"Could not download the sample: {ex}")
            info = CT2.ffprobe(raw)
            start = 25 if info["duration"] > seconds + 60 else 0            # skip a spoken intro ("This is a LibriVox recording...")
            cb("download", 0.6, f"Cutting {seconds} seconds")
            subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-ss", str(start), "-t", str(seconds), "-i", str(raw), "-ac", "1", "-ar", "16000", str(cut)], check=True)
            p = Project.create(body.get("title") or e["title"][:60], cut, language=body.get("language", "en"), aspect=body.get("aspect", "9:16"))
        _set_kind(p, body.get("kind", "explainer"))
        p.update_meta(origin={"url": e["page_url"], "title": e["title"], "uploader": e["creator"], "license": e["licence"], "subtitles": "none"})
        start_pipeline(p, None, False)
        changed(p.id)
        return {"project": p.id}
    return jobs.submit("import", None, "Download the sample", work).public()


# ------------------------------------------------------------------ the voice track: cut, trim, split, mute, volume
class RangeBody(BaseModel):
    start: float
    end: float
    on: bool = True
    db: float = 0.0


class TimeBody(BaseModel):
    t: float


class RestoreBody(BaseModel):
    index: int
    side: str = "all"
    amount: float = 0.0


_AUDIO_LOCKS: dict[str, "threading.Lock"] = {}


def _audio_lock(pid: str):
    import threading

    return _AUDIO_LOCKS.setdefault(pid, threading.Lock())


def _audio_apply(p: Project, pid: str, rerun: bool = True) -> dict:
    from .. import audio_edit as AE

    if rerun:
        old_cuts, old_plan = p.cuts(), p.scenes()
        pl = Pipeline(p)
        pl.stage_cuts()
        if old_plan and old_cuts:
            from ..editor_timing import retime_manual
            remapped, clock = retime_manual(old_plan, old_cuts, p.cuts(), read_json(p.dir / "editor_clock.json", {}) or {})
            p.save_scenes(remapped)
            write_json(p.dir / "editor_clock.json", clock)
        pl.stage_aroll()
        pl.stage_words()
        pl.stage_plan()
        compose_all(p)
    changed(pid)
    return AE.view(p)


def _audio_edit(pid: str, fn, rerun: bool = True) -> dict:
    from .. import audio_edit as AE

    p = proj(pid)
    if not p.cuts_path.exists():
        raise HTTPException(409, "process the audio first")
    with _audio_lock(pid):                         # one voice edit at a time per project (each re-cuts the audio and rewrites the plan)
        try:
            new = fn(AE.load(p), p.cuts())
        except ValueError as e:
            raise HTTPException(422, {"errors": [str(e)]})
        AE.save(p, new)
        return _audio_apply(p, pid, rerun)


@app.get("/api/projects/{pid}/audio")
def get_audio(pid: str) -> dict:
    from .. import audio_edit as AE

    p = proj(pid)
    if not p.cuts_path.exists():
        raise HTTPException(409, "process the audio first")
    return AE.view(p)


@app.post("/api/projects/{pid}/audio/extract")
def extract_voice_clip(pid: str, body: RangeBody) -> dict:
    """Make the selected source audio available as an independently editable sound clip."""
    import soundfile as soundfile
    from ..director.media import add_sound
    from ..audio_edit import src_ranges
    import numpy as np
    p = proj(pid)
    if not 0 <= body.start < body.end <= p.cuts().output_duration:
        raise HTTPException(422, "Choose a range inside the video")
    # Read original audio, so a previously muted selection can still be extracted.
    with soundfile.SoundFile(p.master) as src:
        parts = []
        for start, end in src_ranges(p.cuts(), body.start, body.end):
            src.seek(round(start * src.samplerate))
            parts.append(src.read(round((end-start)*src.samplerate), dtype="float32", always_2d=True))
        rate = src.samplerate
    with tempfile.TemporaryDirectory() as temp:
        wav = Path(temp) / "selected-audio.wav"
        soundfile.write(wav, np.concatenate(parts), rate, subtype="PCM_16")
        item = add_sound(p, wav, caption=f"Audio {body.start:.3f}–{body.end:.3f}s", source="timeline")
    changed(pid)
    return _media_view(p, item)


@app.post("/api/projects/{pid}/audio/cut")
def audio_cut(pid: str, body: RangeBody) -> dict:
    """Ripple delete: remove what plays between two output times (the rest closes up; words and scenes follow)."""
    from .. import audio_edit as AE

    return _audio_edit(pid, lambda e, c: AE.add_cut(e, c, body.start, body.end))


@app.post("/api/projects/{pid}/audio/mute")
def audio_mute(pid: str, body: RangeBody) -> dict:
    from .. import audio_edit as AE

    return _audio_edit(pid, lambda e, c: AE.set_mute(e, c, body.start, body.end, body.on))


@app.post("/api/projects/{pid}/audio/gain")
def audio_gain(pid: str, body: RangeBody) -> dict:
    from .. import audio_edit as AE

    return _audio_edit(pid, lambda e, c: AE.set_gain(e, c, body.start, body.end, body.db))


@app.post("/api/projects/{pid}/audio/split")
def audio_split(pid: str, body: TimeBody) -> dict:
    from .. import audio_edit as AE

    return _audio_edit(pid, lambda e, c: AE.add_split(e, c, body.t), rerun=False)


@app.post("/api/projects/{pid}/audio/restore")
def audio_restore(pid: str, body: RestoreBody) -> dict:
    """Bring back a cut, or part of it (dragging a trimmed edge outward)."""
    from .. import audio_edit as AE

    return _audio_edit(pid, lambda e, c: AE.restore(e, body.index, body.side, body.amount))


@app.post("/api/projects/{pid}/audio/undo")
def audio_undo(pid: str) -> dict:
    from .. import audio_edit as AE

    p = proj(pid)
    with _audio_lock(pid):
        if not AE.undo(p):
            raise HTTPException(409, "nothing to undo")
        return _audio_apply(p, pid)


@app.post("/api/projects/{pid}/audio/redo")
def audio_redo(pid: str) -> dict:
    from .. import audio_edit as AE

    p = proj(pid)
    with _audio_lock(pid):
        if not AE.redo(p):
            raise HTTPException(409, "nothing to redo")
        return _audio_apply(p, pid)


class GlossaryBody(BaseModel):
    term: str
    replacement: str


@app.post("/api/projects/{pid}/glossary")
def add_glossary(pid: str, body: GlossaryBody) -> dict:
    p = proj(pid)
    g = read_json(p.glossary_path, {}) or {}
    g[body.term.strip()] = body.replacement.strip()
    write_json(p.glossary_path, g)
    Pipeline(p).stage_words()
    Pipeline(p).stage_plan()
    compose_all(p)
    changed(pid)
    return {"glossary": p.glossary()}


# ------------------------------------------------------------------ scenes
@app.get("/api/projects/{pid}/scenes")
def get_scenes(pid: str) -> dict:
    p = proj(pid)
    sf = p.scenes()
    if not sf:
        return {"scenes": None}
    cuts = p.cuts()
    dur = cuts.output_duration if cuts else max((w.end for w in p.transcript().kept()), default=1.0) + 0.5
    timing = {"scenes": scene_timing(sf, p.beats(), dur), "duration": round(dur, 3)}
    return {"plan": sf.model_dump(exclude_none=True), "timing": timing, "elements": _element_times(p)}


def _element_times(p):
    from ..editor_timing import resolved_elements
    tag = FORMATS[p.meta().aspect]["tag"]
    return resolved_elements(read_json(p.comp_dir / tag / "data.json", {}) or {})


@app.post("/api/projects/{pid}/scenes/{sid}/edge")
def free_scene_edge(pid: str, sid: str, body: TimeBody) -> dict:
    from ..editor_timing import move_edge
    p = proj(pid)
    sf = edit_scenes(p, lambda s: move_edge(s, p.beats(), p.cuts().output_duration, sid, body.t))
    return {"plan": sf.model_dump(exclude_none=True)}


@app.post("/api/projects/{pid}/scenes/{sid}/split-at")
def free_scene_split(pid: str, sid: str, body: TimeBody) -> dict:
    from ..editor_timing import split_at
    p = proj(pid)
    sf = edit_scenes(p, lambda s: split_at(s, p.beats(), p.cuts().output_duration, sid, body.t, _element_times(p)))
    return {"plan": sf.model_dump(exclude_none=True)}


@app.patch("/api/projects/{pid}/scenes/{sid}/elements/{index}")
def edit_element(pid: str, sid: str, index: int, body: dict[str, Any]) -> dict:
    from ..editor_timing import edit_element as apply_element
    p = proj(pid)
    sf = edit_scenes(p, lambda sf: apply_element(sf, sid, index, body, _element_times(p)))
    return {"plan": sf.model_dump(exclude_none=True)}


@app.put("/api/projects/{pid}/scenes")
def put_scenes(pid: str, body: dict[str, Any]) -> dict:
    p = proj(pid)
    try:
        sf = ScenesFile.model_validate(body)
    except ValidationError as e:
        raise HTTPException(422, {"errors": [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()][:12]})
    save_and_compose(p, sf)
    return {"ok": True}


@app.patch("/api/projects/{pid}/scenes/{sid}")
def patch_scene(pid: str, sid: str, body: dict[str, Any]) -> dict:
    p = proj(pid)
    sf = edit_scenes(p, lambda s: scene_ops.patch_scene(s, sid, body))
    return {"plan": sf.model_dump(exclude_none=True)}



class ActionPatch(BaseModel):
    patch: dict[str, Any] = {}
    delete: bool = False


@app.patch("/api/projects/{pid}/scenes/{sid}/actions/{index}")
def patch_action(pid: str, sid: str, index: int, body: ActionPatch) -> dict:
    """Re-time (drag to another word), change or delete one stick-figure action. Times are recomputed from the words."""
    p = proj(pid)
    tr, beats = p.transcript(), p.beats()
    sf = edit_scenes(p, lambda s: scene_ops.edit_action(s, tr, beats, sid, index, body.patch, body.delete))
    return {"plan": sf.model_dump(exclude_none=True)}


@app.post("/api/projects/{pid}/scenes/{sid}/actions")
def create_action(pid: str, sid: str, body: dict[str, Any]) -> dict:
    """Add a new stick-figure animation action to a scene."""
    p = proj(pid)
    tr, beats = p.transcript(), p.beats()
    sf = edit_scenes(p, lambda s: scene_ops.add_action(s, tr, beats, sid, body))
    return {"plan": sf.model_dump(exclude_none=True)}


@app.get("/api/cast-options")
def cast_options() -> dict:
    """Everything a character can be and wear, for the character editor."""
    from ..script import catalogue as C
    from ..script.animals import ANIMALS

    animals: dict[str, str] = {}
    for word, code in ANIMALS.items():
        if word.isascii():
            animals.setdefault(code, word)
    verbs = [{"verb": v, "about": desc, "seconds": secs, "required": list(req)} for v, (desc, secs, req) in C.VERBS.items()]
    return {"heads": C.HEADS, "accessories": C.ACCESSORIES, "heights": C.HEIGHTS, "hairs": C.HAIRS, "roles": C.ROLES,
            "toons": [{"id": k, "about": v} for k, v in C.TOON_CHARACTERS.items()],
            "animals": [{"code": code, "name": name} for code, name in animals.items()],
            "verbs": verbs}


@app.patch("/api/projects/{pid}/cast/{cid}")
def patch_cast(pid: str, cid: str, body: dict[str, Any]) -> dict:
    """Name, role, who plays it (stick figure, cartoon, animal) and look of a character, in every scene."""
    p = proj(pid)
    sf = edit_scenes(p, lambda s: scene_ops.edit_cast(s, cid, body))
    return {"plan": sf.model_dump(exclude_none=True)}


class SplitBody(BaseModel):
    at_beat: str


@app.post("/api/projects/{pid}/scenes/{sid}/split")
def split_scene(pid: str, sid: str, body: SplitBody) -> dict:
    p = proj(pid)
    sf = edit_scenes(p, lambda s: scene_ops.split_scene(s, p.beats(), sid, body.at_beat))
    return {"plan": sf.model_dump(exclude_none=True)}


@app.post("/api/projects/{pid}/scenes/{sid}/merge-next")
def merge_next(pid: str, sid: str) -> dict:
    p = proj(pid)
    sf = edit_scenes(p, lambda s: scene_ops.merge_with_next(s, p.beats(), sid))
    return {"plan": sf.model_dump(exclude_none=True)}


@app.delete("/api/projects/{pid}/scenes/{sid}")
def remove_scene(pid: str, sid: str) -> dict:
    p = proj(pid)
    sf = edit_scenes(p, lambda s: scene_ops.delete_scene(s, p.beats(), sid))
    return {"plan": sf.model_dump(exclude_none=True)}


@app.post("/api/projects/{pid}/scenes/{sid}/boundary")
def move_boundary(pid: str, sid: str, body: SplitBody) -> dict:
    p = proj(pid)
    sf = edit_scenes(p, lambda s: scene_ops.move_boundary(s, p.beats(), sid, body.at_beat))
    return {"plan": sf.model_dump(exclude_none=True)}


@app.get("/api/projects/{pid}/scenes/undo")
def can_undo_scenes(pid: str) -> dict:
    """Whether the plan as it was before its latest save can be brought back (every save, by the person, the director or an assistant
    over MCP, keeps that one copy). The AI panel offers it, so a change an assistant made can be undone from the app."""
    f = proj(pid).dir / "scenes.prev.json"
    if not f.exists():
        return {"available": False, "at": None}
    return {"available": True, "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(f.stat().st_mtime))}


@app.post("/api/projects/{pid}/scenes/undo")
def undo_scenes(pid: str) -> dict:
    p = proj(pid)
    prev = read_json(p.dir / "scenes.prev.json")
    if not prev:
        raise HTTPException(409, "nothing to undo")
    cur = p.scenes()
    sf = ScenesFile.model_validate(prev)
    p.save_scenes(sf)
    if cur:
        write_json(p.dir / "scenes.prev.json", cur.model_dump(exclude_none=True))  # a second undo = redo
    compose_all(p)
    changed(pid)
    return {"plan": sf.model_dump(exclude_none=True)}


@app.post("/api/projects/{pid}/replan-rules")
def replan_rules(pid: str) -> dict:
    from ..planner import plan_rules
    p = proj(pid)
    sf = plan_rules(p.transcript(), p.beats(), p.meta().theme, language=p.meta().language)
    save_and_compose(p, sf)
    return {"plan": sf.model_dump(exclude_none=True)}


@app.post("/api/projects/{pid}/replan")
def replan_auto(pid: str) -> dict:
    """Throw the plan away and design it again with the full automatic planner (local AI, then rules). The old plan stays undoable."""
    p = proj(pid)
    cur = p.scenes()
    if cur:
        write_json(p.dir / "scenes.prev.json", cur.model_dump(exclude_none=True))
        (p.dir / "scenes.json").unlink(missing_ok=True)
    return start_pipeline(p, "plan", True).public()


# ------------------------------------------------------------------ Claude requests (MCP bridge)
class ReqBody(BaseModel):
    kind: str = "full"
    scene_id: Optional[str] = None
    hint: str = ""
    alternatives: int = 1


@app.delete("/api/projects/{pid}/plan-notice")
def clear_plan_notice(pid: str) -> dict:
    (proj(pid).dir / "plan_notice.json").unlink(missing_ok=True)
    changed(pid)
    return {"ok": True}


@app.get("/api/projects/{pid}/requests")
def get_requests(pid: str) -> list[dict]:
    p = proj(pid)
    out = []
    for r in p.requests():
        d = r.model_dump()
        d["alternatives_available"] = len(planning.alternatives(p, r.id)) if r.status == "done" else 0
        out.append(d)
    return out


@app.post("/api/projects/{pid}/requests")
def make_request(pid: str, body: ReqBody) -> dict:
    p = proj(pid)
    if not p.beats().beats:
        raise HTTPException(409, "process the audio first")
    try:
        r = planning.create_request(p, body.kind, body.scene_id, body.hint, body.alternatives)
    except ValueError as e:
        raise HTTPException(422, str(e))
    changed(pid)
    return r.model_dump()


@app.delete("/api/projects/{pid}/requests/{rid}")
def delete_request(pid: str, rid: str) -> dict:
    p = proj(pid)
    if not re.fullmatch(r"[a-f0-9]{8}", rid):
        raise HTTPException(400)
    for suffix in (".json", ".alternatives.json"):
        (p.requests_dir / f"{rid}{suffix}").unlink(missing_ok=True)
    if not any(r.status == "queued" for r in p.requests()) and p.meta().status == "waiting_for_claude":
        p.update_meta(status="planned")
    changed(pid)
    return {"ok": True}


@app.get("/api/projects/{pid}/requests/{rid}/alternatives")
def get_alternatives(pid: str, rid: str) -> list[dict]:
    return planning.alternatives(proj(pid), rid)


class ApplyBody(BaseModel):
    index: int


@app.post("/api/projects/{pid}/requests/{rid}/apply")
def apply_alt(pid: str, rid: str, body: ApplyBody) -> dict:
    p = proj(pid)
    try:
        sf = planning.apply_alternative(p, rid, body.index)
    except ValueError as e:
        raise HTTPException(422, str(e))
    changed(pid)
    return {"plan": sf.model_dump(exclude_none=True)}


# ------------------------------------------------------------------ thumbnails
@app.post("/api/projects/{pid}/thumbnails")
def make_thumbs(pid: str, aspect: str = "9:16") -> dict:
    p = proj(pid)
    if aspect not in FORMATS:
        raise HTTPException(400)
    if not p.scenes():
        raise HTTPException(409, "no plan yet")
    j = jobs.submit("thumbs", pid, "Scene thumbnails", lambda cb: make_thumbnails(p, aspect), when_busy="reuse")
    return j.public()


@app.get("/api/projects/{pid}/thumbnails")
def get_thumbs(pid: str, aspect: str = "9:16") -> dict:
    p = proj(pid)
    m = read_json(thumbs_dir(p, aspect) / "manifest.json") or {"hash": None, "scenes": {}}
    tag = FORMATS[aspect]["tag"]
    return {"hash": m["hash"], "scenes": {k: f"/media/{pid}/thumbs/{tag}/{v}" for k, v in m["scenes"].items()}}


# ------------------------------------------------------------------ export
# ------------------------------------------------------------------ layers (extra tracks) and sounds
def _layers_view(p: Project) -> dict:
    from .. import layers as L

    cuts = p.cuts()
    duration = cuts.output_duration if cuts else 0.0
    return {"doc": L.load(p), "duration": duration, **L.history(p)}


class LayersBody(BaseModel):
    doc: dict[str, Any]


_LAYER_LOCKS: dict[str, "threading.Lock"] = {}


@app.get("/api/projects/{pid}/layers")
def get_layers(pid: str) -> dict:
    return _layers_view(proj(pid))


@app.put("/api/projects/{pid}/layers")
def put_layers(pid: str, body: LayersBody) -> dict:
    """Save the whole layers document (tracks and clips). Refused with every problem listed when it is not valid; one step of history is kept."""
    from .. import layers as L

    p = proj(pid)
    view = _layers_view(p)
    if not view["duration"]:
        raise HTTPException(409, "process the audio first")
    clean, errors = L.validate(body.doc, view["duration"], L.media_kinds(p))
    if errors:
        raise HTTPException(422, {"errors": errors[:12]})
    with _LAYER_LOCKS.setdefault(pid, threading.Lock()):
        L.save(p, clean)
    compose_all(p)
    changed(pid)
    return _layers_view(p)


@app.post("/api/projects/{pid}/layers/{what}")
def layers_history(pid: str, what: str) -> dict:
    from .. import layers as L

    if what not in ("undo", "redo"):
        raise HTTPException(404)
    p = proj(pid)
    with _LAYER_LOCKS.setdefault(pid, threading.Lock()):
        doc = L.step(p, what)
    if doc is None:
        raise HTTPException(409, f"nothing to {what}")
    compose_all(p)
    changed(pid)
    return _layers_view(p)


# ------------------------------------------------------------------ your own voices (cloning)
class OverdubBody(BaseModel):
    text: str
    voice: str
    start: float
    end: float
    mute: bool = True                     # silence the original words in that range
    engine: str = "clone"
    scene: Optional[str] = None


@app.post("/api/projects/{pid}/voice/overdub")
def overdub(pid: str, body: OverdubBody) -> dict:
    """Say `text` again in one of your saved voices and put it on a sound track at `start` (output time); the original range is muted. Undo with the layers' and the voice's undo."""
    from .. import audio_edit as AE
    from .. import layers as L
    from .. import voices as V
    from ..director import media as M
    from .. import tts

    p = proj(pid)
    text = body.text.strip()
    if body.engine == 'auto':
        body.engine, body.voice = tts.recommended_voice(p.meta().language)
    if not text or len(text) > 600:
        raise HTTPException(422, {"errors": ["write the words to say (up to 600 characters)"]})
    if not p.cuts_path.exists():
        raise HTTPException(409, "process the audio first")
    if body.engine not in {e["id"] for e in tts.ENGINES}:
        raise HTTPException(422, "Choose a supported voice engine")
    if body.engine == "clone" and not V.available():
        raise HTTPException(422, {"errors": ["voice cloning cannot run here (ONNX Runtime is missing)"]})
    try:
        if body.engine == "clone":
            V.ref_path(body.voice)
    except V.VoiceError as e:
        raise HTTPException(404, str(e))
    duration = p.cuts().output_duration
    if not (0 <= body.start < body.end <= duration + 0.01):
        raise HTTPException(422, {"errors": ["the range is outside the video"]})
    if body.scene:
        timing = next((s for s in get_scenes(pid)["timing"]["scenes"] if s["id"] == body.scene), None)
        if timing is None:
            raise HTTPException(404, "Scene not found")
        if abs(body.start-timing["start"]) > .001 or abs(body.end-timing["end"]) > .001:
            raise HTTPException(409, "The scene timing changed. Reload it before replacing its voice.")

    def work(cb):
        tmp = Path(tempfile.mkdtemp())
        try:
            cb("overdub", 0.05, "Speaking in your voice")
            from .. import voice_edit
            baseline = voice_edit.snapshot(p)
            scene_baseline = p.scenes().model_dump() if body.scene else None
            wav = tmp / "say.wav"
            try:
                if body.engine == "clone":
                    V.say(text, body.voice, wav)
                else:
                    tts.synthesize(text, wav, engine=body.engine, voice=body.voice, direction=False, language=p.meta().language)
            except V.VoiceError as e:
                raise RuntimeError(str(e))
            # Keep every spoken word inside the requested scene instead of truncating
            # the new recording or silently sliding it into the following scene.
            import soundfile as sf_audio
            from ..util import find_tool, run
            seconds = sf_audio.info(str(wav)).duration
            slot = body.end-body.start
            if seconds > slot:
                speed = seconds/slot
                if speed > 1.5:
                    raise RuntimeError("This line is too long for the selected scene. Shorten it or extend the scene before regenerating.")
                fitted = tmp / "fitted.wav"
                run([find_tool("ffmpeg"), "-y", "-i", str(wav), "-af", f"atempo={speed:.8f}", str(fitted)])
                wav = fitted
            item = M.add_sound(p, wav, caption=f"Voice: {text[:40]}", source=f"tts:{body.engine}")
            cb("overdub", 0.8, "Placing it")
            with _audio_lock(pid), _LAYER_LOCKS.setdefault(pid, threading.Lock()):
                if voice_edit.snapshot(p) != baseline:
                    raise RuntimeError("The voice, captions or tracks changed during generation. Your edits were kept; regenerate again when ready.")
                if body.scene and p.scenes().model_dump() != scene_baseline:
                    raise RuntimeError("Scene timing or contents changed during generation. Your edits were kept; regenerate again when ready.")
                doc = L.load(p)
                track_name = f"Voice · {body.scene}" if body.scene else "My voice"
                track = next((t for t in doc["tracks"] if t["kind"] == "audio" and t["name"] == track_name and not t.get("locked")), None)
                if track is None:
                    import uuid
                    track = {"id": "voice"+uuid.uuid4().hex[:8], "name": track_name, "kind": "audio", "hidden": False, "muted": False, "locked": False}
                    doc["tracks"].append(track)
                at = body.start
                overlaps = [c for c in doc["clips"] if c["track"] == track["id"] and at < c["start"]+c["dur"]-.001 and at+item.duration > c["start"]+.001]
                if overlaps:
                    if body.scene:
                        doc["clips"] = [c for c in doc["clips"] if c not in overlaps]
                    else:
                        import uuid
                        track = {**track, "id":"voice"+uuid.uuid4().hex[:8]}
                        doc["tracks"].append(track)
                import uuid

                doc["clips"].append({"id": "c" + uuid.uuid4().hex[:8], "track": track["id"], "type": "audio", "start": round(at, 3), "dur": round(min(item.duration, slot, duration - at), 3),
                                     "media": item.id, "in": 0.0, "volume": 1.0, "fade_in": 0.03, "fade_out": 0.05})
                clean, errors = L.validate(doc, duration, L.media_kinds(p))
                if errors:
                    raise RuntimeError("; ".join(errors[:3]))
                voice_edit.apply(p, clean, body.start, body.end, text, body.scene, body.mute)
            changed(pid)
            log = read_json(p.dir / "voice_regenerations.json", {"items": []})
            log["items"].append({"scene":body.scene,"media":item.id,"engine":body.engine,"voice":body.voice,"prompt":text,"made_at":now_iso()})
            write_json(p.dir / "voice_regenerations.json", log)
            return {"sound": item.id, "seconds": item.duration, "start": at}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return jobs.submit("overdub", pid, "Say again in my voice", work, when_busy="refuse").public()


# ------------------------------------------------------------------ context: one shared reading of the video
def _context_view(p: Project) -> dict:
    from .. import context as CX
    from ..ai import providers as AIP

    ctx = CX.load(p)
    return {"context": ctx.model_dump() if ctx else None, "stale": CX.is_stale(p, ctx), "ai_available": AIP.ai_enabled(),
            "overrides": read_json(CX.overrides_path(p), {}) or {}}


@app.get("/api/projects/{pid}/context")
def get_context(pid: str) -> dict:
    """What the video is about: topic, named things with their type, one line per sentence, sections, facts (vt/context.py)."""
    return _context_view(proj(pid))


@app.post("/api/projects/{pid}/context")
def rebuild_context(pid: str, ai: bool = True) -> dict:
    """Read the video again (a job: the AI pass takes about half a minute). The owner's corrections are kept."""
    from .. import context as CX
    from ..ai import providers as AIP

    p = proj(pid)
    if not p.transcript_path.exists():
        raise HTTPException(409, "process the audio first")

    def work(cb):
        cb("context", 0.05, "Reading the video")
        ctx = CX.build(p.transcript(), p.beats(), p.meta().language, use_ai=ai and AIP.ai_enabled(), overrides=read_json(CX.overrides_path(p), None))
        ctx.hash = CX.current_hash(p)
        CX.save(p, ctx)
        changed(pid)
        return {"source": ctx.source, "entities": len(ctx.entities)}
    return jobs.submit("context", pid, "Understand the video", work, when_busy="reuse").public()


class EntityFix(BaseModel):
    name: str
    type: Optional[str] = None
    remove: bool = False


class TopicFix(BaseModel):
    topic: str


@app.put("/api/projects/{pid}/context/entity")
def fix_entity(pid: str, body: EntityFix) -> dict:
    """Correct a named thing ('Amazon here is the river'): the correction is kept across rebuilds."""
    from .. import context as CX

    p = proj(pid)
    ctx = CX.load(p)
    if not ctx:
        raise HTTPException(409, "the video has not been read yet")
    if not body.remove and body.type not in CX.ENTITY_TYPES:
        raise HTTPException(422, {"errors": [f"type must be one of {CX.ENTITY_TYPES}"]})
    if not ctx.entity(body.name):
        raise HTTPException(404, "no such named thing")
    ov = read_json(CX.overrides_path(p), {}) or {}
    ov.setdefault("entities", {})[CX._key(body.name)] = {"remove": True} if body.remove else {"type": body.type}
    write_json(CX.overrides_path(p), ov)
    ctx = CX.apply_overrides(ctx, {"entities": {body.name: ov["entities"][CX._key(body.name)]}})
    ctx.hash = CX.current_hash(p)
    CX.save(p, ctx)
    changed(pid)
    return _context_view(p)


@app.put("/api/projects/{pid}/context/topic")
def fix_topic(pid: str, body: TopicFix) -> dict:
    from .. import context as CX

    p = proj(pid)
    ctx = CX.load(p)
    if not ctx:
        raise HTTPException(409, "the video has not been read yet")
    text = body.topic.strip()[:80]
    if not text:
        raise HTTPException(422, {"errors": ["write what the video is about"]})
    ov = read_json(CX.overrides_path(p), {}) or {}
    ov["topic"] = text
    write_json(CX.overrides_path(p), ov)
    ctx.topic, ctx.hash = text, CX.current_hash(p)
    CX.save(p, ctx)
    changed(pid)
    return _context_view(p)


@app.get("/api/my-voices")
def get_voices() -> dict:
    from .. import voices as V

    return {"voices": V.list_voices(), "available": V.available()}


@app.post("/api/my-voices")
async def add_voice(file: UploadFile = File(...), name: str = Form(""), consent: str = Form("false")) -> dict:
    """Keep a few seconds of a voice for cloning. `consent` must be true: it is the speaker's own voice, or they allowed it."""
    from .. import voices as V

    suffix = Path(file.filename or "v.wav").suffix.lower() or ".wav"
    tmp = Path(tempfile.mkdtemp()) / f"voice{suffix}"
    with tmp.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        return await run_in_threadpool(V.add_voice, tmp, name, consent.strip().lower() in ("1", "true", "yes", "on"))
    except V.VoiceError as e:
        raise HTTPException(422, {"errors": [str(e)]})
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)


@app.delete("/api/my-voices/{vid}")
def delete_voice(vid: str) -> dict:
    from .. import voices as V

    if not V.remove_voice(vid):
        raise HTTPException(404, "no such voice")
    return {"ok": True}


@app.get("/api/my-voices/{vid}/sample")
def voice_sample(vid: str):
    from .. import voices as V

    try:
        return FileResponse(V.ref_path(vid), media_type="audio/wav")
    except V.VoiceError:
        raise HTTPException(404, "no such voice")


@app.get("/api/projects/{pid}/sound-events")
def get_sound_events(pid: str) -> dict:
    """Laughter, applause, music, animals ... found in the voice track: [{concept, label, emoji, start, end, score}] in output time."""
    from .. import sounds as SN

    p = proj(pid)
    doc = SN.load(p) or {"events": [], "analyzed": False}
    return {"events": doc.get("events", []), "analyzed": "hash" in doc, "available": SN.available(), "error": doc.get("error"), "duration": doc.get("duration", 0)}


@app.post("/api/projects/{pid}/sound-events")
def analyze_sound_events(pid: str, force: bool = False) -> dict:
    """Listen to the voice track now (a job). The plan is not changed: use Auto-design afterwards to get pictures for the sounds."""
    from .. import sounds as SN

    p = proj(pid)
    if not p.cut_audio.exists() and not p.master.exists():
        raise HTTPException(409, "process the audio first")
    if not SN.available():
        raise HTTPException(422, {"errors": ["the sound listener needs torch and transformers (pip install torch transformers)"]})

    def work(cb):
        doc = SN.analyze_project(p, lambda f: cb("sounds", f, "listening"), force=force)
        changed(pid)
        return {"events": len(doc["events"])}
    return jobs.submit("sounds", pid, "Listen for sounds", work, when_busy="reuse").public()


@app.get("/api/projects/{pid}/sounds")
def list_sounds(pid: str) -> list[dict]:
    p = proj(pid)
    return [_media_view(p, m) for m in p.meta().sounds]


@app.post("/api/projects/{pid}/sounds")
async def upload_sound(pid: str, file: UploadFile = File(...), caption: str = Form("")) -> dict:
    from ..director import media as M

    p = proj(pid)
    suffix = Path(file.filename or "x.mp3").suffix.lower()
    if suffix not in M.AUDIO_EXT:
        raise HTTPException(400, f"unsupported audio type '{suffix}'. Use {', '.join(sorted(M.AUDIO_EXT))}.")
    tmp = Path(tempfile.mkdtemp()) / f"{re.sub(r'[^A-Za-z0-9._-]', '_', Path(file.filename or 'sound').stem)}{suffix}"
    with tmp.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        item = await run_in_threadpool(M.add_sound, p, tmp, caption=caption.strip()[:80])
    except M.MediaError as e:
        raise HTTPException(422, str(e))
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
    changed(p.id)
    return _media_view(p, item)


@app.delete("/api/projects/{pid}/sounds/{mid}")
def delete_sound(pid: str, mid: str) -> dict:
    from .. import layers as L
    from ..director import media as M

    p = proj(pid)
    if any(c.get("media") == mid for c in L.load(p)["clips"]):
        raise HTTPException(409, "this sound is used in the layers: remove those clips first")
    if not M.remove_sound(p, mid):
        raise HTTPException(404, "no such sound")
    changed(pid)
    return {"ok": True}


class ExportBody(BaseModel):
    aspects: list[str] = ["9:16"]
    quality: str = "looks"
    gpu: bool = True
    music: Optional[str] = "project"
    music_volume: Optional[float] = None
    duck: Optional[bool] = None
    duck_amount: Optional[float] = None
    duck_release: Optional[float] = None
    target_lufs: Optional[float] = None
    music_fade_in: Optional[float] = None
    music_fade_out: Optional[float] = None
    sfx: Optional[bool] = None
    sfx_level: Optional[str] = None
    fps: int = 30
    short_side: Optional[int] = None  # 720 -> downscale to 720p
    captions: bool = True
    clean_voice: bool = False             # noise reduction, presence and level evening on the voice


@app.post("/api/projects/{pid}/export")
def start_export(pid: str, body: ExportBody) -> dict:
    p = proj(pid)
    if not p.scenes():
        raise HTTPException(409, "no plan yet")
    if body.quality not in ("draft", "looks", "delivery"):
        raise HTTPException(400, "quality must be draft, looks or delivery")
    for a in body.aspects:
        if a not in FORMATS:
            raise HTTPException(400, f"bad aspect {a}")
    if body.sfx_level is not None and body.sfx_level not in ("off", "subtle", "normal", "rich"):
        raise HTTPException(400, "sfx_level must be off, subtle, normal or rich")
    if any(v is not None for v in (body.music_volume, body.duck, body.duck_amount, body.duck_release, body.target_lufs, body.music_fade_in, body.music_fade_out, body.sfx, body.sfx_level)):
        m = p.meta()
        if body.duck is not None:
            m.options.duck = body.duck
        if body.target_lufs is not None:
            m.options.target_lufs = max(-23.0, min(-9.0, body.target_lufs))
        if body.music_fade_in is not None:
            m.options.music_fade_in = max(0.0, min(6.0, body.music_fade_in))
        if body.music_fade_out is not None:
            m.options.music_fade_out = max(0.0, min(8.0, body.music_fade_out))
        if body.duck_amount is not None:
            m.options.duck_amount = max(0.0, min(1.0, body.duck_amount))
        if body.duck_release is not None:
            m.options.duck_release = max(0.05, min(2.0, body.duck_release))
        if body.music_volume is not None:
            m.options.music_volume = max(0.0, min(1.0, body.music_volume))
        if body.sfx is not None:
            m.options.sfx = body.sfx
        if body.sfx_level is not None:
            m.options.sfx_level = body.sfx_level  # type: ignore[assignment]
            m.options.sfx = body.sfx_level != "off"
        p.save_meta(m)

    def work(cb):
        results = []
        n = len(body.aspects)
        for i, a in enumerate(body.aspects):
            def sub(stage, frac, msg="", i=i):
                base = {"compose": 0.0, "render": 0.02, "mux": 0.95}.get(stage, 0.0)
                span = {"compose": 0.02, "render": 0.93, "mux": 0.05}.get(stage, 0.0)
                cb(stage, (i + base + span * frac) / n, f"{a} {msg}")
            music = None if body.music == "none" else ("__project__" if body.music in (None, "project") else body.music)
            r = export(p, a, quality=body.quality, gpu=body.gpu, music=music, fps=body.fps if body.fps in (24, 30, 60) else 30,
                       short_side=body.short_side if body.short_side in (480, 720, 1080) else None,
                       captions=body.captions, clean_voice=body.clean_voice, progress=sub)
            r["aspect"] = a
            r["url"] = f"/media/{pid}/exports/{Path(r['video']).name}"
            results.append(r)
        changed(pid)
        return results
    return jobs.submit("export", pid, f"Export {p.meta().title}", work, when_busy="refuse").public()



@app.post("/api/projects/{pid}/publish")
def make_publish_kit(pid: str, cover: bool = True) -> dict:
    """Title, description, hashtags and a cover image for social uploads. Runs as a job."""
    from ..ai import publish

    p = proj(pid)
    if not p.scenes():
        raise HTTPException(409, "Plan the video first.")

    def work(cb):
        kit = publish.build_kit(p, lambda s, f, m: cb("publish", f, m), cover=cover)
        changed(pid)
        return kit
    return jobs.submit("publish", pid, "Write the publishing text", work, when_busy="reuse").public()


@app.get("/api/projects/{pid}/publish")
def get_publish_kit(pid: str) -> dict:
    p = proj(pid)
    kit = read_json(p.dir / "publish.json", None)
    if kit and kit.get("cover") and (p.dir / "exports" / kit["cover"]).exists():
        kit["cover_url"] = f"/media/{pid}/exports/{kit['cover']}?v={int((p.dir / 'exports' / kit['cover']).stat().st_mtime)}"
    return {"kit": kit}


@app.get("/api/projects/{pid}/exports")
def list_exports(pid: str) -> list[dict]:
    p = proj(pid)
    out = []
    if p.exports_dir.exists():
        for f in sorted(p.exports_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.name.startswith('.'):continue
            out.append({"name": f.name, "size": f.stat().st_size, "url": f"/media/{pid}/exports/{f.name}",
                        "srt": f"/media/{pid}/exports/{f.stem}.srt" if f.with_suffix(".srt").exists() else None,
                        "credits": f.with_suffix(".credits.txt").read_text("utf-8") if f.with_suffix(".credits.txt").exists() else "",
                        "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime)), "path": str(f),
                        "retention": _retention_summary(f), "judges": _judges_summary(f),
                        "acceleration": read_json(f.with_suffix('.acceleration.json'),None),
                        "acceleration_url": f"/media/{pid}/exports/{f.stem}.acceleration.json" if f.with_suffix('.acceleration.json').exists() else None})
    return out


def _judges_summary(f: Path):
    from .review_routes import judges_summary

    return judges_summary(f)


def _retention_summary(f: Path):
    from .. import retention as RT

    card = RT.load(f.with_suffix(".retention.json"))
    return {"risk": card["risk"], "score": card["score"], "verdict": RT.verdict(card), "worst": card["worst"], "hook_s": card["hook_s"], "longest_gap_s": card["longest_gap_s"],
            "empty_longest_s": card["empty_longest_s"], "targets": card["targets"], "note": card["note"]} if card else None


@app.post("/api/projects/{pid}/retention")
def check_retention(pid: str, name: Optional[str] = None) -> dict:
    """Score a finished export (the newest, or `name`) for retention: hook time, change gaps, empty stretches, dead air, reading speed. Takes a few seconds."""
    from .. import retention as RT

    p = proj(pid)
    files = sorted(p.exports_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True) if p.exports_dir.exists() else []
    f = next((x for x in files if name is None or x.name == name), None)
    if f is None:
        raise HTTPException(409, "export the video first")
    aspect = next((a for a, v in FORMATS.items() if f"-{v['tag']}-" in f.name), p.meta().aspect)
    comp = read_json(p.comp_dir / FORMATS[aspect]["tag"] / "data.json")
    card = RT.scorecard(f, aspect, comp, p.cut_audio if p.cut_audio.exists() else None)
    RT.save(f.with_suffix(".retention.json"), card)
    return {**card, "verdict": RT.verdict(card), "file": f.name}


@app.post("/api/projects/{pid}/open-folder")
def open_folder(pid: str, request: Request) -> dict:
    """Open the exports folder, but only on the computer the person is sitting at. A request from another computer would pop a window open on this
    server's screen: it is answered with the folder's path instead (`opened` False) and the app says where the files are."""
    p = proj(pid)
    p.exports_dir.mkdir(parents=True, exist_ok=True)
    here = (request.client.host if request.client else "") in ("127.0.0.1", "::1", "localhost")
    if here:
        if sys.platform == "win32":
            os.startfile(str(p.exports_dir))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{p.exports_dir}"')
        else:
            os.system(f'xdg-open "{p.exports_dir}"')
    return {"path": str(p.exports_dir), "opened": here}


# ------------------------------------------------------------------ themes
@app.get("/api/themes")
def api_themes() -> list[dict]:
    return [t.model_dump(exclude_none=True) for t in list_themes()]


@app.get("/api/styles")
def api_styles(use: str = "", category: str = "") -> list[dict]:
    """The film styles (vt/styles.py): each sets the project theme to `theme`; the poster-like preview is the theme's own colours."""
    from .. import styles

    return styles.listing(category, use)


@app.get("/api/styles/{slug}")
def api_style(slug: str) -> dict:
    from .. import styles

    s = styles.get(slug)
    if s is None:
        raise HTTPException(404, "no such style")
    return s


@app.get("/api/projects/{pid}/craft")
def api_craft(pid: str) -> dict:
    """The craft rules this project's plan breaks, with times and fixes (vt/craft.py), for the Review page's checklist."""
    from .. import craft

    return craft.check(proj(pid))


@app.get("/api/design")
def design_catalogue() -> dict:
    from .. import designer

    return designer.catalogue()


class DesignBody(BaseModel):
    style: str
    palette: str
    name: Optional[str] = None
    overrides: Optional[dict[str, Any]] = None


@app.post("/api/design/build")
def design_build(body: DesignBody) -> dict:
    from .. import designer

    try:
        return designer.build_theme(body.style, body.palette, body.name, body.overrides).model_dump(exclude_none=True)
    except (ValueError, ValidationError) as e:
        raise HTTPException(400, str(e))


@app.get("/api/design/surprise")
def design_surprise(seed: Optional[int] = None, dark: Optional[bool] = None) -> dict:
    from .. import designer

    return designer.surprise(seed, dark).model_dump(exclude_none=True)


@app.get("/api/themes/fonts")
def theme_fonts() -> list[str]:
    css = (paths.FONTS / "fonts.css").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"font-family:\s*'([^']+)'", css)))


@app.put("/api/themes/{name}")
def save_theme(name: str, body: dict[str, Any]) -> dict:
    if not THEME_RE.match(name):
        raise HTTPException(400, "theme names use lowercase letters, digits and dashes")
    body["name"] = name
    try:
        t = Theme.model_validate(body)
    except ValidationError as e:
        raise HTTPException(422, {"errors": [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()][:12]})
    write_json(paths.THEMES / name / "theme.json", t.model_dump(exclude_none=True))
    for p in Project.list_all():  # re-compose projects that use this theme
        sf = p.scenes()
        if sf and sf.theme == name:
            compose_all(p)
    return t.model_dump(exclude_none=True)


class DupBody(BaseModel):
    new_name: str
    label: str = ""


@app.post("/api/themes/{name}/duplicate")
def duplicate_theme(name: str, body: DupBody) -> dict:
    if not THEME_RE.match(body.new_name):
        raise HTTPException(400, "theme names use lowercase letters, digits and dashes")
    if (paths.THEMES / body.new_name).exists():
        raise HTTPException(409, "a theme with that name exists")
    try:
        t = load_theme(name)
    except FileNotFoundError:
        raise HTTPException(404)
    t = t.model_copy(update={"name": body.new_name, "label": body.label or body.new_name})
    write_json(paths.THEMES / body.new_name / "theme.json", t.model_dump(exclude_none=True))
    return t.model_dump(exclude_none=True)


BUILTIN_THEMES = {"paper", "dark-neon", "minimal"}


@app.delete("/api/themes/{name}")
def delete_theme(name: str) -> dict:
    if name in BUILTIN_THEMES:
        raise HTTPException(409, "built-in themes cannot be deleted; duplicate them instead")
    if any((p.scenes() and p.scenes().theme == name) for p in Project.list_all()):
        raise HTTPException(409, "a project uses this theme")
    shutil.rmtree(paths.THEMES / name, ignore_errors=True)
    return {"ok": True}


@app.get("/api/themes/{name}/export")
def export_theme(name: str):
    if not THEME_RE.match(name):
        raise HTTPException(400)
    src = paths.THEMES / name / "theme.json"
    if not src.exists():
        raise HTTPException(404)
    out = Path(tempfile.mkdtemp()) / f"{name}.vttheme"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(src, "theme.json")
    return FileResponse(out, filename=f"{name}.vttheme", media_type="application/zip")


@app.post("/api/themes/import")
async def import_theme(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    try:
        if raw[:2] == b"PK":
            import io
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                raw = z.read("theme.json")
        data = json.loads(raw.decode("utf-8"))
        t = Theme.model_validate(data)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"not a valid theme file: {str(e)[:200]}")
    name = t.name if THEME_RE.match(t.name) else "imported"
    base, n = name, 2
    while (paths.THEMES / name).exists():
        name = f"{base}-{n}"
        n += 1
    t = t.model_copy(update={"name": name})
    write_json(paths.THEMES / name / "theme.json", t.model_dump(exclude_none=True))
    return t.model_dump(exclude_none=True)


@app.get("/api/specimen")
def specimen(theme: str = "paper", aspect: str = "9:16") -> dict:
    if aspect not in FORMATS:
        raise HTTPException(400)
    try:
        t = load_theme(theme)
    except FileNotFoundError:
        raise HTTPException(404)
    write_specimen(t, aspect)
    return {"url": f"/media/.specimen/{FORMATS[aspect]['tag']}/index.html", "data": specimen_data(t, aspect)}


# ------------------------------------------------------------------ music + models
@app.get("/api/music")
def list_music() -> list[dict]:
    items = read_json(paths.MUSIC / "index.json", []) or []
    for m in items:
        m["url"] = f"/bundled/music/{m['file']}"
    user = paths.USER_MUSIC
    if user.exists():
        for f in sorted(user.iterdir()):
            if f.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg", ".flac"):
                items.append({"id": f"user/{f.name}", "title": f.stem, "mood": "yours", "bpm": None, "url": f"/bundled/music/user/{f.name}", "file": f"user/{f.name}"})
    return items


@app.post("/api/music")
async def upload_music(file: UploadFile = File(...)) -> dict:
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", file.filename or "track.mp3")
    if Path(name).suffix.lower() not in (".mp3", ".wav", ".m4a", ".ogg", ".flac"):
        raise HTTPException(400, "use mp3, wav, m4a, ogg or flac")
    dest = paths.USER_MUSIC
    dest.mkdir(parents=True, exist_ok=True)
    with (dest / name).open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"id": f"user/{name}"}


@app.get("/api/models")
def list_models() -> list[dict]:
    return asr_mod.list_models()


@app.post("/api/models/{key}/pull")
def pull_model(key: str) -> dict:
    if key not in asr_mod.MODEL_SPECS:
        raise HTTPException(404)
    return jobs.submit("model", None, f"Download model {key}", lambda cb: str(asr_mod.ensure_model(key, cb))).public()


@app.get("/api/gpu")
def get_gpu_info() -> dict:
    from .. import gpu
    return gpu.gpu_info()


# ------------------------------------------------------------------ static
@app.get("/media/{path:path}")
def media(path: str, request: Request):
    """Project files for the Studio (preview iframes, audio, thumbnails, exports). Resolved per request, traversal-safe."""
    root = paths.PROJECTS.resolve()
    f = (root / path).resolve()
    if root not in f.parents:
        raise HTTPException(404)
    import mimetypes
    import time as _time

    parts = path.split("/")
    if not f.exists() and len(parts) == 4 and parts[1] == "composition" and parts[3] == "index.html":
        p = Project(parts[0]) if ID_RE.match(parts[0]) and (root / parts[0]).is_dir() else None
        if p and p.scenes() and p.transcript_path.exists():          # planned but never composed (e.g. a project built by script): make the preview now
            try:
                compose_all(p)
            except Exception:                                        # the preview then just is not there; the error is shown by the page, not raised here
                pass
    for attempt in range(6):                       # a plan edit rewrites the preview files; for an instant the name can be missing or locked (Windows replace)
        try:
            size = f.stat().st_size                    # raises when the file is missing (a streamed response would only fail later)
            streamed = f.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg", ".mp4", ".webm", ".mov") or "range" in request.headers   # audio and video need Range requests (seeking)
            if not streamed and size < 4_000_000:       # small files are sent from memory, so a rewrite in between cannot make the length wrong
                data = f.read_bytes()
                return Response(data, media_type=mimetypes.guess_type(f.name)[0] or "application/octet-stream", headers={"Cache-Control": "no-cache"})
            return FileResponse(f, headers={"Cache-Control": "no-cache"})
        except FileNotFoundError:
            if attempt:                            # missing twice in a row: it really is not there (optional files are asked for often, so do not make the page wait)
                break
            _time.sleep(0.04)
        except PermissionError:
            _time.sleep(0.05 * (attempt + 1))
    raise HTTPException(404)


paths.USER_MUSIC.mkdir(parents=True, exist_ok=True)
app.mount("/bundled/music/user", StaticFiles(directory=str(paths.USER_MUSIC)), name="user-music")
app.mount("/bundled", StaticFiles(directory=str(paths.ASSETS)), name="bundled")

from .shorts_routes import router as shorts_router
app.include_router(shorts_router)
from .social_routes import router as social_router
app.include_router(social_router)
from .comfy_routes import router as comfy_router
app.include_router(comfy_router)
from .modules_routes import router as modules_router
app.include_router(modules_router)
from .log_routes import router as log_router
app.include_router(log_router)
from .engines_routes import router as engines_router
app.include_router(engines_router)
from .review_routes import router as review_router
app.include_router(review_router)
from .setup_routes import router as setup_router
app.include_router(setup_router)
from .hub_routes import router as hub_router
app.include_router(hub_router)
from .plan_routes import router as plan_router
app.include_router(plan_router)
from .script_review_routes import router as script_review_router
app.include_router(script_review_router)
from .story_routes import router as story_router
app.include_router(story_router)
from .shot_routes import router as shot_router  # code-native shots (PLAN-CODE-NATIVE-EDITOR C2)
app.include_router(shot_router)
from .reel_routes import router as reel_router
app.include_router(reel_router)
from .direction_routes import router as direction_router
app.include_router(direction_router)
from .reel_routes import hook_router
app.include_router(hook_router)
from .serve import router as serve_router  # /.well-known, the server's address and the engine contract on the Studio port
app.include_router(serve_router)
from .serve import install_mcp  # the MCP tools at /mcp for assistants on other computers
install_mcp(app)
from .uploads import router as uploads_router  # chunked uploads that survive a dropped connection
app.include_router(uploads_router)
from .system_routes import router as system_router  # live processor, memory and graphics-card numbers
app.include_router(system_router)

@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"], include_in_schema=False)
def unknown_api(rest: str):
    """Registered after every real route: an endpoint this server does not have is a 404 with a clear message, for every method
    (it used to fall into the page's GET-only catch-all and answer 405 Method Not Allowed)."""
    raise HTTPException(404, {"errors": [f"This Studio server has no '/api/{rest}'. If you just updated the app, restart the Studio (close it and run `vt studio` again)."]})


@app.get("/")
def server_home():
    """Server management only. The editor is independently installed on the client."""
    return FileResponse(Path(__file__).with_name('management.html'))


@app.get('/management.js')
def server_management_script():
    return FileResponse(Path(__file__).with_name('management.js'), media_type='text/javascript')


@app.get('/page-theme.js')
def server_page_theme_script():
    return FileResponse(Path(__file__).with_name('page-theme.js'), media_type='text/javascript')


@app.get('/gpu-choice.js')
def server_gpu_choice_script():
    return FileResponse(Path(__file__).with_name('gpu-choice.js'), media_type='text/javascript')


@app.get('/manage')
def server_engine_management():
    return FileResponse(Path(__file__).with_name('engine-management.html'), headers={'Content-Security-Policy': "frame-ancestors 'self' file: http://127.0.0.1:* http://localhost:*"})


@app.get('/manage.js')
def server_engine_management_script():
    return FileResponse(Path(__file__).with_name('engine-management.js'), media_type='text/javascript')
