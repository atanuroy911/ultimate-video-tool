"""Studio API for the director's modules: list, describe, dry-run and call one on a project, with the same validation as MCP and the CLI."""
from __future__ import annotations

import re
import threading
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from ..modules.defs import load
from ..modules.envelope import CallResult
from ..modules.executor import Executor
from ..modules.registry import ModuleSpec, get_module, list_modules
from ..modules.toolspec import export_tool
from ..modules.workspace import Workspace
from ..project import Project

router = APIRouter(prefix="/api", tags=["modules"])

# Calls that are running now, by call id: the log shows them as live rows and the cancel button finds the right one.
RUNNING: dict[str, dict[str, Any]] = {}
_LOCK = threading.RLock()


def project_or_404(pid: str) -> Project:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", pid) or pid in (".", ".."):
        raise HTTPException(400, "Invalid project ID")
    project = Project(pid)
    if not project.exists():
        raise HTTPException(404, f"Project '{pid}' not found")
    return project


def spec_or_404(module_id: str) -> ModuleSpec:
    load()
    try:
        return get_module(module_id)
    except KeyError:
        raise HTTPException(404, f"No module called '{module_id}'. See GET /api/modules.")


def summary(spec: ModuleSpec) -> dict[str, Any]:
    return {"id": spec.id, "plain_name": spec.plain_name, "summary": spec.summary, "cost": spec.cost.kind,
            "effects": spec.effects, "toolboxes": list(spec.toolboxes), "requires": list(spec.requires),
            "produces": list(spec.produces)}


def describe(spec: ModuleSpec) -> dict[str, Any]:
    return {**summary(spec), "version": spec.version, "when_to_use": spec.when_to_use,
            "when_not_to_use": spec.when_not_to_use, "determinism": spec.determinism,
            "fallback": spec.fallback, "fallback_reason": spec.fallback_reason,
            "resources": list(spec.cost.resources), "inputs": spec.inputs.model_json_schema(),
            "outputs": spec.outputs.model_json_schema(),
            "examples": [{"inputs": e.inputs, "outputs": e.outputs} for e in spec.examples]}


def _emitter(request: Request, pid: str):
    hub = getattr(request.app.state, "hub", None)

    def emit(event: dict[str, Any]) -> None:
        if hub:
            hub.emit({**event, "project": pid})
    return emit


class CallBody(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    why: str = Field(default="", max_length=500)
    force: bool = False
    dry_run: bool = False
    background: bool = False
    caller: str = Field(default="person", max_length=40)
    max_seconds: Optional[float] = Field(default=None, gt=0)


@router.get("/modules")
def modules(toolbox: str = "", group: str = "", q: str = "") -> list[dict[str, Any]]:
    load()
    needle = q.strip().lower()
    out = []
    for spec in list_modules():
        if toolbox and toolbox not in spec.toolboxes:
            continue
        if group and not spec.id.startswith(group + "."):
            continue
        if needle and needle not in (spec.id + " " + spec.summary + " " + spec.plain_name).lower():
            continue
        out.append(summary(spec))
    return out


@router.get("/modules/{module_id}")
def module_detail(module_id: str, provider: str = "") -> dict[str, Any]:
    spec = spec_or_404(module_id)
    detail = describe(spec)
    if provider:
        try:
            detail["tool"] = export_tool(spec, provider)          # type: ignore[arg-type]
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    return detail


@router.post("/projects/{pid}/modules/{module_id}/call")
def call_module(pid: str, module_id: str, body: CallBody, request: Request) -> dict[str, Any]:
    project = project_or_404(pid)
    spec = spec_or_404(module_id)
    try:
        inputs = spec.inputs.model_validate(body.inputs)
    except ValidationError as exc:
        return CallResult(ok=False, status="failed", summary="The step's inputs need a correction.",
                          fix=str(exc)[:1200]).model_dump(mode="json")
    if body.dry_run:
        ws = Workspace(project.dir)
        missing = [kind for kind in spec.requires if ws.ref(kind) is None or ws.stale(kind)]
        estimate = spec.cost.estimate(inputs)
        return {"ok": not missing, "status": "dry_run", "module": spec.id,
                "summary": f"{spec.plain_name} would take about {estimate:.1f} s.",
                "estimate_seconds": estimate, "missing": missing,
                "effects": spec.effects, "resources": list(spec.cost.resources)}
    emit = _emitter(request, pid)
    kwargs = dict(caller=body.caller, why=body.why, force=body.force, max_seconds=body.max_seconds)
    if not body.background:
        return Executor(project.dir, on_event=emit).call(module_id, body.inputs, **kwargs).model_dump(mode="json")
    if spec.native_outputs:
        raise HTTPException(409, "This stage writes the project's own files and must run in the foreground.")
    return _start(project, spec, body, kwargs, pid, emit, spec.cost.estimate(inputs))


def _start(project: Project, spec: ModuleSpec, body: CallBody, kwargs: dict[str, Any], pid: str, emit,
           estimate: float) -> dict[str, Any]:
    from ..modules.tickets import submit

    def run(cancel: threading.Event) -> CallResult:
        started = time.monotonic()
        holder: dict[str, str] = {}

        def relay(event: dict[str, Any]) -> None:
            if event.get("type") == "call_started":
                holder["id"] = event["id"]
                with _LOCK:
                    RUNNING[event["id"]] = {"project": pid, "module": spec.id, "plain_name": spec.plain_name,
                                            "caller": body.caller, "started": time.time(), "cancel": cancel,
                                            "estimate": estimate}
                emit({"type": "ticket", "id": event["id"], "module": spec.id, "frac": 0.0,
                      "msg": f"{spec.plain_name}: started", "eta": estimate})
            emit(event)

        try:
            return Executor(project.dir, on_event=relay).call(spec.id, body.inputs, cancel_event=cancel, **kwargs)
        finally:
            with _LOCK:
                RUNNING.pop(holder.get("id", ""), None)
            emit({"type": "ticket", "id": holder.get("id", ""), "module": spec.id, "frac": 1.0,
                  "msg": f"{spec.plain_name}: finished in {time.monotonic() - started:.1f} s", "eta": 0})
    ticket = submit(run)
    return CallResult(ok=True, status="running", summary=f"Started {spec.plain_name.lower()}.",
                      ticket=ticket).model_dump(mode="json")
