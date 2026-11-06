"""Cartoon 2 (the story engine) for the Studio: the catalog that builds the editor's forms, the shared cast, and the director's task/submit pair
(the same functions as the MCP tools get_story_task / submit_story)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from ..schema import StoryCharacter
from ..story import catalog as SC
from ..story import service
from .modules_routes import project_or_404

router = APIRouter(tags=["story"])


@router.get("/api/story/catalog")
def catalog() -> dict[str, Any]:
    return SC.listing()


class CastBody(BaseModel):
    cast: dict[str, dict]


@router.put("/api/projects/{pid}/story-cast")
def put_cast(pid: str, body: CastBody) -> dict[str, Any]:
    """Replace the cast: a look changed here changes that character in every scene."""
    p = project_or_404(pid)
    sf = p.scenes()
    if sf is None:
        raise HTTPException(409, "The video has no plan yet.")
    try:
        cast = {k: StoryCharacter.model_validate(v) for k, v in body.cast.items()}
    except ValidationError as e:
        raise HTTPException(422, str(e).split("\n", 1)[-1][:400])
    used = {getattr(i, "char", None) for sc in sf.scenes for el in sc.elements if el.type == "story" for i in el.items if i.type in ("person", "mini")}
    missing = sorted(c for c in used if c and c not in cast)
    if missing:
        raise HTTPException(409, f"Still used in the story: {', '.join(missing)}. Remove them from the scenes first.")
    sf.story_cast = cast
    p.save_scenes(sf)
    return {"cast": {k: v.model_dump(exclude_none=True) for k, v in cast.items()}}


@router.get("/api/projects/{pid}/story-task")
def task(pid: str) -> dict[str, Any]:
    return service.story_task(project_or_404(pid))


@router.post("/api/projects/{pid}/story")
def submit(pid: str, story: dict[str, Any]) -> dict[str, Any]:
    res = service.submit_story(project_or_404(pid), story, planner="manual")
    if not res.get("ok"):
        raise HTTPException(422, "; ".join(res.get("errors", [])[:6]))
    return res
