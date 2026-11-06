"""Plan decision 1, step B4: what repair_script changes in a director's Video Script is told, not done silently.

One check for each kind of repair: it happens, and it is described (`notes`: where, in words, and whether it changed what the director wrote). A director that can answer (Claude or Codex over
MCP, `apply_script(strict=True)`) gets the changes of meaning back as errors and the small things as `repairs`; the local AI's script is used as repaired and everything is in Details, Problems."""
from __future__ import annotations

import copy

import pytest

from vt.script import repairs as REPAIRS
from vt.script.examples import ED, ED_TEXTS, make
from vt.script.validate import repair_script, validate_script

TR, BEATS = make(ED_TEXTS)


def base() -> dict:
    return copy.deepcopy(ED)


def scene(s: dict, n: int) -> dict:
    return s["scenes"][n - 1]


def eight(prefix: str) -> list[dict]:
    return [{"id": f"{prefix}{i}", "role": "teacher"} for i in range(8)]


def full_sets(s: dict) -> None:
    s["sets"] = [{"id": f"set{i}", "kind": "plain"} for i in range(8)]
    for sc in s["scenes"]:
        sc["set"] = "set0"


# (name, how the script is spoiled, whether the repair changes what the director wrote, a piece of the note, the scene it is about)
CASES = [
    # ---- changes of meaning: told to the director as errors
    ("an overlay text is cut short", lambda s: scene(s, 1)["overlays"][0].update(text="G" * 60), True, "was longer than it may be, so it was cut short", 1),
    ("a bubble is cut short", lambda s: scene(s, 1)["actions"].append({"at_word": "w3", "who": "maya", "do": "say", "bubble": "B" * 90}), True, 'the bubble of "say" was longer than 70 letters', 1),
    ("an action starts at a word the scene does not have", lambda s: scene(s, 1)["actions"][1].update(at_word="w99"), True, "starts at w99, which is not a word of this scene", 1),
    ("an overlay starts at a word the scene does not have", lambda s: scene(s, 1)["overlays"][0].update(at_word="w99"), True, "overlay starts at w99, which is not a word of this scene", 1),
    ("a sound starts at a word the scene does not have", lambda s: scene(s, 4).update(sfx=[{"at_word": "w1", "id": "ding"}]), True, 'the sound "ding" starts at w1', 4),
    ("an action is not a verb", lambda s: scene(s, 1)["actions"][1].update(do="teleport"), True, 'the action "teleport" is not one of the verbs, so it was left out', 1),
    ("an emotion is not one of the emotions", lambda s: scene(s, 4)["actions"][1].update(emotion="furious"), True, 'the emotion "furious" is not one of the emotions, so it is neutral', 4),
    ("an action is by someone the cast cannot hold", lambda s: (s.update(cast=eight("c")), scene(s, 1)["actions"][1].update(who="ninth")), True, 'by "ninth", who is not in the cast, so it is by "c0" instead', 1),
    ("the camera shot is not a shot", lambda s: scene(s, 1)["camera"].update(shot="extreme"), True, 'the camera shot "extreme" is not one of the shots, so it was removed', 1),
    ("the camera move is not a move", lambda s: scene(s, 1)["camera"].update(move="spin"), True, 'the camera move "spin" is not one of the moves, so it was removed', 1),
    ("a scene uses a set that is not one of the sets", lambda s: (full_sets(s), scene(s, 2).update(set="dungeon")), True, 'the set "dungeon" is not one of the sets, so the scene uses "set0"', 2),
    ("a set is not a kind of place", lambda s: s["sets"][0].update(kind="dungeon"), True, 'is a "dungeon", which is not a kind of place, so it is a plain background', None),
    ("a scene names a beat that does not exist", lambda s: scene(s, 2).update(beats=["b2", "b99"]), True, "names the beat(s) b99, which do not exist", None),
    ("a scene has no beat that exists", lambda s: s["scenes"].append({"id": "s9", "beats": ["b99"], "overlays": [], "actions": []}), True, 'scene "s9" has no beat that exists, so the scene was left out', None),
    ("a beat is in no scene", lambda s: s["scenes"].pop(2), True, "the beat b3 was in no scene, so an empty scene was added for it", None),
    ("a beat is in two scenes", lambda s: scene(s, 3).update(beats=["b3", "b2"]), True, "repeats a beat that an earlier scene already has", None),
    ("the scenes cross each other in the beats", lambda s: (scene(s, 1).update(beats=["b1", "b3"]), scene(s, 2).update(beats=["b2", "b4"]), s["scenes"].pop(3), s["scenes"].pop(2)), True,
     "every beat became its own scene and the structure the script wrote was replaced", None),
    ("a sound is not in the library", lambda s: scene(s, 4).update(sfx=[{"at_word": "w22", "id": "boom"}]), True, 'the sound "boom" is not in the sound library, so it was left out', 4),
    ("an overlay cannot be kept", lambda s: scene(s, 1)["overlays"].append({"type": "stat_row", "stats": [{"value": "1", "label": "a"}], "at_word": "w3"}), True, "overlay was left out:", 1),
    ("a side is not a side", lambda s: scene(s, 1)["actions"][0].update(**{"from": "up"}), True, '"up" is not a side (left or right) for "walk_in", so it is "left"', 1),
    # ---- small things filled in: told in `repairs`
    ("a verb has a synonym", lambda s: scene(s, 1)["actions"][1].update(do="hello"), False, 'the verb "hello" is "wave" here', 1),
    ("an emotion has a synonym", lambda s: scene(s, 4)["actions"][1].update(emotion="excited"), False, 'the emotion "excited" is "happy" here', 4),
    ("walk_in names no side", lambda s: scene(s, 1)["actions"][0].pop("from"), False, '"walk_in" named no side, so the character comes in from the left', 1),
    ("react names no emotion", lambda s: scene(s, 4)["actions"][1].pop("emotion"), False, '"react" named no emotion, so it is happy', 4),
    ("count names no number", lambda s: scene(s, 1)["actions"].append({"at_word": "w3", "who": "maya", "do": "count"}), False, '"count" named no number, so it counts one', 1),
    ("a place is outside the picture", lambda s: scene(s, 1)["actions"][0].update(to=1.5), False, "is outside the picture (0 to 1), so it was moved to 1", 1),
    ("someone acts who is not in the cast", lambda s: scene(s, 1)["actions"][1].update(who="bob"), False, '"bob" acts but is not in the cast, so it was added as a narrator', None),
    ("a role is not a role", lambda s: s["cast"][0].update(role="wizard"), False, 'has the role "wizard", which is not known, so it is a narrator', None),
    ("a set is used but not declared", lambda s: scene(s, 1).update(set="forest"), False, 'the set "forest" is used but was not declared, so it was added as a plain background', None),
    ("a pointed-at prop is not in the set", lambda s: scene(s, 2)["actions"][0].update(target="lamp"), False, 'the set did not have "lamp", so it was added', 2),
    ("the kind asked for wins", lambda s: s.update(kind="explainer"), False, 'the script says it is "explainer", but this video is "stick", so it is treated as "stick"', None),
    ("too many highlight words", lambda s: scene(s, 1).update(highlight_words=["w1", "w2", "w3", "w4"]), False, "highlight words that are not in the scene, or more than three, were left out", 1),
    ("the scenes are out of order", lambda s: s["scenes"].reverse(), False, "the scenes were not in the order of the beats, so they were put in order", None),
]


