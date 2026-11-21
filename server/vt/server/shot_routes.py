"""Code-native shots for the Studio and for agents (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD, C2): list, read, write the code, write the visual edits,
see the page the renderer will draw, and get one frame as a picture. The same functions back the MCP tools."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from .. import shots as SH
from .modules_routes import project_or_404

router = APIRouter(tags=["shots"])
MAX_HTML = 1_000_000


def _shot(pid: str, sid: str, *, must_exist: bool = True) -> Path:
    try:
        d = SH.shot_dir(project_or_404(pid), sid)
    except SH.ShotError as e:
        raise HTTPException(422, str(e))
    if must_exist and not (d / "index.html").exists():
        raise HTTPException(404, f"This video has no shot '{sid}'.")
    return d


@router.get("/api/projects/{pid}/shots")
def list_shots(pid: str) -> dict[str, Any]:
    return {"shots": SH.list_shots(project_or_404(pid))}


@router.get("/api/projects/{pid}/shots/{sid}")
def get_shot(pid: str, sid: str) -> dict[str, Any]:
    d = _shot(pid, sid)
    html = (d / "index.html").read_text(encoding="utf-8")
    try:
        return {**SH.info(d), "html": html, "ids": SH.ids_in(html), "overrides": SH.check_overrides(SH.read_json(d / "overrides.json", {}))}
    except SH.ShotError as e:
        raise HTTPException(422, str(e))


class ShotBody(BaseModel):
    html: str
    shot: Optional[dict] = None


@router.put("/api/projects/{pid}/shots/{sid}")
def put_shot(pid: str, sid: str, body: ShotBody) -> dict[str, Any]:
    """Create a shot or replace its code. The code is checked for a timed root before it replaces the old one; the visual edits are kept."""
    d = _shot(pid, sid, must_exist=False)
    if len(body.html) > MAX_HTML:
        raise HTTPException(413, f"A shot's page may be at most {MAX_HTML // 1000} kB; put pictures and clips in its assets.")
    d.mkdir(parents=True, exist_ok=True)
    trial = d / ".check"
    trial.mkdir(exist_ok=True)
    (trial / "index.html").write_text(body.html, encoding="utf-8")
    if body.shot is not None:
        (trial / "shot.json").write_text(json.dumps(body.shot, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        SH.info(trial)
    except SH.ShotError as e:
        raise HTTPException(422, str(e))
    for name in ("index.html", "shot.json"):
        if (trial / name).exists():
            (trial / name).replace(d / name)
    trial.rmdir()
    return get_shot(pid, sid)


class OverridesBody(BaseModel):
    overrides: dict


@router.put("/api/projects/{pid}/shots/{sid}/overrides")
def put_overrides(pid: str, sid: str, body: OverridesBody) -> dict[str, Any]:
    d = _shot(pid, sid)
    try:
        return {"overrides": SH.save_overrides(d, body.overrides)}
    except SH.ShotError as e:
        raise HTTPException(422, str(e))


SAFE_PATH = re.compile(r"^(index\.html|(runtime|fonts|assets)/[A-Za-z0-9._/-]{1,200})$")


@router.get("/api/projects/{pid}/shots/{sid}/page/{path:path}")
def page(pid: str, sid: str, path: str = "index.html", editor: bool = False):
    """The page the renderer draws (code + edits + runtime), for the viewer's sandboxed frame. index.html is built fresh each time.
    ?editor=1: the visual editor's page (no saved edits, the bridge added). The frame has no origin of its own (sandbox without same-origin),
    so its fonts, scripts and pictures are fetched cross-origin: they are sent with Access-Control-Allow-Origin."""
    d = _shot(pid, sid)
    path = path or "index.html"
    if not SAFE_PATH.match(path) or ".." in path.split("/"):
        raise HTTPException(404, "not part of the shot")
    out = d / "preview"
    if path == "index.html":
        try:
            SH.build(d, out, editor=editor, theme=SH.theme_vars(project_or_404(pid)))
        except SH.ShotError as e:
            raise HTTPException(422, str(e))
        return HTMLResponse((out / "index.html").read_text(encoding="utf-8"), headers={"Content-Security-Policy": SH.CSP, "Cache-Control": "no-store"})
    f = (out / path).resolve()
    if not f.is_file() or out.resolve() not in f.parents:
        raise HTTPException(404, "not part of the shot")
    return FileResponse(f, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-store"})


@router.get("/api/projects/{pid}/shots/{sid}/frame")
def frame(pid: str, sid: str, t: float = 0.0):
    """One frame at t seconds as a PNG (software drawing, the same pixels every time)."""
    d = _shot(pid, sid)
    try:
        dur = SH.info(d)["duration"]
        got = SH.frames(d, d / "frames", [min(max(0.0, t), max(0.0, dur - 0.001))], theme=SH.theme_vars(project_or_404(pid)))
    except SH.ShotError as e:
        raise HTTPException(422, str(e))
    if not got:
        raise HTTPException(500, "The renderer gave no frame.")
    return FileResponse(got[0], media_type="image/png", headers={"Cache-Control": "no-store"})
