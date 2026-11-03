"""Audio analysis adapters over the existing, tested functions."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..registry import Cost, Example, module
from ..workspace import Workspace


class FindRetakesIn(BaseModel):
    """The raw transcript is read from the project workspace."""


class RetakeCut(BaseModel):
    start: float = Field(description="Cut start in source seconds.")
    end: float = Field(description="Cut end in source seconds.")
    text: str = Field(description="Words spoken in the discarded take.")
    reason: str = Field(description="Plain explanation of why the take should be cut.")


class FindRetakesOut(BaseModel):
    cuts: list[RetakeCut] = Field(description="Earlier false starts and retakes to discard.")


@module(
    id="audio.find_retakes", version=1,
    summary="Find false starts and repeated takes in a recording; keep the last complete take.",
    when_to_use="A live or phone recording has a word-timed raw transcript.",
    when_not_to_use="The app spoke a typed script, which has no human retakes.",
    inputs=FindRetakesIn, outputs=FindRetakesOut,
    requires=("transcript.raw",), produces=("audio.retakes",),
    cost=Cost("instant", ("cpu",), 0.2), effects="writes_artifact", determinism="pure",
    grounding=(), fallback=None, fallback_reason="The existing retake finder is rule based.",
    examples=(Example(inputs={}, outputs={"cuts": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Looking for repeated takes",
    log_line=lambda i, o: f"Found {len(o.cuts)} repeated take(s).",
)
def find_retakes(ws: Workspace, inputs: FindRetakesIn) -> FindRetakesOut:
    from ...retakes import find_retakes as find

    raw = ws.read_json("transcript.raw")
    cuts = find(raw.get("words", []))
    return FindRetakesOut(cuts=[{key: value for key, value in cut.items() if key != "words"} for cut in cuts])


class ProsodyIn(BaseModel):
    windows: list[tuple[float, float]] = Field(description="Non-overlapping start and end times in source seconds.")


class ProsodyOut(BaseModel):
    scores: list[float] = Field(description="Speaker-relative arousal score for each requested time window.")


@module(
    id="audio.prosody", version=1,
    summary="Measure how worked up the speaker sounds in each time window.",
    when_to_use="Ranking the emotional peaks of a recording or choosing highlight candidates.",
    when_not_to_use="A typed script has not been spoken yet, or no time windows are known.",
    inputs=ProsodyIn, outputs=ProsodyOut,
    requires=("source.audio",), produces=("audio.prosody",),
    cost=Cost("fast", ("cpu",), 3.0), effects="writes_artifact", determinism="pure",
    grounding=(), fallback=None, fallback_reason="The existing prosody measure is deterministic.",
    examples=(Example(inputs={"windows": [[0.0, 1.0]]}, outputs={"scores": [0.0]}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Measuring the voice",
    log_line=lambda i, o: f"Measured voice energy in {len(o.scores)} time window(s).",
)
def prosody(ws: Workspace, inputs: ProsodyIn) -> ProsodyOut:
    from ...prosody import arousal_for

    words = ws.read_json("transcript.raw").get("words", []) if ws.exists("transcript.raw") else None
    return ProsodyOut(scores=arousal_for(ws.path_for("source.audio"), inputs.windows, words))


class AudioEditIn(BaseModel):
    operation: Literal["cut", "restore", "mute", "gain", "split", "remove_split", "undo", "redo"] = Field(
        description="Edit operation in output time, or history operation.")
    start: float | None = Field(default=None, ge=0, description="Range start or split time in output seconds.")
    end: float | None = Field(default=None, ge=0, description="Range end in output seconds.")
    enabled: bool = Field(default=True, description="Whether a mute is applied or removed.")
    db: float = Field(default=0.0, ge=-40, le=18, description="Gain adjustment in decibels.")
    index: int = Field(default=0, ge=0, description="Manual-cut index for restore.")
    side: Literal["all", "start", "end"] = Field(default="all", description="Side restored from a manual cut.")
    amount: float = Field(default=0.0, ge=0, description="Seconds restored from one side.")
    source_time: float | None = Field(default=None, ge=0, description="Source-time split position to remove.")

    @model_validator(mode="after")
    def required_times(self):
        if self.operation in ("cut", "mute", "gain") and (self.start is None or self.end is None):
            raise ValueError(f"{self.operation} needs start and end")
        if self.operation == "split" and self.start is None:
            raise ValueError("split needs start")
        if self.operation == "remove_split" and self.source_time is None:
            raise ValueError("remove_split needs source_time")
        return self


class AudioEditOut(BaseModel):
    changed: bool = Field(description="Whether the stored edit state changed.")
    edits: dict = Field(description="Complete manual audio-edit state in source time.")


@module(
    id="audio.edit", version=1, summary="Cut, mute, change gain or split the voice track with existing undo and redo.",
    when_to_use="The person makes a precise hand edit on the voice timeline.", when_not_to_use="For automatic silence, retake or tightening decisions.",
    inputs=AudioEditIn, outputs=AudioEditOut, requires=("audio.cuts",), produces=("audio.edits",),
    cost=Cost("fast", ("cpu",), 0.5), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing typed edit operations and history are deterministic.",
    examples=(Example(inputs={"operation": "mute", "start": 1.0, "end": 2.0, "enabled": True},
                      outputs={"changed": True, "edits": {"cuts": [], "mutes": [], "gains": [], "splits": []}}),),
    toolboxes=("studio", "full"), plain_name="Editing the voice track",
    log_line=lambda i, o: f"{'Applied' if o.changed else 'Did not apply'} the {i.operation.replace('_', ' ')} edit.",
    native_outputs=True,
)
def edit_audio(ws: Workspace, inputs: AudioEditIn) -> AudioEditOut:
    from ... import audio_edit as edit

    project = _project_for(ws)
    if inputs.operation == "undo":
        changed = edit.undo(project)
        return AudioEditOut(changed=changed, edits=edit.load(project))
    if inputs.operation == "redo":
        changed = edit.redo(project)
        return AudioEditOut(changed=changed, edits=edit.load(project))
    cuts = project.cuts()
    if cuts is None:
        raise ValueError("the project has no valid cut map")
    current = edit.load(project)
    if inputs.operation == "cut":
        updated = edit.add_cut(current, cuts, inputs.start, inputs.end)
    elif inputs.operation == "restore":
        updated = edit.restore(current, inputs.index, inputs.side, inputs.amount)
    elif inputs.operation == "mute":
        updated = edit.set_mute(current, cuts, inputs.start, inputs.end, inputs.enabled)
    elif inputs.operation == "gain":
        updated = edit.set_gain(current, cuts, inputs.start, inputs.end, inputs.db)
    elif inputs.operation == "split":
        updated = edit.add_split(current, cuts, inputs.start)
    else:
        updated = edit.remove_split(current, inputs.source_time)
    edit.save(project, updated)
    return AudioEditOut(changed=updated != current, edits=updated)


def _project_for(ws: Workspace):
    from ...project import Project

    return Project(ws.root.name, ws.root.parent)


class EmphasisIn(BaseModel):
    audio: Literal["cut", "source"] = Field(default="cut", description="Audio timeline whose word times match the transcript.")


class EmphasisOut(BaseModel):
    scores: dict[str, float] = Field(description="Speaker-relative emphasis score from 0 to 1 for each word id.")


@module(
    id="audio.emphasis", version=1, summary="Measure which transcript words the speaker stresses through loudness, pitch and duration.",
    when_to_use="Choosing impact words or visual changes from the actual performance.", when_not_to_use="Before a word-timed transcript exists.",
    inputs=EmphasisIn, outputs=EmphasisOut, requires=("transcript", "audio.cut"), produces=("audio.emphasis",),
    cost=Cost("fast", ("cpu",), 4.0), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing signal analysis returns neutral scores when audio is unavailable.",
    examples=(Example(inputs={"audio": "cut"}, outputs={"scores": {"w1": 0.5}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Measuring stressed words",
    log_line=lambda i, o: f"Measured emphasis for {len(o.scores)} word(s).",
)
def emphasis(ws: Workspace, inputs: EmphasisIn) -> EmphasisOut:
    from ...schema import Transcript
    from ...visuals.emphasis import emphasis_scores

    transcript = Transcript.model_validate(ws.read_json("transcript"))
    path = ws.path_for("audio.cut") if inputs.audio == "cut" else ws.path_for("source.audio")
    return EmphasisOut(scores=emphasis_scores(path, transcript.words))


class VoicesOut(BaseModel):
    voices: list[dict] = Field(description="Locally registered consented voice references and their durations.")


class EmptyIn(BaseModel):
    pass


@module(
    id="audio.voices", version=1, summary="List locally registered consented voice references available to speech synthesis.",
    when_to_use="Choosing a voice for a typed script.", when_not_to_use="The project uses its original recorded voice.",
    inputs=EmptyIn, outputs=VoicesOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.05),
    effects="none", determinism="pure", grounding=(), fallback=None, fallback_reason="This reads the existing local voice registry.",
    examples=(Example(inputs={}, outputs={"voices": []}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Listing local voices", log_line=lambda i, o: f"Found {len(o.voices)} consented local voice(s).",
)
def voices(ws: Workspace, inputs: EmptyIn) -> VoicesOut:
    from ...voices import list_voices

    return VoicesOut(voices=list_voices())


class CloneVoiceIn(BaseModel):
    file: str = Field(description="Path to a clear five-to-sixty-second voice recording.")
    name: str = Field(min_length=1, max_length=40, description="Person-facing name for the voice reference.")
    consent: bool = Field(description="True only when this is the person's voice or explicit permission was obtained.")


class CloneVoiceOut(BaseModel):
    voice: dict = Field(description="Registered voice id, name and retained reference duration.")


@module(
    id="audio.clone_voice", version=1, summary="Register a consented voice sample for local voice cloning.",
    when_to_use="The person explicitly supplies an allowed voice recording for typed scripts.", when_not_to_use="Consent is absent or the recording came from downloaded media.",
    inputs=CloneVoiceIn, outputs=CloneVoiceOut, requires=(), produces=(), cost=Cost("slow", ("cpu",), 10.0),
    effects="writes_artifact", determinism="pure", grounding=(), fallback=None, fallback_reason="The existing registrar rejects missing consent, silence, clipping and invalid duration.",
    examples=(Example(inputs={"file": "voice.wav", "name": "My voice", "consent": True}, outputs={"voice": {"id": "my-voice"}}),),
    toolboxes=("studio", "full"), plain_name="Registering a consented voice",
    log_line=lambda i, o: f"Registered voice {o.voice.get('name', i.name)}.",
)
def clone_voice(ws: Workspace, inputs: CloneVoiceIn) -> CloneVoiceOut:
    from pathlib import Path
    from ...voices import add_voice

    return CloneVoiceOut(voice=add_voice(Path(inputs.file).expanduser(), inputs.name, inputs.consent))


class SpeakersOut(BaseModel):
    speakers: dict[str, str] = Field(description="Sentence beat id to Speaker 1 or Speaker 2; empty when no clear split exists.")


@module(
    id="audio.speakers", version=1, summary="Label transcript words when two clearly distinct voices take turns.",
    when_to_use="An interview, podcast or debate may contain two recurring speakers.", when_not_to_use="A typed script or clear single-speaker recording.",
    inputs=EmptyIn, outputs=SpeakersOut, requires=("audio.cut", "transcript", "beats"), produces=("transcript",),
    cost=Cost("fast", ("cpu",), 5.0), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing conservative detector leaves ambiguous recordings unlabeled.",
    examples=(Example(inputs={}, outputs={"speakers": {}}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Finding different speakers", log_line=lambda i, o: f"Labeled {len(o.speakers)} sentence(s) by speaker." if o.speakers else "No clear second speaker was found.",
    native_outputs=True,
)
def speakers(ws: Workspace, inputs: EmptyIn) -> SpeakersOut:
    from ...project import Project
    from ...stages.speakers import assign, label_words
    from ...visuals.emphasis import load_mono16k

    project = Project(ws.root.name, ws.root.parent)
    transcript, beats = project.transcript(), project.beats()
    found = assign(load_mono16k(project.cut_audio), transcript, beats) or {}
    if found:
        project.save_transcript(label_words(transcript, beats, found))
    return SpeakersOut(speakers=found)
