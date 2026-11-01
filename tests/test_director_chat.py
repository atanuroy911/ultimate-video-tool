"""Talking to the director (vt/script/chat.py and /api/projects/{pid}/director/chat)."""
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
