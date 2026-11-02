"""Director choice: registry, a client-PC request, and timeout fallback policy."""
from __future__ import annotations

import threading

from vt import directors


def test_connected_client_is_in_registry_and_can_finish_a_targeted_request(monkeypatch):
    sent = []
    monkeypatch.setattr(directors.ClaudeCLIProvider, "available", lambda self: False)
    monkeypatch.setattr(directors, "usage_today", lambda: {"calls": 0, "cost_usd": 0.0, "seconds": 0.0})
    directors.broker.connect("laptop", "Roy's laptop", version="2.1", logged_in=True, send=sent.append)
    try:
        result = {}

        def ask():
            result.update(directors.broker.request("laptop", "demo", "Direct it", 1.0))

        thread = threading.Thread(target=ask)
        thread.start()
        for _ in range(100):
            if sent:
                break
            threading.Event().wait(0.005)
        assert sent[0]["type"] == "direct" and sent[0]["project"] == "demo"
        assert directors.broker.finish(sent[0]["request"], ok=True, detail={"approved": True})
        thread.join(1)
        assert result == {"ok": True, "error": "", "approved": True}
        client = next(d for d in directors.listing()["directors"] if d["id"] == "claude@laptop")
        assert client["available"] is True and client["label"] == "Claude on Roy's laptop"
    finally:
        directors.broker.disconnect("laptop")


def test_absent_or_silent_client_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(directors, "settings", lambda: {"order": ["claude-client", "local"], "wait_seconds": 5})
    assert directors.candidates("best")[-1] == "local"
    assert directors.broker.request("missing", "demo", "Direct it", 0.01)["ok"] is False


def test_reconnect_is_not_removed_by_old_socket_and_send_failure_is_clean():
    first, second = [], []
    first_send, second_send = first.append, second.append
    directors.broker.connect("same", "First", logged_in=True, send=first_send)
    current = directors.broker.connect("same", "Second", logged_in=True, send=second_send)
    directors.broker.disconnect("same", first_send)
    assert directors.broker.devices()[0] is current
    directors.broker.disconnect("same")

    def broken(_message):
        raise OSError("gone")

    directors.broker.connect("broken", "Broken", logged_in=True, send=broken)
    try:
        result = directors.broker.request("broken", "demo", "Direct it", 0.01)
        assert result["ok"] is False and "OSError" in result["reason"]
    finally:
        directors.broker.disconnect("broken")


def test_client_prompts_name_real_mcp_tools():
    reel = directors.client_prompt("demo")
    scenes = directors.client_scene_prompt("demo")
    assert "get_reel_plan" in reel and "check_reel_plan" in reel and "module_call_tool" in reel
    assert "craft_check" not in scenes and "module_call_tool" in scenes and "craft.check" in scenes


def test_reel_plan_mcp_tools_return_prompts_and_actionable_checks(ref):
    from vt.direction import plan_doc as PD
    from vt.mcp.server import check_reel_plan, get_reel_plan

    plan = PD.PlanDoc(
        idea=PD.Idea(style="cartoon", character="a person in a blue coat",
                     places={"room": "inside a bright studio room, beside a chair"}),
        moments=[PD.Moment(id="s1", start=0, end=2, sentence_ids=["b1"], text="A point",
                           draw="A person holds a newspaper", place="room")],
    )
    PD.save(ref.dir, plan)
    payload = get_reel_plan(ref.id)
    assert payload["plan"]["moments"][0]["id"] == "s1"
    assert "Setting: inside a bright studio room" in payload["shots"][0]["prompt"]
    checks = check_reel_plan(ref.id)
    assert checks["ok"] is False
    assert any(issue["rule"] == "picture.drawable" for issue in checks["issues"])


def test_api_lists_directors(monkeypatch):
    from vt.server.app import app, get_directors

    monkeypatch.setattr(directors.ClaudeCLIProvider, "available", lambda self: False)
    assert any(getattr(route, "path", "") == "/api/directors" for route in app.routes)
    body = get_directors()
    assert body["directors"][0]["id"] == "best"
    assert {d["id"] for d in body["directors"]} >= {"best", "local", "claude-server"}
