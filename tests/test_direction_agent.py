"""The directors (docs/plans/PLAN-DIRECTOR-MODULES.MD section 3): recipes, the L1 plan with its validator and fallback, the L2 agent loop and its caps, the standing prompt and its worked traces."""
import json
import re

import pytest

from vt.direction import agent as AG
from vt.direction import plan_director as PL


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    monkeypatch.setattr("vt.ai.providers.ai_enabled", lambda: False)


@pytest.fixture()
def project(ref):
    (ref.dir / "script.json").write_text(json.dumps({"text": "Never put your money in one place. Keep three months of bills in savings."}), encoding="utf-8")
    return ref


@pytest.fixture()
def ws(project):
    from vt.modules.workspace import Workspace

    return Workspace(project.dir)


def plan(*calls, **kw):
    return PL.DirectorPlan(calls=[PL.PlanCall(**c) for c in calls], **kw)


# ----------------------------------------------------------------------------- the standing prompt
def test_the_prompt_has_its_sections_in_order_and_five_worked_traces():
    text = AG.load_prompt()
    heads = [m.group(0) for m in re.finditer(r"^# .+$", text, re.M)]
    assert tuple(heads) == AG.SECTIONS
    assert len(re.findall(r"^## Trace \d", text, re.M)) == 5
    for must in ("grounding", "audio comes first", "three seconds", "never start without it", "autonomous"):
        assert must.lower() in text.lower()
    with pytest.raises(KeyError):
        AG.load_prompt("director-v9")


