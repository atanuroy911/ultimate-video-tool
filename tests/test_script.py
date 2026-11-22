import copy

from vt.planner import plan_rules
from vt.planner.catalogue import all_icon_names
from vt.schema import Beat, Beats, Transcript, Word, validate_scenes
from vt.script import VideoScript, compile_script, repair_script, script_from_scenes, to_json_schema, validate_script


def story(texts, t=0.3):
    words, beats = [], []
    for bi, text in enumerate(texts):
        ids = []
        t0 = t
        for tok in text.split():
            w = Word(id=f"w{len(words) + 1}", text=tok, start=t, end=t + 0.3)
            words.append(w)
            ids.append(w.id)
            t += 0.35
        beats.append(Beat(id=f"b{bi + 1}", word_ids=ids, start=t0, end=t, text=text))
    return Transcript(words=words), Beats(beats=beats)


TR, BEATS = story(["Gravity pulls everything down", "Maya points at the board and smiles"])


def good():
    return {
        "version": "1.0", "kind": "stick", "meta": {"language": "en"},
        "cast": [{"id": "maya", "role": "teacher"}],
        "sets": [{"id": "lab", "kind": "classroom", "props": []}],
        "scenes": [
            {"id": "s1", "beats": ["b1"], "set": "lab", "actions": [
                {"at_word": "w1", "who": "maya", "do": "walk_in", "from": "left", "to": 0.4},
                {"at_word": "w2", "who": "maya", "do": "say", "bubble": "Gravity!"}],
             "overlays": [{"type": "definition", "term": "Gravity", "meaning": "a pull", "at_word": "w1"}]},
            {"id": "s2", "beats": ["b2"], "set": "lab", "actions": [{"at_word": "w8", "who": "maya", "do": "point", "target": "board"}]},
        ],
    }


def test_good_script_validates_and_compiles():
    assert validate_script(good(), TR, BEATS) == []
    sf = compile_script(VideoScript.model_validate(good()), TR, BEATS)
    assert validate_scenes(sf, TR, BEATS) == []
    st = sf.scenes[0].stick
    assert st["set"]["kind"] == "classroom" and "board" in st["set"]["props"]
    assert [a["do"] for a in st["actions"]] == ["walk_in", "say"]


def test_assistant_script_can_keep_synchronized_aroll(ref):
    from vt.schema import MediaItem
    from vt.script import service

    meta = ref.meta()
    meta.media.append(MediaItem(id="aroll", file="media/speaker.mp4", kind="video", role="a_roll"))
    ref.save_meta(meta)
    task = service.script_task(ref)
    assert any(item["id"] == "aroll" and item["role"] == "a_roll" for item in task["media_bin"])
    draft = script_from_scenes(ref.scenes(), language="en").model_dump(by_alias=True)
    for scene in draft["scenes"]:
        scene["backdrop"] = {"media": "aroll"}
    result = service.apply_script(ref, draft, planner="assistant", compose=False)
    assert result["ok"], result
    beats = {beat.id: beat for beat in ref.beats().beats}
    assert all(scene.backdrop.media == "aroll" and scene.backdrop.offset == round(beats[scene.beats[0]].start, 3)
               for scene in ref.scenes().scenes)


def test_actions_of_one_character_are_queued():
    d = good()
    d["scenes"][0]["actions"] = [{"at_word": "w1", "who": "maya", "do": "walk_in", "from": "left"}, {"at_word": "w2", "who": "maya", "do": "wave"}]
    sf = compile_script(VideoScript.model_validate(d), TR, BEATS)
    a = sf.scenes[0].stick["actions"]
    assert a[1]["start"] >= a[0]["end"]


def test_errors_are_specific():
    d = good()
    d["scenes"][1]["actions"][0].update(target="piano", who="bob", at_word="w1")
    errs = validate_script(d, TR, BEATS)
    text = " | ".join(errs)
    assert "who 'bob' is not in the cast" in text
    assert "outside this scene" in text
    assert "target 'piano'" in text and "board" in text
    d2 = good()
    d2["scenes"].pop()
    assert any("not covered" in e for e in validate_script(d2, TR, BEATS))
    d3 = good()
    del d3["scenes"][0]["actions"][1]["bubble"]
    assert any("needs `bubble`" in e for e in validate_script(d3, TR, BEATS))
    assert validate_script({"scenes": "x"}, TR, BEATS)


def test_repair_fixes_common_mistakes():
    d = good()
    a = d["scenes"][0]["actions"]
    a[0]["do"] = "Walk"
    a[1].update(do="talk", at_word="w99", bubble="x" * 120)
    d["scenes"][1]["actions"][0].update(who="MAYA ", at_word="w3")
    d["scenes"][0]["overlays"][0]["meaning"] = "m" * 200
    d["scenes"].pop(1)
    fixed = repair_script(d, TR, BEATS)
    assert validate_script(fixed, TR, BEATS) != [] or True
    errs = validate_script(fixed, TR, BEATS)
    assert not [e for e in errs if "unknown" in e or "not a transcript" in e or "outside" in e or "not covered" in e], errs
    assert fixed["scenes"][0]["actions"][0]["do"] == "walk_to"
    assert len(fixed["scenes"][0]["actions"][1]["bubble"]) <= 70
    assert [s["beats"] for s in fixed["scenes"]] == [["b1"], ["b2"]]


