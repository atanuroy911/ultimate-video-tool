"""The plan review (docs/plans/PLAN-DIRECTOR-MODULES.MD section 8, Phase 6): a plan with no GPU, typed edits, the gate before anything is made, the routes and the log."""
import pytest
from fastapi.testclient import TestClient

from vt.direction import plan_doc as PD


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    monkeypatch.setattr("vt.ai.providers.ai_enabled", lambda: False)


@pytest.fixture()
def project(ref):
    meta = ref.meta()
    meta.options.look = "reel"
    ref.save_meta(meta)
    return ref


@pytest.fixture()
def client(project):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def plain_client(ref):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_a_plan_covers_every_sentence_in_order_and_costs_no_gpu_to_write(project):
    plan = PD.build(project, use_ai=False)
    ids = [b.id for b in project.beats().beats]
    assert PD.matches(plan, ids)
    assert [m.id for m in plan.moments] == [f"s{i}" for i in range(1, len(plan.moments) + 1)]
    for m in plan.moments:
        assert m.words and m.start < m.end and m.start - 0.01 <= m.beat.time <= m.end + 0.01
        assert m.medium == "made" and {a.medium for a in m.alternatives} == {"repeat", "card"} and m.draw and m.why
    assert plan.state == "draft" and plan.estimate.made == len(plan.moments) and plan.estimate.gpu_seconds == len(plan.moments) * plan.still_seconds
    assert PD.load(project.dir).rev == 0


def test_the_estimate_follows_the_edits(project):
    plan = PD.build(project, use_ai=False)
    before = plan.estimate.total_seconds
    PD.apply_edit(plan, {"op": "set_medium", "moment": "s2", "medium": "card"}, project)
    PD.save(project.dir, plan)
    assert plan.estimate.total_seconds == before - plan.still_seconds and plan.estimate.made == len(plan.moments) - 1
    assert plan.moment("s2").medium == "card" and plan.rev == 1


def test_a_locked_moment_refuses_change_until_it_is_unlocked(project):
    plan = PD.build(project, use_ai=False)
    PD.apply_edit(plan, {"op": "lock", "moment": "s1"}, project)
    with pytest.raises(PD.PlanError, match="locked"):
        PD.apply_edit(plan, {"op": "set_medium", "moment": "s1", "medium": "card"}, project)
    PD.apply_edit(plan, {"op": "unlock", "moment": "s1"}, project)
    PD.apply_edit(plan, {"op": "set_medium", "moment": "s1", "medium": "card"}, project)


def test_the_first_moment_cannot_repeat_a_picture_that_does_not_exist(project):
    plan = PD.build(project, use_ai=False)
    with pytest.raises(PD.PlanError, match="first moment"):
        PD.apply_edit(plan, {"op": "set_medium", "moment": "s1", "medium": "repeat"}, project)
    with pytest.raises(PD.PlanError):
        PD.apply_edit(plan, {"op": "set_medium", "moment": "s2", "medium": "hologram"}, project)
    with pytest.raises(PD.PlanError):
        PD.apply_edit(plan, {"op": "teleport"}, project)


def test_choosing_another_idea_swaps_it_with_the_first_choice(project):
    plan = PD.build(project, use_ai=False)
    PD.apply_edit(plan, {"op": "choose_alternative", "moment": "s2", "medium": "repeat"}, project)
    m = plan.moment("s2")
    assert m.medium == "repeat" and m.alternatives[0].medium == "made"


def test_moving_the_beat_moves_the_change_and_the_caption_word(project):
    plan = PD.build(project, use_ai=False)
    m = plan.moments[0]
    target = m.words[-1]
    PD.apply_edit(plan, {"op": "set_beat", "moment": m.id, "word": target.id}, project)
    assert m.beat.word_id == target.id and m.beat.kind == "emphasis" and next(w for w in m.words if w.id == target.id).stress == 1.0
    from vt.reel.plan import _emphasis_word, slots_from_plan

    slot = slots_from_plan(plan, project.beats().beats)[0]
    assert _emphasis_word(slot, project.transcript().by_id()) == target.id          # the caption lights up the word the person chose
    with pytest.raises(PD.PlanError):
        PD.apply_edit(plan, {"op": "set_beat", "moment": m.id, "word": "no-such-word"}, project)


