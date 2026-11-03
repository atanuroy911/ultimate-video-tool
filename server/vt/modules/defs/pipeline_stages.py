"""Thin module adapters over the twelve unchanged Pipeline.stage_* methods."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class StageIn(BaseModel):
    force: bool = Field(default=False, description="Rebuild this stage even when its own cache is fresh.")


class StageOut(BaseModel):
    stage: str = Field(description="The completed pipeline stage name.")


_STAGES = (
    ("voice", (), ("script.text",), "Speak the typed script before any visual work."),
    ("preprocess", (), ("audio.master", "audio.asr"), "Clean the source audio for editing and recognition."),
    ("silence", ("audio.asr",), ("audio.silences",), "Find silence in the cleaned audio."),
    ("asr", ("audio.asr",), ("transcript.raw",), "Recognize or recover the spoken words."),
    ("cuts", ("audio.master", "transcript.raw"), ("audio.cuts", "audio.cut"), "Apply the audio cuts first."),
    ("sounds", (), ("audio.events",), "Detect sound events in the cut audio when available."),
    ("aroll", (), ("aroll",), "Cut the speaker picture to match the audio when available."),
    ("words", ("transcript.raw", "audio.cuts"), ("transcript", "beats"), "Align words and sentence beats to the cut audio."),
    ("context", ("transcript", "beats"), ("context",), "Read the spoken content for its topic and facts."),
    ("tighten", ("transcript", "beats"), ("audio.tighten",), "Shorten a long recording when the project requests it."),
    ("plan", ("transcript", "beats"), ("scenes",), "Plan scenes from the spoken words."),
    ("compose", ("scenes",), ("composition",), "Compose the editable timeline in every shape."),
)


def _register(name: str, requires: tuple[str, ...], produces: tuple[str, ...], summary: str) -> None:
    @module(
        id=f"pipeline.{name}", version=1, summary=summary,
        when_to_use=f"When the classic recipe reaches {name} or the director reruns that stage.",
        when_not_to_use="When the director has chosen a different recipe.",
        inputs=StageIn, outputs=StageOut, requires=requires, produces=produces,
        cost=Cost("slow", ("cpu",), 30.0), effects="writes_timeline" if name in ("plan", "compose") else "writes_artifact",
        determinism="external" if name in ("voice", "asr", "context", "plan") else "pure",
        grounding=(), fallback=None, fallback_reason="The existing stage already contains its rule fallback or is deterministic.",
        examples=(Example(inputs={"force": False}, outputs={"stage": name}),),
        toolboxes=("autonomous", "studio", "full"), plain_name=f"{name.title()} stage",
        log_line=lambda i, o: f"Completed the {o.stage} stage.", native_outputs=True,
    )
    def run_stage(ws: Workspace, inputs: StageIn) -> StageOut:
        from ...pipeline import Pipeline
        from ...project import Project

        pipeline = getattr(ws, "pipeline", None) or Pipeline(Project(ws.root.name, ws.root.parent))
        getattr(pipeline, f"stage_{name}")(inputs.force)
        return StageOut(stage=name)


for _name, _requires, _produces, _summary in _STAGES:
    _register(_name, _requires, _produces, _summary)
