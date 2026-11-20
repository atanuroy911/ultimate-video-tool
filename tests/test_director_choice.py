"""Director choice: registry, a client-PC request, and timeout fallback policy."""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from vt import directors
from vt.util import read_json, write_json


def _history_row(device, name, days_ago, assistant="claude"):
    return {"device": device, "name": name, "assistant": assistant,
            "last_seen": (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()}


def test_offline_directors_expire_without_waiting_for_a_new_connection(monkeypatch):
    monkeypatch.setattr(directors, "broker", directors.DirectorBroker())
    seen = {"claude:old": _history_row("old", "Retired laptop", 61),
            "claude:away": _history_row("away", "Travel laptop", 59)}
    path = directors._seen_path()
    write_json(path, seen)

    rows = {row["id"]: row for row in directors.listing()["directors"]}
    assert "claude@old" not in rows
    assert not rows["claude@away"]["available"]
    assert read_json(path) == seen, "reading the list must not rewrite history"

    directors.broker.connect("new", "New laptop", logged_in=True)
    assert "claude:old" not in read_json(path), "a later connection prunes expired history"


def test_recent_offline_aliases_keep_the_latest_registration_per_assistant(monkeypatch):
    monkeypatch.setattr(directors, "broker", directors.DirectorBroker())
    seen = {"claude:older": _history_row("older", "Laptop", 6),
            "claude:newer": _history_row("newer", " laptop ", 3),
            "codex:other": _history_row("other", "Laptop", 4, "codex")}
    path = directors._seen_path()
    write_json(path, seen)

    rows = directors.listing()["directors"]
    assert {row["id"] for row in rows if "last_seen" in row} == {"claude@newer", "codex@other"}
    assert read_json(path) == seen


def test_live_directors_keep_their_own_ids_while_hiding_old_offline_aliases(monkeypatch):
    broker = directors.DirectorBroker()
    monkeypatch.setattr(directors, "broker", broker)
    broker.connect("current", "Laptop", logged_in=True)
    broker.connect("also-live", "Laptop", logged_in=True)
    seen = read_json(directors._seen_path())
    seen["claude:old"] = _history_row("old", "Laptop", 1)
    seen["claude:current"] = _history_row("current", "Laptop", 61)
    write_json(directors._seen_path(), seen)

    rows = directors.listing()["directors"]
    assert {row["id"] for row in rows if row["kind"] == "claude-client"} == {"claude@current", "claude@also-live"}
    assert directors.candidates("claude@old") == ["claude@old", "local"], "a saved director choice never silently becomes a different ID"


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
    assert "call module_call with module_id craft.check" in scenes
    assert scenes.index("get_script_task") < scenes.index("submit_script") < scenes.index("preview_frames")
    assert "Look once" in scenes and "one revision" in scenes


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


def test_a_planning_session_is_never_cut_short_by_the_busy_wait(monkeypatch):
    """The setting "When that computer is busy, wait" defaults to 120 s; a Claude session that is working takes minutes (found 2026-11-20)."""
    for wait, expected in ((120, 1800.0), (30, 1800.0), (3600, 3600.0), (None, None)):
        monkeypatch.setattr(directors, "settings", lambda wait=wait: {"order": ["claude-client"], "wait_seconds": wait})
        assert directors.direct_timeout() == expected