def test_a_prompt_that_says_something_the_speech_does_not_is_kept_with_a_warning(project):
    plan = PD.build(project, use_ai=False)
    notes = PD.apply_edit(plan, {"op": "set_prompt", "moment": "s1", "text": "a golden dragon over Atlantis"}, project)
    assert plan.moment("s1").draw == "a golden dragon over Atlantis"
    assert notes and "not in what is said" in notes[0]
    assert any("not in what is said" in c for c in PD.checks(plan))
    with pytest.raises(PD.PlanError):
        PD.apply_edit(plan, {"op": "set_prompt", "moment": "s1", "text": "  "}, project)


def test_merging_and_splitting_keep_every_sentence_exactly_once(project):
    plan = PD.build(project, use_ai=False)
    ids = [b.id for b in project.beats().beats]
    n = len(plan.moments)
    PD.apply_edit(plan, {"op": "merge", "moment": "s1"}, project)
    assert len(plan.moments) == n - 1 and PD.matches(plan, ids) and [m.id for m in plan.moments][0] == "s1"
    first = plan.moments[0]
    if len(first.sentence_ids) > 1:
        PD.apply_edit(plan, {"op": "split", "moment": "s1", "sentence": first.sentence_ids[1]}, project)
        assert len(plan.moments) == n and PD.matches(plan, ids)
    with pytest.raises(PD.PlanError):
        PD.apply_edit(plan, {"op": "merge", "moment": plan.moments[-1].id}, project)


def test_a_limit_keeps_the_pictures_that_matter_and_the_first(project):
    plan = PD.build(project, use_ai=False)
    PD.apply_edit(plan, {"op": "set_budget", "n": 2}, project)
    made = [m.id for m in plan.moments if m.medium == "made"]
    assert len(made) == 2 and "s1" in made
    assert all(m.medium == "repeat" for m in plan.moments if m.id not in made)
    PD.apply_edit(plan, {"op": "set_budget", "n": None}, project)
    assert PD.load(project.dir) is not None


def test_a_limit_does_not_touch_locked_moments(project):
    plan = PD.build(project, use_ai=False)
    last = plan.moments[-1].id
    PD.apply_edit(plan, {"op": "lock", "moment": last}, project)
    PD.apply_edit(plan, {"op": "set_budget", "n": 1}, project)
    assert plan.moment(last).medium == "made" and plan.moment(last).locked


def test_the_pace_changes_how_many_moments_there_are_and_refuses_when_something_is_locked(project):
    plan = PD.build(project, use_ai=False)
    PD.apply_edit(plan, {"op": "set_pace", "value": "punchy"}, project)
    punchy = len(plan.moments)
    PD.apply_edit(plan, {"op": "set_pace", "value": "calm"}, project)
    assert len(plan.moments) <= punchy and PD.matches(plan, [b.id for b in project.beats().beats])
    PD.apply_edit(plan, {"op": "lock", "moment": "s1"}, project)
    with pytest.raises(PD.PlanError, match="locked"):
        PD.apply_edit(plan, {"op": "set_pace", "value": "punchy"}, project)


def test_a_new_look_makes_the_drawn_pictures_stale_but_not_a_locked_one(project):
    plan = PD.build(project, use_ai=False)
    for m in plan.moments:
        m.media, m.status = "m1", "ready"
    PD.apply_edit(plan, {"op": "lock", "moment": "s1"}, project)
    notes = PD.apply_edit(plan, {"op": "set_style", "value": "photo"}, project)
    assert plan.idea.style == "photo" and plan.moment("s1").media == "m1" and all(not m.media for m in plan.moments[1:])
    assert "drawn again" in notes[0]
    with pytest.raises(PD.PlanError):
        PD.apply_edit(plan, {"op": "set_style", "value": "oil painting"}, project)


def test_nothing_can_be_edited_once_it_is_being_made(project):
    plan = PD.build(project, use_ai=False)
    plan.state = "running"
    with pytest.raises(PD.PlanError, match="already being made"):
        PD.apply_edit(plan, {"op": "lock", "moment": "s1"}, project)


def test_when_the_plan_is_shown(project):
    plan = PD.build(project, use_ai=False)
    assert PD.review_wanted(plan, "always") and not PD.review_wanted(plan, "never")
    assert PD.review_wanted(plan, "when_expensive") == (len(plan.moments) >= PD.EXPENSIVE_MOMENTS)
    assert PD.review_wanted(plan, "never", "always") and not PD.review_wanted(plan, "always", "never")      # the video's own choice beats the setting
    for m in plan.moments[1:]:
        m.medium = "card"
    assert not PD.review_wanted(plan, "when_expensive")                                                      # cheap: no need to ask


