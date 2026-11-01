"""Small sound and timing adapters over existing deterministic helpers."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class SfxPlaceIn(BaseModel):
    scenes: list[dict[str, Any]] = Field(description="Resolved scenes with starts, transitions, elements and optional actions.")


class SfxPlaceOut(BaseModel):
    cues: list[dict[str, Any]] = Field(description="Time-ordered, thinned sound-effect cues.")


@module(
    id="sound.sfx_place", version=1,
    summary="Place restrained sound-effect cues at transitions, reveals and physical actions.",
    when_to_use="After scenes have resolved times and before the final sound mix.",
    when_not_to_use="When sound effects are disabled.",
    inputs=SfxPlaceIn, outputs=SfxPlaceOut, requires=(), produces=(),
    cost=Cost("instant", ("cpu",), 0.05), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing cue builder is deterministic.",
    examples=(Example(inputs={"scenes": []}, outputs={"cues": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Placing sound effects",
    log_line=lambda i, o: f"Placed {len(o.cues)} sound-effect cue(s).",
)
def sfx_place(ws: Workspace, inputs: SfxPlaceIn) -> SfxPlaceOut:
    from ...cues import build_cues

    return SfxPlaceOut(cues=build_cues(inputs.scenes))


class AudioBeatsIn(BaseModel):
    track: str = Field(description="Bundled music track id.")
    duration: float = Field(gt=0, description="Video duration in seconds.")
    bpm: float | None = Field(default=None, gt=20, lt=300, description="Known tempo override in beats per minute.")


class AudioBeatsOut(BaseModel):
    bpm: float = Field(description="Estimated or supplied tempo in beats per minute.")
    offset: float = Field(description="First grid-beat offset in seconds.")
    times: list[float] = Field(description="Beat times inside the requested duration in seconds.")


@module(
    id="audio.beats", version=1,
    summary="Estimate a bundled music track's tempo and return its beat grid.",
    when_to_use="Picture changes or sound effects should align with a selected music track.",
    when_not_to_use="No music is selected or beat sync is disabled.",
    inputs=AudioBeatsIn, outputs=AudioBeatsOut, requires=(), produces=(),
    cost=Cost("fast", ("cpu",), 2.0), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing onset-grid estimator is deterministic.",
    examples=(Example(inputs={"track": "track-id", "duration": 10.0, "bpm": 120.0},
                      outputs={"bpm": 120.0, "offset": 0.0, "times": [0.0, 0.5]}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Finding the music beats",
    log_line=lambda i, o: f"Found {len(o.times)} music beat(s) at {o.bpm:.1f} BPM.",
)
def audio_beats(ws: Workspace, inputs: AudioBeatsIn) -> AudioBeatsOut:
    from ...beatsync import beat_times, grid_for
    from ...render.mux import resolve_music

    path = resolve_music(inputs.track)
    if path is None:
        raise ValueError(f"unknown bundled music track: {inputs.track}")
    bpm, offset = grid_for(path, inputs.bpm)
    return AudioBeatsOut(bpm=bpm, offset=offset,
                         times=[round(float(value), 4) for value in beat_times(bpm, offset, inputs.duration)])


class SnapBeatIn(BaseModel):
    time: float = Field(ge=0, description="Proposed picture-change time in seconds.")
    beats: list[float] = Field(description="Music beat times in seconds.")
    earliest: float = Field(ge=0, description="Earliest allowed snapped time in seconds.")
    latest: float = Field(ge=0, description="Latest allowed snapped time in seconds.")


class SnapBeatOut(BaseModel):
    time: float = Field(description="Nearest allowed music-beat time in seconds.")


@module(
    id="cut.snap_beat", version=1,
    summary="Move a proposed picture change to the nearest allowed music beat.",
    when_to_use="Beat sync helps a visual change without moving it away from the spoken impact.",
    when_not_to_use="The beat lies outside the cut's allowed timing window.",
    inputs=SnapBeatIn, outputs=SnapBeatOut, requires=(), produces=(),
    cost=Cost("instant", ("cpu",), 0.01), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing beat snap is deterministic.",
    examples=(Example(inputs={"time": 1.1, "beats": [1.0, 1.5], "earliest": 0.9, "latest": 1.3},
                      outputs={"time": 1.0}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Snapping a change to the beat",
    log_line=lambda i, o: f"Moved the change to {o.time:.2f} seconds.",
)
def snap_beat(ws: Workspace, inputs: SnapBeatIn) -> SnapBeatOut:
    import numpy as np
    from ...beatsync import snap

    if inputs.latest < inputs.earliest:
        raise ValueError("latest must be at or after earliest")
    return SnapBeatOut(time=snap(inputs.time, np.asarray(inputs.beats, dtype=float),
                                 inputs.earliest, inputs.latest))


class SoundsToPicturesIn(BaseModel):
    events: list[dict[str, Any]] = Field(description="Detected non-speech sound events in output time.")
    speech: list[tuple[float, float]] = Field(default_factory=list, description="Optional spoken ranges in output seconds.")


class SoundsToPicturesOut(BaseModel):
    caption_words: list[dict[str, Any]] = Field(description="Grounded bracketed caption words timed to the sound events.")


@module(
    id="sound.sounds_to_pictures", version=1, summary="Turn detected non-speech sounds into timed, grounded caption words for visual planning.",
    when_to_use="A recording contains laughter, applause, animals or other meaningful sounds.", when_not_to_use="There are no detected sound events.",
    inputs=SoundsToPicturesIn, outputs=SoundsToPicturesOut, requires=(), produces=(),
    cost=Cost("fast", ("cpu",), 0.1), effects="none", determinism="pure", grounding=("caption_words",),
    fallback=None, fallback_reason="The existing sound-caption conversion is deterministic.",
    examples=(Example(inputs={"events": []}, outputs={"caption_words": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Turning sounds into visual cues",
    log_line=lambda i, o: f"Made {len(o.caption_words)} timed sound-caption word(s).",
)
def sounds_to_pictures(ws: Workspace, inputs: SoundsToPicturesIn) -> SoundsToPicturesOut:
    from ...sounds import caption_words

    return SoundsToPicturesOut(caption_words=caption_words(inputs.events, inputs.speech or None))
