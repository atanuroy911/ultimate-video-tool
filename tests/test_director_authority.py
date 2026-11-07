"""Plan decision 1 (docs/plans/PLAN-PERFECT.MD, Phase B): the director's word is final.

Code never hides, shrinks or drops what any AI put on screen, whichever AI it is (the local AI, Claude or Codex). The page measures the crowd instead
(renderer/runtime/vt.js `guardLayout` records what it WOULD have done), the frame facts tell the director (renderer/scripts/frame-facts.mjs), and what is still there after the
director's rounds is listed in the Quality check. A plan made by the built-in rules keeps the guard, and what it did goes to Details, Problems.

The page tests open the real composition in a headless browser with software drawing (no graphics card) and skip when HyperFrames has no browser here."""
from __future__ import annotations

from pathlib import Path

import pytest

AI = ("llm", "claude", "assistant")
AT = 4.5                                                       # seconds: everything has arrived and the scene (0 to 5 s) is still on screen
TIMES = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]               # a crowd that becomes several pages is looked at page by page

SMALL = [{"type": "sticker", "emoji": "1f4b0", "label": "money", "at_word": "w1"}, {"type": "sticker", "emoji": "1f3e0", "label": "house", "at_word": "w1"},
         {"type": "sticker", "emoji": "1f697", "label": "car", "at_word": "w2"}, {"type": "tag", "text": "interest rate", "at_word": "w2"},
         {"type": "keyword", "text": "Mortgage", "at_word": "w3"}, {"type": "icon", "name": "coin", "at_word": "w3"}, {"type": "tag", "text": "down payment", "at_word": "w4"}]
# Each plan is crowded in a way that trips one rule of the guard on the real page (checked on the rules' own plan first, so the test says so if this machine's fonts change that).
# Layout fits what it can by scaling together before the guard looks (vt.js fitGroups, shrinkStages), so the first plan also switches that off: the guard's own shrink needs something layout could not fit.
NO_FIT = ".stage .grp { scale: none !important; translate: none !important; }"
CASES = {
    "runs off the frame": {"aspect": "9:16", "layout": "stack", "rule": "cut-off", "css": NO_FIT + " .stage .el-keyword { width: 1400px !important; max-width: none !important; justify-content: center; }", "elements": [
        {"type": "keyword", "text": "Mortgage", "at_word": "w1"}, {"type": "tag", "text": "interest rate", "at_word": "w2"}]},
    "cut off and optional": {"aspect": "9:16", "layout": "split", "rule": "cut-off", "elements": SMALL},
    "letters too small": {"aspect": "16:9", "layout": "side", "rule": "too-small", "elements": SMALL},
    "on top of another": {"aspect": "9:16", "layout": "hero", "rule": "overlap", "elements": [
        {"type": "compare", "left": {"title": "Before", "value": "1,200,000"}, "right": {"title": "After", "value": "3,400,000"}, "verdict": "Nearly three times as much", "at_word": "w1"},
        {"type": "equation", "parts": [{"text": "A"}, {"text": "+"}, {"text": "B"}, {"text": "="}, {"text": "C"}], "at_word": "w2"},
        {"type": "pros_cons", "pros": ["fast", "cheap", "clear"], "cons": ["noisy", "heavy", "dull"], "at_word": "w3"}]},
}
# Plans that used to run off the frame and that layout now fits by scaling them together: nothing is cut off, whoever planned them, and the guard has nothing to do.
FITTED = {
    "a long word in a grid": {"aspect": "16:9", "layout": "grid", "elements": [
        {"type": "keyword", "text": "Supercalifragilisticexpialidoc", "at_word": "w1"}, {"type": "title", "text": "Pneumonoultramicroscopicsilicovolc", "at_word": "w2"}]},
    "four cards one above the other": {"aspect": "9:16", "layout": "split", "elements": [
        {"type": "value_card", "value": "5,000,000,000", "label": "Revenue per year in total", "at_word": "w1"},
        {"type": "quote", "text": "A long quotation that wraps over several lines of the card for sure and more", "by": "Somebody", "at_word": "w3"},
        {"type": "bar_chart", "bars": [{"label": "a", "value": 3}, {"label": "b", "value": 5}, {"label": "c", "value": 2}, {"label": "d", "value": 4}, {"label": "e", "value": 1}], "at_word": "w4"},
        {"type": "steps", "items": [{"title": "one"}, {"title": "two"}, {"title": "three"}], "at_word": "w5"}]},
}
STICK = {"a prop the shot cuts": {"pattern": "kitchen", "aspect": "16:9", "shot": "close", "also": [(2, "chef", "point", {"target": "window"})]},          # the director points at the window
         "set decoration the shot cuts": {"pattern": "kitchen", "aspect": "16:9", "shot": "close"}}                                                     # nobody names it
