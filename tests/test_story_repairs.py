"""Plan decision 1, step B5: Cartoon 2 (the story videos) does not change a director's story behind its back either.

The story validator used to drop an element type it cannot draw, replace a background it does not have, remove a speaker who is not in the cast and a sound it does not know, and only
the first eight warnings came back. Now every such change is described (`notes`), a director that can answer (Claude or Codex over MCP) gets them as errors and submits again, the person's
own edit is applied as repaired and shows them in Details, Problems, and every warning comes back."""
from __future__ import annotations

import copy

import pytest

from vt.story import engine_validate as V
from vt.story.service import plan_story, story_task, submit_story


@pytest.fixture()
def story(ref):
    sf, _, _ = plan_story(ref)
    ref.save_scenes(sf)
    return ref, story_task(ref)["current_story"]


def scene0(spec: dict) -> dict:
    return spec["scenes"][0]


# (name, how the story is spoiled, whether the validator drops or replaces what the director wrote, a piece of the note)
CASES = [
    ("an element it cannot draw", lambda s: scene0(s)["elements"].append({"type": "unicorn", "x": 270, "y": 300}), True, "is a \"unicorn\", which cannot be drawn, so it was left out"),
    ("a background it does not have", lambda s: scene0(s).update(bg={"type": "moon"}), True, 'the background "moon" does not exist, so it is a plain background'),
    ("a speaker who is not in the cast", lambda s: s["speak"].update(ghost="hello"), True, '"ghost" speaks but is not in the characters, so its speech was left out'),
    ("a sound it does not know", lambda s: s["sfx"].append(["boom", 1.0, 0.5]), True, "'boom' are not in the sound library"),
    ("a first scene that does not start at the start", lambda s: scene0(s).update(s=0.3), False, "so it starts at 0"),
    ("a small gap between two scenes", lambda s: s["scenes"][0].update(e=s["scenes"][0]["e"] - 0.3), False, "so it now ends where the next one starts"),
    ("a last scene that ends early", lambda s: s["scenes"][-1].update(e=s["scenes"][-1]["e"] - 0.2), False, "so it ends with the video at"),
    ("an element that appears outside its scene", lambda s: scene0(s)["elements"].append({"type": "icon", "name": "star", "x": 300, "y": 300, "at": 99.0}), False, "which is outside its scene, so it appears at"),
]


@pytest.mark.parametrize("name,spoil,meaning,says", CASES, ids=[c[0] for c in CASES])
def test_each_change_the_validator_makes_is_described(story, name, spoil, meaning, says):
    _, spec = story
    spec = copy.deepcopy(spec)
    spoil(spec)
    notes: list[dict] = []
    V.validate({"captions": [], "speak": {}, "tags": [], "sfx": [], **spec}, notes=notes)             # what submit_story gives every story that leaves these out
    found = [n for n in notes if says in n["says"]]
    assert found, f"{name}: no note says {says!r}; the notes are {[n['says'] for n in notes]}"
    assert found[0]["meaning"] is meaning


def test_a_story_that_needs_nothing_has_no_notes(story):
    _, spec = story
    notes: list[dict] = []
    V.validate({"captions": [], "speak": {}, "tags": [], "sfx": [], **copy.deepcopy(spec)}, notes=notes)
    assert notes == []


def test_a_director_is_told_what_would_have_been_dropped_and_nothing_is_applied(story):
    ref, spec = story
    before = ref.scenes().model_dump()
    bad = copy.deepcopy(spec)
    scene0(bad)["elements"].append({"type": "unicorn", "x": 270, "y": 300})
    res = submit_story(ref, bad)
    assert res["ok"] is False and any('is a "unicorn", which cannot be drawn, so it was left out' in e for e in res["errors"]), res
    assert ref.scenes().model_dump() == before, "the director fixes its own story and submits again"
    scene0(bad)["elements"].pop()
    scene0(bad).update(bg={"type": "moon"})
    assert submit_story(ref, bad)["ok"] is False


def test_small_things_come_back_as_repairs_and_the_story_is_applied(story):
    from vt.modules.calls import read_calls

    ref, spec = story
    s = copy.deepcopy(spec)
    scene0(s).update(s=0.3)
    res = submit_story(ref, s)
    assert res["ok"] is True and res["repairs"] == ["scene 1: the first scene started at 0.3 s, so it starts at 0"], res
    tidy = read_calls(ref.dir)
    assert len(tidy) == 1 and tidy[0]["module"] == "script.repair" and tidy[0]["level"] == "info" and "story was tidied" in tidy[0]["plain"]


def test_the_person_s_own_edit_is_applied_as_repaired_and_the_person_sees_what_changed(story):
    from vt.modules.calls import read_calls

    ref, spec = story
    s = copy.deepcopy(spec)
    scene0(s)["elements"].append({"type": "unicorn", "x": 270, "y": 300})
    res = submit_story(ref, s, planner="manual")
    assert res["ok"] is True and any("cannot be drawn" in r for r in res["repairs"]), res
    problems = read_calls(ref.dir, level="warn,error")
    assert len(problems) == 1 and problems[0]["plain"].startswith("Scene 1: element ") and "cannot be drawn" in problems[0]["plain"]
    assert "story you wrote" in problems[0]["why"], "it says what was repaired: a story, not a script"


def test_every_warning_comes_back_not_the_first_eight(story):
    ref, spec = story
    s = copy.deepcopy(spec)
    s["tags"] = [{"tag": "a tag that is far too long to keep", "s": 0.5, "e": 1.5} for _ in range(20)]
    res = submit_story(ref, s)
    assert res["ok"] is True and len(res["warnings"]) >= 20, res["warnings"]
    s["tags"] = [{"tag": "a tag that is far too long to keep", "s": 0.5, "e": 1.5} for _ in range(80)]
    res = submit_story(ref, s)
    assert len(res["warnings"]) == 60 and res["warnings_not_listed"] >= 20, "a very long list is counted, not silently cut"


def test_the_mcp_tool_and_the_prompts_tell_the_director(story):
    from vt import directors
    from vt.mcp import server as M

    ref, spec = story
    bad = copy.deepcopy(spec)
    scene0(bad)["elements"].append({"type": "unicorn", "x": 270, "y": 300})
    res = M.submit_story(ref.id, bad)
    assert res["ok"] is False and any("cannot be drawn" in e for e in res["errors"])
    prompt = directors.client_story_prompt(ref.id)
    assert "Nothing is changed behind your back" in prompt and "every error" in prompt and "every warning" in prompt
    assert "Nothing is changed behind your back" in story_task(ref)["how_to"]


def test_the_local_ai_story_is_used_as_repaired_and_shows_what_changed(story, monkeypatch):
    from vt.modules.calls import read_calls
    from vt.story import designer

    ref, spec = story

    def refine(spec, aspect, progress=None, provider=None):
        spec = copy.deepcopy(spec)
        scene0(spec)["elements"].append({"type": "unicorn", "x": 270, "y": 300})
        return spec, 1

    monkeypatch.setattr(designer, "refine", refine)
    sf, how, notice = plan_story(ref, provider=object())
    assert how.startswith("ai") and sf.scenes
    problems = read_calls(ref.dir, level="warn,error")
    assert len(problems) == 1 and "cannot be drawn" in problems[0]["plain"] and "the AI wrote" in problems[0]["why"]
    # the rule director's own story needs no report
    monkeypatch.setattr(designer, "refine", lambda *a, **k: (spec, 0))
    plan_story(ref, provider=object())
    assert len(read_calls(ref.dir, level="warn,error")) == 1
