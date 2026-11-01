"""A real module runs through validation, artifacts, cache and the call log."""
import json
import threading

from pydantic import BaseModel, Field

from vt.modules.executor import Executor
from vt.modules.budget import Budget


def test_missing_prerequisite_names_the_next_step(tmp_path):
    result = Executor(tmp_path).call("audio.find_retakes")
    assert result.status == "needs_input"
    assert "transcript.raw" in result.fix
    assert len((tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_real_retakes_are_cached_until_the_transcript_changes(tmp_path):
    executor = Executor(tmp_path)
    words = [
        {"text": "today", "start": 0.0, "end": 0.3},
        {"text": "we", "start": 0.3, "end": 0.5},
        {"text": "talk", "start": 0.5, "end": 0.8},
        {"text": "today", "start": 1.5, "end": 1.8},
        {"text": "we", "start": 1.8, "end": 2.0},
        {"text": "talk", "start": 2.0, "end": 2.3},
        {"text": "more", "start": 2.3, "end": 2.6},
    ]
    executor.ws.put_json("transcript.raw", {"words": words}, call_id="seed")
    first = executor.call("audio.find_retakes", why="Remove the abandoned opening.")
    assert first.ok and not first.cached
    assert first.output["cuts"][0]["text"] == "today we talk"
    assert executor.ws.read_json("audio.retakes") == first.output
    second = executor.call("audio.find_retakes")
    assert second.ok and second.cached and second.cost["seconds"] == 0
    executor.ws.put_json("transcript.raw", {"words": []}, call_id="edit")
    third = executor.call("audio.find_retakes")
    assert third.ok and not third.cached and third.output == {"cuts": []}
    lines = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [line["seq"] for line in lines] == [1, 2, 3]
    assert lines[0]["why"] == "Remove the abandoned opening."


def test_budget_refuses_before_running(tmp_path):
    executor = Executor(tmp_path)
    (tmp_path / "input.wav").write_bytes(b"not a real wav")
    result = executor.call("audio.prosody", {"windows": [[0, 1]]}, max_seconds=0.1)
    assert result.status == "refused"
    assert not (tmp_path / "prosody.json").exists()


def test_shared_budget_refuses_a_call_before_work(tmp_path):
    budget = Budget(seconds=0.1)
    (tmp_path / "input.wav").write_bytes(b"not a real wav")
    result = Executor(tmp_path).call("audio.prosody", {"windows": [[0, 1]]}, budget=budget)
    assert result.status == "refused" and budget.spent == 0


def test_async_ticket_can_cancel_before_artifact_commit(tmp_path):
    from vt.modules.registry import Cost, Example, _REGISTRY, module
    from vt.modules.tickets import cancel, wait

    started, release = threading.Event(), threading.Event()

    class Empty(BaseModel):
        pass

    class Out(BaseModel):
        value: int = Field(description="The completed value.")

    @module(id="test.blocking", version=1, summary="Wait for the test to release a call.",
            when_to_use="In the cancellation test.", when_not_to_use="In production.",
            inputs=Empty, outputs=Out, requires=(), produces=("audio.prosody",),
            cost=Cost("slow", ("cpu",), 1.0), effects="writes_artifact", determinism="pure",
            grounding=(), fallback=None, fallback_reason="Test implementation is deterministic.",
            examples=(Example(inputs={}, outputs={"value": 1}),),
            toolboxes=("full",), plain_name="Blocking step", log_line=lambda i, o: "Blocking step finished.")
    def blocking(ws, inputs):
        started.set()
        release.wait(5)
        return Out(value=1)

    try:
        running = Executor(tmp_path).call_async("test.blocking")
        assert running.status == "running" and started.wait(2)
        assert cancel(running.ticket)
        release.set()
        result = wait(running.ticket, timeout=5)
        assert result.status == "cancelled"
        assert not (tmp_path / "prosody.json").exists()
    finally:
        release.set()
        _REGISTRY.pop("test.blocking", None)


def test_prerequisite_chain_uses_classic_stages_for_subtitles(projects_dir):
    from pathlib import Path
    from vt.project import Project
    from vt.util import write_json

    source = Path(__file__).resolve().parents[1] / "samples" / "audio" / "bn_plain.mp3"
    p = Project.create("prerequisites", source, language="en", theme="paper")
    write_json(p.dir / "subs.raw.json", {"words": [
        {"text": "hello", "start": 0.1, "end": 0.5},
        {"text": "world", "start": 0.6, "end": 1.0},
    ]})
    result = Executor(p.dir).call("audio.find_retakes")
    assert result.ok
    assert p.raw_transcript_path.exists()
    called = [json.loads(line)["module"] for line in (p.dir / "calls.jsonl").read_text().splitlines()]
    assert called[-1] == "audio.find_retakes"
    assert "pipeline.asr" in called


def test_events_report_start_and_persisted_completion(tmp_path):
    seen = []
    executor = Executor(tmp_path, on_event=seen.append)
    result = executor.call("audio.find_retakes")
    assert result.status == "needs_input"
    assert [event["type"] for event in seen] == ["call_started", "call"]
    assert seen[-1]["entry"]["seq"] == 1


def test_resource_locks_are_ordered_across_callers():
    from concurrent.futures import ThreadPoolExecutor
    from vt.modules.resources import acquire

    def work(names):
        for _ in range(20):
            with acquire(names):
                pass
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(work, ("gpu0", "comfy"))
        b = pool.submit(work, ("comfy", "gpu0"))
        assert a.result(timeout=3) and b.result(timeout=3)