WOULD = {"shrunk": "would-shrink", "dropped": "would-drop"}
LOOK = """(() => {
  const els = [...document.querySelectorAll('.stage .el')], shown = els.map(() => false);
  for (const t of [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5]) { window.__vt.seek(t); els.forEach((w, i) => { if (getComputedStyle(w).display !== 'none') shown[i] = true; }); }
  window.__vt.seek(4.5);
  return { guard: window.__guard || [], props: [...document.querySelectorAll('.stk-prop')].map((g) => getComputedStyle(g).display !== 'none'),
    items: els.map((w, i) => { const r = w.getBoundingClientRect();
    return { el: w.getAttribute('data-el'), type: [...w.classList].find((c) => c.startsWith('el-')).slice(3), shown: shown[i], w: r.width, h: r.height, left: r.left, top: r.top }; }) };
})()"""


def compose(root: Path, planner: str, case: dict, name: str):
    from vt.compose.composer import resolve_composition, write_composition
    from vt.project import load_theme
    from vt.schema import Beat, Beats, ScenesFile, Transcript, Word

    words = [Word(id=f"w{i}", text=f"w{i}", start=0.3 + i * 0.4, end=0.6 + i * 0.4) for i in range(1, 9)]
    beats = Beats(beats=[Beat(id="b1", word_ids=[w.id for w in words], start=0.3, end=4.0, text="x")])
    sf = ScenesFile.model_validate({"planner": planner, "scenes": [{"id": "s1", "beats": ["b1"], "layout": case["layout"], "elements": case["elements"]}]})
    theme = load_theme("paper")
    data = resolve_composition(sf, Transcript(words=words), beats, theme, case["aspect"], 5.0, None, media={})
    data["captions"] = []
    index = write_composition(root / name, data, theme)
    if case.get("css"):
        index.write_text(index.read_text(encoding="utf-8").replace("</head>", f"<style>{case['css']}</style></head>", 1), encoding="utf-8")
    return index.parent, data


def compose_stick(root: Path, planner: str, case: dict, name: str):
    """A stick-figure scene from the QA script's patterns (scripts/qa_stick.py), shot close so that the frame cuts a prop of the set."""
    import importlib.util

    from vt.compose.composer import resolve_composition, write_composition
    from vt.planner.catalogue import all_icon_names
    from vt.project import load_theme
    from vt.script import compile_script, repair_script, validate_script
    from vt.script.models import VideoScript

    spec = importlib.util.spec_from_file_location("qa_stick", Path(__file__).resolve().parents[1] / "scripts" / "qa_stick.py")
    qa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qa)
    pattern = dict(qa.PATTERNS[case["pattern"]])
    first = list(pattern["scenes"][0])
    first[3] = case["shot"]
    first[2] = list(first[2]) + [qa.A(k, who, do, **extra) for k, who, do, extra in case.get("also", [])]
    pattern["scenes"] = [tuple(first)]
    script, tr, beats = qa.build_script(case["pattern"], pattern)
    script = repair_script(script, tr, beats, "stick")
    assert not validate_script(script, tr, beats, all_icon_names())
    sf = compile_script(VideoScript.model_validate(script), tr, beats, "paper").model_copy(update={"planner": planner})
    end = round(beats.beats[-1].end + 1.0, 2)
    theme = load_theme("paper")
    data = resolve_composition(sf, tr, beats, theme, case["aspect"], end, None, media={}, envelope={"dt": 0.04, "v": [0.5] * int(end / 0.04)}, language="en")
    data["icons"] = {}
    return write_composition(root / name, data, theme).parent, data


@pytest.fixture(scope="module")
def see(tmp_path_factory):
    """see(case, planner): the composition of that crowded plan as the page really shows it, and what the frame facts say about it (each computed once)."""
    from vt.render import hyperframes as H

    try:
        H._browser()
    except Exception as e:                                                      # noqa: BLE001
        pytest.skip(f"HyperFrames has no browser here: {str(e)[:120]}")
    root = tmp_path_factory.mktemp("authority")
    seen: dict = {}

    def look(case: str, planner: str) -> dict:
        if (case, planner) not in seen:
            if case in STICK:
                comp, data = compose_stick(root, planner, STICK[case], f"{case.replace(' ', '-')}-{planner}")
            else:
                comp, data = compose(root, planner, {**CASES, **FITTED}[case], f"{case.replace(' ', '-')}-{planner}")
            facts = H.frame_facts(comp, TIMES)
            seen[case, planner] = {"data": data, **H.probe(comp, LOOK, AT), "facts": [f for t in TIMES for f in facts[float(t)]]}
        return seen[case, planner]

    return look


