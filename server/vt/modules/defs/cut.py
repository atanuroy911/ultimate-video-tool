"""Audio-first impact and visual cut-plan modules."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class EmptyIn(BaseModel):
    pass


class ImpactOut(BaseModel):
    impacts: list[dict[str, Any]] = Field(description="Candidate picture-change points with strength and grounded reason.")


@module(id="understand.impact_map", version=1, summary="Combine spoken stress, prosody, sound and auditory saliency into candidate picture changes.",
        when_to_use="Audio analysis and timed words are ready for visual pacing.", when_not_to_use="Before the audio edit is locked.",
        inputs=EmptyIn, outputs=ImpactOut, requires=("transcript",), produces=("impact.map",), cost=Cost("fast", ("cpu",), 1.0), effects="writes_artifact", determinism="pure",
        grounding=(), fallback=None, fallback_reason="Missing optional evidence sources simply contribute no points.",
        examples=(Example(inputs={}, outputs={"impacts": []}),), toolboxes=("autonomous", "studio", "full"),
        plain_name="Building the impact map", log_line=lambda i, o: f"Found {len(o.impacts)} candidate picture changes.")
def impact_map(ws: Workspace, inputs: EmptyIn) -> ImpactOut:
    from ...cutplan import combine
    transcript = ws.read_json("transcript")
    optional = lambda kind: ws.read_json(kind) if ws.exists(kind) else {}
    return ImpactOut(impacts=combine(transcript.get("words", []), optional("audio.emphasis"), optional("audio.prosody"),
                                     optional("audio.events"), optional("audio.saliency")))


class ProposeIn(BaseModel):
    duration: float = Field(gt=0, description="Locked cut-audio duration.")
    max_hold: float = Field(default=3.0, ge=0.5, le=6.0, description="Maximum seconds without a visible change.")


class SlotsOut(BaseModel):
    slots: list[dict[str, Any]] = Field(description="Contiguous audio-first visual slots.")


@module(id="cut.propose", version=1, summary="Propose contiguous visual slots from strong impact points and the pacing limit.",
        when_to_use="An impact map and locked audio duration are ready.", when_not_to_use="Before audio editing is complete.",
        inputs=ProposeIn, outputs=SlotsOut, requires=("impact.map",), produces=("plan.draft",), cost=Cost("fast", ("cpu",), 0.2), effects="writes_artifact", determinism="pure",
        grounding=(), fallback=None, fallback_reason="The heartbeat interval supplies deterministic cuts when impact evidence is sparse.",
        examples=(Example(inputs={"duration": 6.0}, outputs={"slots": []}),), toolboxes=("autonomous", "studio", "full"),
        plain_name="Proposing picture changes", log_line=lambda i, o: f"Proposed {len(o.slots)} visual slots.")
def propose_cuts(ws: Workspace, inputs: ProposeIn) -> SlotsOut:
    from ...cutplan import propose
    return SlotsOut(slots=propose(ws.read_json("impact.map").get("impacts", []), inputs.duration, inputs.max_hold))


class ValidateIn(ProposeIn):
    slots: list[dict[str, Any]] = Field(description="Visual slots to validate.")


class ValidateOut(BaseModel):
    valid: bool = Field(description="Whether every audio-first cut rule passes.")
    errors: list[str] = Field(description="Actionable cut-plan violations.")


@module(id="cut.validate", version=1, summary="Validate complete coverage and the maximum three-second visual heartbeat.",
        when_to_use="Before approving or applying a visual cut plan.", when_not_to_use="No slot proposal exists.",
        inputs=ValidateIn, outputs=ValidateOut, requires=(), produces=(), cost=Cost("fast", ("cpu",), 0.1), effects="none", determinism="pure",
        grounding=(), fallback=None, fallback_reason="Validation reports fixes without mutating the plan.",
        examples=(Example(inputs={"duration": 1.0, "slots": [{"start": 0, "end": 1, "impact": {"time": 0}}]}, outputs={"valid": True, "errors": []}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Checking picture changes", log_line=lambda i, o: "The cut plan is valid." if o.valid else f"The cut plan has {len(o.errors)} issue(s).")
def validate_cuts(ws: Workspace, inputs: ValidateIn) -> ValidateOut:
    from ...cutplan import validate
    errors = validate(inputs.slots, inputs.duration, inputs.max_hold)
    return ValidateOut(valid=not errors, errors=errors)


class ApplyIn(ValidateIn):
    pass


@module(id="cut.apply", version=1, summary="Validate and save approved audio-first slots as the current cut plan.",
        when_to_use="A proposed visual cut plan is approved.", when_not_to_use="The plan has unresolved validation errors.",
        inputs=ApplyIn, outputs=SlotsOut, requires=(), produces=("cutplan",), cost=Cost("instant", ("cpu",), 0.1), effects="writes_timeline", determinism="pure",
        grounding=(), fallback=None, fallback_reason="Invalid plans are rejected without changing the current cut plan.",
        examples=(Example(inputs={"duration": 1.0, "slots": [{"start": 0, "end": 1, "impact": {"time": 0}}]}, outputs={"slots": []}),),
        toolboxes=("studio", "full"), plain_name="Applying picture changes", log_line=lambda i, o: f"Applied {len(o.slots)} visual slots.")
def apply_cuts(ws: Workspace, inputs: ApplyIn) -> SlotsOut:
    from ...cutplan import validate
    errors = validate(inputs.slots, inputs.duration, inputs.max_hold)
    if errors:
        raise ValueError("; ".join(errors[:8]))
    return SlotsOut(slots=inputs.slots)


class SnapQuietIn(BaseModel):
    time: float = Field(ge=0, description="Proposed picture-change time.")
    quiet: list[tuple[float, float]] = Field(description="Measured quiet spans.")
    tolerance: float = Field(default=0.25, ge=0, le=1.0, description="Maximum permitted nudge in seconds.")


class SnapOut(BaseModel):
    time: float = Field(description="Nearest safe quiet boundary or the unchanged time.")


@module(id="cut.snap_quiet", version=1, summary="Nudge a picture change to a nearby measured quiet boundary.",
        when_to_use="A proposed cut is close to a pause and must preserve its impact.", when_not_to_use="No quiet boundary is within tolerance.",
        inputs=SnapQuietIn, outputs=SnapOut, requires=(), produces=(), cost=Cost("fast", ("cpu",), 0.02), effects="none", determinism="pure",
        grounding=(), fallback=None, fallback_reason="The original impact time is retained when no safe quiet point exists.",
        examples=(Example(inputs={"time": 1.1, "quiet": [[1.0, 1.2]]}, outputs={"time": 1.0}),), toolboxes=("autonomous", "studio", "full"),
        plain_name="Snapping a cut to quiet", log_line=lambda i, o: f"Placed the cut at {o.time:.2f} seconds.")
def snap_to_quiet(ws: Workspace, inputs: SnapQuietIn) -> SnapOut:
    from ...cutplan import snap_quiet
    return SnapOut(time=snap_quiet(inputs.time, inputs.quiet, inputs.tolerance))