@pytest.mark.parametrize("name,spoil,meaning,says,scene_no", CASES, ids=[c[0] for c in CASES])
def test_each_repair_is_described(name, spoil, meaning, says, scene_no):
    s = base()
    assert validate_script(s, TR, BEATS) == [], "the starting script is valid"
    spoil(s)
    notes: list[dict] = []
    fixed = repair_script(s, TR, BEATS, "stick", notes=notes)
    found = [n for n in notes if says in n["says"]]
    assert found, f"{name}: no note says {says!r}; the notes are {[n['says'] for n in notes]}"
    assert found[0]["meaning"] is meaning and found[0]["scene"] == scene_no, found[0]
    if scene_no:
        assert found[0]["says"].startswith(f"scene {scene_no}: ")
    assert validate_script(fixed, TR, BEATS) == [], "and the repaired script is valid"


def test_the_emoji_mode_says_what_it_left_out():
    s = base()
    s["kind"] = "emoji"
    notes: list[dict] = []
    repair_script(s, TR, BEATS, "emoji", notes=notes)
    says = [n["says"] for n in notes if n["meaning"]]
    assert any("this is an emoji video: it has no characters and no places" in x for x in says)
    assert any(x.startswith("scene 1: this is an emoji video: only stickers and keywords are drawn") for x in says), says