def reported(facts: list[str], g: dict) -> bool:
    """Do the facts say what the guard found about this element?"""
    what = f"element {g['el']} ({g['type']})"
    if g["rule"] == "cut-off":
        return any(what in f and ("outside the frame" in f or "runs off the frame" in f) for f in facts)
    if g["rule"] == "too-small":
        return any(what in f and "too small" in f for f in facts)
    return any(what in f and f"element {g['with']} (" in f and ("covers" in f or "overlaps" in f) for f in facts)


# ---- the composer marks the plans an AI directed -------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("planner,directed", [("llm", True), ("claude", True), ("assistant", True), ("rules", False), ("manual", False)])
def test_a_scene_is_marked_directed_only_when_an_ai_planned_the_video(planner, directed):
    from vt.compose.composer import resolve_composition
    from vt.project import load_theme
    from vt.schema import Beat, Beats, ScenesFile, Transcript, Word

    words = [Word(id=f"w{i}", text=f"w{i}", start=0.3 + i * 0.4, end=0.6 + i * 0.4) for i in range(1, 5)]
    beats = Beats(beats=[Beat(id="b1", word_ids=["w1", "w2"], start=0.3, end=1.5, text="x"), Beat(id="b2", word_ids=["w3", "w4"], start=1.5, end=3.0, text="y")])
    els = [{"type": "title", "text": "Hello", "at_word": "w1"}]
    sf = ScenesFile.model_validate({"planner": planner, "scenes": [
        {"id": "s1", "beats": ["b1"], "elements": els},
        {"id": "s2", "beats": ["b2"], "elements": [{"type": "title", "text": "Edited by hand", "at_word": "w3", "edited": True}]}]})
    data = resolve_composition(sf, Transcript(words=words), beats, load_theme("paper"), "9:16", 3.0, None, media={})
    assert [s.get("directed", False) for s in data["scenes"]] == [directed, False], "a scene the person edited is theirs, whoever planned the rest"


# ---- the real page: three directors, four kinds of crowd, and the rule plan as before ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_the_rules_keep_the_layout_guard(see, case):
    page = see(case, "rules")
    done = [g for g in page["guard"] if g["rule"] == CASES[case]["rule"]]
    assert done, f"this crowd no longer trips the {CASES[case]['rule']} rule on this machine: {page['guard']}"
    assert all(g["fix"] in ("shrunk", "dropped") and "directed" not in g for g in page["guard"])
    items = {i["el"]: i for i in page["items"]}
    assert all(not items[g["el"]]["shown"] for g in page["guard"] if g["fix"] == "dropped"), "what the guard dropped is never on the page, not even when its turn comes in the timeline"


@pytest.mark.parametrize("planner", AI)
@pytest.mark.parametrize("case", CASES)
def test_nothing_an_ai_placed_is_hidden_shrunk_or_dropped(see, case, planner):
    rules, ai = see(case, "rules"), see(case, planner)
    assert [s.get("directed") for s in ai["data"]["scenes"]] == [True] * len(ai["data"]["scenes"])
    assert not any(s.get("directed") for s in rules["data"]["scenes"])
    assert len(ai["items"]) == len(rules["items"]) and all(i["shown"] for i in ai["items"]), "every element the director placed is on the page"
    assert all(g["fix"] in WOULD.values() or g["fix"] == "left" for g in ai["guard"]), ai["guard"]
    assert all(g["directed"] for g in ai["guard"])
    theirs = {i["el"]: i for i in ai["items"]}
    ours = {i["el"]: i for i in rules["items"]}
    for g in rules["guard"]:                                                    # what the guard did to the rules' plan, the director's plan only gets measured
        said = [x for x in ai["guard"] if x["el"] == g["el"] and x["rule"] == g["rule"]]
        assert said and said[0]["fix"] == WOULD[g["fix"]], (g, ai["guard"])
        if g["fix"] == "shrunk":
            assert theirs[g["el"]]["w"] > ours[g["el"]]["w"] + 1, "it keeps its size"


