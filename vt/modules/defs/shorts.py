"""Shorts detection and slicing adapters over the existing implementation."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class HighlightsIn(BaseModel):
    count: int = Field(default=4, ge=1, le=12, description="Maximum diverse highlight candidates to return.")
    use_audio_signals: bool = Field(default=True, description="Include prosody and detected reaction sounds when available.")


class HighlightsOut(BaseModel):
    highlights: list[dict[str, Any]] = Field(description="Diverse sentence-aligned Shorts candidates with measured scores.")
    content_info: dict[str, Any] = Field(description="Detected content genre and information density.")
    total_duration: float = Field(description="Source transcript duration in seconds.")


@module(
    id="understand.highlights", version=1, summary="Find diverse sentence-aligned Shorts moments using AI plus measured-signal fallback.",
    when_to_use="A long recording should become several focused vertical shorts.", when_not_to_use="The source is already one short focused segment.",
    inputs=HighlightsIn, outputs=HighlightsOut, requires=("transcript.raw",), produces=("shorts.candidates",),
    cost=Cost("slow", ("cpu",), 30.0), effects="external_api", determinism="external", grounding=("highlights",),
    fallback=None, fallback_reason="The wrapped detector applies its rule, saliency, prosody and reaction fallback internally.",
    examples=(Example(inputs={"count": 4}, outputs={"highlights": [], "content_info": {}, "total_duration": 0}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Finding Shorts moments",
    log_line=lambda i, o: f"Found {len(o.highlights)} diverse Shorts candidate(s).",
)
def highlights(ws: Workspace, inputs: HighlightsIn) -> HighlightsOut:
    from ...shorts.detector import detect_highlights

    transcript = ws.read_json("transcript.raw")
    audio = ws.path_for("audio.cut") if inputs.use_audio_signals and ws.exists("audio.cut") else None
    sounds = (ws.read_json("audio.events").get("events", []) if inputs.use_audio_signals and ws.exists("audio.events") else None)
    return HighlightsOut.model_validate(detect_highlights(transcript, inputs.count, audio_path=audio, sound_events=sounds))


class SliceShortIn(BaseModel):
    highlight: dict[str, Any] = Field(description="Chosen grounded highlight with start_time, end_time, title and score.")
    index: int = Field(default=1, ge=1, description="One-based child number used in its stable project id.")
    run_pipeline: bool = Field(default=True, description="Prepare transcript, scenes and composition before returning.")
    aroll: Literal["auto", "on", "off"] = Field(default="auto", description="Whether sliced source video fills the child Short.")
    caption_style: str = Field(default="pop", description="Caption style assigned to the child project.")


class SliceShortOut(BaseModel):
    project_id: str = Field(description="New standalone 9:16 child project id.")
    path: str = Field(description="Absolute child project folder path.")


@module(
    id="publish.shorts_slice", version=1, summary="Materialize one highlight as a standalone vertical project with rebased words and sliced media.",
    when_to_use="A reviewed highlight should become an editable Short project.", when_not_to_use="The candidate boundaries have not been reviewed or validated.",
    inputs=SliceShortIn, outputs=SliceShortOut, requires=("transcript.raw", "project.meta"), produces=(),
    cost=Cost("heavy", ("cpu",), 120.0), effects="writes_artifact", determinism="external", grounding=("highlight",),
    fallback=None, fallback_reason="The existing slicer retries CPU video encoding and preserves a pipeline-ready child.",
    examples=(Example(inputs={"highlight": {"start_time": 0, "end_time": 30, "title": "Short"}}, outputs={"project_id": "parent-s1-short", "path": "projects/parent-s1-short"}),),
    toolboxes=("studio", "full"), plain_name="Creating an editable Short",
    log_line=lambda i, o: f"Created Short project {o.project_id}.",
)
def slice_short(ws: Workspace, inputs: SliceShortIn) -> SliceShortOut:
    from ...shorts.splitter import slice_short_project

    child = slice_short_project(ws.root.name, inputs.highlight, inputs.index, inputs.run_pipeline, inputs.aroll, inputs.caption_style)
    return SliceShortOut(project_id=child.id, path=str(child.dir))
