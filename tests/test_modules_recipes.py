"""The classic recipe must use exactly the legacy pipeline order."""
from vt.modules.defs import load
from vt.modules.recipes import load_classic
from vt.modules.registry import get_module, lint_registry
from vt.pipeline import ORDER
from vt.modules.workspace import Workspace


def test_classic_has_twelve_registered_stage_adapters():
    load()
    assert load_classic() == ORDER
    assert not lint_registry()
    for name in ORDER:
        spec = get_module(f"pipeline.{name}")
        assert spec.native_outputs
        assert spec.run.__name__ == "run_stage"


def test_artifact_undo_restores_bytes_and_marks_dependants_stale(tmp_path):
    ws = Workspace(tmp_path)
    original = ws.put_json("transcript.raw", {"words": ["first"]}, call_id="one")
    ws.put_json("audio.retakes", {"cuts": []}, call_id="two",
                inputs={"transcript.raw": original["hash"]})
    ws.put_json("transcript.raw", {"words": ["second"]}, call_id="three")
    assert ws.stale("audio.retakes")
    restored = ws.undo("transcript.raw")
    assert restored["hash"] == original["hash"]
    assert not ws.stale("audio.retakes")


def test_stage_owned_binary_can_be_undone(tmp_path):
    ws = Workspace(tmp_path)
    path = tmp_path / "audio.master.wav"
    path.write_bytes(b"first")
    ws.snapshot_existing("audio.master")
    path.write_bytes(b"second")
    ws.record_existing("audio.master", call_id="stage")
    ws.undo("audio.master")
    assert path.read_bytes() == b"first"


def test_composition_folder_is_hashed_and_undoable(tmp_path):
    ws = Workspace(tmp_path)
    folder = tmp_path / "composition" / "9x16"
    folder.mkdir(parents=True)
    (folder / "data.json").write_bytes(b"first")
    original = ws.ref("composition")
    ws.snapshot_existing("composition")
    (folder / "data.json").write_bytes(b"second")
    ws.record_existing("composition", call_id="compose")
    assert ws.ref("composition")["hash"] != original["hash"]
    ws.undo("composition")
    assert (folder / "data.json").read_bytes() == b"first"


def test_voice_stage_runs_first_for_a_script(projects_dir, tmp_path, monkeypatch):
    import json
    import soundfile as sf
    import numpy as np
    from vt.project import Project
    from vt.pipeline import Pipeline
    from vt.util import write_json

    source = tmp_path / "placeholder.wav"
    sf.write(str(source), np.zeros(2400, dtype="float32"), 24000)
    p = Project.create("script module", source, language="en", theme="paper")
    write_json(p.script_path, {"text": "Hello world", "engine": "fake", "voice": "fake", "rate": 1.0})

    def fake_synthesize(text, output, **kwargs):
        sf.write(str(output), np.ones(24000, dtype="float32") * 0.01, 24000)
        return {"duration": 1.0, "sentences": [{"text": text, "start": 0.0, "end": 1.0}], "engine": "fake"}

    monkeypatch.setattr("vt.tts.synthesize", fake_synthesize)
    Pipeline(p).run(to_stage="voice")
    calls = [json.loads(line) for line in (p.dir / "calls.jsonl").read_text().splitlines()]
    assert [call["module"] for call in calls] == ["pipeline.voice"]
    assert p.script_path.exists() and p.input_audio.stat().st_size > source.stat().st_size