@pytest.mark.parametrize("planner", AI)
@pytest.mark.parametrize("case", CASES)
def test_the_facts_tell_the_director_what_the_guard_would_have_done(see, case, planner):
    rules, ai = see(case, "rules"), see(case, planner)
    missing = [g for g in rules["guard"] if not reported(ai["facts"], g)]
    assert not missing, f"the facts do not say {missing}; they say {ai['facts']}"
    assert not [f for f in rules["facts"] if "too small" in f or "runs off" in f], "the guard's findings are told only to a director an AI is (a rule plan was fixed by the guard)"


@pytest.mark.parametrize("planner", ("rules", "llm"))
@pytest.mark.parametrize("case", FITTED)
def test_layout_fits_a_crowd_by_scaling_it_together_before_anything_is_judged(see, case, planner):
    page = see(case, planner)
    wide, high = page["data"]["format"]["width"], page["data"]["format"]["height"]
    outside = [i for i in page["items"] if i["shown"] and (i["left"] < -2 or i["top"] < -2 or i["left"] + i["w"] > wide + 2 or i["top"] + i["h"] > high + 2)]
    assert not outside, f"still running off the frame: {outside}"
    assert page["guard"] == [], "layout did its job, so the guard had nothing to do"


# ---- step B3: a prop the shot cuts, and a scene over a person ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("planner", AI)
def test_a_prop_the_shot_cuts_stays_in_a_scene_an_ai_directed(see, planner):
    rules, ai = see("a prop the shot cuts", "rules"), see("a prop the shot cuts", planner)
    cut = [g for g in rules["guard"] if g["type"].startswith("prop:")]
    assert cut and all(g["fix"] == "dropped" and "directed" not in g for g in cut), f"this shot no longer cuts a prop on this machine: {rules['guard']}"
    assert not all(rules["props"]), "the rules keep the guard: the cut prop is not drawn"
    assert all(ai["props"]) and len(ai["props"]) == len(rules["props"]), "a director's prop is drawn, cut or not"
    said = [g for g in ai["guard"] if g["type"].startswith("prop:")]
    assert [g["type"] for g in said] == [g["type"] for g in cut] and all(g["fix"] == "would-drop" and g["directed"] for g in said)
    assert any(f"The prop {cut[0]['type'][5:]} is cut by the shot" in f for f in ai["facts"]), ai["facts"]
    assert not any("is cut by the shot" in f for f in rules["facts"]), "the rules' plan was fixed by the guard, so there is nothing to tell"


@pytest.mark.parametrize("planner", ("rules",) + AI)
def test_set_decoration_nobody_named_is_not_drawn_when_the_shot_cuts_it_whoever_planned(see, planner):
    page = see("set decoration the shot cuts", planner)
    assert not all(page["props"]), "the kind of place brings a window; the close shot cuts it, so it is not drawn (half a window reads as a mistake)"
    assert not [g for g in page["guard"] if g["type"].startswith("prop:")], "and it is nobody's mistake to report: nothing was placed"


def _person_photo(ref, planner: str) -> None:
    """A scene over a picture whose person fills a tall crop: the first element has nowhere to go (tests/test_people.py has the same scene over a video)."""
    from PIL import Image

    from vt import people as PE
    from vt.planner import plan_rules
    from vt.schema import Backdrop, MediaItem, Scrim, Sticker

    body = PE.pack(PE.to_grid(PE.face_body_mask([0.43, 0.08, 0.14, 0.24], 90, 160), margin=0.03))
    sf = plan_rules(ref.transcript(), ref.beats(), ref.meta().theme, language="bn")
    sc = sf.scenes[0]
    sc.elements = [Sticker(at_word=ref.beats().beats[0].word_ids[0], emoji="1f44f", label="Applause")]
    sc.backdrop = Backdrop(media="pic", motion="none", fx=0.5, fy=0.3, scrim=Scrim(), person=body)
    ref.update_meta(media=[MediaItem(id="pic", file="media/pic.jpg", kind="image", width=1920, height=1080, fx=0.5, fy=0.3)])
    (ref.dir / "media").mkdir(exist_ok=True)
    Image.new("RGB", (192, 108), (120, 120, 120)).save(ref.dir / "media" / "pic.jpg")
    ref.save_scenes(sf.model_copy(update={"planner": planner}))


def _composed(ref, aspect: str):
    import json

    from vt.compose import compose_project

    index = compose_project(ref, aspect)
    return index.parent, json.loads((index.parent / "data.json").read_text(encoding="utf-8"))["scenes"][0]


