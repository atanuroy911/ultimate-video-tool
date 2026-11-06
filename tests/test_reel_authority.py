"""Plan decision 1, step B6: the picture-video (reel) path.

The reel plan is the director's own document. It edits it one typed operation at a time, each with a reason in the call log, and the picture checks only report. No code changes a
picture, a place or a prompt behind the director's back; approving the plan with a check still open is the director's choice, and it is written down as one."""
from __future__ import annotations

import pytest

from vt.direction import plan_doc as PD
from vt.modules.calls import read_calls
from vt.modules.executor import Executor


@pytest.fixture()
def reel(ref):
    plan = PD.build(ref, use_ai=False)
    PD.save(ref.dir, plan)
    return ref, plan


def test_the_checks_only_report(reel):
    from vt.mcp import server as M

    ref, _ = reel
    before, stamp = (ref.dir / PD.PLAN).read_bytes(), (ref.dir / PD.PLAN).stat().st_mtime_ns
    checks = M.check_reel_plan(ref.id)
    assert checks["ok"] is False and {x["rule"] for x in checks["issues"]} == {"picture.place"} and all(x["says"] and x["fix"] for x in checks["issues"])
    full = M.get_reel_plan(ref.id)
    assert full["shots"] and full["checks"]["issues"] == checks["issues"] and full["checks"]["plan_notes"]
    assert (ref.dir / PD.PLAN).read_bytes() == before and (ref.dir / PD.PLAN).stat().st_mtime_ns == stamp, "reading and checking the plan changed nothing in it, not even by writing it again"
    assert "nothing is changed" in M.check_reel_plan.__doc__.lower()


def test_an_edit_changes_exactly_what_it_says(reel):
    ref, plan = reel
    first = plan.moments[0]
    was = [m.model_dump() for m in plan.moments]
    PD.apply_edit(plan, {"op": "set_prompt", "moment": first.id, "text": "a sign that reads HELLO in a room"}, ref)
    now = [m.model_dump() for m in plan.moments]
    changed = [(a["id"], k) for a, b in zip(was, now) for k in a if a[k] != b[k]]
    assert changed and {i for i, _ in changed} == {first.id}, f"only the moment named changed: {changed}"
    assert plan.moments[0].draw == "a sign that reads HELLO in a room"
    notes = PD.apply_edit(plan, {"op": "set_medium", "moment": plan.moments[1].id, "medium": "card"}, ref)
    assert notes and plan.moments[1].medium == "card", "an edit that changes more than its own words says what it did"
    with pytest.raises(PD.PlanError):
        PD.apply_edit(plan, {"op": "not_an_operation"}, ref)


def test_an_edit_that_cannot_be_done_is_refused_in_a_sentence_and_changes_nothing(reel):
    ref, plan = reel
    before = plan.model_dump()
    with pytest.raises(PD.PlanError) as e:
        PD.apply_edit(plan, {"op": "set_medium", "moment": plan.moments[0].id, "medium": "repeat"}, ref)
    assert "first moment" in str(e.value) and plan.model_dump() == before


def test_a_director_that_approves_with_checks_open_is_written_down(reel):
    ref, _ = reel
    res = Executor(ref.dir).call("plan.approve", {"by": "Claude"}, caller="claude", why="it reads well")
    assert res.ok, res.fix
    assert PD.load(ref.dir).state == "approved" and PD.load(ref.dir).approved_by == "Claude"
    problems = [e for e in read_calls(ref.dir, level="warn,error") if e["module"] == "plan.checks"]
    assert len(problems) == 1 and "Claude approved the plan with 5 picture check(s) still open" in problems[0]["plain"] and "does not say where it happens" in problems[0]["plain"]
    assert problems[0]["inputs"] == {"by": "Claude"} and "fix the pictures" in problems[0]["fix"]
    approved = [e for e in read_calls(ref.dir) if e["module"] == "plan.approve"]
    assert approved and "5 picture check(s) were still open" in approved[0]["plain"]


def test_a_director_that_fixed_every_check_leaves_nothing_to_say(reel):
    ref, plan = reel
    for m in plan.moments:
        PD.apply_edit(plan, {"op": "set_place", "name": "kitchen", "text": "inside a small kitchen, the table as high as a person's waist"}, ref)
        PD.apply_edit(plan, {"op": "set_moment_place", "moment": m.id, "place": "kitchen"}, ref)
    PD.save(ref.dir, plan)
    assert not PD.open_picture_issues(ref, PD.load(ref.dir))
    res = Executor(ref.dir).call("plan.approve", {"by": "Claude"}, caller="claude", why="every check is clean")
    assert res.ok and [e for e in read_calls(ref.dir) if e["module"] == "plan.checks"] == []


def test_the_person_pressing_start_is_not_second_guessed(reel):
    ref, _ = reel
    res = Executor(ref.dir).call("plan.approve", {"by": "person"}, caller="person", why="Start")
    assert res.ok and [e for e in read_calls(ref.dir) if e["module"] == "plan.checks"] == [], "the person sees the plan and its checks and decides for themselves"


def test_the_prompt_sends_the_director_to_the_checks_and_the_approval(ref):
    from vt import directors

    prompt = directors.client_prompt(ref.id)
    assert "check_reel_plan" in prompt and "picture.place" in prompt and "picture.drawable" in prompt and "plan.approve" in prompt and "plan.edit" in prompt
