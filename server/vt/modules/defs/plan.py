"""The plan the person sees and approves before anything expensive starts (docs/plans/PLAN-DIRECTOR-MODULES.MD section 4.14 and 8).

    plan.make -> plan.edit (as many as the person likes) -> plan.estimate -> plan.approve -> plan.start -> plan.status

Every change is a call by whoever made it, so the log shows the person's edits next to the director's decisions. Nothing here draws a picture except `plan.preview_moment`, and only on request.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


def _project(ws: Workspace):
    from ...project import Project

    return Project(ws.root.name, ws.root.parent)


def _summary(plan) -> dict[str, Any]:
    from ...direction import plan_doc as PD

    return {"state": plan.state, "rev": plan.rev, "moments": len(plan.moments), "made": plan.estimate.made, "estimate_seconds": plan.estimate.total_seconds,
            "gpu_seconds": plan.estimate.gpu_seconds, "notes": PD.checks(plan)}


class MakeIn(BaseModel):
    use_ai: bool = Field(default=True, description="Let the language AI read the script; false uses the rules only.")
    pace: str = Field(default="balanced", description="punchy, balanced or calm: how often the picture changes.")


class SummaryOut(BaseModel):
    state: str = Field(description="draft, approved, running, done or declined.")
    rev: int = Field(description="How many edits the plan has had.")
    moments: int = Field(description="How many moments (places where the picture changes).")
    made: int = Field(description="How many pictures are made for you.")
    estimate_seconds: float = Field(description="About how long making it takes, in seconds.")
    gpu_seconds: float = Field(description="Of which on the picture server.")
    notes: list[str] = Field(description="Gentle notes about the plan; never blockers.")


@module(
    id="plan.make", version=1, summary="Write the plan for a reel: a moment for each picture change, what each shows, and the time it takes. Draws nothing.",
    when_to_use="After listening, before any picture is drawn.", when_not_to_use="For a video whose picture is the speaker.",
    inputs=MakeIn, outputs=SummaryOut, requires=("transcript", "beats"), produces=("plan.doc",), cost=Cost("slow", ("ollama",), 20.0), effects="writes_artifact", determinism="external",
    grounding=("sentence",), fallback=None, fallback_reason="Without a language AI the plan comes from the rules over the same sentences.",
    examples=(Example(inputs={"use_ai": False}, outputs={"state": "draft", "rev": 0, "moments": 9, "made": 9, "estimate_seconds": 100.0, "gpu_seconds": 72.0, "notes": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Writing your plan", native_outputs=True,
    log_line=lambda i, o: f"Wrote a plan of {o.moments} moments, {o.made} made for you, about {round(o.estimate_seconds / 60)} min.",
)
def make(ws: Workspace, inputs: MakeIn) -> SummaryOut:
    from ...direction import plan_doc as PD

    plan = PD.build(_project(ws), use_ai=inputs.use_ai, pace=inputs.pace)
    return SummaryOut(**_summary(plan))


class EditIn(BaseModel):
    operation: dict[str, Any] = Field(description="One typed operation: {op: set_medium|set_beat|set_prompt|choose_alternative|lock|unlock|merge|split|set_style|set_goal|set_idea|set_pace|set_budget|set_place|set_moment_place|set_cast, ...}. "
                                                    "set_place {name, text}: a place every picture in it is painted with (how it looks, how big its things are next to a person); "
                                                    "set_moment_place {moment, place}; set_cast {name, text}: how a named person looks, added to every picture that names them. "
                                                    "Each picture is painted alone: give every moment its place and name its people.")


class EditOut(SummaryOut):
    changes: list[str] = Field(description="What the edit did, in plain sentences.")


@module(
    id="plan.edit", version=1, summary="Change one thing in the plan: a moment's picture, its change point, the look, the pace or how many to make.",
    when_to_use="The person (or a director) wants the plan different before it is made.", when_not_to_use="After the video has started being made.",
    inputs=EditIn, outputs=EditOut, requires=("plan.doc",), produces=("plan.doc",), cost=Cost("instant", ("cpu",), 0.1), effects="writes_artifact", determinism="pure",
    grounding=("sentence",), fallback=None, fallback_reason="An edit that cannot be done is refused with a sentence; nothing else is attempted.",
    examples=(Example(inputs={"operation": {"op": "lock", "moment": "s1"}}, outputs={"state": "draft", "rev": 1, "moments": 9, "made": 9, "estimate_seconds": 100.0, "gpu_seconds": 72.0, "notes": [], "changes": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Changing the plan", native_outputs=True,
    log_line=lambda i, o: (o.changes[0] if o.changes else f"Changed the plan ({i.operation.get('op')}).") + f" Now about {round(o.estimate_seconds / 60)} min.",
)
def edit(ws: Workspace, inputs: EditIn) -> EditOut:
    from ...direction import plan_doc as PD

    project = _project(ws)
    plan = PD.load(project.dir)
    if plan is None:
        raise PD.PlanError("There is no plan yet.")
    notes = PD.apply_edit(plan, inputs.operation, project)
    PD.save(project.dir, plan)
    return EditOut(**_summary(plan), changes=notes)


class EmptyIn(BaseModel):
    pass


@module(
    id="plan.estimate", version=1, summary="How long making the plan takes and how much of it is on the picture server.",
    when_to_use="To show the time and cost before Start.", when_not_to_use="When there is no plan.",
    inputs=EmptyIn, outputs=SummaryOut, requires=("plan.doc",), produces=(), cost=Cost("instant", ("cpu",), 0.05), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The estimate is arithmetic over the plan.",
    examples=(Example(inputs={}, outputs={"state": "draft", "rev": 0, "moments": 9, "made": 9, "estimate_seconds": 100.0, "gpu_seconds": 72.0, "notes": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Estimating the time", native_outputs=True,
    log_line=lambda i, o: f"About {round(o.estimate_seconds / 60)} min, {o.made} pictures made for you.",
)
def estimate(ws: Workspace, inputs: EmptyIn) -> SummaryOut:
    from ...direction import plan_doc as PD

    plan = PD.load(_project(ws).dir)
    if plan is None:
        raise PD.PlanError("There is no plan yet.")
    return SummaryOut(**_summary(plan))


class PreviewIn(BaseModel):
    moment: str = Field(description="The moment id, for example s3.")
    still: bool = Field(default=False, description="Make one small picture now (seconds on the picture server); false shows only the words.")


class PreviewOut(BaseModel):
    moment: str = Field(description="The moment id.")
    prompt: str = Field(description="What the picture will be asked to show, in full.")
    media: str = Field(description="The preview picture's media id, empty when none was made.")
    note: str = Field(description="What the preview is and is not.")


@module(
    id="plan.preview_moment", version=1, summary="Show what a moment will roughly look like: its words, and on request one small picture.",
    when_to_use="The person wants to judge a moment's look before the whole video is made.", when_not_to_use="To make the real picture; Start does that.",
    inputs=PreviewIn, outputs=PreviewOut, requires=("plan.doc",), produces=(), cost=Cost("fast", ("comfy",), 10.0), effects="writes_artifact", determinism="seeded", grounding=(),
    fallback=None, fallback_reason="Without the picture server only the words are shown.",
    examples=(Example(inputs={"moment": "s1"}, outputs={"moment": "s1", "prompt": "an empty room", "media": "", "note": "Words only."}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Previewing a moment", native_outputs=True,
    log_line=lambda i, o: f"Showed a preview of moment {o.moment[1:]}" + (" with a picture." if o.media else "."),
)
def preview_moment(ws: Workspace, inputs: PreviewIn) -> PreviewOut:
    from ...direction import plan_doc as PD
    from ...reel.style import cast_for, drawing_style, prompt_for

    project = _project(ws)
    plan = PD.load(project.dir)
    if plan is None:
        raise PD.PlanError("There is no plan yet.")
    m = plan.moment(inputs.moment)
    prompt = prompt_for(m.draw, drawing_style(plan.idea.style, project.meta().theme), cast_for(m.draw, plan.idea.cast) or plan.idea.character, plan.idea.places.get(m.place, ""))
    media = ""
    note = "These are the words the picture will be asked for. The real picture can look different."
    if inputs.still:
        media, note = _make_still(project, plan, m, prompt)
        if media:
            m.preview = media
            PD.save(project.dir, plan)
    return PreviewOut(moment=m.id, prompt=prompt, media=media, note=note)


def _make_still(project, plan, m, prompt: str) -> tuple[str, str]:
    """One picture for the card, counted in the plan. Never raises: no server means words only, said plainly."""
    import hashlib

    from ...comfy import ComfyError, generate_still, picture_workflow
    from ...reel.plan import reachable
    from ...util import read_json
    from ... import paths

    url = str((read_json(paths.SETTINGS, {}) or {}).get("comfy_url") or "http://192.168.123.47:8188")
    client, why = reachable(url)
    if client is None:
        return "", f"Words only: the picture server does not answer ({why})."
    seed = int(hashlib.sha1(f"{project.id}:{m.id}:{prompt}".encode()).hexdigest()[:7], 16)
    try:
        item, _ = generate_still(project, client, getattr(client, "workflow", None) or picture_workflow(), prompt, aspect=project.meta().aspect, seed=seed, caption=m.draw[:80], scene=f"preview-{m.id}", checked=True)
        return item.id, "One small picture, drawn now. Starting uses it again, so it costs nothing twice."
    except ComfyError as e:
        return "", f"Words only: the picture could not be drawn ({str(e)[:120]})."


class ApproveIn(BaseModel):
    by: str = Field(default="person", description="Who approved: person, or the name of a director.")


class StateOut(BaseModel):
    state: str = Field(description="draft, approved, running, done or declined.")
    rev: int = Field(description="How many edits the plan has had.")
    open_checks: int = Field(default=0, description="Picture checks still open when a director approved the plan (the person is shown the plan and decides for themselves).")
    issues: list[str] = Field(default_factory=list, description="What the open picture checks say.")


@module(
    id="plan.approve", version=1, summary="Approve the plan: from now on it is what gets made.",
    when_to_use="The person pressed Start, or a director may spend without asking.", when_not_to_use="Before the person has seen the plan, when the setting asks them to.",
    inputs=ApproveIn, outputs=StateOut, requires=("plan.doc",), produces=("plan.doc",), cost=Cost("instant", ("cpu",), 0.05), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="Approval is a decision; there is nothing to fall back to.",
    examples=(Example(inputs={"by": "person"}, outputs={"state": "approved", "rev": 3}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Approving the plan", native_outputs=True,
    log_line=lambda i, o: f"{'You' if i.by == 'person' else i.by} approved the plan." + (f" {o.open_checks} picture check(s) were still open." if o.open_checks else ""),
)
def approve(ws: Workspace, inputs: ApproveIn) -> StateOut:
    from ...direction import plan_doc as PD
    from ...util import now_iso

    project = _project(ws)
    plan = PD.load(project.dir)
    if plan is None:
        raise PD.PlanError("There is no plan yet.")
    if plan.state in ("running", "done"):
        raise PD.PlanError("This plan has already been made.")
    plan.state, plan.approved_by, plan.approved_at = "approved", inputs.by, now_iso()
    PD.save(project.dir, plan)
    issues = [f'{x["says"]} {x["fix"]}' for x in PD.open_picture_issues(project, plan)] if inputs.by != "person" else []        # a director may approve with checks open: that is its choice, and it is written down
    if issues:
        import uuid

        from ..calls import append_call

        append_call(project.dir, {"id": "c" + uuid.uuid4().hex[:12], "module": "plan.checks", "caller": {"kind": "rules", "who": "rules"},
                                  "why": "A director approved the plan while picture checks were still open.", "inputs": {"by": inputs.by}, "status": "open", "level": "warn",
                                  "plain": f"{inputs.by} approved the plan with {len(issues)} picture check(s) still open: " + " ".join(issues[:3]) + (" ..." if len(issues) > 3 else ""),
                                  "fix": "Open the plan, fix the pictures the checks name (they are drawn from these words), or leave it as it is."})
    return StateOut(state=plan.state, rev=plan.rev, open_checks=len(issues), issues=issues[:12])


@module(
    id="plan.decline", version=1, summary="Turn the plan down: nothing is made and the project stays as it was.",
    when_to_use="The person does not want this plan.", when_not_to_use="To change one part of it; edit instead.",
    inputs=EmptyIn, outputs=StateOut, requires=("plan.doc",), produces=("plan.doc",), cost=Cost("instant", ("cpu",), 0.05), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="Declining is a decision; there is nothing to fall back to.",
    examples=(Example(inputs={}, outputs={"state": "declined", "rev": 3}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Declining the plan", native_outputs=True,
    log_line=lambda i, o: "You declined the plan; nothing was made.",
)
def decline(ws: Workspace, inputs: EmptyIn) -> StateOut:
    from ...direction import plan_doc as PD

    project = _project(ws)
    plan = PD.load(project.dir)
    if plan is None:
        raise PD.PlanError("There is no plan yet.")
    plan.state = "declined"
    PD.save(project.dir, plan)
    project.update_meta(status="draft")
    return StateOut(state=plan.state, rev=plan.rev)


class StartIn(BaseModel):
    run: bool = Field(default=False, description="Make it now, in this call. False only approves: the Studio's job runner makes it.")


class StartOut(BaseModel):
    state: str = Field(description="approved, running or done.")
    started: bool = Field(description="Whether making has run in this call.")


@module(
    id="plan.start", version=1, summary="Approve the plan and make it: draw the pictures and put the video together.",
    when_to_use="The plan is what the person wants.", when_not_to_use="When the plan still has notes the person has not looked at.",
    inputs=StartIn, outputs=StartOut, requires=("plan.doc",), produces=("plan.doc",), cost=Cost("heavy", ("comfy", "gpu"), 300.0), effects="writes_timeline", determinism="external", grounding=(),
    fallback=None, fallback_reason="A picture that cannot be drawn becomes a word card; the video is always made.",
    examples=(Example(inputs={"run": False}, outputs={"state": "approved", "started": False}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Starting to make it", native_outputs=True,
    log_line=lambda i, o: "Started making the video." if o.started else "Approved the plan; making it is next.",
)
def start(ws: Workspace, inputs: StartIn) -> StartOut:
    from ...direction import plan_doc as PD
    from ...pipeline import Pipeline
    from ...util import now_iso

    project = _project(ws)
    plan = PD.load(project.dir)
    if plan is None:
        raise PD.PlanError("There is no plan yet.")
    if plan.state == "draft":
        plan.state, plan.approved_by, plan.approved_at = "approved", "person", now_iso()
        PD.save(project.dir, plan)
    if inputs.run:
        Pipeline(project).run("plan", None, True)
        plan = PD.load(project.dir) or plan
    return StartOut(state=plan.state, started=inputs.run)


class StatusOut(BaseModel):
    state: str = Field(description="draft, approved, running, done or declined.")
    moments: list[dict[str, Any]] = Field(description="Per moment: id, status (planned, waiting, making, ready, replaced, failed), medium and the problem if any.")
    seconds_left: Optional[float] = Field(description="About how long is left, or null when it is not running.")


@module(
    id="plan.status", version=1, summary="Where each moment of the plan is: waiting, making, ready or needs a look.",
    when_to_use="While the video is being made.", when_not_to_use="Before there is a plan.",
    inputs=EmptyIn, outputs=StatusOut, requires=("plan.doc",), produces=(), cost=Cost("instant", ("cpu",), 0.02), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="A read of the plan file.",
    examples=(Example(inputs={}, outputs={"state": "running", "moments": [{"id": "s1", "status": "ready", "medium": "made", "problem": ""}], "seconds_left": 40.0}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Checking the plan's progress", native_outputs=True,
    log_line=lambda i, o: f"{sum(1 for m in o.moments if m['status'] == 'ready')} of {len(o.moments)} moments are ready.",
)
def status(ws: Workspace, inputs: EmptyIn) -> StatusOut:
    from ...direction import plan_doc as PD

    plan = PD.load(_project(ws).dir)
    if plan is None:
        raise PD.PlanError("There is no plan yet.")
    left = None
    if plan.state == "running":
        left = round(sum(plan.still_seconds for m in plan.moments if m.medium == "made" and m.status in ("planned", "waiting", "making")), 1)
    return StatusOut(state=plan.state, moments=[{"id": m.id, "status": m.status, "medium": m.medium, "problem": m.problem} for m in plan.moments], seconds_left=left)


class WaitIn(BaseModel):
    timeout_seconds: float = Field(default=600.0, ge=0, le=86400, description="How long to wait for the person; 0 looks once. The default is 10 minutes.")
    on_timeout: str = Field(default="stop", description="stop (never spend without the person) or proceed (approve it as it is).")


class WaitOut(BaseModel):
    answered: bool = Field(description="Whether the person approved or declined.")
    state: str = Field(description="draft, approved, running, done or declined.")
    timed_out: bool = Field(description="Whether the wait ran out first.")
    summary: dict[str, Any] = Field(description="The plan as the person left it: moments, estimate, notes.")


@module(
    id="plan.wait", version=1, summary="Wait for the person to approve or decline the plan they are looking at; returns the plan as they left it.",
    when_to_use="After asking the person for a plan review (meta.ask_human, kind plan_review).", when_not_to_use="When the setting says the plan needs no review.",
    inputs=WaitIn, outputs=WaitOut, requires=("plan.doc",), produces=(), cost=Cost("slow", ("cpu",), 60.0), effects="none", determinism="external", grounding=(),
    fallback=None, fallback_reason="An unanswered request stops (nothing is spent) unless the caller said to proceed.",
    examples=(Example(inputs={"timeout_seconds": 0}, outputs={"answered": False, "state": "draft", "timed_out": True, "summary": {}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Waiting for your decision", native_outputs=True,
    log_line=lambda i, o: "You approved the plan." if o.state in ("approved", "running", "done") and o.answered else "You declined the plan." if o.state == "declined" else "The plan was not answered in time.",
)
def wait(ws: Workspace, inputs: WaitIn) -> WaitOut:
    import time

    from ...direction import plan_doc as PD
    from ...util import now_iso

    project = _project(ws)
    deadline = time.time() + inputs.timeout_seconds
    while True:
        plan = PD.load(project.dir)
        if plan is None:
            raise PD.PlanError("There is no plan yet.")
        if plan.state != "draft":
            return WaitOut(answered=True, state=plan.state, timed_out=False, summary=_summary(plan))
        if time.time() >= deadline:
            break
        time.sleep(min(1.0, max(0.05, deadline - time.time())))
    if inputs.on_timeout == "proceed":
        plan.state, plan.approved_by, plan.approved_at = "approved", "timeout", now_iso()
        PD.save(project.dir, plan)
        return WaitOut(answered=False, state=plan.state, timed_out=True, summary=_summary(plan))
    return WaitOut(answered=False, state=plan.state, timed_out=True, summary=_summary(plan))