@pytest.mark.parametrize("planner,kept", [("rules", False), ("manual", False), ("llm", True), ("claude", True), ("assistant", True)])
def test_a_scene_over_a_person_keeps_its_elements_when_an_ai_directed_it(ref, planner, kept):
    _person_photo(ref, planner)
    tall = _composed(ref, "9:16")[1]
    if kept:
        assert tall["elements"] and tall.get("no_room_beside_person") is True and "cleared_for_person" not in tall and "stage" not in tall
    else:
        assert tall["elements"] == [] and tall.get("cleared_for_person") is True and "no_room_beside_person" not in tall, "the rules clear the scene as before"
    wide = _composed(ref, "16:9")[1]
    assert wide["elements"] and wide.get("stage") and "no_room_beside_person" not in wide and "cleared_for_person" not in wide, "where there is room, everything goes beside the person"


@pytest.mark.parametrize("planner", AI)
def test_the_facts_tell_a_director_there_is_no_room_beside_the_person(ref, planner):
    from vt.render import hyperframes as H

    try:
        H._browser()
    except Exception as e:                                                      # noqa: BLE001
        pytest.skip(f"HyperFrames has no browser here: {str(e)[:120]}")
    _person_photo(ref, planner)
    comp, scene = _composed(ref, "9:16")
    middle = round((scene["start"] + scene["end"]) / 2, 2)
    facts = H.frame_facts(comp, [middle])[middle]
    assert any("There is no free room beside the person in the picture" in f for f in facts), facts


# ---- step B7: prove it, for every style a director can write ------------------------------------------------------------------------------------------------------------

SCRIPT_STYLES = ("explainer", "stick", "emoji", "cartoon")
CROWD = {                                   # one scene with far more on it than a screen holds, all at words of the first sentence
    "explainer": [{"type": "title", "text": "Gravity", "at_word": "w2"}, {"type": "sticker", "emoji": "1f34e", "label": "apple", "at_word": "w3"},
                  {"type": "sticker", "emoji": "1f30d", "label": "earth", "at_word": "w3"}, {"type": "tag", "text": "pulls everything down", "at_word": "w4"},
                  {"type": "keyword", "text": "Gravity", "at_word": "w5"}, {"type": "icon", "name": "coin", "at_word": "w6"}, {"type": "tag", "text": "9.8 m per second", "at_word": "w7"}],
    "emoji": [{"type": "sticker", "emoji": "1f34e", "label": "apple", "at_word": "w2"}, {"type": "sticker", "emoji": "1f30d", "label": "earth", "at_word": "w3"},
              {"type": "sticker", "emoji": "1f4a1", "label": "idea", "at_word": "w4"}, {"type": "keyword", "text": "Gravity", "at_word": "w5"},
              {"type": "keyword", "text": "pulls", "at_word": "w6"}, {"type": "keyword", "text": "down", "at_word": "w7"}],
}
CROWD["stick"] = CROWD["cartoon"] = CROWD["explainer"]


def crowded_script_plan(style: str, planner: str):
    """A Video Script of this style with one crowded scene, compiled the way the app does and composed for 9:16: (the plan, its composition data, where it was written)."""
    import copy

    from vt.compose.composer import resolve_composition
    from vt.project import load_theme
    from vt.script import compile_script, repair_script, validate_script
    from vt.script.examples import ED, ED_TEXTS, make
    from vt.script.models import VideoScript

    tr, beats = make(ED_TEXTS)
    s = copy.deepcopy(ED)
    s["kind"] = style
    s["scenes"][0]["overlays"] = copy.deepcopy(CROWD[style])
    if style == "emoji":
        s["scenes"][0]["actions"] = []
    s = repair_script(s, tr, beats, "stick" if style == "cartoon" else style)
    assert validate_script(s, tr, beats) == [], validate_script(s, tr, beats)
    sf = compile_script(VideoScript.model_validate(s), tr, beats, "paper").model_copy(update={"planner": planner})
    theme = load_theme("paper")
    duration = round(beats.beats[-1].end + 1.0, 2)
    data = resolve_composition(sf, tr, beats, theme, "9:16", duration, None, media={}, envelope={"dt": 0.04, "v": [0.5] * int(duration / 0.04)}, language="en")
    data["icons"] = {}
    return sf, data, theme