def test_a_script_that_needs_nothing_has_no_notes():
    notes: list[dict] = []
    repair_script(base(), TR, BEATS, "stick", notes=notes)
    assert notes == []


def test_repair_script_works_without_notes_as_before():
    s = base()
    scene(s, 1)["actions"][1].update(at_word="w99")
    assert validate_script(repair_script(s, TR, BEATS, "stick"), TR, BEATS) == []


# ---- the director that can answer is told; everyone else sees it in Details, Problems ----------------------------------------------------------------------------------------


def _script_for(ref, spoil=None) -> dict:
    ids = [b.id for b in ref.beats().beats]
    first = ref.beats().beats[0].word_ids[0]
    s = {"version": "1.0", "kind": "explainer", "scenes": [{"id": "s1", "beats": ids, "overlays": [{"type": "title", "text": "Hello", "at_word": first}]}]}
    if spoil:
        spoil(s, first)
    return s


def test_a_clean_script_is_applied_with_nothing_to_report(ref):
    from vt.modules.calls import read_calls
    from vt.script import service

    res = service.apply_script(ref, _script_for(ref), planner="claude", strict=True)
    assert res["ok"] and res["repairs"] == [] and read_calls(ref.dir) == []


def test_a_director_that_can_answer_is_told_what_would_have_changed(ref):
    from vt.script import service

    before = ref.scenes().model_dump()
    res = service.apply_script(ref, _script_for(ref, lambda s, w: s["scenes"][0]["overlays"][0].update(text="T" * 80, at_word="w999")), planner="claude", strict=True)
    assert res["ok"] is False
    assert any("starts at w999, which is not a word of this scene" in e for e in res["errors"]), res
    assert any("was longer than it may be, so it was cut short" in e for e in res["errors"]), res
    assert ref.scenes().model_dump() == before, "nothing was applied: the director fixes its own script and submits again"


def test_small_things_come_back_as_repairs_and_the_script_is_applied(ref):
    from vt.modules.calls import read_calls
    from vt.script import service

    res = service.apply_script(ref, _script_for(ref, lambda s, w: s["scenes"][0].update(highlight_words=["w1", "w2", "w3", "w4"])), planner="claude", strict=True)
    assert res["ok"] and res["repairs"] == ["scene 1: highlight words that are not in the scene, or more than three, were left out"], res
    tidy = read_calls(ref.dir)
    assert len(tidy) == 1 and tidy[0]["module"] == "script.repair" and tidy[0]["level"] == "info" and "1 small thing" in tidy[0]["plain"]


def test_the_local_ai_script_is_used_as_repaired_and_the_person_sees_what_changed(ref):
    from vt.modules.calls import read_calls
    from vt.script import service

    res = service.apply_script(ref, _script_for(ref, lambda s, w: s["scenes"][0]["overlays"][0].update(text="T" * 80)), planner="llm")
    assert res["ok"] and any("was longer than it may be" in r for r in res["repairs"]), res
    problems = read_calls(ref.dir, level="warn,error")
    assert len(problems) == 1 and problems[0]["module"] == "script.repair" and problems[0]["caller"]["kind"] == "rules"
    assert problems[0]["plain"].startswith("Scene 1: the text of the title overlay was longer than it may be, so it was cut short") and "edit the scene" in problems[0]["fix"]


def test_the_mcp_tool_tells_the_director(ref):
    from vt.mcp import server as M

    res = M.submit_script(ref.id, _script_for(ref, lambda s, w: s["scenes"][0]["overlays"][0].update(at_word="w999")))
    assert res["ok"] is False and any("starts at w999" in e for e in res["errors"])
    assert "repairs" in (M.submit_script.__doc__ or "") and "Nothing is changed behind your back" in M.submit_script.__doc__