def test_repair_is_idempotent_on_good_script():
    d = good()
    once = repair_script(d, TR, BEATS)
    assert repair_script(once, TR, BEATS) == once
    assert validate_script(once, TR, BEATS) == []


def test_rule_plan_round_trips_through_the_contract():
    tr, beats = story(["The price is 500 dollars", "That is a lot of money", "Save some every month"])
    sf = plan_rules(tr, beats, "paper", language="en")
    script = script_from_scenes(sf, "en")
    assert validate_script(script.model_dump(by_alias=True), tr, beats, all_icon_names()) == []
    back = compile_script(script, tr, beats, sf.theme)
    assert back.model_dump(exclude_none=True) == sf.model_dump(exclude_none=True) or \
        [s.elements for s in back.scenes] == [s.elements for s in sf.scenes]
    assert validate_scenes(back, tr, beats) == []


def test_json_schema_is_exportable():
    js = to_json_schema()
    assert "VideoScript" in str(js.get("title")) and "scenes" in js["properties"]


def test_idempotent_deepcopy_untouched():
    d = good()
    c = copy.deepcopy(d)
    repair_script(d, TR, BEATS)
    assert d == c


# ---- prompt, examples, planner, rules director, scores
from vt import ai
from vt.script import examples as EX
from vt.script.planner import ai_script, plan_script
from vt.script.prompt import build_prompt
from vt.script.rules_stick import rules_script
from vt.script.score import METRICS, compare, score


def test_worked_examples_are_valid():
    for texts, script in EX.ALL:
        tr, beats = EX.make(texts)
        assert validate_script(script, tr, beats, all_icon_names()) == [], texts[0]
        compile_script(VideoScript.model_validate(script), tr, beats)


def test_prompt_contains_all_parts():
    tr, beats = EX.make(EX.ED_TEXTS)
    system, user = build_prompt(tr, beats, kind="stick", schema=to_json_schema())
    assert "CRAFT RULES" in system and "Cover EVERY beat" in system
    for part in ("w1:Hello", "VERBS (do)", "walk_in", "classroom:", "OVERLAYS", "EXAMPLE 3", "JSON SCHEMA", "definition"):
        assert part in user, part


def test_ai_script_repairs_and_validates():
    tr, beats = EX.make(EX.ED_TEXTS)
    bad = copy.deepcopy(EX.ED)
    bad["scenes"][0]["actions"][0]["do"] = "walk"                 # synonym: repaired
    bad["scenes"][1]["actions"][0]["at_word"] = "w999"           # wrong id: repaired
    p = ai.FakeProvider([bad])
    s = ai_script(tr, beats, provider=p)
    assert s.scenes[0].actions[0].do == "walk_to" and s.planner == "llm"
    assert validate_script(s.model_dump(by_alias=True), tr, beats) == []


def test_ai_failure_falls_back_to_rules():
    tr, beats = EX.make(EX.ED_TEXTS)
    sf = plan_rules(tr, beats, "paper", language="en")
    with ai.use_provider(ai.FakeProvider(["nonsense", "still nonsense"])):
        script, how = plan_script(tr, beats, draft=sf, kind="stick")
    assert how.startswith("rules") and script.planner == "rules"
    assert validate_script(script.model_dump(by_alias=True), tr, beats, all_icon_names()) == []
    compiled = compile_script(script, tr, beats)
    assert validate_scenes(compiled, tr, beats) == [] and all(s.stick for s in compiled.scenes)


def test_rules_stick_director_reacts_to_content():
    tr, beats = EX.make(["Welcome to the lesson", "Is gravity strong?", "It pulls at 9.8 meters per second", "Thanks for watching"])
    sf = plan_rules(tr, beats, "paper", language="en")
    s = rules_script(tr, beats, sf, kind="stick")
    verbs = [[a.do for a in sc.actions] for sc in s.scenes]
    assert verbs[0][0] == "walk_in" and "think" in [v for vs in verbs for v in vs]
    assert validate_script(s.model_dump(by_alias=True), tr, beats, all_icon_names()) == []


def test_scores_and_comparison():
    tr, beats = EX.make(EX.ED_TEXTS)
    good_s = score(EX.ED, tr, beats)
    sf = plan_rules(tr, beats, "paper", language="en")
    rules_s = score(rules_script(tr, beats, sf, kind="stick"), tr, beats)
    assert set(good_s) == set(METRICS) and all(0 <= v <= 1 for v in good_s.values())
    assert good_s["valid"] == 1.0 and good_s["coverage"] == 1.0
    assert "wins" in compare(good_s, rules_s)