@pytest.mark.parametrize("planner", AI)
@pytest.mark.parametrize("style", SCRIPT_STYLES)
def test_every_element_an_ai_placed_is_in_the_composition_whatever_the_style(style, planner):
    sf, data, _ = crowded_script_plan(style, planner)
    placed = [e for sc in sf.scenes for e in sc.elements if e.type != "story"]
    composed = [e for sc in data["scenes"] for e in sc["elements"]]
    assert len(placed) >= len(CROWD[style]) and len(composed) == len(placed), f"{style}: {len(placed)} placed, {len(composed)} composed"
    assert sorted(e["type"] for e in composed) == sorted(e.type for e in placed)
    assert data["scenes"] and all(sc.get("directed") for sc in data["scenes"] if not sc.get("edited")), "every scene of the plan an AI directed is marked"
    assert not any(sc.get("cleared_for_person") for sc in data["scenes"])


@pytest.mark.parametrize("planner", AI)
@pytest.mark.parametrize("style", SCRIPT_STYLES)
def test_every_element_an_ai_placed_is_on_the_page_whatever_the_style(tmp_path_factory, style, planner):
    from vt.compose.composer import write_composition
    from vt.render import hyperframes as H

    try:
        H._browser()
    except Exception as e:                                                      # noqa: BLE001
        pytest.skip(f"HyperFrames has no browser here: {str(e)[:120]}")
    sf, data, theme = crowded_script_plan(style, planner)
    rules_sf, rules_data, _ = crowded_script_plan(style, "rules")
    root = tmp_path_factory.mktemp(f"style-{style}-{planner}")
    page = H.probe(write_composition(root / "ai", data, theme).parent, LOOK, AT)
    old = H.probe(write_composition(root / "rules", rules_data, theme).parent, LOOK, AT)
    placed = sum(len(sc["elements"]) for sc in data["scenes"])
    assert len(page["items"]) >= 1 and len(page["items"]) == placed - sum(1 for sc in data["scenes"] for e in sc["elements"] if e.get("free")), "every element is on the page"
    assert all(i["shown"] for i in page["items"]), f"{style}: something the director placed never shows: {[i for i in page['items'] if not i['shown']]}"
    assert all(g["fix"].startswith("would-") or g["fix"] == "left" for g in page["guard"] if "directed" in g), page["guard"]
    assert not [g for g in page["guard"] if g["fix"] in ("shrunk", "dropped")], "the guard changed nothing on an AI's plan"
    assert len(old["items"]) == len(page["items"]), "the same crowd, planned by the rules, is the same elements (the guard may hide some of them for the rules)"


# ---- what the guard did to a plan the rules made goes to Details, Problems ------------------------------------------------------------------------------------------


def _as(ref, planner):
    ref.save_scenes(ref.scenes().model_copy(update={"planner": planner}))
    return ref.scenes().scenes[1].id


def _found(sid):
    return [{"scene": sid, "el": "3", "type": "tag", "rule": "too-small", "fix": "dropped"},
            {"scene": sid, "el": "0", "type": "big_number", "rule": "cut-off", "fix": "shrunk"},
            {"scene": sid, "type": "prop:chair", "rule": "cut-off", "fix": "dropped"},
            {"scene": sid, "el": "2", "type": "sticker", "rule": "cut-off", "fix": "would-drop", "directed": True}]


def test_what_the_guard_did_to_a_rule_plan_is_in_details_problems(ref, monkeypatch):
    import vt.render.hyperframes as H
    from vt import layout_check as L
    from vt.modules.calls import read_calls

    monkeypatch.setenv("VT_LAYOUT_CHECK", "1")
    sid = _as(ref, "rules")
    monkeypatch.setattr(H, "guard_log", lambda comp: _found(sid))
    rows = L.record(ref)
    problems = read_calls(ref.dir, level="warn,error")
    assert len(rows) == 1 and len(problems) == 1
    p = problems[0]
    assert p["module"] == "layout.guard" and p["level"] == "warn" and p["caller"]["kind"] == "rules" and p["inputs"] == {"scene": sid}
    assert p["plain"] == ("Scene 2: the tag had letters too small to read on a phone, so it was hidden; the big number ran off the frame, so it was made smaller to fit; "
                          "the prop chair was cut by the shot, so it was not drawn.")
    assert "sticker" not in p["plain"], "what was only measured (a plan an AI directed) is not a change"
    assert "fewer or smaller" in p["fix"] and "AI direct" in p["fix"]
    assert L.record(ref) == rows and len(read_calls(ref.dir, level="warn")) == 1, "the same plan is written once"
    ref.save_scenes(ref.scenes().model_copy(update={"scenes": [s.model_copy(update={"tone": 1}) if s.id == sid else s for s in ref.scenes().scenes]}))
    L.record(ref)
    assert len(read_calls(ref.dir, level="warn")) == 2, "a changed plan is looked at again"