def traces():
    text = AG.load_prompt()
    return [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", text, re.S)]


def test_every_worked_trace_is_a_plan_the_validator_accepts(ws):
    found = traces()
    assert len(found) == 5
    for t in found:
        p = PL.DirectorPlan.model_validate(t)
        assert PL.validate(p, ws=ws) == [], (t["goal"], PL.validate(p, ws=ws))


# ----------------------------------------------------------------------------- recipes
def test_the_stored_recipes_are_plans_that_validate_and_the_classic_one_is_the_pipeline(ws):
    names = PL.recipe_names()
    assert {"classic", "image-story", "impact-talkinghead", "impact-explainer"} <= set(names)
    for n in names:
        p = PL.load_recipe(n)
        assert p.source == "rules" and p.calls
        if n != "classic":
            assert PL.validate(p, ws=ws) == [], (n, PL.validate(p, ws=ws))
    classic = PL.load_recipe("classic")
    assert [c.module for c in classic.calls][:2] == ["pipeline.voice", "pipeline.preprocess"]
    with pytest.raises(KeyError):
        PL.load_recipe("nonsense")


def test_the_recipe_follows_the_kind_of_project(project):
    assert PL.recipe_for(project) in ("classic", "impact-explainer")
    meta = project.meta()
    meta.options.look = "reel"
    project.save_meta(meta)
    assert PL.recipe_for(project) == "image-story"


# ----------------------------------------------------------------------------- the validator names every problem
def test_the_validator_says_what_is_wrong_in_sentences(ws):
    bad = plan(
        {"id": "a", "module": "nothing.here"},
        {"id": "a", "module": "voice.describe", "inputs": {"description": "x"}},
        {"id": "b", "module": "voice.describe", "inputs": {"colour": "red"}, "after": ["zzz"]},
        {"id": "c", "module": "publish.dispatch", "inputs": {}},
        {"id": "d", "module": "plan.start", "inputs": {}},
        {"id": "e", "module": "voice.describe", "inputs": {"description": "@later"}, "after": ["f"]},
        {"id": "f", "module": "meta.note", "inputs": {"text": "x"}},
        checkpoints=["after_nothing"])
    problems = "\n".join(PL.validate(bad, ws=None, toolbox="autonomous"))
    assert "Two calls are named 'a'" in problems
    assert "no module called 'nothing.here'" in problems and "meta.catalog" in problems
    assert "has no input called 'colour'" in problems
    assert "'zzz', which is not in the plan" in problems
    assert "not in the autonomous toolbox" in problems
    assert "needs plan.doc" in problems and "add plan.make first" in problems
    assert "'f', but 'f' is listed later" in problems
    assert "@later" in problems
    assert "'after_nothing' is not a checkpoint" in problems


def test_inputs_that_do_not_fit_the_module_are_refused_before_anything_runs(ws):
    p = plan({"id": "a", "module": "voice.speak", "inputs": {"text": "", "rate": 9}})
    out = PL.validate(p, ws=ws)
    assert out and "inputs for voice.speak are not right" in out[0]


def test_a_budget_the_plan_cannot_fit_is_a_problem(ws):
    heavy = plan({"id": "a", "module": "voice.speak_script", "inputs": {"text": "One. Two."}})
    assert any("budget" in p for p in PL.validate(heavy, ws=ws, budget_seconds=5))
    assert not any("budget" in p for p in PL.validate(heavy, ws=ws, budget_seconds=500))


def test_references_are_resolved_from_results_facts_and_the_goal(project):
    facts = PL.project_facts(project)
    assert facts["duration"] > 5 and facts["aspect"] == "9:16"
    got = PL.resolve({"d": "@project.duration", "g": "@goal", "s": "@a.slots", "n": ["@a.x.y", "plain"]}, {"a": {"slots": [1, 2], "x": {"y": 7}}}, "my goal", facts)
    assert got == {"d": facts["duration"], "g": "my goal", "s": [1, 2], "n": [7, "plain"]}


# ----------------------------------------------------------------------------- the L1 director
GOOD = {"goal": "g", "style": "s", "calls": [{"id": "d", "module": "voice.describe", "inputs": {"description": "a warm older man"}, "why": "see what it means"}]}


def test_a_good_plan_from_the_model_is_used(project):
    p, notes = PL.make_plan(project, chat=lambda system, user, schema: GOOD)
    assert p.source == "ai" and p.calls[0].module == "voice.describe" and notes == []


def test_a_wrong_plan_is_sent_back_with_its_problems_and_the_corrected_one_is_used(project):
    seen = []

    def chat(system, user, schema):
        seen.append(user)
        return {"calls": [{"id": "d", "module": "voice.describe", "inputs": {"colour": "red"}}]} if len(seen) == 1 else GOOD

    p, notes = PL.make_plan(project, chat=chat)
    assert p.source == "ai" and len(seen) == 2 and "has no input called 'colour'" in seen[1]
    assert notes and "problem" in notes[0]


def test_a_model_that_keeps_getting_it_wrong_gets_the_stored_recipe(project):
    p, notes = PL.make_plan(project, chat=lambda system, user, schema: {"calls": [{"id": "x", "module": "does.not.exist"}]})
    assert p.source == "rules" and any("stored recipe" in n for n in notes)


def test_a_model_that_cannot_answer_gets_the_stored_recipe(project):
    def down(system, user, schema):
        raise ConnectionError("the language AI is not running")

    p, notes = PL.make_plan(project, chat=down)
    assert p.source == "rules" and any("stored recipe" in n for n in notes)
    p, notes = PL.make_plan(project)                                      # no AI at all
    assert p.source == "rules"


def test_a_plan_runs_in_order_logs_each_call_as_the_directors_and_fills_references(project):
    p = plan({"id": "d", "module": "voice.describe", "inputs": {"description": "a deep older man"}, "why": "see what it means"},
             {"id": "n", "module": "meta.note", "inputs": {"text": "@d.instruction"}, "after": ["d"], "why": "write it down"})
    fired = []
    r = PL.run(p, project, caller="director", goal="g", on_checkpoint=lambda e, res: fired.append(e))
    assert r["ok"] and [c["id"] for c in r["calls"]] == ["d", "n"]
    log = [json.loads(line) for line in (project.dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    mine = [x for x in log if x["caller"]["kind"] == "director"]
    assert [x["module"] for x in mine] == ["voice.describe", "meta.note"] and mine[0]["why"] == "see what it means"
    assert "male" in json.dumps(mine[1]["inputs"])                         # the reference was filled in before the call


def test_a_failing_call_is_reported_and_the_plan_goes_on(project):
    p = plan({"id": "a", "module": "voice.speak", "inputs": {"text": "x", "voice": "nonsense:voice"}}, {"id": "n", "module": "meta.note", "inputs": {"text": "still here"}})
    r = PL.run(p, project)
    assert [c["ok"] for c in r["calls"]] == [False, True] and r["calls"][0]["fix"]
    assert len(PL.run(p, project, stop_on_failure=True)["calls"]) == 1


def test_checkpoints_fire_when_the_last_call_of_their_group_is_done(project):
    p = plan({"id": "n", "module": "meta.note", "inputs": {"text": "a"}}, {"id": "d", "module": "direct.set_direction", "inputs": {"goal": "g"}}, checkpoints=["after_direction"])
    fired = []
    PL.run(p, project, on_checkpoint=lambda e, res: fired.append(e))
    assert fired == ["after_direction"] and PL.checkpoint_call(p, "after_direction") == "d" and PL.checkpoint_call(p, "after_judge") is None


# ----------------------------------------------------------------------------- the L2 agent
def scripted(*answers):
    it = iter(answers)

    def step(system, card, last, working, goal):
        a = next(it)
        if isinstance(a, Exception):
            raise a
        return a(card, last, working) if callable(a) else a

    return step


def call(module, inputs=None, why="because"):
    return {"call": {"module": module, "inputs": inputs or {}, "why": why}}


def test_an_agent_calls_modules_one_at_a_time_and_finishes(project):
    seen = []
    step = scripted(call("voice.describe", {"description": "a warm man"}), lambda card, last, working: (seen.append((card, last, working)) or call("meta.note", {"text": "ok"})), {"finish": "done"})
    r = AG.run_agent(project, step)
    assert r.ended == "finished" and r.finish == "done" and [s.module for s in r.steps] == ["voice.describe", "meta.note"] and all(s.ok for s in r.steps)
    card, last, working = seen[0]
    assert last["module"] == "voice.describe" and last["ok"] and "male" in last["output"] and working[0] == "voice.describe" and "project:" in card


def test_a_module_that_does_not_exist_is_told_so_and_the_agent_corrects_itself(project):
    seen = []
    step = scripted(call("make.video"), lambda card, last, working: (seen.append(last) or call("meta.note", {"text": "x"})), {"finish": "ok"})
    r = AG.run_agent(project, step)
    assert "no module 'make.video'" in seen[0]["error"] and [s.ok for s in r.steps] == [False, True]


def test_a_module_outside_the_toolbox_is_refused_and_three_refusals_stop_the_run(project):
    r = AG.run_agent(project, scripted(*[call("publish.dispatch")] * 5))
    assert r.ended == "refused" and len(r.steps) == 3 and all(s.status == "refused" for s in r.steps)
    log = (project.dir / "calls.jsonl").read_text(encoding="utf-8").splitlines() if (project.dir / "calls.jsonl").exists() else []
    assert not any(json.loads(x)["module"] == "publish.dispatch" for x in log)                  # a refused call never ran


def test_the_same_call_with_the_same_answer_ends_the_run(project):
    r = AG.run_agent(project, scripted(*[call("voice.describe", {"description": "same"})] * 6))
    assert r.ended == "no_progress" and len(r.steps) == 2


def test_the_step_cap_and_the_time_cap_stop_the_run(project):
    texts = iter(f"note {i}" for i in range(99))
    r = AG.run_agent(project, lambda *a: call("meta.note", {"text": next(texts)}), limits=AG.Limits(steps=3))
    assert r.ended == "step_cap" and len(r.steps) == 3
    r = AG.run_agent(project, lambda *a: call("meta.note", {"text": "t"}), limits=AG.Limits(seconds=1))
    assert r.ended in ("time_cap", "no_progress")


def test_a_model_that_errors_or_answers_nonsense_ends_the_run_without_crashing(project):
    assert AG.run_agent(project, scripted(ConnectionError("down"))).ended == "no_answer"
    assert AG.run_agent(project, lambda *a: "not a dict").ended == "no_answer"


def test_the_state_card_stays_under_600_tokens_however_long_the_run(project):
    steps = [AG.Step(n=i, module=f"fill.something_{i}", inputs={}, ok=False, status="failed", summary="x" * 300, fix="y" * 400) for i in range(80)]
    card = AG.state_card(project, steps, AG.Limits(), 0.0)
    assert AG.tokens(card) <= AG.CARD_TOKENS and card.startswith("project:") and "budget:" in card


def test_only_the_modules_in_play_have_their_schemas_shown(project):
    steps = [AG.Step(n=1, module="plan.make"), AG.Step(n=2, module="plan.make"), AG.Step(n=3, module="plan.edit")]
    assert AG.working_set(steps, ("plan.start",)) == ["plan.make", "plan.edit", "plan.start"]
    assert AG.hints_for(project, []) [0] == "understand.read_script"
    assert "plan.start" in AG.hints_for(project, [AG.Step(n=1, module="plan.make", ok=True)])
    assert len(AG.working_set([AG.Step(n=i, module=f"m.x{i}") for i in range(30)])) == 12


def test_the_ai_backed_step_asks_with_the_card_and_only_the_working_set(project, monkeypatch):
    asked = {}

    def fake(user, schema, **kw):
        asked.update(user=user, system=kw["system"])
        return {"finish": "nothing to do"}

    monkeypatch.setattr("vt.ai.complete_json", fake)
    step = AG.ollama_step()
    out = step("SYSTEM", "CARD", {"ok": True}, ["voice.describe", "not.a.module"], "make it warm")
    assert out == {"finish": "nothing to do"} and "CARD" in asked["user"] and "voice.describe" in asked["user"] and "not.a.module" not in asked["user"] and asked["system"] == "SYSTEM"
