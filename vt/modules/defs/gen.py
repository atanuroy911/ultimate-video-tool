"""Thin modules around the existing ComfyUI client and generation path."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


def _url(value: str | None) -> str:
    if value:
        return value.rstrip("/")
    from ...server.comfy_routes import comfy_url

    return comfy_url()


class StatusIn(BaseModel):
    url: str | None = Field(default=None, description="Optional ComfyUI base URL; omitted uses Settings.")
    check_workflows: bool = Field(default=False, description="Validate workflow nodes and model filenames against the live server.")


class StatusOut(BaseModel):
    status: dict[str, Any] = Field(description="Reachability, GPU memory, queue and workflow readiness without secrets.")


@module(
    id="gen.status", version=1, summary="Report ComfyUI reachability, GPU memory, queue and optional workflow readiness.",
    when_to_use="Before scheduling generated footage or diagnosing an unavailable engine.", when_not_to_use="Between calls to a known healthy server.",
    inputs=StatusIn, outputs=StatusOut, requires=(), produces=(), cost=Cost("fast", ("net",), 3.0),
    effects="external_api", determinism="external", grounding=(), fallback=None, fallback_reason="The existing client returns a plain unavailable status without raising.",
    examples=(Example(inputs={}, outputs={"status": {"ok": False, "workflows": []}}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Checking the generation server", log_line=lambda i, o: "The generation server is ready." if o.status.get("ok") else "The generation server is unavailable.",
)
def status(ws: Workspace, inputs: StatusIn) -> StatusOut:
    from ...comfy import ComfyClient, ComfyError, list_workflows

    client = ComfyClient(_url(inputs.url))
    try:
        state = client.status()
        info = client.object_info() if inputs.check_workflows and state.get("ok") else None
        workflows = []
        for workflow in list_workflows():
            row = workflow.public()
            if info is not None:
                row["problems"] = workflow.problems(info)
                row["ready"] = not row["problems"]
            workflows.append(row)
        return StatusOut(status={**state, "workflows": workflows})
    except ComfyError as exc:
        return StatusOut(status={"ok": False, "url": client.url, "error": str(exc),
                                 "workflows": [workflow.public() for workflow in list_workflows()]})
    finally:
        client.close()


class WorkflowsOut(BaseModel):
    workflows: list[dict[str, Any]] = Field(description="Installed workflow ids, labels, versions, status, sizes and frame rates.")


class EmptyIn(BaseModel):
    pass


@module(
    id="gen.workflows", version=1, summary="List installed ComfyUI workflow manifests and supported output shapes.",
    when_to_use="Choosing a generation engine and compatible aspect before contacting the server.", when_not_to_use="Live model readiness is required; use gen.status.",
    inputs=EmptyIn, outputs=WorkflowsOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.05),
    effects="none", determinism="pure", grounding=(), fallback=None, fallback_reason="This reads pinned local workflow manifests.",
    examples=(Example(inputs={}, outputs={"workflows": []}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Listing generation workflows", log_line=lambda i, o: f"Found {len(o.workflows)} generation workflow(s).",
)
def workflows(ws: Workspace, inputs: EmptyIn) -> WorkflowsOut:
    from ...comfy import list_workflows

    return WorkflowsOut(workflows=[workflow.public() for workflow in list_workflows()])


class FreeMemoryIn(BaseModel):
    url: str | None = Field(default=None, description="Optional ComfyUI base URL; omitted uses Settings.")
    ollama_url: str | None = Field(default=None, description="Optional Ollama URL to unload only when it shares ComfyUI's machine.")


class FreeMemoryOut(BaseModel):
    ollama_models: list[str] = Field(description="Names of resident Ollama models asked to unload.")


@module(
    id="gen.free_memory", version=1, summary="Release ComfyUI caches and resident Ollama models sharing the same GPU machine.",
    when_to_use="Immediately before a memory-heavy video generation.", when_not_to_use="A generation is currently running.",
    inputs=FreeMemoryIn, outputs=FreeMemoryOut, requires=(), produces=(), cost=Cost("fast", ("comfy", "ollama"), 3.0),
    effects="external_api", determinism="external", grounding=(), fallback=None, fallback_reason="Both existing release operations are best effort.",
    examples=(Example(inputs={}, outputs={"ollama_models": []}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Freeing generation memory", log_line=lambda i, o: f"Released generation memory and {len(o.ollama_models)} Ollama model(s).",
)
def free_memory(ws: Workspace, inputs: FreeMemoryIn) -> FreeMemoryOut:
    from ...comfy import ComfyClient
    from ...comfy.gpu_share import release_ollama_models, same_machine

    url = _url(inputs.url)
    client = ComfyClient(url)
    try:
        client.free_memory()
    finally:
        client.close()
    unloaded = release_ollama_models(inputs.ollama_url) if inputs.ollama_url and same_machine(url, inputs.ollama_url) else []
    return FreeMemoryOut(ollama_models=unloaded)


class CancelIn(BaseModel):
    prompt_id: str = Field(description="ComfyUI prompt id belonging to this Video Tool request.")
    url: str | None = Field(default=None, description="Optional ComfyUI base URL; omitted uses Settings.")


class CancelOut(BaseModel):
    cancelled: bool = Field(description="Whether the targeted interrupt/dequeue request was sent.")


@module(
    id="gen.cancel", version=1, summary="Interrupt or dequeue one Video Tool ComfyUI prompt without stopping another user's job.",
    when_to_use="A generated clip is no longer needed.", when_not_to_use="The prompt already completed.",
    inputs=CancelIn, outputs=CancelOut, requires=(), produces=(), cost=Cost("fast", ("comfy",), 1.0),
    effects="external_api", determinism="external", grounding=(), fallback=None, fallback_reason="The client targets only the supplied prompt id.",
    examples=(Example(inputs={"prompt_id": "prompt-1"}, outputs={"cancelled": True}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Cancelling generated footage", log_line=lambda i, o: f"Sent cancellation for generated prompt {i.prompt_id}.",
)
def cancel(ws: Workspace, inputs: CancelIn) -> CancelOut:
    from ...comfy import ComfyClient

    client = ComfyClient(_url(inputs.url))
    try:
        client.interrupt(inputs.prompt_id)
    finally:
        client.close()
    return CancelOut(cancelled=True)


class VideoFromImageIn(BaseModel):
    media_id: str = Field(description="Project image id used as the first frame.")
    prompt: str = Field(min_length=3, max_length=600, description="Grounded description of desired motion and appearance.")
    workflow: str = Field(default="ltx23_i2v", description="Installed workflow id, such as LTX or Wan.")
    aspect: Literal["9:16", "16:9"] = Field(default="9:16", description="Generated clip shape.")
    seconds: float = Field(default=3.0, ge=1, le=8, description="Requested clip duration in seconds.")
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1, description="Optional reproducible sampler seed.")
    scene: str | None = Field(default=None, description="Optional target scene id for provenance.")
    url: str | None = Field(default=None, description="Optional ComfyUI base URL; omitted uses Settings.")


class VideoFromImageOut(BaseModel):
    media: dict[str, Any] = Field(description="Generated B-roll media-bin item.")
    record: dict[str, Any] = Field(description="Workflow, prompt, seed, timing and server provenance.")


@module(
    id="gen.video_from_image", version=1, summary="Generate a silent B-roll clip from a project still through a pinned ComfyUI workflow.",
    when_to_use="A grounded slot benefits from motion and has an approved first-frame image.", when_not_to_use="Stock, speaker footage or a still zoom can communicate the idea more cheaply.",
    inputs=VideoFromImageIn, outputs=VideoFromImageOut, requires=("project.meta", "media.bin"), produces=("project.meta", "media.bin", "gen.clips"),
    cost=Cost("heavy", ("comfy", "gpu0", "net"), 300.0), effects="external_api", determinism="external", grounding=("prompt",),
    fallback=None, fallback_reason="The director can choose a non-generated fill module when the server is unavailable.",
    engines=("video.generate",),
    examples=(Example(inputs={"media_id": "still", "prompt": "The supplied flower moves gently"}, outputs={"media": {"id": "clip"}, "record": {}}),),
    toolboxes=("studio", "full"), plain_name="Generating motion footage",
    log_line=lambda i, o: f"Generated B-roll clip {o.media.get('id', '')} with {i.workflow}.", native_outputs=True, version_outputs=False,
)
def video_from_image(ws: Workspace, inputs: VideoFromImageIn) -> VideoFromImageOut:
    from ...comfy import ComfyClient, generate_clip, load_workflow
    from ...project import Project

    project = Project(ws.root.name, ws.root.parent)
    item = next((media for media in project.meta().media if media.id == inputs.media_id and media.kind == "image"), None)
    if item is None:
        raise ValueError("choose an image from the project media bin")
    workflow = load_workflow(inputs.workflow)
    client = ComfyClient(_url(inputs.url))
    try:
        media, record = generate_clip(project, client, workflow, project.dir / item.file, inputs.prompt,
                                      aspect=inputs.aspect, seconds=inputs.seconds, seed=inputs.seed,
                                      caption=inputs.prompt[:80], scene=inputs.scene, source_media=item.id,
                                      focus=(item.fx, item.fy))
    finally:
        client.close()
    return VideoFromImageOut(media=media.model_dump(mode="json"), record=record)


class CutoutIn(BaseModel):
    media_id: str = Field(description="Project image id whose background should be removed.")


class CutoutOut(BaseModel):
    media: dict[str, Any] = Field(description="New transparent PNG media-bin item; the original remains.")
    kept: float = Field(ge=0, le=1, description="Mean retained alpha share of the picture.")


@module(
    id="gen.cutout", version=1, summary="Remove a project picture's background and add a transparent PNG while keeping the original.",
    when_to_use="A supplied subject should be layered over another visual.", when_not_to_use="For video or when the original background is meaningful.",
    inputs=CutoutIn, outputs=CutoutOut, requires=("project.meta", "media.bin"), produces=("project.meta", "media.bin"),
    cost=Cost("slow", ("gpu0", "cpu"), 30.0), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing IS-Net path reports model or subject failures explicitly.",
    examples=(Example(inputs={"media_id": "portrait"}, outputs={"media": {"id": "portrait-cutout"}, "kept": 0.5}),),
    toolboxes=("studio", "full"), plain_name="Removing the picture background",
    log_line=lambda i, o: f"Made transparent picture {o.media.get('id', '')}; kept {round(o.kept * 100)}% of the frame.",
    native_outputs=True, version_outputs=False,
)
def cutout(ws: Workspace, inputs: CutoutIn) -> CutoutOut:
    import shutil
    import tempfile
    from pathlib import Path

    from ... import cutout as remover
    from ...director.media import add_media
    from ...project import Project

    project = Project(ws.root.name, ws.root.parent)
    item = next((media for media in project.meta().media if media.id == inputs.media_id), None)
    if item is None or item.kind != "image":
        raise ValueError("choose a picture from the project media bin")
    if not remover.available():
        raise ValueError("background removal needs ONNX Runtime")
    temp = Path(tempfile.mkdtemp(prefix="vt-cutout-"))
    try:
        remover.ensure_model()
        out = temp / f"{item.id[:30]}-cutout.png"
        info = remover.cut_out(project.dir / item.file, out)
        if info["kept"] < 0.005:
            raise ValueError("no clear subject was found in this picture")
        new = add_media(project, out, caption=(item.caption + " (cutout)").strip()[:80], tags=item.tags,
                        source="cutout", credit=item.credit, licence=item.licence)
        return CutoutOut(media=new.model_dump(mode="json"), kept=info["kept"])
    finally:
        shutil.rmtree(temp, ignore_errors=True)


class FitClipIn(BaseModel):
    video: str = Field(description="Existing silent clip path.")
    seconds: float = Field(gt=0, le=30, description="Exact target slot duration.")


class FitClipOut(BaseModel):
    video: str = Field(description="Project-relative fitted silent clip.")


@module(id="gen.fit_clip", version=1, summary="Trim or gently retime a silent generated clip to an exact audio-first slot.",
        when_to_use="A generated clip must fit a locked speech slot.", when_not_to_use="Retime would exceed twenty percent; regenerate instead.",
        inputs=FitClipIn, outputs=FitClipOut, requires=(), produces=("gen.fit",), cost=Cost("fast", ("cpu",), 8.0), effects="writes_artifact", determinism="pure",
        grounding=(), fallback=None, fallback_reason="Clips outside the safe retime range are rejected.",
        examples=(Example(inputs={"video": "clip.mp4", "seconds": 3.0}, outputs={"video": "media/fitted-clip.mp4"}),),
        toolboxes=("studio", "full"), plain_name="Fitting generated footage", log_line=lambda i, o: f"Fitted generated footage to {i.seconds:.1f} seconds.", native_outputs=True)
def fit_clip(ws: Workspace, inputs: FitClipIn) -> FitClipOut:
    from pathlib import Path
    from ...aroll import video_info
    from ...util import find_tool, run
    source = Path(inputs.video)
    info = video_info(source)
    if not info or not info.get("duration"):
        raise ValueError("generated clip has no measurable duration")
    ratio = float(info["duration"]) / inputs.seconds
    if ratio < 0.8:
        raise ValueError("clip would need to be slowed by more than twenty percent")
    out = ws.path_for("gen.fit")
    out.parent.mkdir(parents=True, exist_ok=True)
    run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(source), "-an", "-vf", f"setpts={1 / ratio:.6f}*PTS",
         "-t", f"{inputs.seconds:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)])
    return FitClipOut(video=str(out.relative_to(ws.root)).replace("\\", "/"))


class VisionCheckIn(BaseModel):
    frame: str = Field(description="Generated frame path.")
    sentence: str = Field(min_length=1, description="Exact spoken sentence the frame must support.")


class VisionCheckOut(BaseModel):
    result: dict[str, Any] = Field(description="Existing focused vision-check result.")


@module(id="gen.vision_check", version=1, summary="Check whether a generated frame is readable and related to its spoken sentence.",
        when_to_use="Before accepting generated footage into the timeline.", when_not_to_use="No generated frame exists.",
        inputs=VisionCheckIn, outputs=VisionCheckOut, requires=(), produces=(), cost=Cost("slow", ("gpu",), 30.0), effects="external_api", determinism="external",
        grounding=("sentence",), fallback=None, fallback_reason="Pixel checks remain available through judge.vision_qa when vision is unavailable.",
        examples=(Example(inputs={"frame": "frame.png", "sentence": "An apple falls."}, outputs={"result": {"ok": True, "problems": []}}),),
        toolboxes=("studio", "full"), plain_name="Checking generated footage", log_line=lambda i, o: "Checked the generated frame against the spoken sentence.")
def vision_check(ws: Workspace, inputs: VisionCheckIn) -> VisionCheckOut:
    from pathlib import Path
    from ...ai.vision import check_frame
    return VisionCheckOut(result=check_frame(Path(inputs.frame), inputs.sentence))
