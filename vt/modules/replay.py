"""Replay recorded deterministic calls without consulting any AI provider."""
from __future__ import annotations

import json
from pathlib import Path

from .executor import Executor
from .registry import get_module


def replay(project_dir: Path) -> list[dict]:
    path = Path(project_dir) / "calls.jsonl"
    if not path.exists():
        raise FileNotFoundError(path)
    recorded = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    executor = Executor(project_dir)
    results = []
    for entry in recorded:
        if entry.get("status") != "ok":
            continue
        spec = get_module(entry["module"])
        if spec.determinism != "pure":
            # External results stay as their recorded artifacts. Replay never
            # makes a new network, model or generation request.
            continue
        result = executor.call(spec.id, entry.get("inputs") or {}, caller="replay",
                               why=f"Replay {entry['id']}", force=True,
                               auto_prerequisites=False)
        if not result.ok:
            raise RuntimeError(f"cannot replay {entry['id']}: {result.fix or result.summary}")
        results.append({"id": entry["id"], "module": spec.id, "artifacts": result.artifacts})
    return results