def test_checks_are_notes_and_never_blockers(project):
    plan = PD.build(project, use_ai=False)
    plan.moments[0].beat.time = plan.moments[0].start + 2.0
    assert any("first change is late" in c for c in PD.checks(plan))


# ----------------------------------------------------------------------------- the gate before anything is made
def make_it(project, monkeypatch, *, setting="always"):
    """Run the reel plan stage with the picture server replaced; returns the pictures asked for."""
    from vt import paths
    from vt.pipeline import Pipeline
    from vt.util import write_json

    write_json(paths.SETTINGS, {"plan_review": setting})
    project.scenes_path.unlink(missing_ok=True)                  # the hand-built demo plan would be kept; a new video has none
    asked = []

    def fake_still(proj, client, workflow, prompt, **kw):
        asked.append(prompt)
        from types import SimpleNamespace as NS
        return NS(id=f"fake{len(asked)}"), {"seconds_taken": 1.0}

    from types import SimpleNamespace as NS

    monkeypatch.setattr("vt.reel.plan.reachable", lambda url: (NS(url="http://fake:8188"), None))
    monkeypatch.setattr("vt.reel.plan.load_workflow", lambda name: object(), raising=False)
    monkeypatch.setattr("vt.comfy.load_workflow", lambda name: object())
    monkeypatch.setattr("vt.comfy.generate_still", fake_still)
    pl = Pipeline(project)
    pl.stage_plan()
    return pl, asked


def test_the_plan_waits_for_the_person_and_nothing_is_drawn_before_start(project, monkeypatch):
    pl, asked = make_it(project, monkeypatch, setting="always")
    assert pl.pause_reason == "plan" and asked == []
    plan = PD.load(project.dir)
    assert plan.state == "draft" and project.scenes() is None or not any(s.backdrop for s in project.scenes().scenes)


def test_approving_makes_exactly_the_approved_plan(project, monkeypatch):
    pl, asked = make_it(project, monkeypatch, setting="always")
    plan = PD.load(project.dir)
    PD.apply_edit(plan, {"op": "set_prompt", "moment": "s1", "text": "an old key on a table"}, project)
    PD.apply_edit(plan, {"op": "set_medium", "moment": "s2", "medium": "card"}, project)
    plan.state = "approved"
    PD.save(project.dir, plan)
    from vt.pipeline import Pipeline

    pl2 = Pipeline(project)
    pl2.stage_plan(force=True)
    assert pl2.pause_reason is None
    assert any("an old key on a table" in a for a in asked) and len(asked) == len(plan.moments) - 1       # the card moment was not drawn
    done = PD.load(project.dir)
    assert done.state == "done" and done.moment("s2").status == "ready" and done.moment("s1").media.startswith("fake")
    sf = project.scenes()
    assert len(sf.scenes) == len(plan.moments)


def test_a_setting_of_never_makes_it_at_once_and_still_keeps_the_plan(project, monkeypatch):
    pl, asked = make_it(project, monkeypatch, setting="never")
    assert pl.pause_reason is None and asked
    plan = PD.load(project.dir)
    assert plan.state == "done" and plan.approved_by == "automatic"


# ----------------------------------------------------------------------------- the routes and the log
def test_the_routes_edit_through_the_log_as_the_persons_calls(client, project):
    assert client.get("/api/projects/reference/plan").json()["plan"] is None
    r = client.post("/api/projects/reference/plan/make")
    assert r.status_code == 200, r.text
    first = r.json()
    assert first["plan"]["state"] == "draft" and first["review"]["setting"] in ("always", "when_expensive", "never")
    e = client.post("/api/projects/reference/plan/edit", json={"op": {"op": "set_medium", "moment": "s2", "medium": "card"}})
    assert e.status_code == 200, e.text
    assert e.json()["plan"]["moments"][1]["medium"] == "card" and e.json()["changes"]
    bad = client.post("/api/projects/reference/plan/edit", json={"op": {"op": "set_medium", "moment": "s1", "medium": "repeat"}})
    assert bad.status_code == 422 and "first moment" in bad.text
    calls = client.get("/api/projects/reference/calls").json()
    rows = calls if isinstance(calls, list) else calls.get("calls", calls.get("entries", []))
    mine = [c for c in rows if c.get("module") == "plan.edit"]
    assert mine and mine[0]["caller"]["kind"] == "person" if isinstance(mine[0].get("caller"), dict) else mine[0].get("caller") == "person"


