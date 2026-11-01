"""Remaining thin Phase 2 adapters over established project functions."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ..registry import Cost, Example, module
from ..workspace import Workspace
from .fill import Fragment, SlotIn, _fragment


class FrameIn(BaseModel):
    frame: str = Field(description="Path to an existing image frame.")


class FacesOut(BaseModel):
    faces: list[list[float]] = Field(description="Detected face boxes as x, y, width and height fractions.")


@module(id="understand.faces", version=1, summary="Detect face boxes in an existing frame with the established detector.",
        when_to_use="Framing supplied video or finding clear space around a person.", when_not_to_use="No image frame exists.",
        inputs=FrameIn, outputs=FacesOut, requires=(), produces=(), cost=Cost("fast", ("cpu",), 1.0), effects="none", determinism="pure",
        grounding=(), fallback=None, fallback_reason="An empty list safely means no face was detected.",
        examples=(Example(inputs={"frame": "frame.png"}, outputs={"faces": []}),), toolboxes=("autonomous", "studio", "full"),
        plain_name="Finding faces", log_line=lambda i, o: f"Found {len(o.faces)} face(s).")
def faces(ws: Workspace, inputs: FrameIn) -> FacesOut:
    import numpy as np
    from PIL import Image
    from ...director.media import detect_faces
    return FacesOut(faces=detect_faces(np.asarray(Image.open(inputs.frame).convert("RGB"))))


class PeopleIn(FrameIn):
    face: list[float] | None = Field(default=None, description="Optional known face box used by the fallback body mask.")
    use_model: bool = Field(default=True, description="Use the installed person segmentation model when available.")


class PeopleOut(BaseModel):
    occupied: list[str] = Field(description="Packed editable occupancy grid rows for people in the frame.")


@module(id="understand.people", version=1, summary="Measure where people occupy a frame so text can use the remaining space.",
        when_to_use="A supplied image or video frame contains a person.", when_not_to_use="The scene has no photographic frame.",
        inputs=PeopleIn, outputs=PeopleOut, requires=(), produces=(), cost=Cost("fast", ("cpu",), 2.0), effects="none", determinism="pure",
        grounding=(), fallback=None, fallback_reason="The existing helper uses a face-shaped fallback when segmentation is unavailable.",
        examples=(Example(inputs={"frame": "frame.png"}, outputs={"occupied": []}),), toolboxes=("autonomous", "studio", "full"),
        plain_name="Finding people", log_line=lambda i, o: f"Measured {len(o.occupied)} occupancy row(s).")
def people(ws: Workspace, inputs: PeopleIn) -> PeopleOut:
    import numpy as np
    from PIL import Image
    from ...people import pack, person_mask, to_grid
    rgb = np.asarray(Image.open(inputs.frame).convert("RGB"))
    return PeopleOut(occupied=pack(to_grid(person_mask(rgb, inputs.face, inputs.use_model))))


class ShotsIn(BaseModel):
    duration: float = Field(gt=0, description="Source-video duration in seconds.")


class ShotsOut(BaseModel):
    shots: list[list[float]] = Field(description="Camera-shot spans with face positions and pan endpoints.")


@module(id="understand.video_shots", version=1, summary="Find camera cuts and face-guided pan positions in the source video.",
        when_to_use="A video source needs stable A-roll framing.", when_not_to_use="The source is audio-only or a still image.",
        inputs=ShotsIn, outputs=ShotsOut, requires=("source.video",), produces=(), cost=Cost("slow", ("cpu",), 30.0), effects="none", determinism="pure",
        grounding=(), fallback=None, fallback_reason="The established tracker returns stable full-frame shots when no face is found.",
        examples=(Example(inputs={"duration": 10.0}, outputs={"shots": []}),), toolboxes=("autonomous", "studio", "full"),
        plain_name="Tracking source-video shots", log_line=lambda i, o: f"Tracked {len(o.shots)} shot(s).")
def video_shots(ws: Workspace, inputs: ShotsIn) -> ShotsOut:
    from ...aroll import shot_track
    return ShotsOut(shots=shot_track(ws.path_for("source.video"), inputs.duration))


class VisualWordIn(BaseModel):
    use_embedder: bool = Field(default=True, description="Use semantic embeddings when installed.")


class VisualWordOut(BaseModel):
    picks: dict[str, dict[str, Any]] = Field(description="Best grounded visual candidate for each selected word id.")


@module(id="understand.visual_for_word", version=1, summary="Rank grounded sticker, icon or text visuals for words in their sentences.",
        when_to_use="Timed transcript words need concrete editable visual candidates.", when_not_to_use="To generate an ungrounded image prompt.",
        inputs=VisualWordIn, outputs=VisualWordOut, requires=("transcript", "beats"), produces=(), cost=Cost("fast", ("cpu",), 5.0), effects="external_api", determinism="external",
        grounding=(), fallback=None, fallback_reason="Dictionary and rule matches remain available without embeddings or translation.",
        examples=(Example(inputs={"use_embedder": False}, outputs={"picks": {}}),), toolboxes=("autonomous", "studio", "full"),
        plain_name="Matching words to visuals", log_line=lambda i, o: f"Matched {len(o.picks)} visual word(s).")
def visual_for_word(ws: Workspace, inputs: VisualWordIn) -> VisualWordOut:
    from dataclasses import asdict
    from ...project import Project
    from ...visuals.picker import pick_visuals
    project = Project(ws.root.name, ws.root.parent)
    return VisualWordOut(picks={key: asdict(value) for key, value in pick_visuals(project.transcript(), project.beats(),
                                                                                  use_embedder=inputs.use_embedder).items()})


class TextFixIn(BaseModel):
    operation: Literal["word", "sentence", "glossary"] = Field(description="Kind of grounded transcript correction.")
    word_id: str | None = Field(default=None, description="Word id for a one-word correction or cut.")
    text: str | None = Field(default=None, description="Replacement word or corrected sentence text.")
    cut: bool | None = Field(default=None, description="Remove or restore the selected word.")
    word_ids: list[str] = Field(default_factory=list, description="Existing word ids spanned by a corrected sentence.")
    term: str | None = Field(default=None, description="Recognition term stored in the project glossary.")
    replacement: str | None = Field(default=None, description="Preferred glossary spelling.")

    @model_validator(mode="after")
    def valid_edit(self):
        if self.operation == "word" and not self.word_id:
            raise ValueError("word correction needs word_id")
        if self.operation == "sentence" and (not self.word_ids or not self.text):
            raise ValueError("sentence correction needs word_ids and text")
        if self.operation == "glossary" and (not self.term or not self.replacement):
            raise ValueError("glossary correction needs term and replacement")
        return self


class TextFixOut(BaseModel):
    edit: dict[str, Any] = Field(description="Stored correction or glossary entry.")


@module(id="text.fix", version=1, summary="Correct transcript words or sentences while preserving their measured time span.",
        when_to_use="A person confirms a recognition error or glossary spelling.", when_not_to_use="To rewrite narration or invent words.",
        inputs=TextFixIn, outputs=TextFixOut, requires=("transcript", "beats", "project.meta"), produces=("transcript", "beats"),
        cost=Cost("fast", ("cpu",), 3.0), effects="writes_timeline", determinism="pure", grounding=("word_id", "word_ids"), fallback=None,
        fallback_reason="Invalid or ungrounded edits are rejected.", examples=(Example(inputs={"operation": "word", "word_id": "w1", "text": "Codex"}, outputs={"edit": {"text": "Codex"}}),),
        toolboxes=("studio", "full"), plain_name="Correcting transcript text", log_line=lambda i, o: "Saved the grounded transcript correction.", native_outputs=True)
def text_fix(ws: Workspace, inputs: TextFixIn) -> TextFixOut:
    from ...pipeline import Pipeline
    from ...project import Project
    from ...transcript_edit import align, merge
    from ...util import read_json, write_json
    project = Project(ws.root.name, ws.root.parent)
    if inputs.operation == "glossary":
        glossary = read_json(project.glossary_path, {}) or {}
        glossary[inputs.term.strip()] = inputs.replacement.strip()
        write_json(project.glossary_path, glossary)
        edit = {inputs.term.strip(): inputs.replacement.strip()}
    else:
        path = project.dir / "edits.json"
        edits = read_json(path, {"words": {}}) or {"words": {}}
        if inputs.operation == "word":
            edit = dict(edits["words"].get(inputs.word_id, {}))
            if inputs.text is not None:
                edit["text"] = inputs.text.strip()
            if inputs.cut is not None:
                edit["cut"] = inputs.cut
            edits["words"][inputs.word_id] = edit
        else:
            current = project.transcript().by_id()
            old = [(word_id, current[word_id].text) for word_id in inputs.word_ids if word_id in current]
            changes = align(old, inputs.text)
            edits["words"] = merge(edits["words"], changes)
            edit = changes
        write_json(path, edits)
    pipeline = Pipeline(project)
    pipeline.stage_words()
    return TextFixOut(edit=edit)


class MixIn(BaseModel):
    video: str = Field(description="Silent source-video path.")
    voice: str = Field(description="Master voice-audio path.")
    duration: float = Field(gt=0, description="Final duration in seconds.")
    music: str | None = Field(default=None, description="Optional music file path.")
    music_volume: float = Field(default=0.14, ge=0, le=1, description="Music volume before voice ducking.")
    sfx: str | None = Field(default=None, description="Optional mixed sound-effects track.")
    short_side: int | None = Field(default=None, ge=240, description="Optional delivery downscale short side.")
    gpu: bool = Field(default=True, description="Try the hardware video encoder for downscaling.")
    clean_voice: bool = Field(default=False, description="Apply the established rough-recording cleanup chain.")


class MixOut(BaseModel):
    video: str = Field(description="Project-relative final mixed video path.")


@module(id="sound.mix", version=1, summary="Mix voice, ducked music and effects to social loudness and mux the final video.",
        when_to_use="A silent render and final voice track are ready.", when_not_to_use="Before edit timing is locked.",
        inputs=MixIn, outputs=MixOut, requires=(), produces=("sound.mix",), cost=Cost("slow", ("cpu",), 60.0), effects="writes_artifact", determinism="pure",
        grounding=(), fallback=None, fallback_reason="The existing mixer retries CPU encoding when GPU encoding fails.",
        examples=(Example(inputs={"video": "silent.mp4", "voice": "voice.wav", "duration": 10.0}, outputs={"video": "exports/module-mix.mp4"}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Mixing final sound", log_line=lambda i, o: "Mixed and muxed the final video.", native_outputs=True)
def sound_mix(ws: Workspace, inputs: MixIn) -> MixOut:
    from ...render.mux import mix_and_mux
    out = ws.path_for("sound.mix")
    out.parent.mkdir(parents=True, exist_ok=True)
    mix_and_mux(Path(inputs.video), Path(inputs.voice), out, duration=inputs.duration,
                music=Path(inputs.music) if inputs.music else None, music_volume=inputs.music_volume,
                sfx=Path(inputs.sfx) if inputs.sfx else None, short_side=inputs.short_side,
                gpu=inputs.gpu, clean_voice=inputs.clean_voice)
    return MixOut(video=str(out.relative_to(ws.root)).replace("\\", "/"))


class CreateProjectIn(BaseModel):
    source: str | None = Field(default=None, description="Existing recording or video path.")
    script: str | None = Field(default=None, description="Typed narration used when no recording is supplied.")
    title: str = Field(default="Untitled video", description="Project title.")
    language: str = Field(default="en", description="Narration language code.")
    aspect: Literal["9:16", "1:1", "16:9"] = Field(default="9:16", description="Delivery aspect ratio.")
    theme: str = Field(default="paper", description="Existing theme name.")
    voice_engine: str = Field(default="edge", description="Speech engine for typed narration.")
    voice: str = Field(default="en-US-AriaNeural", description="Voice id for typed narration.")
    rate: float = Field(default=1.0, ge=0.5, le=2.0, description="Typed narration speech rate.")

    @model_validator(mode="after")
    def one_source(self):
        if bool(self.source) == bool(self.script):
            raise ValueError("provide exactly one of source or script")
        return self


class ProjectOut(BaseModel):
    project_id: str = Field(description="Created project id.")
    directory: str = Field(description="Created project directory.")


@module(id="project.create", version=1, summary="Create an ordinary project from a recording, video or typed script.",
        when_to_use="Starting a new video from one local source.", when_not_to_use="For a web link; fetch it through project.fetch_link.",
        inputs=CreateProjectIn, outputs=ProjectOut, requires=(), produces=(), cost=Cost("fast", ("cpu",), 2.0), effects="writes_artifact", determinism="pure",
        grounding=(), fallback=None, fallback_reason="Invalid or missing sources are rejected before a project is created.",
        examples=(Example(inputs={"source": "voice.wav", "title": "Demo"}, outputs={"project_id": "demo", "directory": "projects/demo"}),),
        toolboxes=("studio", "full"), plain_name="Creating a project", log_line=lambda i, o: f"Created project {o.project_id}.")
def create_project(ws: Workspace, inputs: CreateProjectIn) -> ProjectOut:
    from ...project import Project
    project = (Project.create_from_script(inputs.title, inputs.script, voice_engine=inputs.voice_engine, voice=inputs.voice,
                                          rate=inputs.rate, language=inputs.language, aspect=inputs.aspect, theme=inputs.theme)
               if inputs.script else
               Project.create(inputs.title, Path(inputs.source), language=inputs.language, aspect=inputs.aspect, theme=inputs.theme))
    return ProjectOut(project_id=project.id, directory=str(project.dir))


class FetchLinkIn(BaseModel):
    url: str = Field(description="Supported public HTTPS video URL.")
    language: str = Field(default="en", description="Narration or subtitle language code.")
    title: str = Field(default="", description="Optional project title override.")
    use_subs: Literal["auto", "any", "off"] = Field(default="auto", description="Subtitle trust policy.")
    want_video: bool = Field(default=True, description="Keep source video for A-roll when available.")
    aspect: Literal["9:16", "1:1", "16:9"] = Field(default="9:16", description="Delivery aspect ratio.")


@module(id="project.fetch_link", version=1, summary="Fetch a supported public link and create an ordinary audio-first project.",
        when_to_use="The person supplies a supported public video URL.", when_not_to_use="Private, signed-in or local sources.",
        inputs=FetchLinkIn, outputs=ProjectOut, requires=(), produces=(), cost=Cost("heavy", ("network",), 180.0), effects="external_api", determinism="external",
        grounding=(), fallback=None, fallback_reason="The existing ingester validates hosts and returns actionable network errors.",
        examples=(Example(inputs={"url": "https://www.youtube.com/watch?v=example"}, outputs={"project_id": "imported", "directory": "projects/imported"}),),
        toolboxes=("studio", "full"), plain_name="Importing a video link", log_line=lambda i, o: f"Imported link as project {o.project_id}.")
def fetch_link(ws: Workspace, inputs: FetchLinkIn) -> ProjectOut:
    from ...ingest import create_project as create_from_link
    project = create_from_link(inputs.url, language=inputs.language, title=inputs.title, use_subs=inputs.use_subs,
                               want_video=inputs.want_video, aspect=inputs.aspect)
    return ProjectOut(project_id=project.id, directory=str(project.dir))


class ReviseIn(BaseModel):
    notes: str = Field(default="", max_length=2000, description="Grounded critic notes; the existing critic remains authoritative.")


class ReviseOut(BaseModel):
    changed: bool = Field(description="Whether the validated revision was better and retained.")
    scenes: int = Field(description="Number of Video Script scenes after revision.")


@module(id="direct.revise_script", version=1, summary="Revise a Video Script through the existing critic loop and keep only a better result.",
        when_to_use="A validated Video Script has grounded editor notes.", when_not_to_use="No timed transcript or script exists.",
        inputs=ReviseIn, outputs=ReviseOut, requires=("script.video", "transcript", "beats", "project.meta"), produces=("script.video",),
        cost=Cost("slow", ("cpu",), 120.0), effects="external_api", determinism="external", grounding=("notes",), fallback=None,
        fallback_reason="The existing revision loop keeps the original on failure or a lower score.",
        examples=(Example(inputs={"notes": "Keep the opening active."}, outputs={"changed": False, "scenes": 1}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Revising the Video Script", log_line=lambda i, o: f"Reviewed {o.scenes} scripted scene(s).", native_outputs=True)
def revise_script(ws: Workspace, inputs: ReviseIn) -> ReviseOut:
    from ...planner.catalogue import all_icon_names
    from ...project import Project
    from ...script.compile import to_json_schema
    from ...script.models import VideoScript
    from ...script.planner import revise
    from ...script.prompt import build_prompt
    from ...util import write_json
    project = Project(ws.root.name, ws.root.parent)
    original = VideoScript.model_validate(ws.read_json("script.video"))
    meta, tr, beats = project.meta(), project.transcript(), project.beats()
    system, _ = build_prompt(tr, beats, kind=original.kind, language=meta.language, aspect=meta.aspect,
                             hint=inputs.notes, schema=to_json_schema())
    revised = revise(original, tr, beats, system, to_json_schema(), original.kind, all_icon_names(),
                     {item.id for item in meta.media}, None, lambda f, m: None)
    changed = revised.model_dump() != original.model_dump()
    write_json(ws.path_for("script.video"), revised.model_dump(by_alias=True, exclude_none=True, mode="json"))
    return ReviseOut(changed=changed, scenes=len(revised.scenes))


class GraphicIn(SlotIn):
    scene_id: str | None = Field(default=None, description="Existing planned scene to adapt; omitted matches the slot sentence.")


@module(id="fill.graphic", version=1, summary="Adapt an existing grounded planned graphic into an editable slot fragment.",
        when_to_use="The rule or AI planner already chose a chart, list, comparison or text graphic.", when_not_to_use="No planned scene covers the slot.",
        inputs=GraphicIn, outputs=Fragment, requires=("scenes",), produces=(), cost=Cost("fast", ("cpu",), 0.2), effects="none", determinism="pure",
        grounding=(), fallback="fill.text_card", fallback_reason="The slot's spoken text remains a safe fallback.",
        examples=(Example(inputs={"slot": {"id": "sl1", "start": 0, "end": 2, "impact": {"time": 1}}}, outputs={"slot_id": "sl1", "items": [], "assets": [], "confidence": 1, "provenance": {}, "placeholder_for": None}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Placing a planned graphic", log_line=lambda i, o: f"Placed {len(o.items)} graphic item(s).")
def graphic(ws: Workspace, inputs: GraphicIn) -> Fragment:
    from ...project import Project
    scenes = Project(ws.root.name, ws.root.parent).scenes().scenes
    scene = next((s for s in scenes if s.id == inputs.scene_id), None) if inputs.scene_id else None
    scene = scene or next((s for s in scenes if inputs.slot.sentence_id in s.beats), None)
    if scene is None or not scene.elements:
        raise ValueError("no planned graphic covers this slot")
    items = [{"start": inputs.slot.start, "end": inputs.slot.end, **element.model_dump(exclude_none=True)}
             for element in scene.elements]
    return Fragment(slot_id=inputs.slot.id, items=items, confidence=1.0,
                    provenance={"module": "fill.graphic", "scene_id": scene.id,
                                "word_ids": [word.id for word in inputs.slot.words]})


class StickerIn(SlotIn):
    kind: Literal["sticker", "icon", "keyword"] = Field(default="sticker", description="Editable visual element kind.")
    visual_id: str = Field(description="Existing sticker emoji, icon or grounded keyword id.")
    label: str = Field(default="", description="Optional label copied from spoken words.")


@module(id="fill.sticker_icon", version=1, summary="Place an existing grounded sticker or icon on the slot's impact word.",
        when_to_use="Word-to-visual matching produced a concrete candidate.", when_not_to_use="The visual adds an unspoken claim.",
        inputs=StickerIn, outputs=Fragment, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.03), effects="none", determinism="pure",
        grounding=("visual_id", "label"), fallback="fill.text_card", fallback_reason="Grounded spoken text remains available.",
        examples=(Example(inputs={"visual_id": "apple", "slot": {"id": "sl1", "start": 0, "end": 2, "impact": {"time": 1}}}, outputs={"slot_id": "sl1", "items": [], "assets": [], "confidence": 1, "provenance": {}, "placeholder_for": None}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Placing a sticker or icon", log_line=lambda i, o: f"Placed a visual in slot {o.slot_id}.")
def sticker_icon(ws: Workspace, inputs: StickerIn) -> Fragment:
    spoken = " ".join(word.text for word in inputs.slot.words).casefold()
    if inputs.label and inputs.label.casefold() not in spoken:
        raise ValueError("the visual label must appear in the spoken slot")
    key = "emoji" if inputs.kind == "sticker" else "name" if inputs.kind == "icon" else "text"
    return _fragment(inputs.slot, {"type": inputs.kind, key: inputs.visual_id, "label": inputs.label,
                                   "at": inputs.slot.impact.time}, "fill.sticker_icon")


class IllustrationIn(SlotIn):
    word: str = Field(description="Spoken concept used to find existing hand-built art.")


@module(id="fill.illustration", version=1, summary="Place existing hand-built SVG art for a grounded spoken concept.",
        when_to_use="The art library contains the spoken concept.", when_not_to_use="No existing illustration matches the words.",
        inputs=IllustrationIn, outputs=Fragment, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.05), effects="none", determinism="pure",
        grounding=("word",), fallback="fill.sticker_icon", fallback_reason="Existing icons and stickers cover broader vocabulary.",
        examples=(Example(inputs={"word": "galaxy", "slot": {"id": "sl1", "start": 0, "end": 2, "impact": {"time": 1}}}, outputs={"slot_id": "sl1", "items": [], "assets": [], "confidence": 1, "provenance": {}, "placeholder_for": None}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Placing an illustration", log_line=lambda i, o: f"Placed an illustration in slot {o.slot_id}.")
def illustration(ws: Workspace, inputs: IllustrationIn) -> Fragment:
    from ...art import lookup
    spoken = " ".join(word.text for word in inputs.slot.words).casefold()
    if inputs.word.casefold() not in spoken:
        raise ValueError("illustration concept must appear in the spoken slot")
    key = lookup(inputs.word)
    if not key:
        raise ValueError("no existing illustration matches this concept")
    return _fragment(inputs.slot, {"type": "sticker", "emoji": key, "label": inputs.word,
                                   "at": inputs.slot.impact.time}, "fill.illustration")


class CharacterIn(SlotIn):
    scene_id: str = Field(description="Existing Video Script scene id.")


@module(id="fill.character_scene", version=1, summary="Place an existing directed character scene into an audio-first slot.",
        when_to_use="A validated Video Script already directs this spoken moment.", when_not_to_use="No character script scene covers the slot.",
        inputs=CharacterIn, outputs=Fragment, requires=("script.video",), produces=(), cost=Cost("fast", ("cpu",), 0.2), effects="none", determinism="pure",
        grounding=(), fallback="fill.graphic", fallback_reason="The ordinary planned graphic remains editable and grounded.",
        examples=(Example(inputs={"scene_id": "s1", "slot": {"id": "sl1", "start": 0, "end": 2, "impact": {"time": 1}}}, outputs={"slot_id": "sl1", "items": [], "assets": [], "confidence": 1, "provenance": {}, "placeholder_for": None}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Placing a character scene", log_line=lambda i, o: f"Placed a character scene in slot {o.slot_id}.")
def character_scene(ws: Workspace, inputs: CharacterIn) -> Fragment:
    from ...script.models import VideoScript
    script = VideoScript.model_validate(ws.read_json("script.video"))
    scene = next((scene for scene in script.scenes if scene.id == inputs.scene_id), None)
    if scene is None:
        raise ValueError("character scene is not in the Video Script")
    return _fragment(inputs.slot, {"type": "character_scene", "scene": scene.model_dump(by_alias=True, exclude_none=True),
                                   "cast": [cast.model_dump(exclude_none=True) for cast in script.cast],
                                   "sets": [place.model_dump(exclude_none=True) for place in script.sets]}, "fill.character_scene")


class StockIn(SlotIn):
    query: str = Field(min_length=1, max_length=80, description="Grounded stock-search phrase.")
    kind: Literal["image", "video", "clipart"] = Field(default="image", description="Requested stock asset kind.")
    aspect: Literal["9:16", "1:1", "16:9"] = Field(default="9:16", description="Required framing orientation.")
    provider: Literal["pexels", "pixabay"] | None = Field(default=None, description="Optional configured provider.")
    limit: int = Field(default=6, ge=1, le=12, description="Maximum candidates to return.")


class StockOut(BaseModel):
    fragment: Fragment = Field(description="Placeholder fragment grounded to the requested stock search.")
    candidates: list[dict[str, Any]] = Field(description="Licensed provider results for explicit selection.")


@module(id="fill.stock", version=1, summary="Search configured stock providers and return licensed candidates for a grounded slot.",
        when_to_use="Spoken words name a concrete subject and stock keys are configured.", when_not_to_use="A person's own media already fits better.",
        inputs=StockIn, outputs=StockOut, requires=(), produces=(), cost=Cost("slow", ("network",), 15.0), effects="external_api", determinism="external",
        grounding=("query",), fallback="fill.text_card", fallback_reason="The spoken phrase remains grounded when providers are unavailable.",
        examples=(Example(inputs={"query": "apple", "slot": {"id": "sl1", "start": 0, "end": 2, "impact": {"time": 1}}}, outputs={"fragment": {"slot_id": "sl1", "items": [], "assets": [], "confidence": 0.5, "provenance": {}, "placeholder_for": None}, "candidates": []}),),
        toolboxes=("studio", "full"), plain_name="Searching stock media", log_line=lambda i, o: f"Found {len(o.candidates)} stock candidate(s).")
def stock(ws: Workspace, inputs: StockIn) -> StockOut:
    from ...director.stock import search
    spoken = " ".join(word.text for word in inputs.slot.words).casefold()
    if inputs.slot.words and inputs.query.casefold() not in spoken:
        raise ValueError("stock query must appear in the spoken slot")
    candidates = search(inputs.query, kind=inputs.kind, aspect=inputs.aspect, provider=inputs.provider, limit=inputs.limit)
    fragment = _fragment(inputs.slot, {"type": "stock_pending", "query": inputs.query}, "fill.stock", confidence=0.5)
    return StockOut(fragment=fragment, candidates=candidates)


class DispatchIn(BaseModel):
    group_id: str = Field(description="Existing connected social-account group id.")
    title: str = Field(min_length=1, description="Grounded post title.")
    description: str = Field(default="", description="Grounded post description.")
    hashtags: list[str] = Field(default_factory=list, description="Grounded hashtags without credentials.")
    video_filename: str | None = Field(default=None, description="Exported project MP4 filename; omitted uses the latest.")
    scheduled_for: str | None = Field(default=None, description="Optional ISO timestamp with time zone.")
    confirmed: bool = Field(default=False, description="Explicit human confirmation that real posting may be queued.")


class DispatchOut(BaseModel):
    batch_id: str = Field(description="Persistent publishing batch id.")
    total_tasks: int = Field(description="Number of account-specific publishing tasks queued.")


@module(id="publish.dispatch", version=1, summary="Queue an explicitly confirmed export for connected social accounts.",
        when_to_use="A person approved the final export, accounts, copy and schedule.", when_not_to_use="During autonomous creation or without explicit posting confirmation.",
        inputs=DispatchIn, outputs=DispatchOut, requires=("project.meta", "render.final"), produces=(), cost=Cost("heavy", ("network",), 300.0),
        effects="external_post", determinism="external", grounding=("title", "description", "hashtags"), fallback=None,
        fallback_reason="Posting is refused unless the confirmed field is true.",
        examples=(Example(inputs={"group_id": "grp1", "title": "Video", "confirmed": True}, outputs={"batch_id": "batch1", "total_tasks": 1}),),
        toolboxes=("full",), plain_name="Queuing social publishing", log_line=lambda i, o: f"Queued {o.total_tasks} publishing task(s).")
def publish_dispatch(ws: Workspace, inputs: DispatchIn) -> DispatchOut:
    if not inputs.confirmed:
        raise ValueError("real posting requires explicit human confirmation")
    from ...server.social_routes import DispatchInput, dispatch
    body = DispatchInput(group_id=inputs.group_id, title=inputs.title, description=inputs.description,
                         hashtags=inputs.hashtags, video_filename=inputs.video_filename,
                         scheduled_for=inputs.scheduled_for, platform_overrides={})
    return DispatchOut.model_validate(dispatch(ws.root.name, body))


class PlaceIn(BaseModel):
    fragments: list[Fragment] = Field(description="Validated audio-first fragments to place as editable clips.")


class PlaceOut(BaseModel):
    placed: int = Field(description="Number of editable layer clips placed.")
    skipped: int = Field(description="Renderer-specific items skipped instead of being flattened.")


@module(id="timeline.place", version=1, summary="Place fragment text and media as validated editable timeline-layer clips.",
        when_to_use="Audio-first fill modules have returned ordinary fragments.", when_not_to_use="For renderer-private or unvalidated data.",
        inputs=PlaceIn, outputs=PlaceOut, requires=("project.meta",), produces=("layers",), cost=Cost("fast", ("cpu",), 1.0),
        effects="writes_timeline", determinism="pure", grounding=(), fallback=None,
        fallback_reason="Unsupported fragment items are skipped and remain available for explicit scene compilation.",
        examples=(Example(inputs={"fragments": []}, outputs={"placed": 0, "skipped": 0}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Placing timeline fragments", log_line=lambda i, o: f"Placed {o.placed} editable clip(s).", native_outputs=True)
def timeline_place(ws: Workspace, inputs: PlaceIn) -> PlaceOut:
    from ... import layers
    from ...project import Project
    project = Project(ws.root.name, ws.root.parent)
    document = layers.load(project)
    media = {item.id: item.kind for item in (*project.meta().media, *project.meta().sounds)}
    placed = skipped = 0
    for fragment in inputs.fragments:
        for item in fragment.items:
            kind = item.get("type")
            clip = None
            if kind in ("text", "text_card") and item.get("text"):
                clip = {"type": "text", "text": item["text"], "x": item.get("x", 0.5), "y": item.get("y", 0.35)}
            elif kind in ("media", "speaker") and item.get("media") in media:
                clip = {"type": "media", "media": item["media"], "fit": item.get("fit", "cover"),
                        "anim": item.get("anim", "none"), "x": item.get("x", 0.5), "y": item.get("y", 0.5)}
            if clip is None:
                skipped += 1
                continue
            placed += 1
            track_id = f"frag{len(document['tracks']) + 1}"
            document["tracks"].append({"id": track_id, "name": f"Moment {fragment.slot_id}", "kind": "visual"})
            document["clips"].append({"id": f"clip{len(document['clips']) + 1}", "track": track_id,
                                      "start": item["start"], "dur": item["end"] - item["start"], **clip})
    duration = max((word.end for word in project.transcript().kept()), default=1.0) + 0.5
    clean, errors = layers.validate(document, duration, media)
    if errors:
        raise ValueError("; ".join(errors[:6]))
    layers.save(project, clean)
    return PlaceOut(placed=placed, skipped=skipped)


class DirectionIn(BaseModel):
    goal: str = Field(default="", description="Grounded communication goal.")
    audience: str = Field(default="", description="Intended audience.")
    tone: str = Field(default="", description="Delivery tone.")
    style: str = Field(default="", description="Visual style bible summary.")
    pacing: list[dict[str, Any]] = Field(default_factory=list, description="Pacing curve sections and intensity.")
    budget_seconds: float | None = Field(default=None, ge=0, description="Optional execution-time budget.")
    preferences: dict[str, Any] = Field(default_factory=dict, description="Medium and visual preferences.")


class DirectionOut(BaseModel):
    direction: dict[str, Any] = Field(description="Persisted director decisions.")


@module(id="direct.set_direction", version=1, summary="Persist the director's goal, audience, tone, style, pacing and budget decisions.",
        when_to_use="Before planning when the creative direction is known.", when_not_to_use="To infer facts absent from the source.",
        inputs=DirectionIn, outputs=DirectionOut, requires=(), produces=("direction",), cost=Cost("instant", ("cpu",), 0.03), effects="writes_artifact", determinism="pure",
        grounding=("goal", "audience", "tone", "style"), fallback=None, fallback_reason="Empty fields allow use-case profiles to supply defaults later.",
        examples=(Example(inputs={"goal": "Explain gravity", "audience": "students"}, outputs={"direction": {"goal": "Explain gravity", "audience": "students"}}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Setting creative direction", log_line=lambda i, o: "Recorded the creative direction.")
def set_direction(ws: Workspace, inputs: DirectionIn) -> DirectionOut:
    return DirectionOut(direction=inputs.model_dump(mode="json"))


class PromptIn(BaseModel):
    slot: dict[str, Any] = Field(description="Audio-first slot containing only grounded spoken words and constraints.")
    style: str = Field(default="cinematic", description="Requested visual style tags.")


class PromptOut(BaseModel):
    prompt: str = Field(description="Grounded visual-generation prompt.")
    source: Literal["ai", "rules"] = Field(description="Whether AI or deterministic fallback wrote it.")


@module(id="direct.write_prompt", version=1, summary="Write a visual-generation prompt using only words and constraints from one slot.",
        when_to_use="A grounded slot is approved for image or video generation.", when_not_to_use="The slot can be filled with supplied or existing art.",
        inputs=PromptIn, outputs=PromptOut, requires=(), produces=(), cost=Cost("slow", ("cpu",), 20.0), effects="external_api", determinism="external",
        grounding=("slot",), fallback=None, fallback_reason="The deterministic fallback joins the spoken words with safe style tags.",
        examples=(Example(inputs={"slot": {"words": [{"text": "red apple"}]}, "style": "paper cutout"}, outputs={"prompt": "red apple, paper cutout", "source": "rules"}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Writing a visual prompt", log_line=lambda i, o: f"Wrote a grounded visual prompt with {o.source}.")
def write_prompt(ws: Workspace, inputs: PromptIn) -> PromptOut:
    words = " ".join(str(word.get("text", "")) for word in inputs.slot.get("words", [])).strip()
    if not words:
        raise ValueError("slot has no grounded spoken words")
    fallback = f"{words}, {inputs.style}, no text, silent visual"[:600]
    try:
        from ...ai import complete_json
        schema = {"type": "object", "properties": {"prompt": {"type": "string", "maxLength": 600}}, "required": ["prompt"]}
        result = complete_json("Write one visual prompt using ONLY these spoken words: " + words + "\nStyle: " + inputs.style,
                               schema, max_tokens=180, timeout=120, temperature=0.2)
        prompt = str(result["prompt"]).strip()
        if not prompt:
            raise ValueError("empty prompt")
        return PromptOut(prompt=prompt, source="ai")
    except Exception:
        return PromptOut(prompt=fallback, source="rules")