def test_the_ai_script_path_keeps_the_notes_of_the_script_it_used(ref, monkeypatch):
    from vt import ai
    from vt.script import planner

    tr, beats = ref.transcript(), ref.beats()
    bad = _script_for(ref, lambda s, w: s["scenes"][0]["overlays"][0].update(text="T" * 80))

    def answer(user, schema, **kw):                              # the AI answers with a script that needs repairing, as the local AI does
        data = kw["repair"](copy.deepcopy(bad))
        assert kw["check"](data) == []
        return data

    monkeypatch.setattr(ai, "complete_json", answer)
    monkeypatch.setattr(planner, "revise", lambda script, *a, **k: script)
    notes: list[dict] = []
    script = planner.ai_script(tr, beats, kind="explainer", notes=notes)
    assert script.scenes and [n["says"] for n in notes if n["meaning"]] == ["scene 1: the text of the title overlay was longer than it may be, so it was cut short"]
    from vt.modules.calls import read_calls

    REPAIRS.record(ref, notes, "the AI")
    assert [e["level"] for e in read_calls(ref.dir)] == ["warn"]


def test_the_director_stage_shows_what_the_repair_changed_in_the_ai_script(ref, monkeypatch):
    from vt import ai
    from vt.modules.calls import read_calls
    from vt.script import planner, service
    from vt.script.rules_stick import rules_script

    sf = ref.scenes()
    service.set_script_kind(ref, "stick")
    script = rules_script(ref.transcript(), ref.beats(), sf, kind="stick", language=ref.meta().language, aspect=ref.meta().aspect)
    says = 'scene 1: the bubble of "say" was longer than 70 letters, so it was cut short: "Hello there my frie…"'

    def plan(tr, beats, *, draft, use_ai=True, notes=None, **kw):
        notes.append({"scene": 1, "says": says, "meaning": True})
        return script, "ai"

    monkeypatch.setattr(planner, "plan_script", plan)
    monkeypatch.setattr(ai, "provider_status", lambda: {"available": True})
    out, how = service.direct(ref, sf, want_ai=True)
    assert how == "ai" and out.scenes
    problems = read_calls(ref.dir, level="warn,error")
    assert len(problems) == 1 and problems[0]["module"] == "script.repair" and problems[0]["plain"].startswith("Scene 1: the bubble of")
    # a plan the rules made (the AI could not answer) has nothing of an AI's to report
    monkeypatch.setattr(planner, "plan_script", lambda *a, notes=None, **k: (script, "rules (no AI)"))
    service.direct(ref, sf, want_ai=True)
    assert len(read_calls(ref.dir, level="warn,error")) == 1


def test_a_change_the_person_asks_the_director_for_shows_what_the_repair_changed(ref, monkeypatch):
    from vt import ai
    from vt.modules.calls import read_calls
    from vt.project import Project
    from vt.script import chat
    from vt.script.rules_stick import rules_script
    from vt.script.service import apply_script, set_script_kind

    p = Project("reference")
    set_script_kind(p, "stick")
    cur = rules_script(p.transcript(), p.beats(), p.scenes(), kind="stick", language=p.meta().language, aspect=p.meta().aspect)
    assert apply_script(p, cur.model_dump(by_alias=True, exclude_none=True), planner="rules", compose=False)["ok"]
    want = cur.model_dump(by_alias=True, exclude_none=True)
    first = want["scenes"][0]
    first["actions"].append({"at_word": p.beats().beats[0].word_ids[0], "who": want["cast"][0]["id"], "do": "say", "bubble": "B" * 90})

    def answer(user, schema, **k):
        return k["repair"](copy.deepcopy(want))                    # the AI's reply is repaired the way every reply is

    monkeypatch.setattr(ai, "complete_json", answer)
    monkeypatch.setattr("vt.pipeline.compose_all", lambda p: None)
    res = chat.talk(p, "make them say something long", provider=ai.FakeProvider({}))
    assert res["ok"]
    assert any("the bubble of" in e["plain"] and "cut short" in e["plain"] for e in read_calls(p.dir, level="warn")), read_calls(p.dir)