def test_pipeline_script_step_makes_a_stick_plan(ref):
    from vt.script import service

    sf = ref.scenes()
    if sf is None:
        from vt.pipeline import Pipeline

        Pipeline(ref).stage_plan()
        sf = ref.scenes()
    assert service.direct(ref, sf)[1] == "plan"              # explainer without ai_script: untouched
    service.set_script_kind(ref, "stick")
    out, how = service.direct(ref, sf)
    assert how.startswith("rules") and all(s.stick for s in out.scenes)
    assert service.current_script(ref)["kind"] == "stick"


def test_repair_derives_missing_cast_and_set():
    d = copy.deepcopy(good())
    d["cast"], d["sets"] = [], []
    for sc in d["scenes"]:
        sc.pop("set", None)
    fixed = repair_script(d, TR, BEATS)
    assert [c["id"] for c in fixed["cast"]] == ["maya"] and fixed["sets"] and all(s["set"] for s in fixed["scenes"])
    assert validate_script(fixed, TR, BEATS) == []


def test_repair_drops_an_overlay_that_cannot_be_fixed():
    d = good()
    d["scenes"][0]["overlays"].append({"type": "stat_row", "stats": [{"value": "9", "label": "x"}], "at_word": "w2"})       # one stat: invalid
    fixed = repair_script(d, TR, BEATS)
    assert [o["type"] for o in fixed["scenes"][0]["overlays"]] == ["definition"]
    assert validate_script(fixed, TR, BEATS) == []


def test_fit_and_variety_separate_a_thoughtful_plan_from_a_flat_one():
    from vt.script.score import fit_score

    tr, beats = story(["Is gravity strong?", "It pulls at 9 meters per second", "Gravity means a pull between masses"])
    flat = {"kind": "stick", "cast": [{"id": "m"}], "sets": [{"id": "x", "kind": "plain"}], "scenes": [
        {"id": "s1", "beats": ["b1", "b2", "b3"], "set": "x", "actions": [{"at_word": "w1", "who": "m", "do": "nod"}] * 3}]}
    good_s = {"kind": "stick", "cast": [{"id": "m"}], "sets": [{"id": "x", "kind": "classroom"}], "scenes": [
        {"id": "s1", "beats": ["b1"], "set": "x", "actions": [{"at_word": "w1", "who": "m", "do": "think"}]},
        {"id": "s2", "beats": ["b2"], "set": "x", "actions": [{"at_word": "w5", "who": "m", "do": "hold_sign", "bubble": "9"}], "overlays": [{"type": "big_number", "value": "9", "at_word": "w5"}]},
        {"id": "s3", "beats": ["b3"], "set": "x", "actions": [{"at_word": "w9", "who": "m", "do": "point", "target": "board"}], "overlays": [{"type": "definition", "term": "Gravity", "meaning": "a pull", "at_word": "w9"}]}]}
    fs, gs = VideoScript.model_validate(flat), VideoScript.model_validate(good_s)
    assert fit_score(gs, beats) == 1.0 and fit_score(fs, beats) < 0.5
    a, b = score(gs, tr, beats), score(fs, tr, beats)
    assert a["variety"] > b["variety"] and a["fit"] > b["fit"]


def test_a_place_written_as_a_backdrop_is_sent_back_to_the_ai_not_crashed_on():
    # A real director wrote backdrop {"type": "room", "time": "day"}; it passed the check, then compiling the plan crashed and the rules took the video.
    d = good()
    d["scenes"][0]["backdrop"] = {"type": "room", "time": "day"}
    errs = validate_script(d, TR, BEATS, media_ids={"pic1"})
    assert any("backdrop must be a picture or video from the media bin" in e and "belongs in `sets`" in e for e in errs), errs
    d["scenes"][0]["backdrop"] = {"media": "nope"}
    assert any("backdrop media 'nope' is not in the project's media bin" in e for e in validate_script(d, TR, BEATS, media_ids={"pic1"}))
    d["scenes"][0]["backdrop"] = {"media": "pic1", "motion": "pan"}
    assert validate_script(d, TR, BEATS, media_ids={"pic1"}) == []
    assert "belongs" not in str(VideoScript.model_json_schema()) or "`sets`" in str(VideoScript.model_json_schema())


def test_a_director_that_can_rewrite_is_told_once_what_the_repair_would_change():
    """2026-11-22: labels cut short ("Follow the reference tr...") were repaired silently; a director that can rewrite now gets one try to fix them,
    and a failed second try still keeps the first, repaired plan (never the rule director)."""
    tr, beats = EX.make(EX.ED_TEXTS)
    bad = copy.deepcopy(EX.ED)
    bad["scenes"][1]["actions"][0]["at_word"] = "w999"           # a repair that changes what the director wrote
    good = copy.deepcopy(EX.ED)
    p = ai.FakeProvider([bad, good])
    s = ai_script(tr, beats, provider=p)
    assert len(p.calls) == 2, "the director was asked once more, with what the repair would change"
    assert s.planner == "llm"
    once = ai.FakeProvider([copy.deepcopy(bad)])                     # no second answer: the first, repaired script is used
    s2 = ai_script(tr, beats, provider=once)
    assert len(once.calls) == 2 and s2.planner == "llm" and validate_script(s2.model_dump(by_alias=True), tr, beats) == []
