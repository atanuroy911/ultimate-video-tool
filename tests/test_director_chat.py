"""Talking to the director (vt/script/chat.py and /api/projects/{pid}/director/chat)."""
import copy
import threading

from vt import ai
from vt.script import chat
from vt.script.models import VideoScript
from vt.util import read_json


def _stick(p):
    from vt.script.rules_stick import rules_script
    from vt.script.service import apply_script, set_script_kind

    set_script_kind(p, "stick")
    s = rules_script(p.transcript(), p.beats(), p.scenes(), kind="stick", language=p.meta().language, aspect=p.meta().aspect)
    assert apply_script(p, s.model_dump(by_alias=True, exclude_none=True), planner="rules", compose=False)["ok"]
    return s


def test_a_request_changes_the_plan_and_says_what_changed(ref, monkeypatch):
    from vt.project import Project

    p = Project("reference")
    cur = _stick(p)
    want = cur.model_dump(by_alias=True, exclude_none=True)
    want["cast"][0]["style"]["height"] = "elder"                       # "the narrator should be an old man"
    seen = {}

    def fake(user, schema, **k):
        seen["user"] = user
        return want

    monkeypatch.setattr(ai, "complete_json", fake)
    monkeypatch.setattr("vt.pipeline.compose_all", lambda p: None)
    res = chat.talk(p, "make the narrator an old man", provider=ai.FakeProvider({}))
    assert res["ok"] and "New look for" in res["reply"]
    assert res["previous_plan"] and res["previous_state"]
    assert res["changed_scenes"] == [s.id for s in p.scenes().scenes] and res["removed_scenes"] == []
    assert res["previous_plan"] == read_json(p.dir / "scenes.prev.json")
    assert "REQUEST FROM THE PERSON: make the narrator an old man" in seen["user"] and "CURRENT SCRIPT" in seen["user"]
    assert VideoScript.model_validate(read_json(p.dir / "video_script.json")).cast[0].style.height == "elder"
    h = chat.history(p)
    assert [m["from"] for m in h] == ["person", "director"] and (p.dir / "scenes.prev.json").exists()     # undo keeps the previous plan


def test_no_ai_is_a_plain_error_not_a_crash(ref, monkeypatch):
    from fastapi.testclient import TestClient

    import vt.server.app as A

    with TestClient(A.app) as c:
        assert c.post("/api/projects/reference/director/chat", json={"message": "  "}).status_code == 400
        assert c.get("/api/projects/reference/director").json()["messages"] == []


def test_a_timeline_edit_made_while_the_director_works_is_never_overwritten(ref, monkeypatch):
    from vt.project import Project

    p = Project("reference")
    cur = _stick(p)
    want = cur.model_dump(by_alias=True, exclude_none=True)
    want["cast"][0]["style"]["height"] = "elder"

    def fake(user, schema, **kwargs):
        latest = p.scenes()
        assert latest
        p.save_scenes(latest.model_copy(update={"planner": "manual"}))
        return want

    monkeypatch.setattr(ai, "complete_json", fake)
    monkeypatch.setattr("vt.pipeline.compose_all", lambda p: None)
    res = chat.talk(p, "make the narrator an old man", provider=ai.FakeProvider({}))
    assert not res["ok"] and "edited while I was working" in res["reply"]
    assert p.scenes().planner == "manual" and res["previous_plan"] is None and res["changed_scenes"] == []


def test_director_state_round_trip_restores_the_script_and_plan_together(ref, monkeypatch):
    from vt.project import Project

    p = Project("reference")
    cur = _stick(p)
    p.update_meta(status="review")
    before = chat.director_state(p)
    want = cur.model_dump(by_alias=True, exclude_none=True)
    want["cast"][0]["style"]["height"] = "elder"
    monkeypatch.setattr(ai, "complete_json", lambda *args, **kwargs: want)
    monkeypatch.setattr("vt.pipeline.compose_all", lambda p: None)
    result = chat.talk(p, "make the narrator an old man", provider=ai.FakeProvider({}))
    after = chat.director_state(p)
    assert result["ok"] and after != before

    chat.restore_director_state(p, result["previous_state"])
    assert chat.director_state(p) == before
    chat.restore_director_state(p, after)
    assert chat.director_state(p) == after


def test_compiled_plan_change_markers_include_reorders_globals_and_removals(ref):
    from vt.project import Project

    p = Project("reference")
    _stick(p)
    old = p.scenes()
    assert old and len(old.scenes) > 1
    reordered = old.model_copy(update={"scenes": list(reversed(old.scenes))})
    touched, removed = chat.changed_plan_scenes(old, reordered)
    assert touched == [s.id for i, s in enumerate(reordered.scenes) if s.id != old.scenes[i].id] and removed == []

    themed = old.model_copy(update={"theme": old.theme + "-changed"})
    touched, removed = chat.changed_plan_scenes(old, themed)
    assert touched == [s.id for s in themed.scenes] and removed == []

    shorter = old.model_copy(update={"scenes": old.scenes[:-1]})
    touched, removed = chat.changed_plan_scenes(old, shorter)
    assert touched == [] and removed == [old.scenes[-1].id]


def test_apply_script_compare_and_commit_is_locked(ref, monkeypatch):
    from vt.project import Project
    from vt.script import service

    p = Project("reference")
    script = _stick(p)
    expected = p.scenes().model_dump(exclude_none=True)
    wanted = script.model_dump(by_alias=True, exclude_none=True)
    wanted["cast"][0]["style"]["height"] = "elder"
    inside_commit = threading.Event()
    release_commit = threading.Event()
    original_write = service.write_json

    def paused_write(path, value):
        if path.name == "video_script.json" and not inside_commit.is_set():
            inside_commit.set()
            assert release_commit.wait(3)
        return original_write(path, value)

    monkeypatch.setattr(service, "write_json", paused_write)
    director_result = {}
    user_finished = threading.Event()

    def director():
        director_result.update(service.apply_script(p, wanted, planner="claude", compose=False, expected_plan=expected))

    def user_edit():
        with p.scenes_lock():
            latest = p.scenes()
            p.save_scenes(latest.model_copy(update={"planner": "manual"}))
        user_finished.set()

    director_thread = threading.Thread(target=director)
    director_thread.start()
    assert inside_commit.wait(3)
    user_thread = threading.Thread(target=user_edit)
    user_thread.start()
    assert not user_finished.wait(0.1), "a plan writer entered halfway through the Director's compare-and-commit"
    release_commit.set()
    director_thread.join(3)
    user_thread.join(3)
    assert director_result["ok"] and user_finished.is_set() and p.scenes().planner == "manual"


def test_director_state_route_rolls_back_when_compose_fails(ref, monkeypatch):
    from fastapi.testclient import TestClient

    import vt.server.app as A
    from vt.project import Project
    from vt.util import write_json

    p = Project("reference")
    _stick(p)
    p.update_meta(status="review")
    before = chat.director_state(p)
    target = copy.deepcopy(before)
    target["plan"]["planner"] = "manual"
    target["status"] = "planned"
    backup = copy.deepcopy(before["plan"])
    write_json(p.dir / "scenes.prev.json", backup)

    def fail_compose(project):
        raise RuntimeError("compose failed for the test")

    monkeypatch.setattr(A, "compose_all", fail_compose)
    with TestClient(A.app) as client:
        response = client.put("/api/projects/reference/director/state", json={"state": target})
    assert response.status_code == 500
    assert chat.director_state(p) == before
    assert read_json(p.dir / "scenes.prev.json") == backup