@pytest.mark.parametrize("planner", AI)
def test_a_plan_an_ai_directed_is_never_reported_as_changed(ref, monkeypatch, planner):
    import vt.render.hyperframes as H
    from vt import layout_check as L
    from vt.modules.calls import read_calls

    monkeypatch.setenv("VT_LAYOUT_CHECK", "1")
    sid = _as(ref, planner)
    monkeypatch.setattr(H, "guard_log", lambda comp: pytest.fail("an AI's plan is not opened for the guard's sake: the director's last look measures it") or [])
    assert L.record(ref) == [] and read_calls(ref.dir) == []


def test_reading_the_guard_is_a_report_and_never_stops_a_video(ref, monkeypatch):
    import vt.render.hyperframes as H
    from vt import layout_check as L
    from vt.modules.calls import read_calls
    from vt.util import read_json

    sid = _as(ref, "rules")
    monkeypatch.setattr(H, "guard_log", lambda comp: _found(sid))
    monkeypatch.delenv("VT_LAYOUT_CHECK", raising=False)
    monkeypatch.setenv("VT_LAYOUT_CHECK", "0")
    assert L.record(ref) == [] and read_calls(ref.dir) == [], "switched off"
    monkeypatch.setenv("VT_LAYOUT_CHECK", "1")

    def no_browser(comp):
        raise RuntimeError("HyperFrames has no browser")

    monkeypatch.setattr(H, "guard_log", no_browser)
    assert L.record(ref) == [] and read_calls(ref.dir) == []
    assert "no browser" in read_json(ref.dir / L.REPORT, {})["error"]


@pytest.mark.parametrize("planner,expected", [("rules", True), ("manual", True), ("claude", False)])
def test_the_pipeline_reads_the_guard_only_for_plans_no_ai_directed(ref, monkeypatch, planner, expected):
    from vt import layout_check
    from vt.pipeline import Pipeline

    seen = []
    monkeypatch.setattr(layout_check, "record", lambda p: seen.append(p.scenes().planner) or [])
    _as(ref, planner)
    Pipeline(ref).stage_compose(force=True)
    assert seen == ([planner] if expected else [])


# ---- the director's last look keeps what is left -------------------------------------------------------------------------------------------------------------------


def _look(ref, monkeypatch, measure, answers):
    """The director's last look with stand-ins for the page and the AI: (report, what the page was asked, the two scenes)."""
    import vt.ai.providers as P
    import vt.director_review as R
    import vt.render.hyperframes as H

    ids = [s.id for s in ref.scenes().scenes][:2]
    monkeypatch.setattr(R, "_frame_times", lambda comp, plan: [(ids[0], 1.0), (ids[1], 2.0)])
    monkeypatch.setattr(H, "snapshot", lambda *a, **k: [Path("a.png"), Path("b.png")])
    asked = []

    def facts(comp, times):
        asked.append(times)
        return measure(len(asked))

    monkeypatch.setattr(H, "frame_facts", facts)
    monkeypatch.setattr(R, "_png", lambda f: b"x")
    answers = iter(answers)
    monkeypatch.setattr(P, "complete_json", lambda *a, **k: next(answers))
    return R.review(ref, compose=lambda p: None), asked, ids


RIGHT = {"people": [], "what_i_see": "", "looks_right": True, "changes": []}
MOVES = {"people": [], "what_i_see": "", "looks_right": False, "changes": [{"element": 0, "set": {"opacity": .9}}]}
TAG = "element 1 (tag) has letters too small to read on a phone."


def test_what_the_director_leaves_is_stored_for_the_quality_check(ref, monkeypatch):
    report, asked, ids = _look(ref, monkeypatch, lambda n: {1.0: [TAG, "Empty across the frame: y 0.70 to 0.84."], 2.0: ["Nothing covers any character."]}, [RIGHT, RIGHT])
    assert report["left"] == [{"scene": ids[0], "at": 1.0, "facts": [TAG]}], "information for the director is not trouble"
    assert len(asked) == 1 and report["changed"] == 0


def test_the_director_looks_once_and_what_is_left_is_measured_after_its_change(ref, monkeypatch):
    # one look and one revision (owner decision 9): the director changes a scene, the cut is composed again and measured once more; the person fixes what is left in the editor
    report, asked, ids = _look(ref, monkeypatch, lambda n: {1.0: [TAG] if n == 1 else [], 2.0: []}, [MOVES, RIGHT, RIGHT, RIGHT])
    assert report["left"] == [] and len(asked) == 2 and report["changed"] == 1 and len(report["rounds"]) == 1, "no second look: the answers of a second round were never asked for"


