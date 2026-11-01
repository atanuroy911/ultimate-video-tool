"""Small remaining Phase 2 adapters over established functions."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class MusicIn(BaseModel):
    mood: str | None = Field(default=None, description="Known video mood or use case.")
    seed: str = Field(default="", description="Stable selection seed; empty uses project id.")


class MusicOut(BaseModel):
    track: str | None = Field(description="Bundled music track id, or null when none is installed.")


@module(id="sound.music_pick", version=1, summary="Choose a stable bundled music track for the video's mood.",
        when_to_use="Music is automatic and the video's mood is known.", when_not_to_use="The person chose music or disabled it.",
        inputs=MusicIn, outputs=MusicOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.02), effects="none", determinism="pure",
        grounding=(), fallback=None, fallback_reason="The existing picker is deterministic.", examples=(Example(inputs={"mood": "story"}, outputs={"track": None}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Choosing soundtrack music", log_line=lambda i, o: f"Chose {o.track}." if o.track else "No bundled track was available.")
def music_pick(ws: Workspace, inputs: MusicIn) -> MusicOut:
    from ...musicpick import pick
    return MusicOut(track=pick(inputs.mood, inputs.seed or ws.root.name))


class ThemeIn(BaseModel):
    name: str = Field(description="Built-in or saved theme name.")


class ThemeOut(BaseModel):
    theme: dict[str, Any] = Field(description="Complete validated composer theme.")


@module(id="timeline.theme", version=1, summary="Resolve the colours, type, captions and motion settings of a named theme.",
        when_to_use="Before composition or when the visual theme changes.", when_not_to_use="To construct a new style and palette.",
        inputs=ThemeIn, outputs=ThemeOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.02), effects="none", determinism="pure",
        grounding=(), fallback=None, fallback_reason="The existing loader validates and falls back safely.", examples=(Example(inputs={"name": "paper"}, outputs={"theme": {"name": "paper"}}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Resolving the timeline theme", log_line=lambda i, o: f"Resolved theme {o.theme.get('name', i.name)}.")
def timeline_theme(ws: Workspace, inputs: ThemeIn) -> ThemeOut:
    from ...project import load_theme
    return ThemeOut(theme=load_theme(inputs.name).model_dump(mode="json"))


class EmptyIn(BaseModel): pass


class PolishOut(BaseModel):
    suggestions: list[dict[str, Any]] = Field(description="Pending grounded one-word recognition corrections.")


@module(id="text.polish", version=1, summary="Suggest one-word recognition corrections without applying them.",
        when_to_use="The transcript may contain misheard names or terms.", when_not_to_use="For rewriting style or changing timing.",
        inputs=EmptyIn, outputs=PolishOut, requires=("transcript", "beats", "project.meta"), produces=("text.polish",), cost=Cost("slow", ("cpu",), 30.0),
        effects="external_api", determinism="external", grounding=("suggestions",), fallback=None, fallback_reason="The wrapped function preserves prior decisions and stops cleanly if AI becomes unavailable.",
        examples=(Example(inputs={}, outputs={"suggestions": []}),), toolboxes=("studio", "full"), plain_name="Checking transcript spellings",
        log_line=lambda i, o: f"Suggested {len(o.suggestions)} transcript correction(s).", native_outputs=True)
def polish(ws: Workspace, inputs: EmptyIn) -> PolishOut:
    from ...ai.polish import suggest
    from ...project import Project
    return PolishOut(suggestions=suggest(Project(ws.root.name, ws.root.parent)))


class UnderstandMediaIn(BaseModel):
    only_missing: bool = Field(default=True, description="Keep captions and tags already supplied by the person.")


class UnderstandMediaOut(BaseModel):
    result: dict[str, Any] = Field(description="Described media ids, skipped count and optional provider error.")


@module(id="understand.media", version=1, summary="Caption and tag the person's media so it can be matched to spoken sentences.",
        when_to_use="Media lacks person-supplied captions or searchable tags.", when_not_to_use="The person already described every asset.",
        inputs=UnderstandMediaIn, outputs=UnderstandMediaOut, requires=("project.meta", "media.bin"), produces=("project.meta",), cost=Cost("slow", ("cpu",), 30.0),
        effects="external_api", determinism="external", grounding=(), fallback=None, fallback_reason="Existing descriptions remain untouched when vision is unavailable.",
        examples=(Example(inputs={}, outputs={"result": {"described": [], "skipped": 0, "error": None}}),), toolboxes=("studio", "full"),
        plain_name="Understanding supplied media", log_line=lambda i, o: f"Described {len(o.result.get('described', []))} media item(s).", native_outputs=True)
def understand_media(ws: Workspace, inputs: UnderstandMediaIn) -> UnderstandMediaOut:
    from ...ai.media_tags import describe_project
    from ...project import Project
    return UnderstandMediaOut(result=describe_project(Project(ws.root.name, ws.root.parent), only_missing=inputs.only_missing))


class CopyOut(BaseModel):
    kit: dict[str, Any] = Field(description="Grounded title, description, hashtags, hook and source.")


@module(id="direct.write_copy", version=1, summary="Write grounded publishing copy with the existing rule fallback.",
        when_to_use="Final transcript needs a title, description, hashtags and hook.", when_not_to_use="Transcript corrections are unfinished.",
        inputs=EmptyIn, outputs=CopyOut, requires=("transcript", "beats"), produces=(), cost=Cost("slow", ("cpu",), 15.0), effects="external_api", determinism="external",
        grounding=("kit",), fallback=None, fallback_reason="The wrapped metadata function applies its rule fallback internally.", examples=(Example(inputs={}, outputs={"kit": {}}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Writing publishing copy", log_line=lambda i, o: f"Wrote publishing copy with {len(o.kit.get('hashtags', []))} hashtag(s).")
def write_copy(ws: Workspace, inputs: EmptyIn) -> CopyOut:
    from ...ai.publish import metadata
    from ...project import Project
    return CopyOut(kit=metadata(Project(ws.root.name, ws.root.parent)))


class CompileOut(BaseModel):
    scenes: int = Field(description="Number of compiled editable scenes.")


@module(id="timeline.compile", version=1, summary="Compile the Video Script into the editable scenes timeline.",
        when_to_use="A validated Video Script is ready for the ordinary scene editor.", when_not_to_use="No Video Script exists.",
        inputs=EmptyIn, outputs=CompileOut, requires=("script.video", "transcript", "beats", "project.meta"), produces=("scenes",), cost=Cost("fast", ("cpu",), 1.0),
        effects="writes_timeline", determinism="pure", grounding=(), fallback=None, fallback_reason="The existing compiler validates typed script data.", examples=(Example(inputs={}, outputs={"scenes": 1}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Compiling the video script", log_line=lambda i, o: f"Compiled {o.scenes} editable scene(s).", native_outputs=True)
def compile_timeline(ws: Workspace, inputs: EmptyIn) -> CompileOut:
    from ...project import Project
    from ...script.compile import compile_script
    from ...script.models import VideoScript
    project = Project(ws.root.name, ws.root.parent)
    scenes = compile_script(VideoScript.model_validate(ws.read_json("script.video")), project.transcript(), project.beats(), project.meta().theme)
    project.save_scenes(scenes)
    return CompileOut(scenes=len(scenes.scenes))


class SpeakSentenceIn(BaseModel):
    text: str = Field(min_length=1, description="Exact sentence to speak.")
    engine: Literal["edge", "kokoro", "mms", "clone"] = Field(default="edge", description="Installed speech engine.")
    voice: str = Field(description="Voice id accepted by the selected engine.")
    rate: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed multiplier.")


class SpeakSentenceOut(BaseModel):
    wav: str = Field(description="Project-relative synthesized wave file.")
    seconds: float = Field(description="Measured duration of the synthesized audio.")
    words: list[tuple[float, float]] = Field(description="Measured start and end time for each spoken word.")


@module(id="audio.speak_sentence", version=1, summary="Speak one sentence and measure its real duration and word timings.",
        when_to_use="A script sentence needs voice audio before visual timing is decided.", when_not_to_use="Existing recorded audio is the master.",
        inputs=SpeakSentenceIn, outputs=SpeakSentenceOut, requires=(), produces=("audio.sentence",), cost=Cost("slow", ("cpu",), 30.0),
        effects="writes_audio", determinism="external", grounding=(), fallback=None, fallback_reason="Voice engine errors are returned without inventing timing.",
        examples=(Example(inputs={"text": "Hello world.", "voice": "en-US-AriaNeural"}, outputs={"wav": "speech/sentence.wav", "seconds": 1.0, "words": [[0.0, 0.5], [0.5, 1.0]]}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Speaking one sentence", log_line=lambda i, o: f"Spoke {o.seconds:.2f} seconds.", native_outputs=True)
def speak_sentence(ws: Workspace, inputs: SpeakSentenceIn) -> SpeakSentenceOut:
    import soundfile as sf
    from ...tts import synth_sentence, word_times

    out = ws.path_for("audio.sentence")
    out.parent.mkdir(parents=True, exist_ok=True)
    synth_sentence(inputs.engine, inputs.voice, inputs.text, inputs.rate, out)
    audio, sample_rate = sf.read(str(out), dtype="float32")
    if getattr(audio, "ndim", 1) > 1:
        audio = audio.mean(axis=1)
    words = inputs.text.split()
    return SpeakSentenceOut(wav=str(out.relative_to(ws.root)).replace("\\", "/"),
                            seconds=len(audio) / float(sample_rate),
                            words=word_times(words, audio, sample_rate))


class PlanScriptIn(BaseModel):
    kind: Literal["stick", "emoji", "explainer", "infographic", "cartoon", "mixed"] = Field(default="stick", description="Visual directing style.")
    use_ai: bool = Field(default=True, description="Try the configured AI director before the rule fallback.")
    audience: str = Field(default="", description="Known target audience, without invented facts.")
    tone: str = Field(default="", description="Requested delivery tone.")
    hint: str = Field(default="", description="Optional grounded direction for the planner.")


class PlanScriptOut(BaseModel):
    how: str = Field(description="Whether AI or the deterministic rules made the script.")
    scenes: int = Field(description="Number of directed script scenes.")


@module(id="direct.plan_script", version=1, summary="Direct the Video Script with AI first and the established rule fallback.",
        when_to_use="Timed words, sentences and a draft scene plan are ready.", when_not_to_use="Audio timing or transcript facts are unsettled.",
        inputs=PlanScriptIn, outputs=PlanScriptOut, requires=("transcript", "beats", "scenes", "project.meta"), produces=("script.video",),
        cost=Cost("slow", ("cpu",), 90.0), effects="external_api", determinism="external", grounding=(), fallback=None,
        fallback_reason="The wrapped planner already falls back to its deterministic rules director.",
        examples=(Example(inputs={"kind": "stick", "use_ai": False}, outputs={"how": "rules", "scenes": 1}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Directing the Video Script", log_line=lambda i, o: f"Directed {o.scenes} scene(s) with {o.how}.", native_outputs=True)
def plan_video_script(ws: Workspace, inputs: PlanScriptIn) -> PlanScriptOut:
    from ...project import Project
    from ...script.planner import plan_script
    from ...util import write_json

    project = Project(ws.root.name, ws.root.parent)
    meta = project.meta()
    script, how = plan_script(project.transcript(), project.beats(), draft=project.scenes(), use_ai=inputs.use_ai,
                              kind=inputs.kind, language=meta.language, aspect=meta.aspect,
                              audience=inputs.audience, tone=inputs.tone, hint=inputs.hint,
                              media_ids={item.id for item in meta.media})
    write_json(ws.path_for("script.video"), script.model_dump(by_alias=True, exclude_none=True, mode="json"))
    return PlanScriptOut(how=how, scenes=len(script.scenes))


class TalkIn(BaseModel):
    message: str = Field(min_length=1, max_length=600, description="Plain-language visual direction; it cannot change spoken facts or timing.")


class TalkOut(BaseModel):
    ok: bool = Field(description="Whether the direction was safely applied.")
    reply: str = Field(description="Plain explanation of what changed or why it was refused.")


@module(id="direct.talk", version=1, summary="Apply a plain-language visual direction without changing words or speech timing.",
        when_to_use="The person asks to change how an existing directed video looks.", when_not_to_use="The request changes narration facts or audio timing.",
        inputs=TalkIn, outputs=TalkOut, requires=("transcript", "beats", "scenes", "project.meta"),
        produces=("script.video", "scenes"), cost=Cost("slow", ("cpu",), 90.0), effects="writes_timeline", determinism="external",
        grounding=(), fallback=None, fallback_reason="The existing chat director validates and refuses unsafe script changes.",
        examples=(Example(inputs={"message": "Less talking, more action."}, outputs={"ok": True, "reply": "Changed one scene."}),),
        toolboxes=("studio", "full"), plain_name="Applying director feedback", log_line=lambda i, o: o.reply, native_outputs=True)
def talk_to_director(ws: Workspace, inputs: TalkIn) -> TalkOut:
    from ...project import Project
    from ...script.chat import talk
    return TalkOut.model_validate(talk(Project(ws.root.name, ws.root.parent), inputs.message))


class VisionQAIn(BaseModel):
    video: str | None = Field(default=None, description="Optional rendered video path; otherwise inspect composition frames.")
    max_scenes: int = Field(default=0, ge=0, description="Maximum evenly sampled scenes; zero checks all.")


class VisionQAOut(BaseModel):
    report: dict[str, Any] = Field(description="Scene-level pixel and vision findings.")


@module(id="judge.vision_qa", version=1, summary="Inspect rendered scenes for cut-off, overlap, empty and unreadable visuals.",
        when_to_use="A composition or draft render is ready for visual QA.", when_not_to_use="Before scenes have been composed.",
        inputs=VisionQAIn, outputs=VisionQAOut, requires=("scenes", "beats", "transcript", "project.meta"), produces=("judge.qa",),
        cost=Cost("slow", ("gpu",), 120.0), effects="external_api", determinism="external", grounding=(), fallback=None,
        fallback_reason="The existing checker falls back from vision to deterministic pixel checks.",
        examples=(Example(inputs={"max_scenes": 3}, outputs={"report": {"bad": [], "scenes": []}}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Checking rendered pictures", log_line=lambda i, o: f"Found {len(o.report.get('bad', []))} scene(s) needing review.", native_outputs=True)
def vision_qa(ws: Workspace, inputs: VisionQAIn) -> VisionQAOut:
    from pathlib import Path
    from ...ai.vision import qa_project
    from ...project import Project
    return VisionQAOut(report=qa_project(Project(ws.root.name, ws.root.parent),
                                         video=Path(inputs.video) if inputs.video else None,
                                         max_scenes=inputs.max_scenes))


class PictureIn(BaseModel):
    word: str = Field(min_length=1, description="Grounded impact word being illustrated.")
    sentence: str = Field(min_length=1, description="Spoken sentence containing the word.")
    candidates: list[dict[str, Any]] = Field(description="Existing sticker or icon candidates.")


class PictureOut(BaseModel):
    choice: int | None = Field(description="Best candidate index, or null when vision cannot judge.")


@module(id="judge.picture", version=1, summary="Choose which existing visual candidate best fits a word in its sentence.",
        when_to_use="Two or more grounded icon or sticker candidates need a visual tie-break.", when_not_to_use="To generate a new picture or infer an unspoken claim.",
        inputs=PictureIn, outputs=PictureOut, requires=(), produces=(), cost=Cost("slow", ("gpu",), 45.0), effects="external_api", determinism="external",
        grounding=("word", "sentence"), fallback=None, fallback_reason="No choice is returned when the vision provider cannot judge.",
        examples=(Example(inputs={"word": "apple", "sentence": "Eat an apple.", "candidates": []}, outputs={"choice": None}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Judging picture candidates", log_line=lambda i, o: f"Chose candidate {o.choice}." if o.choice is not None else "Could not safely choose a picture.")
def judge_picture(ws: Workspace, inputs: PictureIn) -> PictureOut:
    from ...ai.vision import judge_picture as judge
    return PictureOut(choice=judge(inputs.word, inputs.sentence, inputs.candidates, ws.root / "picture_judge"))
