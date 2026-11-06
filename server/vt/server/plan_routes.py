"""Studio API for the plan review (docs/plans/PLAN-DIRECTOR-MODULES.MD section 8.10): read the plan, change it one typed step at a time, preview a moment, approve or decline.

Every change goes through the module executor as a call by the person, so the director's log shows it and a replay reproduces it. Approving starts the making as a job; the plan's
moments then report their own status (waiting, making, ready, failed) and the page watches them.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import paths
from ..direction import plan_doc as PD
from ..util import read_json
from .modules_routes import project_or_404

router = APIRouter(prefix="/api/projects/{pid}/plan", tags=["plan"])


class EditBody(BaseModel):
    op: dict[str, Any] = Field(description="one typed operation, e.g. {op: set_medium, moment: s3, medium: card}")


class AskBody(BaseModel):
    text: str = Field(min_length=1, max_length=300)


def _call(project, module: str, values: dict[str, Any], why: str):
    from ..modules.defs import load
    from ..modules.executor import Executor

    load()
    # skip_prerequisites: the plan reads the project's own words and sentences; it must never start a recognition run behind the person's back if an artifact record is missing
    res = Executor(project.dir).call(module, values, caller="person", why=why, force=True, skip_prerequisites=True)
    if not res.ok:
        raise HTTPException(422, res.fix or res.summary)
    return res


def _view(project, plan: Optional[PD.PlanDoc]) -> dict[str, Any]:
    meta = project.meta()
    setting = str((read_json(paths.SETTINGS, {}) or {}).get("plan_review", "when_expensive"))
    return {"plan": plan.model_dump() if plan else None, "checks": PD.checks(plan) if plan else [], "project_status": meta.status, "title": meta.title,
            "review": {"setting": setting, "project": meta.options.plan_review, "wanted": bool(plan and PD.review_wanted(plan, setting, meta.options.plan_review))},
            "speech": {m.id: m.text for m in plan.moments} if plan else {}}


@router.get("")
def get_plan(pid: str) -> dict[str, Any]:
    p = project_or_404(pid)
    return _view(p, PD.load(p.dir))


@router.post("/make")
def make_plan(pid: str, pace: str = "balanced") -> dict[str, Any]:
    """Write a fresh draft plan (nothing is drawn). Used when the person opens a video that has none."""
    p = project_or_404(pid)
    if p.meta().options.look != "reel":
        raise HTTPException(422, "Only a reel has a plan to look at: its pictures are made one by one. Other videos are made at once.")
    _call(p, "plan.make", {"use_ai": True, "pace": pace}, "The person asked for the plan.")
    return _view(p, PD.load(p.dir))


@router.put("")
def put_plan(pid: str, body: PD.PlanDoc) -> dict[str, Any]:
    p = project_or_404(pid)
    cur = PD.load(p.dir)
    if cur is None:
        raise HTTPException(404, "There is no plan to replace.")
    if cur.state in ("running", "done"):
        raise HTTPException(409, "The video is already being made.")
    body.rev = cur.rev + 1
    PD.save(p.dir, body)
    return _view(p, body)


@router.post("/edit")
def edit_plan(pid: str, body: EditBody) -> dict[str, Any]:
    p = project_or_404(pid)
    res = _call(p, "plan.edit", {"operation": body.op}, f"The person changed the plan ({body.op.get('op')}).")
    out = _view(p, PD.load(p.dir))
    out["changes"] = (res.output or {}).get("changes", [])
    return out


@router.post("/ask")
def ask_director(pid: str, body: AskBody) -> dict[str, Any]:
    """'Make the opening faster': the director turns a sentence into plan operations. They are applied as the person's edits and listed, so each can be undone with the sheet's own controls."""
    p = project_or_404(pid)
    plan = PD.load(p.dir)
    if plan is None:
        raise HTTPException(404, "There is no plan yet.")
    from ..ai import talk

    with talk.for_project(p.dir):                                       # what it asks the AI is on the video's record
        ops, why = ops_for(plan, body.text, director_of(p))
    if not ops:
        return {**_view(p, plan), "changes": [], "said": why}
    changes: list[str] = []
    for op in ops:
        try:
            res = _call(p, "plan.edit", {"operation": op}, f"The person asked the director: “{body.text[:80]}”")
            changes += (res.output or {}).get("changes", [])
        except HTTPException as e:
            changes.append(str(e.detail))
    return {**_view(p, PD.load(p.dir)), "changes": changes, "said": why}


def director_of(p) -> Any:
    """The AI that directs this video (None: the one chosen in Settings), so the director the person talks to is the one that made the plan."""
    try:
        from ..pipeline import Pipeline

        pipeline = Pipeline(p)
        return pipeline._director_provider(pipeline.director())
    except Exception:                                                   # noqa: BLE001  never stops a request
        return None


def ops_for(plan: PD.PlanDoc, text: str, provider: Any = None) -> tuple[list[dict[str, Any]], str]:
    """A few plain requests the rules understand; with a language AI connected a model may also propose operations, but only from the same vocabulary (`PD.OPS`)."""
    t = text.casefold()
    if any(w in t for w in ("faster", "punchier", "quicker", "snappier", "more cuts", "more changes")):
        return [{"op": "set_pace", "value": "punchy"}], "A punchier pace: more changes, each shorter."
    if any(w in t for w in ("slower", "calmer", "calm down", "breathe", "fewer cuts", "fewer changes")):
        return [{"op": "set_pace", "value": "calm"}], "A calmer pace: fewer, longer pictures."
    if any(w in t for w in ("cheaper", "quicker to make", "less to make", "fewer pictures", "fewer clips")):
        n = max(1, round(len(PD.made_moments(plan)) * 0.6))
        return [{"op": "set_budget", "n": n}], f"Making {n} pictures instead of {len(PD.made_moments(plan))}; the rest keep the picture before them."
    for style, words in (("photo", ("photo", "realistic")), ("cartoon", ("cartoon",)), ("comic", ("comic",)), ("line-art", ("line art", "pencil", "sketch"))):
        if any(w in t for w in words):
            return [{"op": "set_style", "value": style}], f"Drawn as {style}."
    ai = _ai_ops(plan, text, provider)
    if ai:
        return ai, "The director's suggestion."
    return [], "I can change the pace (faster, calmer), how many pictures are made (fewer pictures) or the look (photo, cartoon, comic, pencil). For one moment, use its card."


def _ai_ops(plan: PD.PlanDoc, text: str, provider: Any = None) -> list[dict[str, Any]]:
    """Ask the language AI for operations from the allowed list. Anything it cannot do, or that is not in the vocabulary, is dropped: the answer is [] and the rules' message stands."""
    try:
        from ..ai import complete_json
        from ..ai.providers import ai_enabled

        if not (provider.available() if provider is not None else ai_enabled()):
            return []
        schema = {"type": "object", "properties": {"ops": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {"op": {"type": "string", "enum": list(PD.OPS)}}, "required": ["op"]}}},
                  "required": ["ops"]}
        brief = [{"id": m.id, "text": m.text[:90], "medium": m.medium} for m in plan.moments][:30]
        data = complete_json(f"The person says: “{text}”.\nThe plan's moments: {brief}\nAnswer with the operations that do it, each with the fields it needs "
                             f"(moment, medium, word, text, value, n). Use only these operations: {', '.join(PD.OPS)}. If nothing fits, answer an empty list.", schema,
                             system="You edit a video plan with typed operations. Never invent facts for a picture's text; use words from the moment.", retries=1, max_tokens=400, temperature=0.2,
                             provider=provider)
        return [o for o in data.get("ops", []) if isinstance(o, dict) and o.get("op") in PD.OPS]
    except Exception:                                                                   # noqa: BLE001
        return []


