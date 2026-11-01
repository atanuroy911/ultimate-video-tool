"""Deterministic quality adapters for the existing Video Script."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class EmptyIn(BaseModel):
    pass


class ScriptScoreOut(BaseModel):
    scores: dict[str, float] = Field(description="Zero-to-one validity, coverage, motion, fidelity, variety and fit metrics.")


@module(
    id="judge.script", version=1, summary="Score a Video Script for validity, coverage, idle gaps, number fidelity, variety and fit.",
    when_to_use="Comparing candidate Video Scripts before compilation or revision.", when_not_to_use="For rendered-pixel or audio quality.",
    inputs=EmptyIn, outputs=ScriptScoreOut, requires=("script.video", "transcript", "beats"), produces=(),
    cost=Cost("fast", ("cpu",), 0.2), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing score is deterministic and needs no model.",
    examples=(Example(inputs={}, outputs={"scores": {"valid": 1.0}}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Scoring the video script", log_line=lambda i, o: f"Scored the script on {len(o.scores)} quality measures.",
)
def script_score(ws: Workspace, inputs: EmptyIn) -> ScriptScoreOut:
    from ...project import Project
    from ...script.score import score

    project = Project(ws.root.name, ws.root.parent)
    return ScriptScoreOut(scores=score(ws.read_json("script.video"), project.transcript(), project.beats()))


class CritiqueOut(BaseModel):
    report: dict[str, Any] = Field(description="Rule-based editor score, metrics and scene-specific actionable issues.")


@module(
    id="direct.critique", version=1, summary="Review a Video Script like a picky editor and identify dull or repetitive scenes.",
    when_to_use="Before accepting or revising a planned character or explainer video.", when_not_to_use="For pixel-level inspection of a rendered video.",
    inputs=EmptyIn, outputs=CritiqueOut, requires=("script.video", "transcript", "beats"), produces=("direct.report",),
    cost=Cost("fast", ("cpu",), 0.3), effects="writes_artifact", determinism="pure", grounding=("report",),
    fallback=None, fallback_reason="The existing critic is already rule based.",
    examples=(Example(inputs={}, outputs={"report": {"score": 100, "metrics": {}, "issues": []}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Reviewing the video script",
    log_line=lambda i, o: f"The video script scored {o.report.get('score', 0)} with {len(o.report.get('issues', []))} issue(s).",
)
def critique(ws: Workspace, inputs: EmptyIn) -> CritiqueOut:
    from ...project import Project
    from ...script.critic import review

    project = Project(ws.root.name, ws.root.parent)
    return CritiqueOut(report=review(ws.read_json("script.video"), project.transcript(), project.beats()))


class EnrichOut(BaseModel):
    added: int = Field(description="Number of grounded character actions added to long still stretches.")
    script: dict[str, Any] = Field(description="Enriched validated Video Script.")


@module(
    id="direct.enrich", version=1, summary="Fill long still stretches in a character script with grounded gestures and reactions.",
    when_to_use="The script critic finds idle gaps in scenes that already have actors.", when_not_to_use="For scenes without actors or for inventing new claims.",
    inputs=EmptyIn, outputs=EnrichOut, requires=("script.video", "transcript", "beats"), produces=("script.video",),
    cost=Cost("fast", ("cpu",), 0.5), effects="writes_artifact", determinism="pure", grounding=("script",),
    fallback=None, fallback_reason="The existing enricher uses transcript word ids and a fixed gesture catalogue.",
    examples=(Example(inputs={}, outputs={"added": 0, "script": {}}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Adding visual actions", log_line=lambda i, o: f"Added {o.added} grounded action(s) to the video script.",
    native_outputs=True,
)
def enrich_script(ws: Workspace, inputs: EmptyIn) -> EnrichOut:
    from ...project import Project
    from ...script.critic import enrich
    from ...script.models import VideoScript
    from ...util import write_json

    project = Project(ws.root.name, ws.root.parent)
    enriched, added = enrich(VideoScript.model_validate(ws.read_json("script.video")), project.transcript(), project.beats())
    data = enriched.model_dump(by_alias=True, exclude_none=True, mode="json")
    write_json(ws.path_for("script.video"), data)
    return EnrichOut(added=added, script=data)


class ScorecardIn(BaseModel):
    video: str = Field(description="Path to the rendered video to analyze.")
    aspect: str = Field(default="9:16", description="Rendered shape used for safe-zone and empty-screen checks.")
    composition: dict[str, Any] | None = Field(default=None, description="Optional resolved composition data for caption and motion checks.")
    voice: str | None = Field(default=None, description="Optional voice-track path for dead-air checks.")


class ScorecardOut(BaseModel):
    card: dict[str, Any] = Field(description="Retention-risk metrics, worst moments and aggregate score.")


@module(
    id="judge.scorecard", version=1, summary="Measure hook delay, visual gaps, empty screens, dead air, reading speed and motion risk.",
    when_to_use="After a draft render and before final delivery or revision.", when_not_to_use="Before any rendered frames exist.",
    inputs=ScorecardIn, outputs=ScorecardOut, requires=(), produces=("judge.scorecard",),
    cost=Cost("slow", ("cpu",), 30.0), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing retention analyzer is deterministic over rendered frames and audio.",
    examples=(Example(inputs={"video": "draft.mp4", "aspect": "9:16"}, outputs={"card": {"score": 0}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Scoring the finished cut",
    log_line=lambda i, o: f"The retention scorecard returned {o.card.get('score', 0)}.",
)
def scorecard(ws: Workspace, inputs: ScorecardIn) -> ScorecardOut:
    from pathlib import Path
    from ...retention import scorecard as analyze

    return ScorecardOut(card=analyze(Path(inputs.video).expanduser(), inputs.aspect, inputs.composition,
                                     Path(inputs.voice).expanduser() if inputs.voice else None))


class FactsIn(BaseModel):
    content: Any = Field(description="On-screen element, prompt or script data to check.")


class FactsOut(BaseModel):
    valid: bool = Field(description="Whether all claim-like text and numbers are grounded in narration.")
    ungrounded: list[str] = Field(description="Text or numbers not found in the transcript.")


@module(id="judge.facts", version=1, summary="Check that claim-like text and numbers exist in the spoken transcript.",
        when_to_use="Before accepting on-screen copy or a generation prompt.", when_not_to_use="For fixed catalogue labels and visual ids.",
        inputs=FactsIn, outputs=FactsOut, requires=("transcript",), produces=(), cost=Cost("fast", ("cpu",), 0.1), effects="none", determinism="pure",
        grounding=("content",), fallback=None, fallback_reason="Questionable content is reported rather than silently accepted.",
        examples=(Example(inputs={"content": {"text": "gravity"}}, outputs={"valid": True, "ungrounded": []}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Checking factual grounding", log_line=lambda i, o: "All visible claims are grounded." if o.valid else f"Found {len(o.ungrounded)} ungrounded value(s).")
def facts(ws: Workspace, inputs: FactsIn) -> FactsOut:
    import re
    transcript = " ".join(word.get("text", "") for word in ws.read_json("transcript").get("words", [])).casefold()
    found = []
    def walk(value, key=""):
        if isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, child_key)
        elif isinstance(value, list):
            for child in value:
                walk(child, key)
        elif key in ("text", "label", "title", "value", "prompt", "bubble", "quote") and str(value).strip():
            text = str(value).strip()
            tokens = re.findall(r"[\w.%]+", text.casefold())
            if any((token.isdigit() or len(token) > 3) and token not in transcript for token in tokens):
                found.append(text)
    walk(inputs.content)
    ungrounded = list(dict.fromkeys(found))
    return FactsOut(valid=not ungrounded, ungrounded=ungrounded)


class AlignmentIn(BaseModel):
    impacts: list[dict[str, Any]] = Field(description="Expected impact points.")
    changes: list[float] = Field(description="Measured picture-change times.")
    tolerance: float = Field(default=0.1, ge=0.01, le=0.5, description="Maximum alignment error in seconds.")


class AlignmentOut(BaseModel):
    score: float = Field(ge=0, le=1, description="Share of impact points with a nearby picture change.")
    misses: list[dict[str, Any]] = Field(description="Impact points without an aligned picture change.")


@module(id="judge.impact_alignment", version=1, summary="Measure whether picture changes land within tolerance of audio impact points.",
        when_to_use="A rendered or resolved cut exposes exact picture-change times.", when_not_to_use="No impact map exists.",
        inputs=AlignmentIn, outputs=AlignmentOut, requires=(), produces=(), cost=Cost("fast", ("cpu",), 0.05), effects="none", determinism="pure",
        grounding=(), fallback=None, fallback_reason="The metric is a direct time comparison.",
        examples=(Example(inputs={"impacts": [{"time": 1.0}], "changes": [1.05]}, outputs={"score": 1.0, "misses": []}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Checking impact alignment", log_line=lambda i, o: f"{round(o.score * 100)}% of impact points align with picture changes.")
def impact_alignment(ws: Workspace, inputs: AlignmentIn) -> AlignmentOut:
    misses = [impact for impact in inputs.impacts if not any(abs(float(impact["time"]) - change) <= inputs.tolerance for change in inputs.changes)]
    return AlignmentOut(score=(1.0 - len(misses) / len(inputs.impacts)) if inputs.impacts else 1.0, misses=misses)


class WatchIn(BaseModel):
    video: str = Field(description="Draft rendered video path.")
    card: dict[str, Any] = Field(description="Existing retention scorecard.")
    qa: dict[str, Any] | None = Field(default=None, description="Optional visual-QA report.")


class WatchOut(BaseModel):
    changed: bool = Field(description="Whether the established revision loop retained an improvement.")


@module(id="judge.watch_and_revise", version=1, summary="Run the established scorecard-and-QA revision loop and keep only an improvement.",
        when_to_use="A draft render, scorecard and optional vision QA are ready.", when_not_to_use="Before the first render.",
        inputs=WatchIn, outputs=WatchOut, requires=("scenes", "transcript", "beats", "project.meta"), produces=("scenes",),
        cost=Cost("heavy", ("cpu",), 180.0), effects="writes_timeline", determinism="external", grounding=(), fallback=None,
        fallback_reason="The existing loop leaves the first cut unchanged when a revision is not better.",
        examples=(Example(inputs={"video": "draft.mp4", "card": {}}, outputs={"changed": False}),), toolboxes=("autonomous", "studio", "full"),
        plain_name="Watching and revising the draft", log_line=lambda i, o: "Kept an improved revision." if o.changed else "Kept the stronger existing cut.", native_outputs=True)
def watch_and_revise(ws: Workspace, inputs: WatchIn) -> WatchOut:
    from pathlib import Path
    from ...project import Project
    from ...server.app import watch_and_revise as revise
    changed = revise(Project(ws.root.name, ws.root.parent), inputs.card, Path(inputs.video), lambda *args: None, inputs.qa)
    return WatchOut(changed=bool(changed))


class VideoJudgeIn(BaseModel):
    video: str = Field(description="Path to the rendered video to judge.")
    kind: str = Field(default="explanation", description="Content kind (steps, story, explanation, list, argument, opinion): sets the words-per-picture range.")
    target_seconds: float | None = Field(default=None, description="Length the person asked for, if any.")
    composition: dict[str, Any] | None = Field(default=None, description="Optional resolved composition (captions) for the caption and sync checks.")


class VideoJudgeOut(BaseModel):
    passed: bool = Field(description="True when no judge failed.")
    verdicts: list[dict[str, Any]] = Field(description="One entry per judge: judge, passed (null = could not be judged), value, limit, says, where.")
    failed: list[str] = Field(description="Names of the judges that failed.")
    skipped: list[str] = Field(description="Names of the judges that lacked inputs.")


@module(id="judge.video", version=1, summary="Check a finished video: first frame, nothing still, change on the word, glitches, loudness, length, captions, sync.",
        when_to_use="After a render, before a person sees the video.", when_not_to_use="Before any video file exists.",
        inputs=VideoJudgeIn, outputs=VideoJudgeOut, requires=(), produces=(), cost=Cost("slow", ("cpu",), 20.0), effects="none", determinism="pure",
        grounding=(), fallback=None, fallback_reason="The judges are deterministic measurements of frames, audio and word times.",
        examples=(Example(inputs={"video": "draft.mp4"}, outputs={"passed": True, "verdicts": [], "failed": [], "skipped": []}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Judging the finished video",
        log_line=lambda i, o: "The finished video passed every check." if o.passed else f"The finished video failed: {', '.join(o.failed)}.")
def video_judges(ws: Workspace, inputs: VideoJudgeIn) -> VideoJudgeOut:
    from pathlib import Path
    from ...judges import judge_video

    try:
        words = ws.read_json("transcript").get("words", [])
    except Exception:                                                                       # noqa: BLE001
        words = []
    try:
        scenes = ws.read_json("scenes")
        scenes = scenes.get("scenes", scenes) if isinstance(scenes, dict) else scenes
    except Exception:                                                                       # noqa: BLE001
        scenes = []
    r = judge_video(Path(inputs.video).expanduser(), words=words, scenes=scenes, composition=inputs.composition, target_seconds=inputs.target_seconds, kind=inputs.kind)
    return VideoJudgeOut(**{k: r[k] for k in ("passed", "verdicts", "failed", "skipped")})
