"""Canonical Phase 2 adapters over existing project, audio, ASR and text code."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace
from .pipeline_stages import StageIn, StageOut


_ALIASES = (
    ("audio.speak_script", "voice", ("script.text",), ("script.text", "source.audio"), "Speak a typed script one sentence at a time."),
    ("audio.clean", "preprocess", ("source.audio",), ("audio.master", "audio.asr"), "Clean and normalize the audio before any editing decision."),
    ("audio.find_silences", "silence", ("audio.asr",), ("audio.silences",), "Find pauses in the cleaned audio at the project's pace."),
    ("asr.transcribe", "asr", ("audio.asr",), ("transcript.raw",), "Turn speech into timed words using the project's configured recognizer."),
    ("audio.cut", "cuts", ("audio.master", "transcript.raw"), ("audio.retakes", "audio.cuts", "audio.cut"), "Apply pauses, fillers, retakes, tightening and hand edits to the audio."),
    ("audio.events", "sounds", ("audio.cut",), ("audio.events",), "Find laughter, applause, music and other audible events."),
    ("text.build_transcript", "words", ("transcript.raw", "audio.cuts"), ("transcript", "beats"), "Build stable word ids and sentence beats in cut-audio time."),
    ("audio.tighten", "tighten", ("transcript.raw", "audio.cuts", "beats"), ("audio.tighten",), "Drop low-value sentences when the project requests a shorter video."),
    ("understand.context", "context", ("transcript", "beats"), ("context",), "Understand the topic, mood, named things, sentence roles and facts."),
    ("direct.plan_scenes", "plan", ("transcript", "beats", "context"), ("scenes",), "Plan scenes from the spoken words using AI first and the rule director as fallback."),
    ("timeline.compose", "compose", ("scenes",), ("composition",), "Write the editable HTML composition in every supported shape."),
)


def _register_alias(module_id: str, stage: str, requires: tuple[str, ...],
                    produces: tuple[str, ...], summary: str) -> None:
    @module(
        id=module_id, version=1, summary=summary,
        when_to_use=f"When the director needs the existing {stage} pipeline capability by itself.",
        when_not_to_use="When the same current artifacts already exist and are not stale.",
        inputs=StageIn, outputs=StageOut, requires=requires, produces=produces,
        cost=Cost("slow", ("cpu",), 30.0),
        effects="writes_timeline" if stage in ("plan", "compose") else "writes_artifact",
        determinism="external" if stage in ("voice", "asr", "context", "plan") else "pure",
        grounding=(), fallback=None,
        fallback_reason="This adapter calls the existing stage, including its established fallback behavior.",
        examples=(Example(inputs={"force": False}, outputs={"stage": stage}),),
        toolboxes=("autonomous", "studio", "full"), plain_name=summary.rstrip("."),
        log_line=lambda i, o: f"Completed the {o.stage} stage.", native_outputs=True,
    )
    def run_stage(ws: Workspace, inputs: StageIn) -> StageOut:
        from ...pipeline import Pipeline
        from ...project import Project

        pipeline = getattr(ws, "pipeline", None) or Pipeline(Project(ws.root.name, ws.root.parent))
        getattr(pipeline, f"stage_{stage}")(inputs.force)
        return StageOut(stage=stage)


for _module_id, _stage, _requires, _produces, _summary in _ALIASES:
    _register_alias(_module_id, _stage, _requires, _produces, _summary)


class DetectLanguageIn(BaseModel):
    text: str = Field(default="", description="Spoken or written text; empty uses the project source audio.")


class DetectLanguageOut(BaseModel):
    language: Literal["bn", "en"] = Field(description="Detected language; Banglish is reported as Bangla.")
    confidence: float = Field(description="Detector confidence from 0 to 1; text rules return 1.")


@module(
    id="audio.detect_language", version=1,
    summary="Detect Bangla or English; Banglish counts as Bangla.",
    when_to_use="Before recognition or voice selection when the person did not choose a language.",
    when_not_to_use="When the project already has a confirmed language.",
    inputs=DetectLanguageIn, outputs=DetectLanguageOut, requires=(), produces=(),
    cost=Cost("fast", ("cpu",), 3.0), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing detector has deterministic text rules and an audio model fallback.",
    examples=(Example(inputs={"text": "আমি আজকে বাজারে যাব"}, outputs={"language": "bn", "confidence": 1.0}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Detecting the language",
    log_line=lambda i, o: f"Detected {o.language} speech.",
)
def detect_language(ws: Workspace, inputs: DetectLanguageIn) -> DetectLanguageOut:
    from ... import langdetect

    if inputs.text.strip():
        return DetectLanguageOut(language=langdetect.from_text(inputs.text), confidence=1.0)
    language, confidence = langdetect.from_audio(ws.path_for("source.audio"), allowed=["bn", "en"])
    return DetectLanguageOut(language=language, confidence=confidence)


class PauseSentencesIn(BaseModel):
    punctuation: str = Field(default=".!?।", description="Characters that always end a sentence.")


class PauseSentencesOut(BaseModel):
    boundaries: list[int] = Field(description="Zero-based word indexes that end sentences.")


@module(
    id="audio.pause_sentences", version=1,
    summary="Find sentence endings from punctuation and natural pauses.",
    when_to_use="Recognition returned an unpunctuated stream of timed words.",
    when_not_to_use="The transcript already has reliable sentence boundaries.",
    inputs=PauseSentencesIn, outputs=PauseSentencesOut, requires=("transcript.raw",), produces=(),
    cost=Cost("instant", ("cpu",), 0.05), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing pause splitter is deterministic.",
    examples=(Example(inputs={}, outputs={"boundaries": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Finding sentence pauses",
    log_line=lambda i, o: f"Found {len(o.boundaries)} sentence ending(s).",
)
def pause_sentences(ws: Workspace, inputs: PauseSentencesIn) -> PauseSentencesOut:
    from ...pausesplit import boundaries

    raw = ws.read_json("transcript.raw")
    return PauseSentencesOut(boundaries=boundaries(raw.get("words", []), inputs.punctuation))


class RankSentencesIn(BaseModel):
    sentences: list[str] = Field(description="Sentence texts in spoken order.")
    keep: int = Field(default=3, ge=0, description="Maximum number of diverse sentences to select.")


class RankSentencesOut(BaseModel):
    scores: list[float] = Field(description="LexRank relevance score for each sentence.")
    selected: list[int] = Field(description="Zero-based indexes selected by maximal marginal relevance.")


@module(
    id="text.rank_sentences", version=1,
    summary="Rank the sentences that carry the talk and select a diverse subset.",
    when_to_use="Tightening a long talk or finding representative moments.",
    when_not_to_use="The person has explicitly marked which sentences to keep.",
    inputs=RankSentencesIn, outputs=RankSentencesOut, requires=(), produces=(),
    cost=Cost("fast", ("cpu",), 0.5), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="LexRank and MMR are deterministic rule algorithms.",
    examples=(Example(inputs={"sentences": ["One idea.", "Another idea."], "keep": 1},
                      outputs={"scores": [0.5, 0.5], "selected": [0]}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Ranking the sentences",
    log_line=lambda i, o: f"Selected {len(o.selected)} important sentence(s).",
)
def rank_sentences(ws: Workspace, inputs: RankSentencesIn) -> RankSentencesOut:
    from ...saliency import lexrank, mmr_select, similarity_matrix

    if not inputs.sentences:
        return RankSentencesOut(scores=[], selected=[])
    scores = lexrank(inputs.sentences)
    selected = mmr_select(scores, similarity_matrix(inputs.sentences), min(inputs.keep, len(inputs.sentences)))
    return RankSentencesOut(scores=scores, selected=selected)


class ProjectOptionsIn(BaseModel):
    language: Literal["bn", "en", "auto"] | None = Field(default=None, description="Confirmed speech language.")
    aspect: Literal["9:16", "1:1", "16:9"] | None = Field(default=None, description="Primary video shape.")
    theme: str | None = Field(default=None, description="Installed theme name.")
    pace: Literal["calm", "normal", "fast"] | None = Field(default=None, description="Audio editing pace.")
    usecase: str | None = Field(default=None, description="Video use case or auto.")
    options: dict[str, Any] = Field(default_factory=dict, description="Validated project option fields to patch.")


class ProjectOptionsOut(BaseModel):
    project: dict[str, Any] = Field(description="The complete validated project metadata after the patch.")


@module(
    id="project.options", version=1,
    summary="Read or update the project's language, shape, theme, pace and editing options.",
    when_to_use="The director or person changes how this video should be made.",
    when_not_to_use="For timeline edits or source replacement.",
    inputs=ProjectOptionsIn, outputs=ProjectOptionsOut, requires=("project.meta",), produces=("project.meta",),
    cost=Cost("instant", ("cpu",), 0.05), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="Pydantic validates the existing project metadata and patch.",
    examples=(Example(inputs={}, outputs={"project": {}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Updating video options",
    log_line=lambda i, o: "Updated the video options.", native_outputs=True,
)
def project_options(ws: Workspace, inputs: ProjectOptionsIn) -> ProjectOptionsOut:
    from ...project import Project
    from ...schema import ProjectMeta

    project = Project(ws.root.name, ws.root.parent)
    data = project.meta().model_dump()
    for key in ("language", "aspect", "theme", "pace", "usecase"):
        value = getattr(inputs, key)
        if value is not None:
            data[key] = value
    data["options"] = {**data.get("options", {}), **inputs.options}
    meta = ProjectMeta.model_validate(data)
    project.save_meta(meta)
    return ProjectOptionsOut(project=meta.model_dump(mode="json"))


class RolesIn(BaseModel):
    language: Literal["bn", "en"] | None = Field(default=None, description="Language override; defaults to the project language.")


class RolesOut(BaseModel):
    sentences: list[dict[str, Any]] = Field(description="One rule-derived role and its grounded facts per sentence.")


@module(
    id="understand.roles", version=1,
    summary="Explain what each spoken sentence does: hook, question, proof, step, story, claim or call to action.",
    when_to_use="Before choosing scene structures or checking the shape of an argument.",
    when_not_to_use="When a current context artifact already contains sufficient sentence roles.",
    inputs=RolesIn, outputs=RolesOut, requires=("transcript", "beats"), produces=(),
    cost=Cost("instant", ("cpu",), 0.1), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing bilingual role analyser is rule based.",
    examples=(Example(inputs={}, outputs={"sentences": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Reading the sentence roles",
    log_line=lambda i, o: f"Read the role of {len(o.sentences)} sentence(s).",
)
def understand_roles(ws: Workspace, inputs: RolesIn) -> RolesOut:
    from dataclasses import asdict
    from ...director.roles import analyse
    from ...project import Project

    project = Project(ws.root.name, ws.root.parent)
    facts = analyse(project.transcript(), project.beats(), inputs.language or project.meta().language)
    return RolesOut(sentences=[asdict(item) for item in facts])


class KeyTermsIn(BaseModel):
    minimum_score: float = Field(default=0.42, ge=0, le=1, description="Minimum importance score for returned words.")


class KeyTermsOut(BaseModel):
    terms: list[dict[str, Any]] = Field(description="Distinct grounded words with key-term scores, highest first.")


@module(
    id="understand.key_terms", version=1, summary="Find specific, repeated noun-like words worth showing on screen.",
    when_to_use="Selecting grounded labels, icons or illustrations from the transcript.", when_not_to_use="For inventing a title or unspoken concept.",
    inputs=KeyTermsIn, outputs=KeyTermsOut, requires=("transcript",), produces=(),
    cost=Cost("fast", ("cpu",), 0.5), effects="none", determinism="pure", grounding=("terms",),
    fallback=None, fallback_reason="The existing bilingual term scorer is rule based.",
    examples=(Example(inputs={"minimum_score": 0.42}, outputs={"terms": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Finding the key terms",
    log_line=lambda i, o: f"Found {len(o.terms)} key term(s).",
)
def key_terms(ws: Workspace, inputs: KeyTermsIn) -> KeyTermsOut:
    from ...schema import Transcript
    from ...visuals.terms import norm, score, topic_counts

    words = Transcript.model_validate(ws.read_json("transcript")).words
    topics = topic_counts(word.text for word in words if not word.cut)
    best: dict[str, dict[str, Any]] = {}
    for word in words:
        term = norm(word.text)
        value = score(word.text, topics)
        if not word.cut and term and value >= inputs.minimum_score:
            row = {"text": word.text, "word_id": word.id, "score": round(value, 6)}
            if term not in best or row["score"] > best[term]["score"]:
                best[term] = row
    return KeyTermsOut(terms=sorted(best.values(), key=lambda row: (-row["score"], row["word_id"])))


class UsecaseIn(BaseModel):
    has_media: bool | None = Field(default=None, description="Whether user-supplied visual media is available; defaults to project metadata.")


class UsecaseOut(BaseModel):
    usecase: str = Field(description="Rule-selected use case such as teach, sell, story, discuss or general.")


@module(
    id="understand.usecase", version=1, summary="Classify the recording as teaching, selling, storytelling, discussion or general speech.",
    when_to_use="The project use case is auto and direction needs an editing profile.", when_not_to_use="The person explicitly chose a use case.",
    inputs=UsecaseIn, outputs=UsecaseOut, requires=("transcript", "beats", "project.meta"), produces=(),
    cost=Cost("fast", ("cpu",), 0.2), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing bilingual detector is entirely rule based.",
    examples=(Example(inputs={}, outputs={"usecase": "general"}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Choosing the video use case", log_line=lambda i, o: f"Classified the video as {o.usecase}.",
)
def usecase(ws: Workspace, inputs: UsecaseIn) -> UsecaseOut:
    from ...director.plan import detect_usecase
    from ...director.roles import analyse
    from ...project import Project

    project = Project(ws.root.name, ws.root.parent)
    meta = project.meta()
    facts = analyse(project.transcript(), project.beats(), meta.language)
    return UsecaseOut(usecase=detect_usecase(facts, bool(meta.media) if inputs.has_media is None else inputs.has_media))


class TidyScreenIn(BaseModel):
    text: str = Field(description="Grounded spoken text to shorten for a visual label.")
    max_chars: int = Field(default=36, ge=4, le=200, description="Maximum output characters.")
    whole: bool = Field(default=False, description="Keep a complete phrase rather than extracting a fragment.")


class TidyScreenOut(BaseModel):
    text: str | None = Field(description="Screen-ready text, or null when no useful phrase remains.")


@module(
    id="text.tidy_for_screen", version=1,
    summary="Shorten grounded spoken text into a readable on-screen phrase.",
    when_to_use="A graphic needs a compact label derived from the speaker's words.",
    when_not_to_use="For adding a new claim or fact that was not spoken.",
    inputs=TidyScreenIn, outputs=TidyScreenOut, requires=(), produces=(),
    cost=Cost("instant", ("cpu",), 0.02), effects="none", determinism="pure", grounding=("text",),
    fallback=None, fallback_reason="The existing phrase tidier is deterministic and never invents text.",
    examples=(Example(inputs={"text": "This is a very useful idea", "max_chars": 20}, outputs={"text": "useful idea"}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Shortening text for the screen",
    log_line=lambda i, o: "Prepared a grounded screen phrase." if o.text else "Found no useful screen phrase.",
)
def tidy_for_screen(ws: Workspace, inputs: TidyScreenIn) -> TidyScreenOut:
    from ...director.phrases import tidy

    return TidyScreenOut(text=tidy(inputs.text, max_chars=inputs.max_chars, whole=inputs.whole))


class ChooseMusicIn(BaseModel):
    mood: str | None = Field(default=None, description="Context mood such as story, finance, tech or motivation.")
    seed: str = Field(default="", description="Stable project seed; empty uses the project id.")


class ChooseMusicOut(BaseModel):
    track: str | None = Field(description="Bundled track id, or null when the music library is empty.")


@module(
    id="direct.choose_music", version=1,
    summary="Choose a stable bundled music track that suits the video's mood.",
    when_to_use="Music is set to auto after the video's mood is known.",
    when_not_to_use="The person selected a track or turned music off.",
    inputs=ChooseMusicIn, outputs=ChooseMusicOut, requires=(), produces=(),
    cost=Cost("instant", ("cpu",), 0.02), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing music picker is deterministic over the bundled catalogue.",
    examples=(Example(inputs={"mood": "story", "seed": "example"}, outputs={"track": None}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Choosing the music",
    log_line=lambda i, o: f"Chose {o.track}." if o.track else "No bundled music was available.",
)
def choose_music(ws: Workspace, inputs: ChooseMusicIn) -> ChooseMusicOut:
    from ...musicpick import pick

    return ChooseMusicOut(track=pick(inputs.mood, inputs.seed or ws.root.name))


class LearnTasteIn(BaseModel):
    kind: Literal["spelling", "choice", "note"] = Field(description="Type of creator preference being recorded.")
    value: str = Field(description="Chosen value, director note, or corrected spelling.")
    heard: str = Field(default="", description="Originally recognized spelling when kind is spelling.")
    choice: str = Field(default="theme", description="Preference category when kind is choice.")
    project_id: str = Field(default="", description="Project id proving a spelling correction occurred in a distinct video.")


class LearnTasteOut(BaseModel):
    learned: bool = Field(description="Whether this observation became a durable default or global spelling.")
    preference: str | None = Field(default=None, description="Newly established choice preference, when any.")


@module(
    id="direct.learn_taste", version=1, summary="Remember repeated creator corrections, choices and direction notes locally.",
    when_to_use="After the person changes a spelling, visual preference or gives reusable direction.", when_not_to_use="For an inferred preference the person did not express.",
    inputs=LearnTasteIn, outputs=LearnTasteOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.05),
    effects="writes_artifact", determinism="pure", grounding=(), fallback=None, fallback_reason="The existing local taste store is deterministic.",
    examples=(Example(inputs={"kind": "note", "value": "Use fewer text cards."}, outputs={"learned": True, "preference": None}),),
    toolboxes=("studio", "full"), plain_name="Remembering the creator's taste",
    log_line=lambda i, o: f"Recorded the creator's {i.kind} preference.",
)
def learn_taste(ws: Workspace, inputs: LearnTasteIn) -> LearnTasteOut:
    from ... import taste

    if inputs.kind == "spelling":
        learned = taste.learn_fix(inputs.heard, inputs.value, inputs.project_id or ws.root.name)
        return LearnTasteOut(learned=learned)
    if inputs.kind == "choice":
        preference = taste.learn_choice(inputs.choice, inputs.value)
        return LearnTasteOut(learned=preference is not None, preference=preference)
    taste.learn_note(inputs.value)
    return LearnTasteOut(learned=True)


class EmptyIn(BaseModel):
    pass


class TasteHintOut(BaseModel):
    hint: str = Field(description="Plain-language summary of recurring creator notes, or empty when none exist.")


@module(
    id="direct.taste_hint", version=1, summary="Summarize the creator's recurring local direction notes for the next video.",
    when_to_use="Before asking a director to plan a new video.", when_not_to_use="No creator preferences should carry across projects.",
    inputs=EmptyIn, outputs=TasteHintOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.02),
    effects="none", determinism="pure", grounding=(), fallback=None, fallback_reason="The existing hint builder reads only local confirmed notes.",
    examples=(Example(inputs={}, outputs={"hint": ""}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Reading the creator's taste", log_line=lambda i, o: "Loaded creator preferences." if o.hint else "No creator preferences were recorded.",
)
def taste_hint(ws: Workspace, inputs: EmptyIn) -> TasteHintOut:
    from ...taste import director_hint

    return TasteHintOut(hint=director_hint())
