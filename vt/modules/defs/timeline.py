"""Timeline presentation adapters over existing composer helpers."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class CaptionsIn(BaseModel):
    words_per_line: int = Field(default=6, ge=1, le=12, description="Maximum spoken words in one caption chunk.")
    max_chars: int = Field(default=42, ge=8, le=120, description="Maximum visible characters in one caption chunk.")
    highlight_ids: list[str] = Field(default_factory=list, description="Grounded word ids that receive highlight styling.")


class CaptionsOut(BaseModel):
    chunks: list[dict[str, Any]] = Field(description="Word-timed caption chunks consumed by the composer.")
    srt: str = Field(description="Equivalent SubRip subtitle document.")


@module(
    id="timeline.captions", version=1, summary="Build readable word-timed caption chunks and matching SubRip subtitles.",
    when_to_use="Preparing captions after the final transcript and cuts are stable.", when_not_to_use="Captions are disabled for this output.",
    inputs=CaptionsIn, outputs=CaptionsOut, requires=("transcript",), produces=(),
    cost=Cost("instant", ("cpu",), 0.1), effects="none", determinism="pure", grounding=("chunks",),
    fallback=None, fallback_reason="The existing caption chunker is deterministic.",
    examples=(Example(inputs={}, outputs={"chunks": [], "srt": ""}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Building the captions", log_line=lambda i, o: f"Built {len(o.chunks)} caption chunk(s).",
)
def captions(ws: Workspace, inputs: CaptionsIn) -> CaptionsOut:
    from ...compose.composer import build_caption_chunks, to_srt
    from ...schema import Transcript

    words = [word for word in Transcript.model_validate(ws.read_json("transcript")).words if not word.cut]
    chunks = build_caption_chunks(words, inputs.words_per_line, inputs.max_chars, set(inputs.highlight_ids))
    return CaptionsOut(chunks=chunks, srt=to_srt(chunks))


class MotionIn(BaseModel):
    composition: dict[str, Any] = Field(description="Resolved composition data containing scenes and elements.")
    level: Literal["auto", "subtle", "off"] = Field(default="auto", description="Requested motion intensity.")
    seed: str = Field(default="", description="Stable selection seed; empty uses the project id.")


class MotionOut(BaseModel):
    composition: dict[str, Any] = Field(description="Composition with deterministic entrance, transition and scene-move recipes.")


@module(
    id="timeline.motion", version=1, summary="Apply deterministic shotcraft entrances, transitions and camera moves to a composition.",
    when_to_use="Resolved scenes need varied motion before rendering.", when_not_to_use="Motion is off or already hand-directed.",
    inputs=MotionIn, outputs=MotionOut, requires=(), produces=(), cost=Cost("fast", ("cpu",), 0.2),
    effects="none", determinism="seeded", grounding=(), fallback=None, fallback_reason="The existing seeded motion engine is deterministic.",
    examples=(Example(inputs={"composition": {"scenes": []}}, outputs={"composition": {"scenes": [], "motion": "auto"}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Adding timeline motion",
    log_line=lambda i, o: f"Applied {i.level} motion to {len(o.composition.get('scenes', []))} scene(s).",
)
def motion(ws: Workspace, inputs: MotionIn) -> MotionOut:
    from ...compose.motion import apply

    return MotionOut(composition=apply(deepcopy(inputs.composition), inputs.level, inputs.seed or ws.root.name))


class ContrastIn(BaseModel):
    media_id: str = Field(description="Project media id used behind text.")
    aspect: Literal["9:16", "1:1", "16:9"] = Field(default="9:16", description="Target frame shape.")
    layout: str = Field(default="stack", description="Scene layout controlling the text zone.")
    start: float = Field(default=0.0, ge=0, description="Scene start in output seconds.")
    end: float | None = Field(default=None, ge=0, description="Scene end in output seconds.")
    media_start: float = Field(default=0.0, ge=0, description="Trim start inside the media in seconds.")


class ContrastOut(BaseModel):
    scrim: dict[str, Any] = Field(description="Ink and scrim treatment meeting the existing contrast policy.")


@module(
    id="timeline.contrast", version=1, summary="Choose readable ink and the lightest sufficient scrim over project media.",
    when_to_use="Text or captions sit over an image or video backdrop.", when_not_to_use="The background is a theme colour with known contrast.",
    inputs=ContrastIn, outputs=ContrastOut, requires=("project.meta", "media.bin"), produces=(),
    cost=Cost("fast", ("cpu",), 3.0), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="Missing media returns the existing neutral scrim.",
    examples=(Example(inputs={"media_id": "photo"}, outputs={"scrim": {"kind": "none"}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Checking text contrast",
    log_line=lambda i, o: f"Selected {o.scrim.get('kind', 'no')} contrast treatment for {i.media_id}.",
)
def contrast(ws: Workspace, inputs: ContrastIn) -> ContrastOut:
    from ...director.contrast import decide_for_media
    from ...project import Project

    project = Project(ws.root.name, ws.root.parent)
    result = decide_for_media(project, inputs.media_id, inputs.aspect, inputs.layout, inputs.start, inputs.end, inputs.media_start)
    return ContrastOut(scrim=result.model_dump(mode="json"))


class ValidateTimelineIn(BaseModel):
    check_icons: bool = Field(default=False, description="Also verify icon ids against the installed icon catalogue.")


class ValidateTimelineOut(BaseModel):
    valid: bool = Field(description="Whether the current scenes satisfy all semantic checks.")
    problems: list[str] = Field(description="Actionable scene, beat, word, icon and media validation errors.")


@module(
    id="timeline.validate", version=1, summary="Check scene coverage, order, word anchors, icons and media against the transcript.",
    when_to_use="After planning or editing scenes and before composition.", when_not_to_use="No scene plan exists yet.",
    inputs=ValidateTimelineIn, outputs=ValidateTimelineOut, requires=("scenes", "transcript", "beats", "project.meta"), produces=(),
    cost=Cost("fast", ("cpu",), 0.5), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing semantic validator returns actionable errors.",
    examples=(Example(inputs={}, outputs={"valid": True, "problems": []}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Checking the timeline", log_line=lambda i, o: "The timeline is valid." if o.valid else f"Found {len(o.problems)} timeline problem(s).",
)
def validate_timeline(ws: Workspace, inputs: ValidateTimelineIn) -> ValidateTimelineOut:
    from ...project import Project
    from ...schema import validate_scenes

    project = Project(ws.root.name, ws.root.parent)
    scenes = project.scenes()
    if scenes is None:
        raise ValueError("the project has no scenes")
    icons = None
    if inputs.check_icons:
        from ...visuals.icons import all_names
        icons = set(all_names())
    media_ids = {item.id for item in project.meta().media}
    problems = validate_scenes(scenes, project.transcript(), project.beats(), icons, media_ids)
    return ValidateTimelineOut(valid=not problems, problems=problems)


class HeartbeatIn(BaseModel):
    aspect: Literal["9:16", "1:1", "16:9"] | None = Field(default=None, description="Shape controlling the maximum still gap; defaults to project shape.")


class HeartbeatOut(BaseModel):
    added: int = Field(description="Number of grounded visual elements added to long still stretches.")
    still_scenes: list[str] = Field(description="Scene ids still exceeding the three-second visual-change rule.")


@module(
    id="timeline.heartbeat", version=1, summary="Add grounded visual changes so static scenes do not sit unchanged for over three seconds.",
    when_to_use="After scene planning and before composition.", when_not_to_use="Scenes already contain moving speaker, video, chart or character visuals.",
    inputs=HeartbeatIn, outputs=HeartbeatOut, requires=("scenes", "transcript", "beats", "project.meta"), produces=("scenes",),
    cost=Cost("fast", ("cpu",), 1.0), effects="writes_timeline", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing heartbeat uses only grounded transcript terms and known visuals.",
    examples=(Example(inputs={"aspect": "9:16"}, outputs={"added": 0, "still_scenes": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Keeping the picture moving",
    log_line=lambda i, o: f"Added {o.added} grounded visual change(s); {len(o.still_scenes)} scene(s) remain still.",
    native_outputs=True,
)
def heartbeat(ws: Workspace, inputs: HeartbeatIn) -> HeartbeatOut:
    from ...director.heartbeat import add_heartbeats, still_scenes
    from ...project import Project

    project = Project(ws.root.name, ws.root.parent)
    scenes = project.scenes()
    if scenes is None:
        raise ValueError("the project has no scenes")
    transcript, beats = project.transcript(), project.beats()
    aspect = inputs.aspect or project.meta().aspect
    added = add_heartbeats(scenes, transcript, beats, aspect)
    project.save_scenes(scenes)
    return HeartbeatOut(added=added, still_scenes=still_scenes(scenes, transcript, beats, aspect))


class ThumbsIn(BaseModel):
    aspect: Literal["9:16", "1:1", "16:9"] | None = Field(default=None, description="Thumbnail shape; defaults to the project shape.")


class ThumbsOut(BaseModel):
    manifest: dict[str, Any] = Field(description="Composition hash and scene-id to thumbnail-filename mapping.")


@module(
    id="timeline.thumbs", version=1, summary="Render cached scene thumbnails for the Studio scene list.",
    when_to_use="The scene plan or theme changed and the editor needs visual thumbnails.", when_not_to_use="For delivery-quality frames.",
    inputs=ThumbsIn, outputs=ThumbsOut, requires=("scenes", "transcript", "beats", "project.meta"), produces=("timeline.thumbs",),
    cost=Cost("slow", ("cpu",), 20.0), effects="writes_artifact", determinism="external", grounding=(),
    fallback=None, fallback_reason="The existing thumbnail builder caches by composition hash.",
    examples=(Example(inputs={"aspect": "9:16"}, outputs={"manifest": {"hash": "abc", "scenes": {}}}),),
    toolboxes=("studio", "full"), plain_name="Rendering scene thumbnails",
    log_line=lambda i, o: f"Rendered {len(o.manifest.get('scenes', {}))} scene thumbnail(s).", native_outputs=True,
    version_outputs=False,
)
def thumbs(ws: Workspace, inputs: ThumbsIn) -> ThumbsOut:
    from ...project import Project
    from ...thumbs import make_thumbnails

    project = Project(ws.root.name, ws.root.parent)
    return ThumbsOut(manifest=make_thumbnails(project, inputs.aspect or project.meta().aspect))


class LayersIn(BaseModel):
    operation: Literal["get", "set", "undo", "redo"] = Field(default="get", description="Read, replace, undo or redo the layer document.")
    document: dict[str, Any] | None = Field(default=None, description="Complete tracks-and-clips document required for set.")
    duration: float | None = Field(default=None, gt=0, description="Video duration in seconds; omitted derives it from sentence beats.")


class LayersOut(BaseModel):
    document: dict[str, Any] = Field(description="Current validated layer document.")
    errors: list[str] = Field(description="Validation errors that prevented a set operation.")
    can_undo: bool = Field(description="Whether another layer undo is available.")
    can_redo: bool = Field(description="Whether another layer redo is available.")


@module(
    id="timeline.layers", version=1, summary="Read, validate, save, undo or redo editable text, media, video and audio tracks.",
    when_to_use="The person or director adds independent overlay or audio clips.", when_not_to_use="For generated scene elements owned by scenes.json.",
    inputs=LayersIn, outputs=LayersOut, requires=("project.meta",), produces=("layers",),
    cost=Cost("fast", ("cpu",), 0.3), effects="writes_timeline", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing layer validator and history provide actionable errors and recovery.",
    examples=(Example(inputs={"operation": "get"}, outputs={"document": {"v": 1, "tracks": [], "clips": []}, "errors": [], "can_undo": False, "can_redo": False}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Editing timeline layers",
    log_line=lambda i, o: f"Layer {i.operation} completed with {len(o.errors)} validation error(s).",
    native_outputs=True,
)
def layers(ws: Workspace, inputs: LayersIn) -> LayersOut:
    from ... import layers as layer_api
    from ...project import Project

    project = Project(ws.root.name, ws.root.parent)
    errors: list[str] = []
    if inputs.operation == "set":
        if inputs.document is None:
            raise ValueError("set needs a complete layer document")
        duration = inputs.duration
        if duration is None:
            beats = project.beats().beats
            duration = max((beat.end for beat in beats), default=0.1)
        document, errors = layer_api.validate(inputs.document, duration, layer_api.media_kinds(project))
        if not errors:
            layer_api.save(project, document)
    elif inputs.operation in ("undo", "redo"):
        layer_api.step(project, inputs.operation)
    if inputs.operation != "get" and not errors and project.scenes():
        from ...pipeline import compose_all
        compose_all(project)
    document = layer_api.load(project)
    state = layer_api.history(project)
    return LayersOut(document=document, errors=errors, can_undo=state["can_undo"], can_redo=state["can_redo"])


class EditSceneIn(BaseModel):
    operation: Literal["split", "split_at", "move_edge", "edit_element", "merge_next", "delete", "move_boundary", "patch", "reorder_elements", "edit_action", "add_action", "edit_cast"] = Field(
        description="Typed existing scene-edit operation.")
    scene_id: str = Field(default="", description="Target scene id for scene and action operations.")
    beat_id: str | None = Field(default=None, description="Split beat or new first beat of the following scene.")
    time: float | None = Field(default=None, ge=0, allow_inf_nan=False, description="Exact video seconds for split_at or move_edge; independent of sentence boundaries.")
    patch: dict[str, Any] = Field(default_factory=dict, description="Validated fields for scene, action or cast changes.")
    order: list[int] = Field(default_factory=list, description="Element-index order for reorder_elements.")
    index: int = Field(default=0, ge=0, description="Zero-based action or element index. edit_element accepts content, start/end seconds, x/y, scale, rotation, opacity, duplicate, delete or split in patch.")
    delete_action: bool = Field(default=False, description="Delete rather than patch the selected action.")
    cast_id: str = Field(default="", description="Cast id for edit_cast.")


class EditSceneOut(BaseModel):
    scenes: int = Field(description="Number of scenes after the edit.")


@module(
    id="timeline.edit_scene", version=2, summary="Edit any visual, character or scene, including precise splits, timing, position and content.",
    when_to_use="The person or director changes the editable scene timeline.", when_not_to_use="For rebuilding the entire plan from scratch.",
    inputs=EditSceneIn, outputs=EditSceneOut, requires=("scenes", "transcript", "beats"), produces=("scenes",),
    cost=Cost("fast", ("cpu",), 0.3), effects="writes_timeline", determinism="pure", grounding=("patch",),
    fallback=None, fallback_reason="The existing scene operations validate ids, ordering and typed scene models.",
    examples=(Example(inputs={"operation": "patch", "scene_id": "s1", "patch": {"layout": "hero"}}, outputs={"scenes": 1}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Editing a scene",
    log_line=lambda i, o: f"Applied {i.operation.replace('_', ' ')}; the timeline has {o.scenes} scene(s).", native_outputs=True,
)
def edit_scene(ws: Workspace, inputs: EditSceneIn) -> EditSceneOut:
    from ... import scene_ops
    from ...project import Project

    project = Project(ws.root.name, ws.root.parent)
    scenes = project.scenes()
    if scenes is None:
        raise ValueError("the project has no scenes")
    beats, transcript = project.beats(), project.transcript()
    from ... import editor_timing
    if inputs.operation in ("split_at", "move_edge"):
        if inputs.time is None:
            raise ValueError("Give time in video seconds")
        args = (scenes, beats, project.cuts().output_duration, inputs.scene_id, inputs.time)
        scenes = (editor_timing.split_at(*args, editor_timing.project_element_times(project)) if inputs.operation == "split_at"
                  else editor_timing.move_edge(*args))
    elif inputs.operation == "edit_element":
        scenes = editor_timing.edit_element(scenes, inputs.scene_id, inputs.index, inputs.patch, editor_timing.project_element_times(project))
    elif inputs.operation == "split":
        scenes = scene_ops.split_scene(scenes, beats, inputs.scene_id, inputs.beat_id or "")
    elif inputs.operation == "merge_next":
        scenes = scene_ops.merge_with_next(scenes, beats, inputs.scene_id)
    elif inputs.operation == "delete":
        scenes = scene_ops.delete_scene(scenes, beats, inputs.scene_id)
    elif inputs.operation == "move_boundary":
        scenes = scene_ops.move_boundary(scenes, beats, inputs.scene_id, inputs.beat_id or "")
    elif inputs.operation == "patch":
        scenes = scene_ops.patch_scene(scenes, inputs.scene_id, inputs.patch)
    elif inputs.operation == "reorder_elements":
        scenes = scene_ops.reorder_elements(scenes, inputs.scene_id, inputs.order)
    elif inputs.operation == "edit_action":
        scenes = scene_ops.edit_action(scenes, transcript, beats, inputs.scene_id, inputs.index,
                                       inputs.patch or None, inputs.delete_action)
    elif inputs.operation == "add_action":
        scenes = scene_ops.add_action(scenes, transcript, beats, inputs.scene_id, inputs.patch)
    else:
        scenes = scene_ops.edit_cast(scenes, inputs.cast_id, inputs.patch)
    from ...schema import validate_scenes
    from ...planner.catalogue import all_icon_names
    from ...pipeline import compose_all
    from ...util import write_json
    errors = validate_scenes(scenes, transcript, beats, all_icon_names(), {m.id for m in project.meta().media})
    if errors:
        raise ValueError("; ".join(errors[:12]))
    write_json(project.dir / "scenes.prev.json", project.scenes().model_dump(exclude_none=True))
    project.save_scenes(scenes)
    compose_all(project)
    return EditSceneOut(scenes=len(scenes.scenes))
