import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(ref):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_list_and_describe(client):
    everything = client.get("/api/modules").json()
    assert len(everything) > 100 and {"id", "plain_name", "summary", "cost"} <= set(everything[0])
    audio = client.get("/api/modules", params={"group": "audio"}).json()
    assert audio and all(m["id"].startswith("audio.") for m in audio)
    assert any(m["id"] == "audio.find_retakes" for m in client.get("/api/modules", params={"q": "retake"}).json())
    detail = client.get("/api/modules/audio.find_retakes", params={"provider": "mcp"}).json()
    assert detail["inputs"]["type"] == "object" and detail["tool"]["name"] == "audio.find_retakes"
    assert client.get("/api/modules/nope.nope").status_code == 404
    assert client.get("/api/modules/audio.find_retakes", params={"provider": "x"}).status_code == 400


def test_call_validates_dry_runs_and_logs(client):
    url = "/api/projects/reference/modules/audio.find_retakes/call"
    bad = client.post("/api/projects/reference/modules/audio.prosody/call", json={"inputs": {"windows": "x"}}).json()
    assert bad["status"] == "failed" and bad["fix"]
    dry = client.post(url, json={"dry_run": True}).json()
    assert dry["status"] == "dry_run" and "estimate_seconds" in dry
    done = client.post(url, json={"why": "Look for abandoned openings."}).json()
    assert done["status"] in ("ok", "needs_input")
    entries = client.get("/api/projects/reference/calls").json()["entries"]
    assert entries and entries[-1]["module"] == "audio.find_retakes"
    assert entries[-1]["why"] == "Look for abandoned openings."
    assert client.post("/api/projects/nope/modules/audio.find_retakes/call", json={}).status_code == 404
    assert client.post("/api/projects/reference/modules/nope.nope/call", json={}).status_code == 404


def test_log_filters_one_call_download_and_cancel(client):
    from vt.modules.calls import append_call, append_technical
    from vt.project import Project

    folder = Project("reference").dir
    first = append_call(folder, {"id": "ca", "module": "audio.x", "level": "ok", "plain": "Cleaned the audio."})
    append_call(folder, {"id": "cb", "module": "cut.y", "level": "error", "plain": "Cut failed.", "token": "secret"})
    append_technical(folder, "ffmpeg line\napi_key=abc")
    base = "/api/projects/reference/calls"
    after = client.get(base, params={"after": first["seq"]}).json()["entries"]
    assert [e["id"] for e in after] == ["cb"]
    assert [e["id"] for e in client.get(base, params={"level": "error"}).json()["entries"]] == ["cb"]
    assert [e["id"] for e in client.get(base, params={"group": "audio"}).json()["entries"]] == ["ca"]
    assert [e["id"] for e in client.get(base, params={"q": "cleaned"}).json()["entries"]] == ["ca"]
    assert client.get(base + "/cb").json()["plain"] == "Cut failed."
    assert client.get(base + "/zz").status_code == 404
    assert "abc" not in client.get(base + "/technical").json()["text"]
    archive = zipfile.ZipFile(io.BytesIO(client.get(base + "/download").content))
    assert sorted(archive.namelist()) == ["calls.jsonl", "technical.log"]
    assert "secret" not in archive.read("calls.jsonl").decode()
    assert client.post(base + "/cb/cancel").status_code == 404


def test_background_call_streams_events_and_can_cancel(client):
    import threading
    from vt.modules.registry import Cost, Example, _REGISTRY, module
    from pydantic import BaseModel
    from vt.modules.tickets import wait

    started, release = threading.Event(), threading.Event()

    class In(BaseModel):
        pass

    class Out(BaseModel):
        done: bool = True

    @module(id="test.apiblock", version=1, summary="Wait for the test to release it.", when_to_use="Tests.",
            when_not_to_use="Never in a video.", inputs=In, outputs=Out, requires=(), produces=(),
            cost=Cost("fast", (), 1.0), effects="none", determinism="pure", grounding=(), fallback=None,
            fallback_reason="", examples=(Example({}, {"done": True}),), toolboxes=("studio",),
            plain_name="Waiting step", log_line=lambda i, o: "Waited.")
    def run(ws, inputs):
        started.set()
        release.wait(5)
        return Out()

    try:
        events = []
        hub = client.app.state.hub
        original = hub.emit
        hub.emit = lambda msg: (events.append(msg), original(msg))
        started_call = client.post("/api/projects/reference/modules/test.apiblock/call",
                                   json={"background": True}).json()
        assert started_call["status"] == "running" and started_call["ticket"]
        assert started.wait(5)
        live = client.get("/api/projects/reference/calls").json()["running"]
        assert live and live[0]["module"] == "test.apiblock"
        assert client.post(f"/api/projects/reference/calls/{live[0]['id']}/cancel").json()["ok"]
        release.set()
        result = wait(started_call["ticket"], 5)
        assert result.status == "cancelled"
        kinds = [e["type"] for e in events]
        assert "ticket" in kinds and "call" in kinds
        assert not client.get("/api/projects/reference/calls").json()["running"]
    finally:
        hub.emit = original
        _REGISTRY.pop("test.apiblock", None)
