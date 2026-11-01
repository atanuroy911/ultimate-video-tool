"""Completion contracts for the final Phase 2 module slices."""
from __future__ import annotations

import numpy as np
import soundfile as sf

from vt.modules.defs import load
from vt.modules.executor import Executor
from vt.modules.registry import get_module, lint_registry
from vt.modules.workspace import KNOWN_ARTIFACTS, Workspace
from vt.util import write_json


def test_completed_catalogue_is_registered_and_lints_cleanly():
    load()
    ids = (
        "project.create", "project.fetch_link", "audio.align_words", "audio.saliency", "text.fix",
        "understand.faces", "understand.people", "understand.video_shots", "understand.visual_for_word",
        "understand.impact_map", "direct.revise_script", "direct.set_direction", "direct.write_prompt",
        "cut.propose", "cut.validate", "cut.apply", "cut.snap_quiet",
        "fill.character_scene", "fill.generated_clip", "fill.graphic", "fill.illustration", "fill.sticker_icon", "fill.stock",
        "gen.fit_clip", "gen.vision_check", "timeline.place", "sound.mix", "judge.facts", "judge.impact_alignment",
        "judge.watch_and_revise", "render.preview", "publish.dispatch", "meta.ask_human", "meta.budget", "meta.finish", "meta.redo",
    )
    assert all(get_module(module_id).id == module_id for module_id in ids)
    assert lint_registry(known_artifacts=KNOWN_ARTIFACTS) == []


def test_workspace_undo_and_redo_round_trip(tmp_path):
    ws = Workspace(tmp_path)
    ws.put_json("direction", {"value": 1}, call_id="one")
    ws.put_json("direction", {"value": 2}, call_id="two")
    ws.undo("direction")
    assert ws.read_json("direction") == {"value": 1}
    ws.redo("direction")
    assert ws.read_json("direction") == {"value": 2}


def test_audio_first_saliency_alignment_and_cut_plan(tmp_path):
    master = tmp_path / "audio.master.wav"
    signal = np.r_[np.zeros(1200), np.ones(1200) * 0.2, np.zeros(1200)].astype(np.float32)
    sf.write(str(master), signal, 24000)
    executor = Executor(tmp_path)
    saliency = executor.call("audio.saliency", {"hop_seconds": 0.02})
    aligned = executor.call("audio.align_words", {"wav": str(master), "text": "hello world"})
    assert saliency.ok and saliency.output["points"]
    assert aligned.ok and len(aligned.output["words"]) == 2

    write_json(tmp_path / "transcript.json", {"language": "en", "words": [
        {"id": "w1", "text": "hello", "start": 0.0, "end": 0.4},
        {"id": "w2", "text": "world", "start": 3.0, "end": 3.4},
    ]})
    write_json(tmp_path / "emphasis.json", {"scores": {"w1": 0.8, "w2": 0.9}})
    impact = executor.call("understand.impact_map", {})
    proposed = executor.call("cut.propose", {"duration": 6.0, "max_hold": 3.0})
    checked = executor.call("cut.validate", {"duration": 6.0, "max_hold": 3.0, "slots": proposed.output["slots"]})
    applied = executor.call("cut.apply", {"duration": 6.0, "max_hold": 3.0, "slots": proposed.output["slots"]})
    assert impact.ok and proposed.ok and checked.output["valid"] and applied.ok
    assert max(slot["end"] - slot["start"] for slot in proposed.output["slots"]) <= 3.01


def test_direction_prompt_budget_and_finish_modules(tmp_path, monkeypatch):
    monkeypatch.setattr("vt.ai.complete_json", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    executor = Executor(tmp_path)
    direction = executor.call("direct.set_direction", {"goal": "Explain gravity", "audience": "students"})
    prompt = executor.call("direct.write_prompt", {"slot": {"words": [{"text": "falling apple"}]}, "style": "paper"})
    budget = executor.call("meta.budget", {"total_seconds": 10, "calls": [{"module": "cut.snap_quiet", "inputs": {"time": 1, "quiet": []}}]})
    assert direction.ok and prompt.output["source"] == "rules"
    assert budget.ok and budget.output["affordable"]
    write_json(tmp_path / "project.json", {"id": tmp_path.name, "created_at": "now"})
    asked = executor.call("meta.ask_human", {"question": "Approve?", "kind": "approval"})
    finished = executor.call("meta.finish", {"summary": "Finished the grounded video."})
    assert asked.ok and asked.output["request"]["status"] == "pending"
    assert finished.ok and finished.output["report"]["summary"].startswith("Finished")


def test_grounding_and_impact_judges(tmp_path):
    write_json(tmp_path / "transcript.json", {"language": "en", "words": [
        {"id": "w1", "text": "gravity", "start": 0.0, "end": 0.5},
        {"id": "w2", "text": "falls", "start": 0.5, "end": 1.0},
    ]})
    executor = Executor(tmp_path)
    good = executor.call("judge.facts", {"content": {"text": "gravity falls"}})
    bad = executor.call("judge.facts", {"content": {"text": "Mars rises"}})
    alignment = executor.call("judge.impact_alignment", {"impacts": [{"time": 1.0}, {"time": 2.0}], "changes": [1.05]})
    assert good.output["valid"] and not bad.output["valid"]
    assert alignment.output["score"] == 0.5 and len(alignment.output["misses"]) == 1


def test_social_dispatch_refuses_without_explicit_confirmation(tmp_path):
    write_json(tmp_path / "project.json", {"id": tmp_path.name, "created_at": "now"})
    (tmp_path / "exports").mkdir(); (tmp_path / "exports" / "final.mp4").write_bytes(b"video")
    result = Executor(tmp_path).call("publish.dispatch", {"group_id": "group", "title": "Grounded title"},
                                     skip_prerequisites=True)
    assert not result.ok and "confirmation" in result.fix
