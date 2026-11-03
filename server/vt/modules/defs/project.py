"""Project capabilities exposed through the common module contract."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class InspectSourceIn(BaseModel):
    """The source file is read from the project workspace."""


class InspectSourceOut(BaseModel):
    mode: Literal["audio", "video", "talking_head"] = Field(description="Detected source mode.")
    has_picture: bool = Field(description="Whether the source contains video frames.")
    face_share: float = Field(description="Share of inspected frames with a speaking face, from 0 to 1.")
    duration: float | None = Field(description="Source duration in seconds, when known.")
    width: int | None = Field(description="Source picture width in pixels, when present.")
    height: int | None = Field(description="Source picture height in pixels, when present.")


@module(
    id="project.inspect_source", version=1,
    summary="Identify whether the source is audio, ordinary video, or a person speaking on camera.",
    when_to_use="After importing a recording or video, before choosing its visual treatment.",
    when_not_to_use="A project already has a current source.info artifact.",
    inputs=InspectSourceIn, outputs=InspectSourceOut,
    requires=("source.audio",), produces=("source.info",),
    cost=Cost("fast", ("cpu",), 2.0), effects="writes_artifact", determinism="pure",
    grounding=(), fallback=None, fallback_reason="The adapter already uses the deterministic source inspector.",
    examples=(Example(inputs={}, outputs={"mode": "audio", "has_picture": False, "face_share": 0.0,
                                        "duration": None, "width": None, "height": None}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Checking the source",
    log_line=lambda i, o: f"Found a {o.mode.replace('_', ' ')} source.",
)
def inspect_source(ws: Workspace, inputs: InspectSourceIn) -> InspectSourceOut:
    from ...source_inspect import inspect_source as inspect

    return InspectSourceOut.model_validate(inspect(ws.path_for("source.audio")))
