"""The director's script review: scenes next to their words, feedback rounds, approval (vt/server/script_review_routes.py)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(ref):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_the_script_is_shown_scene_by_scene_with_its_words(client):
    r = client.get("/api/projects/reference/script-review").json()
    assert len(r["scenes"]) == 3 and r["approved"] is False
    first = r["scenes"][0]
    assert first["narration"] and first["layout"] in r["options"]["layouts"] and first["end"] > first["start"]
    assert all(isinstance(s["elements"], list) for s in r["scenes"])


def test_feedback_is_a_round_and_approval_waits_for_the_answer(client):
    assert client.post("/api/projects/reference/script-review/ask", json={"note": "  "}).status_code == 422
    r = client.post("/api/projects/reference/script-review/ask", json={"note": "make this more visual", "scene_id": "s2"}).json()
    assert r["rounds"][-1]["note"] == "make this more visual" and r["scenes"][1]["request"]["status"] == "queued"
    assert client.post("/api/projects/reference/script-review/ask", json={"note": "x", "scene_id": "nope"}).status_code == 422
    assert client.post("/api/projects/reference/script-review/approve").status_code == 409      # the director has not answered yet


def test_approve_and_reopen(client):
    r = client.post("/api/projects/reference/script-review/approve").json()
    assert r["approved"] is True and r["approved_at"]
    assert client.post("/api/projects/reference/script-review/reopen").json()["approved"] is False


def test_a_recording_kept_as_recorded_says_so_and_can_be_given_graphics(client, ref, monkeypatch):
    assert client.get("/api/projects/reference/script-review").json()["kept_as_recorded"] is False
    assert client.post("/api/projects/reference/script-review/add-graphics").status_code == 409      # directed normally already
    m = ref.meta()
    m.options.recording_edit = "subtitles"
    ref.save_meta(m)
    assert client.get("/api/projects/reference/script-review").json()["kept_as_recorded"] is True
    calls = []

    class _Job:
        def public(self):
            return {"id": "j"}
    monkeypatch.setattr("vt.server.app.start_pipeline", lambda p, stage, force, rerender=False: calls.append((stage, force)) or _Job())
    assert client.post("/api/projects/reference/script-review/add-graphics").json() == {"job": {"id": "j"}}
    assert calls == [("plan", True)] and ref.meta().options.recording_edit == "screen" and not ref.scenes_path.exists()
