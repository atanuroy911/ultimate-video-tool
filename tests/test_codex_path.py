"""Plan step B11: Codex on the person's computer is a director like Claude: it gets the same brief, the same tools (frame facts, frames), the frames themselves when it is asked a question, and no Claude
model name. Codex is not installed on the computer these tests run on, so a stand-in for the helper answers (as client/desktop/test-director-runner.js does for the Codex program itself)."""
from __future__ import annotations

import base64
from pathlib import Path

import pytest
from PIL import Image

from test_one_director import Laptop, _choose, _no_computer_left_connected, _no_plan, _watch_the_other_minds   # noqa: F401  (the autouse fixture comes along)


def _scene_plan(ref, planner):
    ref.save_scenes(ref.scenes().model_copy(update={"planner": planner}))


def _direct(ref, monkeypatch, assistant):
    """Make one planning task go to a stand-in computer running this assistant: the task the server sends."""
    from vt import directors
    from vt.pipeline import Pipeline

    _no_plan(ref)
    _watch_the_other_minds(monkeypatch)
    _choose(ref, f"{assistant}@laptop")
    laptop = Laptop(directors, assistant=assistant, plan=lambda m: _scene_plan(ref, "assistant" if assistant == "codex" else "claude"))
    Pipeline(ref).stage_plan(force=True)
    return [m for m in laptop.sent if m["type"] == "direct"][0], ref.scenes().planner


def test_codex_gets_the_same_brief_as_claude(ref, monkeypatch):
    from vt import directors

    claude, planned_by_claude = _direct(ref, monkeypatch, "claude")
    codex, planned_by_codex = _direct(ref, monkeypatch, "codex")
    assert codex["prompt"] == claude["prompt"] == directors.client_scene_prompt(ref.id), "one brief for every director"
    for needed in ("preview_frames", "frame_facts", "update_scene", "submit_script", "craft.check"):
        assert needed in codex["prompt"], needed
    assert (claude["assistant"], codex["assistant"]) == ("claude", "codex") and planned_by_claude == "claude" and planned_by_codex == "assistant"


def test_codex_is_not_given_a_claude_model(ref, monkeypatch, tmp_path):
    from vt import directors
    from vt.ai import providers as AIP

    assert directors.task_model("claude") == "sonnet" and directors.task_model("codex") == ""
    directors.save_settings(model="opus")
    assert directors.task_model("claude") == "opus" and directors.task_model("codex") == "", "the Claude setting is Claude's"
    claude, _ = _direct(ref, monkeypatch, "claude")
    codex, _ = _direct(ref, monkeypatch, "codex")
    assert claude["model"] == "opus" and codex["model"] == ""
    laptop = Laptop(directors, device="desk", assistant="codex")
    AIP.ClientProvider("codex@desk").complete("s", "q", {"type": "object"}, [], 100, 30, 0.2)
    assert [m["model"] for m in laptop.sent if m["type"] == "ask"] == [""] and AIP.ClientProvider("codex@desk").model() == "" and AIP.ClientProvider("claude@desk").model() == "opus"


def test_a_question_to_codex_carries_the_pictures_and_the_measured_facts(ref, monkeypatch, tmp_path):
    import vt.ai.providers as P
    import vt.director_review as R
    import vt.render.hyperframes as H
    from vt import directors

    frame = tmp_path / "frame.png"
    Image.new("RGB", (90, 160), (200, 80, 80)).save(frame)
    sid = ref.scenes().scenes[0].id
    monkeypatch.setattr(R, "_frame_times", lambda comp, plan: [(sid, 1.0)])
    monkeypatch.setattr(H, "snapshot", lambda *a, **k: [frame])
    facts = ["element 1 (tag) has letters too small to read on a phone."]
    monkeypatch.setattr(H, "frame_facts", lambda comp, times: {1.0: facts})
    laptop = Laptop(directors, assistant="codex")
    _watch_the_other_minds(monkeypatch)
    report = R.review(ref, compose=lambda p: None, provider=P.ClientProvider("codex@laptop"))
    asks = [m for m in laptop.sent if m["type"] == "ask"]
    assert asks and all(m["assistant"] == "codex" and m["model"] == "" for m in asks)
    assert all(len(m["images"]) == 1 and base64.b64decode(m["images"][0])[:4] == b"\x89PNG" for m in asks), "the frame itself goes with the question"
    assert all(facts[0] in m["prompt"] for m in asks), "and the exact measurements, in the words the director reads"
    assert report["left"] == [{"scene": sid, "at": 1.0, "facts": facts}], "what it left standing is listed for the person"


def test_codex_has_the_same_tools_and_the_same_server(ref):
    from vt.mcp import server as M

    for tool in ("frame_facts", "preview_frames", "update_scene", "submit_script", "submit_story", "get_script_task", "get_story_task", "check_reel_plan"):
        assert callable(getattr(M, tool, None)), f"{tool} is a tool every MCP client gets"
    assert "exact measurements" in (M.frame_facts.__doc__ or "").lower() or "covers" in (M.frame_facts.__doc__ or "").lower()
    # the person's story and script prompts do not depend on who answers
    from vt import directors

    assert directors.client_story_prompt(ref.id) and directors.client_prompt(ref.id) and "codex" not in directors.client_scene_prompt(ref.id).lower()
