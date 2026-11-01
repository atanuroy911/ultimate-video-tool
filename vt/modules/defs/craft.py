"""Craft rules for directors (vt/craft.py): read them while planning, check a plan against them before rendering."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class RulesIn(BaseModel):
    area: str = Field("", description="hook, sync, pacing, captions, motion, ending, sound or facts; empty = all")


class RulesOut(BaseModel):
    rules: list[dict[str, Any]] = Field(description="Each rule: area, id, rule, why, whether it is measured, and its source.")


@module(
    id="craft.rules", version=1, summary="The craft rules for a high-retention short video: hook, say-it-show-it, pacing, captions, motion, ending, sound, facts.",
    when_to_use="Before and while directing or revising any video: follow these rules.", when_not_to_use="To check a finished plan (use craft.check).",
    inputs=RulesIn, outputs=RulesOut, requires=(), produces=(),
    cost=Cost("fast", ("cpu",), 0.01), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="Static rules.",
    examples=(Example(inputs={"area": "hook"}, outputs={"rules": [{"id": "hook.frame0"}]}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Reading the craft rules", log_line=lambda i, o: f"Read {len(o.rules)} craft rule(s).",
)
def craft_rules(ws: Workspace, inputs: RulesIn) -> RulesOut:
    from ... import craft

    return RulesOut(rules=craft.rules(inputs.area))


class EmptyIn(BaseModel):
    pass


class CheckOut(BaseModel):
    report: dict[str, Any] = Field(description="score (0-100), violations [{rule, t0, t1, severity, says, fix}], passed and unmeasured rule ids.")


@module(
    id="craft.check", version=1, summary="Check a planned video against the measurable craft rules; each violation has its time and a fix.",
    when_to_use="After planning or editing scenes and before rendering; fix critical and major violations first.",
    when_not_to_use="For rendered pixels (the retention scorecard measures the MP4).",
    inputs=EmptyIn, outputs=CheckOut, requires=("scenes", "transcript", "beats"), produces=("craft",),
    cost=Cost("fast", ("cpu",), 0.5), effects="writes_artifact", determinism="pure", grounding=("report",),
    fallback=None, fallback_reason="Rule based.",
    examples=(Example(inputs={}, outputs={"report": {"score": 92, "violations": []}}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Checking the craft rules", log_line=lambda i, o: f"Craft score {o.report.get('score')} with {len(o.report.get('violations', []))} violation(s).",
)
def craft_check(ws: Workspace, inputs: EmptyIn) -> CheckOut:
    from ... import craft
    from ...project import Project
    from ...util import write_json

    project = Project(ws.root.name, ws.root.parent)
    report = craft.check(project)
    write_json(project.dir / "craft.json", report)
    return CheckOut(report=report)
