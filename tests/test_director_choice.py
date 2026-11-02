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


def test_api_lists_directors(client, monkeypatch):
    monkeypatch.setattr(directors.ClaudeCLIProvider, "available", lambda self: False)
    response = client.get("/api/directors")
    assert response.status_code == 200
    body = response.json()
    assert body["directors"][0]["id"] == "best"
    assert {d["id"] for d in body["directors"]} >= {"best", "local", "claude-server"}
