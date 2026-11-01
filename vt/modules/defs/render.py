"""Render and publish adapters over the existing delivery code."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class ExportIn(BaseModel):
    aspect: Literal["9:16", "1:1", "16:9"] | None = Field(default=None, description="Output shape; null uses the project shape.")
    quality: Literal["fast", "looks"] = Field(default="looks", description="Renderer quality preset.")
    gpu: bool = Field(default=True, description="Use hardware encoding when available.")
    captions: bool = Field(default=True, description="Draw word-timed captions into the video.")
    clean_voice: bool = Field(default=False, description="Apply the optional final voice cleanup.")
    short_side: int | None = Field(default=None, ge=240, le=2160, description="Optional delivery resolution short side in pixels.")


class ExportOut(BaseModel):
    video: str = Field(description="Absolute path of the finished MP4 inside the project exports folder.")
    srt: str = Field(description="Absolute path of the matching subtitle file.")
    seconds: float = Field(description="Measured render wall time in seconds.")
    duration: float = Field(description="Finished video duration in seconds.")


@module(
    id="render.export", version=1,
    summary="Render and mix a finished MP4 and subtitle file from the editable composition.",
    when_to_use="The timeline is valid and the person or recipe needs a delivery file.",
    when_not_to_use="For a cheap still or draft preview.",
    inputs=ExportIn, outputs=ExportOut, requires=("composition", "audio.cut"), produces=("render.final",),
    cost=Cost("heavy", ("gpu0", "cpu"), 120.0), effects="writes_artifact", determinism="external",
    grounding=(), fallback=None, fallback_reason="The renderer already selects hardware or software encoding as configured.",
    examples=(Example(inputs={"aspect": "9:16", "quality": "fast", "gpu": False},
                      outputs={"video": "exports/video.mp4", "srt": "exports/video.srt", "seconds": 1.0, "duration": 1.0}),),
    toolboxes=("studio", "full"), plain_name="Rendering the finished video",
    log_line=lambda i, o: f"Rendered {o.duration:.1f} seconds of finished video.", native_outputs=True,
    version_outputs=False,
)
def render_export(ws: Workspace, inputs: ExportIn) -> ExportOut:
    from ...pipeline import export
    from ...project import Project

    project = Project(ws.root.name, ws.root.parent)
    return ExportOut.model_validate(export(
        project, aspect=inputs.aspect, quality=inputs.quality, gpu=inputs.gpu,
        captions=inputs.captions, clean_voice=inputs.clean_voice, short_side=inputs.short_side,
    ))


class PublishKitIn(BaseModel):
    cover: bool = Field(default=True, description="Also render a cover image from the best finished frame.")


class PublishKitOut(BaseModel):
    kit: dict[str, Any] = Field(description="Grounded title, description, hashtags, hook and cover metadata.")


@module(
    id="publish.kit", version=1,
    summary="Create grounded title, description, hashtags and an optional cover for the finished video.",
    when_to_use="After the spoken content is final and delivery text is needed.",
    when_not_to_use="Before transcript corrections are complete.",
    inputs=PublishKitIn, outputs=PublishKitOut, requires=("transcript", "beats"), produces=("publish.kit",),
    cost=Cost("slow", ("cpu",), 15.0), effects="external_api", determinism="external",
    grounding=("kit",), fallback=None, fallback_reason="The wrapped function applies its grounded rule fallback internally when AI is unavailable.",
    examples=(Example(inputs={"cover": False}, outputs={"kit": {"title": "Video", "description": "", "hashtags": ["video"], "hook": "Video"}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Preparing the publishing kit",
    log_line=lambda i, o: f"Prepared publishing text with {len(o.kit.get('hashtags', []))} hashtag(s).",
    native_outputs=True,
)
def publish_kit(ws: Workspace, inputs: PublishKitIn) -> PublishKitOut:
    from ...ai.publish import build_kit
    from ...project import Project

    project = Project(ws.root.name, ws.root.parent)
    return PublishKitOut(kit=build_kit(project, cover=inputs.cover))


class EmptyCreditsIn(BaseModel):
    pass


class PublishCreditsOut(BaseModel):
    text: str = Field(description="Plain-text credits for non-upload media used by the project.")


@module(
    id="publish.credits", version=1, summary="Write the licence and creator credits required by non-upload project media.",
    when_to_use="Before delivery when stock or catalogue media may require attribution.", when_not_to_use="The project contains only the person's own uploads.",
    inputs=EmptyCreditsIn, outputs=PublishCreditsOut, requires=("project.meta",), produces=("publish.credits",),
    cost=Cost("instant", ("cpu",), 0.05), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing credit collector is deterministic from media provenance.",
    examples=(Example(inputs={}, outputs={"text": ""}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Writing the media credits", log_line=lambda i, o: "Wrote media credits." if o.text else "No media credits were required.",
    native_outputs=True,
)
def publish_credits(ws: Workspace, inputs: "EmptyCreditsIn") -> PublishCreditsOut:
    from ...director.stock import credits_text
    from ...project import Project

    text = credits_text(Project(ws.root.name, ws.root.parent))
    path = ws.path_for("publish.credits")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return PublishCreditsOut(text=text)


class SnapshotIn(BaseModel):
    times: list[float] = Field(min_length=1, max_length=30, description="Frame times in composition seconds.")
    aspect: Literal["9:16", "1:1", "16:9"] | None = Field(default=None, description="Composition shape; omitted uses project shape.")
    gpu: bool = Field(default=True, description="Enable browser GPU acceleration.")


class SnapshotOut(BaseModel):
    files: list[str] = Field(description="Absolute paths of rendered PNG frames in requested order.")


@module(
    id="render.snapshot", version=1, summary="Render one or more exact composition frames as PNG files.",
    when_to_use="Inspecting selected moments or preparing a cover without rendering a video.", when_not_to_use="For every scene thumbnail; use timeline.thumbs.",
    inputs=SnapshotIn, outputs=SnapshotOut, requires=("composition", "project.meta"), produces=("render.snapshots",),
    cost=Cost("slow", ("cpu",), 15.0), effects="writes_artifact", determinism="external", grounding=(),
    fallback=None, fallback_reason="The existing renderer chooses browser GPU or software as requested.",
    examples=(Example(inputs={"times": [1.0], "aspect": "9:16"}, outputs={"files": ["snapshots/frame-0001.png"]}),),
    toolboxes=("studio", "full"), plain_name="Rendering selected frames",
    log_line=lambda i, o: f"Rendered {len(o.files)} selected frame(s).", native_outputs=True, version_outputs=False,
)
def render_snapshot(ws: Workspace, inputs: SnapshotIn) -> SnapshotOut:
    from ...compose import FORMATS
    from ...project import Project
    from ...render.hyperframes import snapshot

    project = Project(ws.root.name, ws.root.parent)
    aspect = inputs.aspect or project.meta().aspect
    files = snapshot(project.comp_dir / FORMATS[aspect]["tag"], ws.path_for("render.snapshots"), inputs.times, inputs.gpu)
    return SnapshotOut(files=[str(path) for path in files])


class SilentIn(BaseModel):
    aspect: Literal["9:16", "1:1", "16:9"] | None = Field(default=None, description="Composition shape; omitted uses project shape.")
    fps: int | None = Field(default=None, ge=12, le=60, description="Frames per second; omitted uses the format default.")
    quality: Literal["fast", "looks"] = Field(default="looks", description="Existing HyperFrames quality preset.")
    gpu: bool = Field(default=True, description="Use hardware browser and video encoding when available.")
    workers: str | int = Field(default="auto", description="HyperFrames worker count or auto.")


class SilentOut(BaseModel):
    video: str = Field(description="Absolute path of the rendered silent MP4.")


@module(
    id="render.silent", version=1, summary="Render the current composition to a silent H.264 MP4.",
    when_to_use="A director needs picture-only output before final audio mixing.", when_not_to_use="A finished delivery file is required; use render.export.",
    inputs=SilentIn, outputs=SilentOut, requires=("composition", "project.meta"), produces=("render.silent",),
    cost=Cost("heavy", ("gpu0", "cpu"), 90.0), effects="writes_artifact", determinism="external", grounding=(),
    fallback=None, fallback_reason="The existing renderer retries CPU automatically when GPU rendering fails.",
    examples=(Example(inputs={"aspect": "9:16", "quality": "fast", "gpu": False}, outputs={"video": "exports/module-silent.mp4"}),),
    toolboxes=("studio", "full"), plain_name="Rendering the silent video",
    log_line=lambda i, o: "Rendered the silent video.", native_outputs=True, version_outputs=False,
)
def silent(ws: Workspace, inputs: SilentIn) -> SilentOut:
    from ...compose import FORMATS
    from ...project import Project
    from ...render.hyperframes import render_silent

    project = Project(ws.root.name, ws.root.parent)
    aspect = inputs.aspect or project.meta().aspect
    fmt = FORMATS[aspect]
    path = render_silent(project.comp_dir / fmt["tag"], ws.path_for("render.silent"), fps=inputs.fps or fmt["fps"],
                         quality=inputs.quality, gpu=inputs.gpu, workers=inputs.workers)
    return SilentOut(video=str(path))


class PreviewIn(BaseModel):
    aspect: Literal["9:16", "1:1", "16:9"] | None = Field(default=None, description="Composition shape; omitted uses project shape.")
    fps: int = Field(default=15, ge=12, le=30, description="Low preview frame rate.")
    gpu: bool = Field(default=True, description="Use browser GPU acceleration when available.")


class PreviewOut(BaseModel):
    video: str = Field(description="Absolute path of the low-cost preview MP4.")


@module(id="render.preview", version=1, summary="Render the current composition with the established fast low-frame-rate preset.",
        when_to_use="Reviewing direction before an expensive delivery render.", when_not_to_use="For final delivery quality.",
        inputs=PreviewIn, outputs=PreviewOut, requires=("composition", "project.meta"), produces=("render.preview",),
        cost=Cost("slow", ("cpu",), 30.0), effects="writes_artifact", determinism="external", grounding=(), fallback=None,
        fallback_reason="The existing renderer retries software paths when hardware is unavailable.",
        examples=(Example(inputs={"aspect": "9:16"}, outputs={"video": "exports/module-preview.mp4"}),),
        toolboxes=("studio", "full"), plain_name="Rendering a preview", log_line=lambda i, o: "Rendered the review preview.", native_outputs=True, version_outputs=False)
def preview(ws: Workspace, inputs: PreviewIn) -> PreviewOut:
    from ...compose import FORMATS
    from ...project import Project
    from ...render.hyperframes import render_silent
    project = Project(ws.root.name, ws.root.parent)
    aspect = inputs.aspect or project.meta().aspect
    path = render_silent(project.comp_dir / FORMATS[aspect]["tag"], ws.path_for("render.preview"),
                         fps=inputs.fps, quality="fast", gpu=inputs.gpu, workers="auto")
    return PreviewOut(video=str(path))
