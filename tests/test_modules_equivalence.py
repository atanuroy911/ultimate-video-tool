"""Compare the recipe with the pre-module driver on the same scratch project path."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from vt.pipeline import LABELS, ORDER, Pipeline
from vt.project import Project


def _legacy_driver(pipeline: Pipeline, stages: list[str], *, force: bool = False) -> None:
    """Exact former Pipeline.run driver, retained here as a migration oracle."""
    from vt import gpu

    gpu.prepare()
    pipeline.p.update_meta(status="processing")
    try:
        for name in stages:
            pipeline._say(name, 0.0, LABELS[name])
            getattr(pipeline, f"stage_{name}")(force)
            pipeline._say(name, 1.0, "done")
        pipeline.p.update_meta(status="planned")
    except Exception:
        pipeline.p.update_meta(status="error")
        raise


def _hashes(root: Path) -> dict[str, str]:
    # The executor's provenance and call records are new sidecars. Legacy
    # project and generated media files are compared byte for byte.
    excluded = {"calls.jsonl", "artifacts.json", ".module_cache.json"}
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file() and path.name not in excluded
            and ".artifact_versions" not in path.parts}


def _compare(p: Project, tmp_path: Path, *, from_stage: str | None = None) -> None:
    stages = ORDER[:] if p.script_path.exists() else [x for x in ORDER if x != "voice"]
    if from_stage:
        stages = stages[stages.index(from_stage):]
    starting = tmp_path / "starting"
    shutil.copytree(p.dir, starting)
    _legacy_driver(Pipeline(p), stages, force=bool(from_stage))
    before = _hashes(p.dir)
    shutil.rmtree(p.dir)
    shutil.copytree(starting, p.dir)
    Pipeline(p).run(from_stage=from_stage)
    after = _hashes(p.dir)
    assert after == before
    stage_times = {key: value["done_at"] for key, value in p.meta().stages.items()}
    Pipeline(p).run(from_stage=from_stage)
    assert _hashes(p.dir) == after
    assert {key: value["done_at"] for key, value in p.meta().stages.items()} == stage_times


def test_reference_is_byte_identical(ref, tmp_path, monkeypatch):
    monkeypatch.setattr("vt.project.now_iso", lambda: "2026-10-26T00:00:00+00:00")
    monkeypatch.setattr("vt.pipeline.now_iso", lambda: "2026-10-26T00:00:00+00:00")
    monkeypatch.setattr("vt.context.now_iso", lambda: "2026-10-26T00:00:00+00:00")
    _compare(ref, tmp_path, from_stage="plan")


@pytest.mark.slow
@pytest.mark.parametrize("sample,language", [
    ("samples/audio/bn_plain.mp3", "bn"),
    ("english sample.mp3", "en"),
])
def test_recordings_are_byte_identical(projects_dir, tmp_path, monkeypatch, sample, language):
    source = Path(__file__).resolve().parents[1] / sample
    if not source.exists():
        pytest.skip(f"sample missing: {sample}")
    if language == "en":
        # Exercise recognition on a fixed excerpt of the owner's long English
        # recording. The full 227 s recording is an extended QA input;
        # keeping this regression gate short makes it practical to run in CI.
        import subprocess
        from vt.util import find_tool

        excerpt = tmp_path / "english-excerpt.wav"
        subprocess.run([find_tool("ffmpeg"), "-y", "-loglevel", "error", "-i", str(source),
                        "-t", "20", "-ac", "1", "-ar", "16000", str(excerpt)], check=True)
        source = excerpt
    monkeypatch.setattr("vt.project.now_iso", lambda: "2026-10-26T00:00:00+00:00")
    monkeypatch.setattr("vt.pipeline.now_iso", lambda: "2026-10-26T00:00:00+00:00")
    monkeypatch.setattr("vt.context.now_iso", lambda: "2026-10-26T00:00:00+00:00")
    p = Project.create(f"equivalence-{language}", source, language=language, theme="paper")
    _compare(p, tmp_path)
