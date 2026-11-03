"""Read-only system modules for a director deciding what is available."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class EmptyIn(BaseModel):
    pass


class HealthOut(BaseModel):
    checks: list[dict[str, Any]] = Field(description="Environment checks with ok, detail and an actionable fix.")


@module(
    id="meta.health", version=1, summary="Check the local tools, models, assets and Studio build needed to make videos.",
    when_to_use="A capability is unavailable or before a long unattended run.",
    when_not_to_use="Between ordinary deterministic editing steps.",
    inputs=EmptyIn, outputs=HealthOut, requires=(), produces=(),
    cost=Cost("slow", ("cpu",), 8.0), effects="none", determinism="external", grounding=(),
    fallback=None, fallback_reason="Each existing health check catches its own error and supplies a fix.",
    examples=(Example(inputs={}, outputs={"checks": []}),), toolboxes=("studio", "full"),
    plain_name="Checking the video tools", log_line=lambda i, o: f"Checked {len(o.checks)} parts of the video tools.",
)
def health(ws: Workspace, inputs: EmptyIn) -> HealthOut:
    from ...doctor import run_checks

    return HealthOut(checks=run_checks())


class HardwareOut(BaseModel):
    hardware: dict[str, Any] = Field(description="GPU, CUDA, encoder and runtime availability.")


@module(
    id="meta.hardware", version=1, summary="Report the local GPU, CUDA runtimes and video encoder availability.",
    when_to_use="Choosing between CPU, local GPU and a remote generation server.",
    when_not_to_use="A recipe already fixed its execution resources.",
    inputs=EmptyIn, outputs=HardwareOut, requires=(), produces=(),
    cost=Cost("fast", ("cpu",), 2.0), effects="none", determinism="external", grounding=(),
    fallback=None, fallback_reason="The existing diagnostic returns CPU-safe defaults when a runtime is absent.",
    examples=(Example(inputs={}, outputs={"hardware": {"available": False, "backend": "cpu"}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Checking the hardware",
    log_line=lambda i, o: f"Hardware backend: {o.hardware.get('backend', 'unknown')}.",
)
def hardware(ws: Workspace, inputs: EmptyIn) -> HardwareOut:
    from ...gpu import gpu_info

    return HardwareOut(hardware=gpu_info())


class ModelsOut(BaseModel):
    speech: list[dict[str, Any]] = Field(description="Speech-recognition models and installation state.")
    downloadable: list[dict[str, Any]] = Field(description="Other downloadable app models and readiness.")
    local_ai: dict[str, Any] = Field(description="Configured local AI server and model state.")
    provider: dict[str, Any] = Field(description="Configured AI provider state without secrets.")


@module(
    id="meta.models", version=1, summary="List installed and downloadable speech, vision, voice and local AI models.",
    when_to_use="A director needs to choose an available model or explain a fallback.",
    when_not_to_use="For downloading a model.",
    inputs=EmptyIn, outputs=ModelsOut, requires=(), produces=(),
    cost=Cost("fast", ("cpu",), 2.0), effects="none", determinism="external", grounding=(),
    fallback=None, fallback_reason="The existing status functions report unavailable services without failing.",
    examples=(Example(inputs={}, outputs={"speech": [], "downloadable": [], "local_ai": {}, "provider": {}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Checking the available models",
    log_line=lambda i, o: f"Found {sum(1 for model in o.speech if model.get('installed'))} installed speech model(s).",
)
def models(ws: Workspace, inputs: EmptyIn) -> ModelsOut:
    from ... import llm
    from ... import models as downloadable
    from ...ai.providers import provider_status
    from ...stages.asr import list_models

    rows = []
    for model_id in downloadable.MODELS:
        model = downloadable.get(model_id)
        rows.append({"id": model.id, "label": model.title, "ready": downloadable.ready(model.id),
                     "missing_bytes": downloadable.missing_bytes(model.id)})
    return ModelsOut(speech=list_models(), downloadable=rows,
                     local_ai=llm.status(), provider=provider_status())


class CatalogIn(BaseModel):
    group: str | None = Field(default=None, description="Optional module-id prefix, such as audio or timeline.")
    toolbox: str | None = Field(default=None, description="Optional toolbox name: autonomous, studio or full.")


class CatalogOut(BaseModel):
    modules: list[dict[str, Any]] = Field(description="Matching module ids, versions and one-line summaries.")


@module(
    id="meta.catalog", version=1, summary="List callable modules with their one-line purpose and availability.",
    when_to_use="Choosing the next capability without loading every schema.", when_not_to_use="The module id is already known.",
    inputs=CatalogIn, outputs=CatalogOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.02),
    effects="none", determinism="pure", grounding=(), fallback=None, fallback_reason="This reads the in-process registry.",
    examples=(Example(inputs={}, outputs={"modules": []}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Listing the video tools", log_line=lambda i, o: f"Listed {len(o.modules)} available module(s).",
)
def catalog(ws: Workspace, inputs: CatalogIn) -> CatalogOut:
    from ..registry import list_modules

    rows = []
    for spec in list_modules():
        if inputs.group and not spec.id.startswith(inputs.group + "."):
            continue
        if inputs.toolbox and inputs.toolbox not in spec.toolboxes:
            continue
        rows.append({"id": spec.id, "version": spec.version, "summary": spec.summary,
                     "cost": spec.cost.kind, "effects": spec.effects})
    return CatalogOut(modules=rows)


class DescribeIn(BaseModel):
    module_id: str = Field(description="Exact stable module id to describe.")


class DescribeOut(BaseModel):
    module: dict[str, Any] = Field(description="Contract, schemas, examples and usage guidance for the module.")


@module(
    id="meta.describe", version=1, summary="Describe one module's inputs, outputs, examples, cost and usage guidance.",
    when_to_use="Immediately before calling an unfamiliar module.", when_not_to_use="Only a short catalogue is needed.",
    inputs=DescribeIn, outputs=DescribeOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.02),
    effects="none", determinism="pure", grounding=(), fallback=None, fallback_reason="This reads the in-process registry.",
    examples=(Example(inputs={"module_id": "meta.health"}, outputs={"module": {"id": "meta.health"}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Describing a video tool",
    log_line=lambda i, o: f"Described {i.module_id}.",
)
def describe(ws: Workspace, inputs: DescribeIn) -> DescribeOut:
    from ..registry import get_module

    spec = get_module(inputs.module_id)
    return DescribeOut(module={
        "id": spec.id, "version": spec.version, "summary": spec.summary,
        "when_to_use": spec.when_to_use, "when_not_to_use": spec.when_not_to_use,
        "inputs": spec.inputs.model_json_schema(), "outputs": spec.outputs.model_json_schema(),
        "requires": list(spec.requires), "produces": list(spec.produces), "cost": spec.cost.kind,
        "effects": spec.effects, "determinism": spec.determinism, "fallback": spec.fallback,
        "examples": [{"inputs": e.inputs, "outputs": e.outputs} for e in spec.examples],
    })


class StateIn(BaseModel):
    artifact_type: str | None = Field(default=None, description="Optional artifact type to read or summarize.")
    offset: int = Field(default=0, ge=0, description="First item for paging a JSON list.")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum JSON list items to return.")


class StateOut(BaseModel):
    have: list[dict[str, Any]] = Field(description="Present artifacts with compact references and stale state.")
    value: Any | None = Field(default=None, description="Requested JSON value or page; binary artifacts are not inlined.")


@module(
    id="meta.state", version=1, summary="Show project artifacts, stale state, or a bounded page of one JSON artifact.",
    when_to_use="Inspecting project state before deciding the next call.", when_not_to_use="Reading raw binary media.",
    inputs=StateIn, outputs=StateOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.05),
    effects="none", determinism="pure", grounding=(), fallback=None, fallback_reason="This reads the workspace index and files.",
    examples=(Example(inputs={}, outputs={"have": [], "value": None}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Checking the project state", log_line=lambda i, o: f"Found {len(o.have)} project artifact(s).",
)
def state(ws: Workspace, inputs: StateIn) -> StateOut:
    from ..workspace import KNOWN_ARTIFACTS

    have = []
    for kind in sorted(KNOWN_ARTIFACTS):
        ref = ws.ref(kind)
        if ref:
            have.append({"type": kind, "ref": ref["ref"], "bytes": ref["bytes"], "stale": ws.stale(kind)})
    value = None
    if inputs.artifact_type:
        path = ws.path_for(inputs.artifact_type)
        if path.suffix.lower() == ".json":
            value = ws.read_json(inputs.artifact_type)
            if isinstance(value, list):
                value = {"items": value[inputs.offset:inputs.offset + inputs.limit], "total": len(value),
                         "offset": inputs.offset}
    return StateOut(have=have, value=value)


class DryRunIn(BaseModel):
    calls: list[dict[str, Any]] = Field(description="Ordered calls, each with module and optional inputs fields.")


class DryRunOut(BaseModel):
    valid: bool = Field(description="Whether all module ids and input values validate.")
    seconds: float = Field(description="Sum of declared estimated wall seconds.")
    calls: list[dict[str, Any]] = Field(description="Validation and prerequisite result for every proposed call.")


@module(
    id="meta.dry_run", version=1, summary="Validate a proposed sequence of module calls and estimate it without running it.",
    when_to_use="Before an expensive or multi-step plan.", when_not_to_use="For one cheap call with known inputs.",
    inputs=DryRunIn, outputs=DryRunOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.1),
    effects="none", determinism="pure", grounding=(), fallback=None, fallback_reason="Validation needs no fallback.",
    examples=(Example(inputs={"calls": []}, outputs={"valid": True, "seconds": 0.0, "calls": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Checking the proposed work",
    log_line=lambda i, o: f"Checked {len(o.calls)} proposed call(s); estimated {o.seconds:.1f} seconds.",
)
def dry_run(ws: Workspace, inputs: DryRunIn) -> DryRunOut:
    from ..registry import get_module

    rows, total, valid = [], 0.0, True
    for item in inputs.calls:
        try:
            spec = get_module(str(item.get("module", "")))
            parsed = spec.inputs.model_validate(item.get("inputs") or {})
            estimate = spec.cost.estimate(parsed)
            missing = [kind for kind in spec.requires if not ws.exists(kind)]
            rows.append({"module": spec.id, "valid": True, "seconds": estimate, "missing": missing})
            total += estimate
        except Exception as exc:
            valid = False
            rows.append({"module": str(item.get("module", "")), "valid": False, "error": str(exc)[:400]})
    return DryRunOut(valid=valid, seconds=total, calls=rows)


class UndoIn(BaseModel):
    artifact_type: str = Field(description="Artifact type whose preceding saved version should be restored.")


class UndoOut(BaseModel):
    artifact: dict[str, Any] = Field(description="Reference to the restored artifact version.")


@module(
    id="meta.undo", version=1, summary="Restore the preceding saved version of one project artifact.",
    when_to_use="Reversing the most recent write to a named artifact.", when_not_to_use="No earlier version exists.",
    inputs=UndoIn, outputs=UndoOut, requires=(), produces=(), cost=Cost("fast", ("cpu",), 1.0),
    effects="writes_artifact", determinism="pure", grounding=(), fallback=None, fallback_reason="Undo is the recovery operation.",
    examples=(Example(inputs={"artifact_type": "scenes"}, outputs={"artifact": {"type": "scenes"}}),),
    toolboxes=("studio", "full"), plain_name="Undoing the last change",
    log_line=lambda i, o: f"Restored the previous {i.artifact_type}.",
)
def undo(ws: Workspace, inputs: UndoIn) -> UndoOut:
    return UndoOut(artifact=ws.undo(inputs.artifact_type))


@module(id="meta.redo", version=1, summary="Restore the artifact version most recently removed by unified undo.",
        when_to_use="A person reverses an immediately preceding undo.", when_not_to_use="A new write occurred after undo.",
        inputs=UndoIn, outputs=UndoOut, requires=(), produces=(), cost=Cost("fast", ("cpu",), 1.0), effects="writes_artifact", determinism="pure",
        grounding=(), fallback=None, fallback_reason="Redo is available only while its saved version remains valid.",
        examples=(Example(inputs={"artifact_type": "scenes"}, outputs={"artifact": {"type": "scenes"}}),), toolboxes=("studio", "full"),
        plain_name="Redoing the last undone change", log_line=lambda i, o: f"Restored the later {i.artifact_type}.")
def redo(ws: Workspace, inputs: UndoIn) -> UndoOut:
    return UndoOut(artifact=ws.redo(inputs.artifact_type))


class TicketIn(BaseModel):
    ticket: str = Field(description="Ticket id returned by an asynchronous module call.")
    timeout: float | None = Field(default=None, ge=0, le=300, description="Maximum seconds to wait, or no limit when omitted.")


class TicketOut(BaseModel):
    result: dict[str, Any] = Field(description="Current or completed call result envelope.")


@module(
    id="meta.wait", version=1, summary="Wait for an asynchronous module ticket and return its result.",
    when_to_use="A prior heavy call returned a running ticket.", when_not_to_use="The call already completed synchronously.",
    inputs=TicketIn, outputs=TicketOut, requires=(), produces=(), cost=Cost("slow", ("cpu",), 1.0),
    effects="none", determinism="external", grounding=(), fallback=None, fallback_reason="The ticket owns the underlying result.",
    examples=(Example(inputs={"ticket": "t123", "timeout": 1}, outputs={"result": {"status": "ok"}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Waiting for a video task",
    log_line=lambda i, o: f"Ticket {i.ticket} is {o.result.get('status', 'unknown')}.",
)
def wait_for_ticket(ws: Workspace, inputs: TicketIn) -> TicketOut:
    from ..tickets import wait

    return TicketOut(result=wait(inputs.ticket, inputs.timeout).model_dump(mode="json"))


class CancelIn(BaseModel):
    ticket: str = Field(description="Ticket id returned by an asynchronous module call.")


class CancelOut(BaseModel):
    cancelled: bool = Field(description="Whether cancellation was requested before completion.")


@module(
    id="meta.cancel", version=1, summary="Request cancellation of one asynchronous module call.",
    when_to_use="A running task is no longer wanted.", when_not_to_use="The task has already completed.",
    inputs=CancelIn, outputs=CancelOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.02),
    effects="none", determinism="external", grounding=(), fallback=None, fallback_reason="Cancellation is best effort by definition.",
    examples=(Example(inputs={"ticket": "t123"}, outputs={"cancelled": True}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Cancelling a video task",
    log_line=lambda i, o: f"Cancellation {'requested' if o.cancelled else 'was too late'} for {i.ticket}.",
)
def cancel_ticket(ws: Workspace, inputs: CancelIn) -> CancelOut:
    from ..tickets import cancel

    return CancelOut(cancelled=cancel(inputs.ticket))


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000, description="Plain-language decision, reason or finding to preserve in the call log.")


class NoteOut(BaseModel):
    recorded: bool = Field(description="Whether the note was accepted for logging.")


@module(
    id="meta.note", version=1, summary="Record a director decision or finding in the project call log.",
    when_to_use="Preserving why a later decision was made.", when_not_to_use="For secrets or raw diagnostic output.",
    inputs=NoteIn, outputs=NoteOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.01),
    effects="none", determinism="pure", grounding=(), fallback=None, fallback_reason="The executor already appends and redacts the call log.",
    examples=(Example(inputs={"text": "Keep the opening pause for emphasis."}, outputs={"recorded": True}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Recording a director note",
    log_line=lambda i, o: i.text,
)
def note(ws: Workspace, inputs: NoteIn) -> NoteOut:
    return NoteOut(recorded=True)


class BudgetIn(BaseModel):
    total_seconds: float = Field(gt=0, description="Total wall-time allowance for the run.")
    spent_seconds: float = Field(default=0, ge=0, description="Wall time already spent.")
    calls: list[dict[str, Any]] = Field(default_factory=list, description="Optional proposed module calls to estimate.")


class BudgetOut(BaseModel):
    left_seconds: float = Field(description="Unspent wall-time allowance.")
    planned_seconds: float = Field(description="Declared estimate of proposed calls.")
    affordable: bool = Field(description="Whether all proposed calls fit the remaining allowance.")


@module(id="meta.budget", version=1, summary="Report remaining wall-time budget and whether proposed module calls fit.",
        when_to_use="Before an expensive generation, render or multi-call plan.", when_not_to_use="No execution budget was set.",
        inputs=BudgetIn, outputs=BudgetOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.03), effects="none", determinism="pure",
        grounding=(), fallback=None, fallback_reason="Unknown calls fail validation rather than receiving invented costs.",
        examples=(Example(inputs={"total_seconds": 100, "spent_seconds": 20}, outputs={"left_seconds": 80, "planned_seconds": 0, "affordable": True}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Checking the execution budget", log_line=lambda i, o: f"{o.left_seconds:.1f} seconds remain in the budget.")
def budget(ws: Workspace, inputs: BudgetIn) -> BudgetOut:
    from ..registry import get_module
    planned = 0.0
    for item in inputs.calls:
        spec = get_module(str(item.get("module", "")))
        planned += spec.cost.estimate(spec.inputs.model_validate(item.get("inputs") or {}))
    left = max(0.0, inputs.total_seconds - inputs.spent_seconds)
    return BudgetOut(left_seconds=left, planned_seconds=planned, affordable=planned <= left)


class AskHumanIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000, description="Plain approval or choice request.")
    kind: str = Field(default="choice", description="Request kind such as choice, approval or plan_review.")
    options: list[dict[str, Any]] = Field(default_factory=list, description="Bounded choices displayed by a surface.")


class AskHumanOut(BaseModel):
    request: dict[str, Any] = Field(description="Persisted request for a Studio or external director surface.")


@module(id="meta.ask_human", version=1, summary="Persist an approval or choice request for a connected human-facing surface.",
        when_to_use="Policy or a material creative choice requires a person.", when_not_to_use="An autonomous safe default is already defined.",
        inputs=AskHumanIn, outputs=AskHumanOut, requires=(), produces=("human.request",), cost=Cost("instant", ("cpu",), 0.02), effects="writes_artifact", determinism="pure",
        grounding=(), fallback=None, fallback_reason="The request remains pending until a surface records an answer.",
        examples=(Example(inputs={"question": "Approve this plan?", "kind": "plan_review"}, outputs={"request": {"status": "pending"}}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Requesting a human decision", log_line=lambda i, o: "Recorded a pending human decision.")
def ask_human(ws: Workspace, inputs: AskHumanIn) -> AskHumanOut:
    from ...util import now_iso
    if inputs.kind == "plan_review":                                   # the Studio shows the plan sheet; `plan.wait` returns what the person decides
        from ...direction import plan_doc as PD
        from ...project import Project

        project = Project(ws.root.name, ws.root.parent)
        if PD.load(project.dir) is not None:
            project.update_meta(status="review")
    return AskHumanOut(request={"status": "pending", "kind": inputs.kind, "question": inputs.question,
                                "options": inputs.options, "created_at": now_iso()})


class FinishIn(BaseModel):
    summary: str = Field(min_length=1, max_length=1000, description="Plain completion report grounded in produced artifacts.")


class FinishOut(BaseModel):
    report: dict[str, Any] = Field(description="Completion report with present artifact references.")


@module(id="meta.finish", version=1, summary="Declare a video run complete and persist its artifact-backed closing report.",
        when_to_use="All required recipe outputs and quality gates are complete.", when_not_to_use="Required artifacts are missing or stale.",
        inputs=FinishIn, outputs=FinishOut, requires=("project.meta",), produces=("finish.report",), cost=Cost("instant", ("cpu",), 0.05), effects="writes_artifact", determinism="pure",
        grounding=("summary",), fallback=None, fallback_reason="Incomplete work is rejected by the caller's recipe gate.",
        examples=(Example(inputs={"summary": "Finished the approved short."}, outputs={"report": {"summary": "Finished the approved short.", "artifacts": []}}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Finishing the video run", log_line=lambda i, o: i.summary)
def finish(ws: Workspace, inputs: FinishIn) -> FinishOut:
    from ...util import now_iso
    from ..workspace import KNOWN_ARTIFACTS
    artifacts = [ref for kind in sorted(KNOWN_ARTIFACTS) if (ref := ws.ref(kind)) and not ws.stale(kind)]
    return FinishOut(report={"summary": inputs.summary, "at": now_iso(), "artifacts": artifacts})
