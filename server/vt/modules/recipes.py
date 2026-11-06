"""Stored L0 recipes; execution preserves the pipeline's stage ordering and progress."""
from __future__ import annotations

import json
from pathlib import Path

from .executor import Executor


def load_classic() -> list[str]:
    path = Path(__file__).resolve().parents[1] / "recipes" / "classic.json"
    calls = json.loads(path.read_text(encoding="utf-8"))["calls"]
    seen: set[str] = set()
    for call in calls:
        if call["id"] in seen or call["module"] != f"pipeline.{call['id']}" or not set(call["after"]) <= seen:
            raise ValueError(f"classic recipe has an unmet dependency at {call['id']}")
        seen.add(call["id"])
    return [call["id"] for call in calls]


def run_classic(pipeline, stages: list[str], *, force: bool = False) -> None:
    from ..pipeline import LABELS

    executor = Executor(pipeline.p.dir, pipeline=pipeline)
    for name in stages:
        pipeline._say(name, 0.0, LABELS[name])
        executor.call(f"pipeline.{name}", {"force": force}, caller="rules",
                      why="", force=True, raise_errors=True,
                      skip_prerequisites=True)
        pipeline._say(name, 1.0, "done")
        if getattr(pipeline, "pause_reason", None):                  # the plan is waiting for the person's approval: the later stages must not run
            break