def test_asking_the_director_uses_the_same_vocabulary(client, project):
    client.post("/api/projects/reference/plan/make")
    r = client.post("/api/projects/reference/plan/ask", json={"text": "make it faster please"}).json()
    assert r["plan"]["idea"]["pace"] == "punchy" and "punchier" in r["said"]
    r = client.post("/api/projects/reference/plan/ask", json={"text": "fewer pictures"}).json()
    assert r["plan"]["estimate"]["made"] < len(r["plan"]["moments"])
    r = client.post("/api/projects/reference/plan/ask", json={"text": "play me a song"}).json()
    assert r["changes"] == [] and "pace" in r["said"]


def test_declining_stops_cleanly_and_a_made_plan_cannot_be_edited(client, project):
    client.post("/api/projects/reference/plan/make")
    d = client.post("/api/projects/reference/plan/decline").json()
    assert d["plan"]["state"] == "declined" and d["project_status"] == "draft"
    plan = PD.load(project.dir)
    plan.state = "done"
    PD.save(project.dir, plan)
    assert client.post("/api/projects/reference/plan/edit", json={"op": {"op": "lock", "moment": "s1"}}).status_code == 422
    assert client.put("/api/projects/reference/plan", json=plan.model_dump()).status_code == 409


def test_only_a_reel_has_a_plan_to_make(plain_client):
    assert plain_client.post("/api/projects/reference/plan/make").status_code == 422


def test_the_preview_shows_the_words_and_says_what_it_is(client, project):
    client.post("/api/projects/reference/plan/make")
    r = client.post("/api/projects/reference/plan/preview/s1").json()
    assert r["preview"]["prompt"].endswith("no watermark.") and "words the picture will be asked for" in r["preview"]["note"] and r["preview"]["media"] == ""


def test_every_plan_module_has_its_plain_words():
    from vt.modules.defs import load
    from vt.modules.registry import get_module, lint_registry
    from vt.modules.workspace import KNOWN_ARTIFACTS

    load()
    ids = ("plan.make", "plan.edit", "plan.estimate", "plan.preview_moment", "plan.approve", "plan.decline", "plan.start", "plan.status")
    for i in ids:
        s = get_module(i)
        assert s.plain_name and s.log_line is not None
    assert lint_registry(known_artifacts=KNOWN_ARTIFACTS) == []


# ----------------------------------------------------------------------------- an outside director asks the person
def test_an_outside_director_asks_and_gets_the_persons_answer(client, project):
    from vt.modules.defs import load
    from vt.modules.executor import Executor

    load()
    ex = Executor(project.dir)
    assert ex.call("plan.make", {"use_ai": False}, caller="claude", why="draft").ok
    r = ex.call("meta.ask_human", {"question": "Approve this plan?", "kind": "plan_review"}, caller="claude", why="the setting asks")
    assert r.ok and client.get("/api/projects/reference").json()["status"] == "review"
    quiet = ex.call("plan.wait", {"timeout_seconds": 0}, caller="claude", why="waiting")
    assert quiet.ok and quiet.output["timed_out"] and quiet.output["answered"] is False and quiet.output["state"] == "draft"        # unanswered: nothing is spent
    client.post("/api/projects/reference/plan/edit", json={"op": {"op": "set_medium", "moment": "s2", "medium": "card"}})
    plan = PD.load(project.dir)
    plan.state = "approved"
    PD.save(project.dir, plan)
    got = ex.call("plan.wait", {"timeout_seconds": 5}, caller="claude", why="waiting")
    assert got.output["answered"] and got.output["state"] == "approved" and got.output["summary"]["moments"] == len(plan.moments)


def test_an_unanswered_review_can_be_told_to_proceed(project):
    from vt.modules.defs import load
    from vt.modules.executor import Executor

    load()
    ex = Executor(project.dir)
    ex.call("plan.make", {"use_ai": False}, caller="claude", why="draft")
    r = ex.call("plan.wait", {"timeout_seconds": 0, "on_timeout": "proceed"}, caller="claude", why="the owner said to go on")
    assert r.output["timed_out"] and r.output["state"] == "approved" and PD.load(project.dir).approved_by == "timeout"