def test_a_cut_the_director_changed_is_listed_with_what_is_still_wrong(ref, monkeypatch):
    report, asked, ids = _look(ref, monkeypatch, lambda n: {1.0: [TAG], 2.0: ["Nothing covers any character."]}, [MOVES, RIGHT])
    assert len(asked) == 2 and report["left"] == [{"scene": ids[0], "at": 1.0, "facts": [TAG]}] and report["changed"] == 1


def test_a_cut_that_could_not_be_measured_is_not_called_clean(ref, monkeypatch):
    from fastapi.testclient import TestClient

    from vt.server.app import app

    def no_page(n):
        raise RuntimeError("the page did not open")

    report, asked, ids = _look(ref, monkeypatch, no_page, [RIGHT, RIGHT])
    assert report["left"] == [] and "did not open" in report["facts_error"]
    with TestClient(app) as client:
        said = client.get(f"/api/projects/{ref.id}/look-at").json()
    assert said["looked"] is False and said["left"] == [], "nothing is claimed about a cut nobody measured"


def test_the_quality_check_is_told_what_is_left_and_what_the_guard_changed(ref, monkeypatch):
    from fastapi.testclient import TestClient

    import vt.render.hyperframes as H
    from vt import layout_check as L
    from vt.server.app import app
    from vt.util import file_hash, write_json

    sid = _as(ref, "rules")
    monkeypatch.setenv("VT_LAYOUT_CHECK", "1")
    monkeypatch.setattr(H, "guard_log", lambda comp: _found(sid))
    L.record(ref)
    write_json(ref.dir / "director_review.json", {"left": [{"scene": sid, "at": 3.0, "facts": [TAG]}], "scenes_hash": file_hash(ref.scenes_path)})
    with TestClient(app) as client:
        said = client.get(f"/api/projects/{ref.id}/look-at").json()
        assert said["looked"] and said["current"] and said["guard_current"] and said["planner"] == "rules"
        assert said["left"] == [{"scene": sid, "at": 3.0, "facts": [TAG], "number": 2}]
        assert said["changed"][0]["number"] == 2 and "the tag had letters too small to read on a phone, so it was hidden" in said["changed"][0]["says"]
        ref.save_scenes(ref.scenes().model_copy(update={"scenes": [s.model_copy(update={"tone": 2}) if s.id == sid else s for s in ref.scenes().scenes]}))
        later = client.get(f"/api/projects/{ref.id}/look-at").json()
        assert later["current"] is False and later["guard_current"] is False, "the person is told the plan changed since it was looked at"
        assert client.get("/api/projects/nope/look-at").status_code == 404


def test_a_cut_changed_after_the_look_is_measured_again_so_the_quality_check_is_not_stale(ref, monkeypatch):
    # the viewer-test revision rewrites the plan after the director looked: what is left is measured on the new cut (page facts only, nobody is asked)
    import vt.director_review as R
    import vt.render.hyperframes as H
    from vt.util import file_hash, read_json, write_json

    report, asked, ids = _look(ref, monkeypatch, lambda n: {1.0: [], 2.0: []}, [RIGHT, RIGHT])
    assert report["left"] == []
    sf = ref.scenes()
    sf.scenes[0].elements[0] = sf.scenes[0].elements[0].model_copy(update={"opacity": 0.5})        # the plan is rewritten: its file changes
    ref.save_scenes(sf)
    assert read_json(ref.dir / R.REPORT)["scenes_hash"] != file_hash(ref.scenes_path)
    monkeypatch.setattr(H, "frame_facts", lambda comp, times: {1.0: [TAG], 2.0: []})
    R.remeasure(ref)
    now = read_json(ref.dir / R.REPORT)
    assert now["left"] == [{"scene": ids[0], "at": 1.0, "facts": [TAG]}] and now["scenes_hash"] == file_hash(ref.scenes_path)
    assert now["rounds"] == report["rounds"], "what the director saw stays as it was"


def test_a_cut_nobody_looked_at_is_not_given_a_record_by_the_remeasure(ref):
    import vt.director_review as R

    (ref.dir / R.REPORT).unlink(missing_ok=True)
    R.remeasure(ref)
    assert not (ref.dir / R.REPORT).exists()
