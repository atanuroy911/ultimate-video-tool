"""The same module contract is available from the command line."""
import json

from typer.testing import CliRunner

from vt import paths
from vt.cli import app


def test_cli_lists_describes_and_calls_a_module(tmp_path, monkeypatch):
    import numpy as np
    import soundfile as sf

    monkeypatch.setattr(paths, "PROJECTS", tmp_path)
    project = tmp_path / "sample"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    (project / "transcript.raw.json").write_text(json.dumps({"words": []}), encoding="utf-8")
    sf.write(str(project / "input.wav"), np.zeros(24000, dtype="float32"), 24000)
    runner = CliRunner()
    assert "audio.find_retakes" in runner.invoke(app, ["modules", "list"]).output
    described = runner.invoke(app, ["modules", "describe", "audio.find_retakes"])
    assert described.exit_code == 0 and "transcript.raw" in described.output
    called = runner.invoke(app, ["call", "audio.find_retakes", "--project", "sample", "--json", "{}"])
    assert called.exit_code == 0, called.output
    assert '"ok": true' in called.output
    assert (project / "calls.jsonl").exists()
    for module_id, values in (("project.inspect_source", {}),
                              ("audio.prosody", {"windows": [[0.0, 1.0]]})):
        result = runner.invoke(app, ["call", module_id, "--project", "sample", "--json", json.dumps(values)])
        assert result.exit_code == 0 and '"ok": true' in result.output, result.output
    (project / "retakes.json").unlink()
    replayed = runner.invoke(app, ["replay", "sample"])
    assert replayed.exit_code == 0, replayed.output
    assert (project / "retakes.json").exists()


def test_cli_call_rejects_project_path_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROJECTS", tmp_path / "projects")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "project.json").write_text("{}", encoding="utf-8")
    result = CliRunner().invoke(app, ["call", "audio.find_retakes", "--project", "../outside"])
    assert result.exit_code != 0
    assert "Invalid project id" in result.output
    assert not (outside / "calls.jsonl").exists()


def test_cli_call_works_on_reference_project(ref):
    result = CliRunner().invoke(app, ["call", "audio.find_retakes", "--project", ref.id, "--json", "{}"])
    assert result.exit_code == 0 and '"ok": true' in result.output