@router.post("/preview/{moment}")
def preview(pid: str, moment: str, still: bool = False) -> dict[str, Any]:
    p = project_or_404(pid)
    res = _call(p, "plan.preview_moment", {"moment": moment, "still": still}, "The person asked to see a moment.")
    out = _view(p, PD.load(p.dir))
    out["preview"] = res.output
    return out


@router.post("/approve")
def approve(pid: str) -> dict[str, Any]:
    """The Start button: approve the plan and make the video. Nothing expensive ran before this."""
    from .app import jobs, start_pipeline

    p = project_or_404(pid)
    if jobs.active_for(pid):
        raise HTTPException(409, "The video is already being made.")
    plan = PD.load(p.dir)
    if plan is None:
        raise HTTPException(404, "There is no plan yet.")
    _call(p, "plan.approve", {"by": "person"}, "The person pressed Start.")
    p.update_meta(status="processing")
    job = start_pipeline(p, "plan", True)
    out = _view(p, PD.load(p.dir))
    out["job"] = job.public() if hasattr(job, "public") else {"id": getattr(job, "id", "")}
    return out


@router.post("/decline")
def decline(pid: str) -> dict[str, Any]:
    p = project_or_404(pid)
    _call(p, "plan.decline", {}, "The person declined the plan.")
    return _view(p, PD.load(p.dir))


@router.get("/status")
def status(pid: str) -> dict[str, Any]:
    p = project_or_404(pid)
    plan = PD.load(p.dir)
    if plan is None:
        raise HTTPException(404, "There is no plan yet.")
    return {"state": plan.state, "estimate": plan.estimate.model_dump(),
            "moments": [{"id": m.id, "status": m.status, "medium": m.medium, "media": m.media, "problem": m.problem, "seconds_taken": m.seconds_taken} for m in plan.moments]}
