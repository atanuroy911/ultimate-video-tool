"""Subtitle and transcript adapters over existing parsers and editors."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class SubtitlesIn(BaseModel):
    file: str = Field(description="Path to a WebVTT or YouTube JSON3 subtitle file.")
    language: str = Field(default="en", description="BCP-47-like language label stored with the words.")
    duration: float = Field(default=0.0, ge=0, description="Source duration in seconds; zero uses the last subtitle word.")


class RawTranscriptOut(BaseModel):
    language: str = Field(description="Language label for the subtitle words.")
    model: str = Field(description="Word source; subtitles for this adapter.")
    duration: float = Field(description="Transcript duration in seconds.")
    chunks: list[Any] = Field(description="Recognition chunks; empty for subtitle imports.")
    chunks_without_speech: int = Field(description="Empty recognition chunks; zero for subtitle imports.")
    words: list[dict[str, Any]] = Field(description="Subtitle words with text, start, end and confidence.")


@module(
    id="asr.from_subtitles", version=1, summary="Turn a page's WebVTT or JSON3 subtitles into word-timed raw transcript data.",
    when_to_use="A fetched page supplied trustworthy subtitles for enough of the source.", when_not_to_use="The subtitle track is sparse or unrelated.",
    inputs=SubtitlesIn, outputs=RawTranscriptOut, requires=(), produces=("transcript.raw",),
    cost=Cost("fast", ("cpu",), 0.5), effects="writes_artifact", determinism="pure", grounding=("words",),
    fallback="asr.transcribe", fallback_reason="Speech recognition is used when the subtitle track is too sparse.",
    examples=(Example(inputs={"file": "captions.vtt", "language": "en", "duration": 10},
                      outputs={"language": "en", "model": "subtitles", "duration": 10, "chunks": [],
                               "chunks_without_speech": 0, "words": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Reading the page subtitles",
    log_line=lambda i, o: f"Read {len(o.words)} timed word(s) from subtitles.",
)
def from_subtitles(ws: Workspace, inputs: SubtitlesIn) -> RawTranscriptOut:
    from ...ingest import raw_transcript_from_subs

    result = raw_transcript_from_subs(Path(inputs.file).expanduser(), inputs.language, inputs.duration)
    if result is None:
        raise ValueError("the subtitles are too sparse or could not be read; use asr.transcribe")
    return RawTranscriptOut.model_validate(result)
