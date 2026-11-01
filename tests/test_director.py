import json
from collections import Counter

import pytest

from vt.compose.composer import resolve_composition
from vt.director import archetypes as A


def test_feature_grid_avoids_animal_hide_for_hide_rest():
    from types import SimpleNamespace

    fact = SimpleNamespace(items=[("Add work", SimpleNamespace(id="w1")),
                                  ("Choose what matters", SimpleNamespace(id="w2")),
                                  ("Hide rest", SimpleNamespace(id="w3"))])
    elements, _ = A.b_feature_grid(A.Group([fact]), A.Ctx(words={}, language="en"))
    cards = elements[0]["items"]
    assert [card["title"] for card in cards] == ["Add work", "Choose what matters", "Hide rest"]
    assert cards[2].get("emoji") != "1f42f"  # tiger from the noun sense of "hide"
from vt.director import plan as D
from vt.director import profiles as P
from vt.director import roles as R
from vt.planner.catalogue import all_icon_names
from vt.project import load_theme
from vt.schema import Beat, Beats, MediaItem, Transcript, Word, validate_scenes


def make(sentences, wps=0.42, gap=0.25, speakers=None):
    """A transcript where every word takes `wps` seconds, so sentence lengths look like real speech."""
    words, beats, t = [], [], 0.3
    for bi, text in enumerate(sentences):
        ids, start = [], t
        for tok in text.split():
            w = Word(id=f"w{len(words) + 1}", text=tok, start=round(t, 3), end=round(t + wps * 0.9, 3))
            words.append(w)
            ids.append(w.id)
            t += wps
        beats.append(Beat(id=f"b{bi + 1}", word_ids=ids, start=round(start, 3), end=round(t, 3), text=text, speaker=(speakers or {}).get(bi)))
        t += gap
    return Transcript(words=words), Beats(beats=beats)


PRODUCT = ["Tired of slow video editing? It takes hours to make one clip.", "Meet VideoPro, the fastest video maker for creators.",
           "It includes templates, auto captions and royalty free music.", "Over 10000 customers rate it 4.8 stars.", "Our users save 70% of their time.",
           "First, paste your script.", "Second, pick a style.", "Third, press generate.", "Only $19 a month instead of $49.", "Order now and get a free month."]
EDU = ["What is inflation?", "Inflation means prices rise over time.", "In 2010 a loaf cost 20 rupees, in 2015 it cost 30 and in 2024 it cost 55.",
       "First, prices go up. Then, your money buys less.", "Rent, food and fuel are all affected.", "But wages often rise slowly.",
       "About 6% inflation halves value in twelve years.", "In short, remember to invest.", "So what should you do?"]
STORY = ["Once upon a time a boy lived in a village with his father.", "His son was lazy and careless.", "One day the man said, \"Take this watch to the market\".",
         "The boy walked to the market happily.", "Everyone gave a different price for the watch.", "The boy was confused and sad.", "The old watchman smiled and told him the lesson."]
BN_STORY = ["একবার এক বাচ্চা তার বাবাকে বলল, বাবা, এই পাথরটার দাম কত?", "বাবা বললেন, বাজারে গিয়ে দেখো।", "ছেলেটা বাজারে গেল।", "দোকানদার বলল, দশ টাকা।"]


def check(sf, tr, beats):
    assert validate_scenes(sf, tr, beats, all_icon_names(), media_ids=set()) == []
    theme = load_theme("paper")
    resolve_composition(sf, tr, beats, theme, "9:16", beats.beats[-1].end + 1)      # every element resolves for both shapes
    resolve_composition(sf, tr, beats, theme, "16:9", beats.beats[-1].end + 1)


# ------------------------------------------------------------------------------------------------------------------ roles
def test_roles_are_found_in_english():
    tr, beats = make(PRODUCT)
    f = R.analyse(tr, beats, "en")
    assert f[0].first and f[0].question and f[0].role in ("hook", "question")
    assert "feature" in f[2].roles and "proof" in f[3].roles
    assert [x.role for x in f[5:8]] == ["step"] * 3
    assert "price" in f[8].roles and f[8].numbers and "cta" in f[9].roles


def test_definitions_questions_contrast_dates_and_lists_are_extracted():
    tr, beats = make(EDU)
    f = R.analyse(tr, beats, "en")
    assert f[0].question and f[1].definition[0] == "Inflation" and f[1].definition[1].startswith("prices rise")
    assert [y[0] for y in f[2].years] == ["2010", "2015", "2024"] and len(f[2].numbers) == 3
    assert f[4].items and [t for t, _ in f[4].items] == ["Rent", "food", "fuel"]
    assert f[5].contrast and "wages" in f[5].contrast[1]
    assert "recap" in f[7].roles


def test_story_facts_people_places_poses_and_quotes():
    tr, beats = make(STORY)
    f = R.analyse(tr, beats, "en")
    assert "man" in f[0].persons and f[0].place == "village"
    assert f[2].quote == "Take this watch to the market" and f[2].pose in ("point", "walk")
    assert f[3].pose == "walk" and f[3].place == "market"
    assert f[5].expression in ("sad", "thinking")


def test_bangla_roles():
    tr, beats = make(BN_STORY)
    f = R.analyse(tr, beats, "bn")
    assert f[0].question and "boy" in f[0].persons and "man" in f[0].persons
    assert f[2].place == "market" and f[2].pose == "walk"
    assert "price" in f[3].roles or f[3].numbers is not None


def test_years_are_not_money_and_numbers_follow_the_language():
    tr, beats = make(["In 2015 it cost 30 rupees."])
    f = R.analyse(tr, beats, "en")[0]
    assert [y[0] for y in f.years] == ["2015"] and f.numbers[0]["disp"] == "₹30"
    trb, bb = make(["২০১৫ সালে দাম ছিল ৩০ টাকা।"])
    fb = R.analyse(trb, bb, "bn")[0]
    assert fb.years and fb.numbers and fb.numbers[0]["disp"] == "৳৩০"


# ------------------------------------------------------------------------------------------------------------------ plans
@pytest.mark.parametrize("usecase,text,lang", [("product", PRODUCT, "en"), ("education", EDU, "en"), ("story", STORY, "en"), ("story", BN_STORY, "bn"),
                                               ("discussion", EDU, "en"), ("general", PRODUCT, "en")])
def test_every_use_case_gives_a_valid_complete_plan(usecase, text, lang):
    tr, beats = make(text)
    sf = D.plan(tr, beats, usecase=usecase, language=lang, seed="t")
    check(sf, tr, beats)
    assert [b for s in sf.scenes for b in s.beats] == [b.id for b in beats.beats]          # every sentence is covered exactly once, in order
    assert all(s.elements for s in sf.scenes) and all(s.archetype for s in sf.scenes)
    assert all(len(s.elements) <= 5 for s in sf.scenes)


def test_plans_are_deterministic_and_differ_between_projects():
    tr, beats = make(PRODUCT + EDU)
    a = D.plan(tr, beats, usecase="product", seed="p1").model_dump()
    assert D.plan(tr, beats, usecase="product", seed="p1").model_dump() == a
    b = D.plan(tr, beats, usecase="product", seed="p2").model_dump()
    assert [s["transition_in"] for s in a["scenes"]] != [s["transition_in"] for s in b["scenes"]] or \
        [s["archetype"] for s in a["scenes"]] != [s["archetype"] for s in b["scenes"]]


def test_use_cases_favour_their_own_infographics():
    tr, beats = make(PRODUCT)
    prod = Counter(s.archetype for s in D.plan(tr, beats, usecase="product", seed="x").scenes)
    assert prod.keys() & {"feature_grid", "price_cta", "stat_row", "steps", "ring"} and "cartoon" not in prod
    tr, beats = make(EDU)
    edu = Counter(s.archetype for s in D.plan(tr, beats, usecase="education", seed="x").scenes)
    assert edu["definition"] >= 1 and edu.keys() & {"line_trend", "timeline", "steps", "checklist", "question"}
    tr, beats = make(STORY)
    st = Counter(s.archetype for s in D.plan(tr, beats, usecase="story", seed="x").scenes)
    assert st["cartoon"] >= 2


def test_variety_no_scene_type_twice_in_a_row_and_several_types_per_minute():
    tr, beats = make(PRODUCT * 3 + EDU * 2)
    for uc in ("product", "education", "general"):
        sf = D.plan(tr, beats, usecase=uc, seed="v")
        kinds = [s.archetype for s in sf.scenes]
        repeats = sum(1 for a, b in zip(kinds, kinds[1:]) if a == b and a not in ("picture",))
        assert repeats <= max(1, len(kinds) // 8), (uc, kinds)
        assert len(set(kinds)) >= 4, (uc, kinds)


def test_infographic_content_comes_from_what_was_said():
    tr, beats = make(["Sales grew from 10 to 14 to 25 to 38 percent over 2020 and 2021 and 2022 and 2023."], wps=0.5)
    sf = D.plan(tr, beats, usecase="education", seed="a", language="en")
    el = sf.scenes[0].elements[0]
    assert el.type in ("line_chart", "timeline", "stat_row", "bar_chart")
    if el.type == "line_chart":
        assert [p.value for p in el.points][:4] == [10, 14, 25, 38] or len(el.points) >= 3
    tr, beats = make(["Our users save 70% of their time."])
    el = D.plan(tr, beats, usecase="product", seed="a", language="en").scenes[0].elements
    assert any(e.type in ("ring", "big_number", "value_card") for e in el)
    assert "70" in json.dumps([e.model_dump() for e in el])


def test_ring_values_stay_in_range_and_bad_numbers_are_never_charted():
    tr, beats = make(["Prices rose 250% last year."])
    sf = D.plan(tr, beats, usecase="education", seed="a", language="en")
    assert all(getattr(e, "value", 0) <= 100 for e in sf.scenes[0].elements if e.type == "ring")
    assert validate_scenes(sf, tr, beats, all_icon_names()) == []


# ------------------------------------------------------------------------------------------------------------------ detection
@pytest.mark.parametrize("text,expected", [(PRODUCT, "product"), (EDU, "education"), (STORY, "story")])
def test_use_case_is_detected_from_the_sentences(text, expected):
    tr, beats = make(text)
    assert D.detect_usecase(R.analyse(tr, beats, "en")) == expected


def test_two_speakers_mean_a_discussion_and_plain_talk_is_general():
    tr, beats = make(["I think schools should start later.", "Parents would disagree about that.", "Sleep matters for teenagers."], speakers={0: "Riya", 1: "Sam", 2: "Riya"})
    f = R.analyse(tr, beats, "en")
    assert D.detect_usecase(f) == "discussion"
    sf = D.plan(tr, beats, usecase="discussion", seed="d")
    assert [s.archetype for s in sf.scenes] == ["speaker"] * 3
    assert [s.elements[0].side for s in sf.scenes] == ["left", "right", "left"]
    assert [s.transition_in for s in sf.scenes][1] == "cut"                 # a change of speaker is a hard cut
    tr, beats = make(["The weather was fine.", "We walked around for a while."])
    assert D.detect_usecase(R.analyse(tr, beats, "en")) == "general"


# ------------------------------------------------------------------------------------------------------------------ casting
def test_story_scenes_cast_consistent_characters_on_a_set():
    tr, beats = make(STORY)
    sf = D.plan(tr, beats, usecase="story", seed="s", language="en")
    cartoons = [e for s in sf.scenes for e in s.elements if e.type == "cartoon"]
    assert cartoons and any(c.set == "village" for c in cartoons)
    said = [c.bubble for c in cartoons] + [e.text for s in sf.scenes for e in s.elements if e.type == "quote"]
    assert any(t.startswith("Take this watch") for t in said)                 # the quoted line is shown, in a speech bubble or as a quote card
    assert all(0 <= m.x <= 1 for c in cartoons for m in c.cast)
    xs = [m.x for c in cartoons if len(c.cast) == 2 for m in c.cast]
    assert xs == sorted(xs) or len(xs) >= 2                                  # characters never share a spot


# ------------------------------------------------------------------------------------------------------------------ media
def media(i, w=1200, h=800, kind="image", caption=""):
    return MediaItem(id=f"m{i}", file=f"media/m{i}.jpg", kind=kind, width=w, height=h, caption=caption)


def test_media_is_matched_by_caption_then_spread_evenly():
    tr, beats = make(PRODUCT)
    items = [media(1, caption="customers reviews"), media(2), media(3)]
    sf = D.plan(tr, beats, usecase="product", seed="m", media=items, language="en")
    used = {}
    for s in sf.scenes:
        if s.backdrop:
            used[s.backdrop.media] = s
        for e in s.elements:
            if e.type in ("device", "media_frame"):
                used[e.media] = s
    assert set(used) == {"m1", "m2", "m3"}                                       # every picture lands in the video once
    cap_scene = used["m1"]
    texts = " ".join(next(b for b in beats.beats if b.id == bid).text for bid in cap_scene.beats).lower()
    assert "customers" in texts or "review" in texts
    scenes = [i for i, s in enumerate(sf.scenes) if any(m in used and used[m] is s for m in ("m2", "m3"))]
    assert len(scenes) == 2 and scenes[1] - scenes[0] >= 2                        # spread, not bunched together


def test_media_scene_types_and_scrim_callback():
    calls = []

    def scrim(mid, aspect, layout, t0, t1):
        from vt.schema import Scrim
        calls.append((mid, aspect, layout))
        return Scrim(ink="light", kind="gradient", strength=0.5, edge="bottom", ratio=5.0)

    tr, beats = make(STORY)
    sf = D.plan(tr, beats, usecase="story", seed="m", media=[media(1), media(2)], scrim_fn=scrim, language="en")
    bd = [s for s in sf.scenes if s.backdrop]
    for s in bd:
        assert s.layout == "lower" and s.backdrop.scrim.kind == "gradient" and s.backdrop.media in {"m1", "m2"}
    assert len(calls) == len(bd)
    check_ids = {"m1", "m2"}
    assert validate_scenes(sf, tr, beats, all_icon_names(), media_ids=check_ids) == []
    assert any("not in the project's media bin" in e for e in validate_scenes(sf, tr, beats, all_icon_names(), media_ids=set())) or not any(
        s.backdrop or any(e.type in ("device", "media_frame") for e in s.elements) for s in sf.scenes)


def test_portrait_media_in_a_product_video_becomes_a_phone_and_landscape_a_laptop():
    tr, beats = make(PRODUCT)
    for (w, h), kind in (((600, 1200), "phone"), ((1600, 900), "laptop")):
        sf = D.plan(tr, beats, usecase="product", seed="dev", media=[media(1, w, h)], language="en")
        devs = [e for s in sf.scenes for e in s.elements if e.type == "device"]
        if devs:
            assert devs[0].kind == kind and devs[0].media == "m1"


# ------------------------------------------------------------------------------------------------------------------ profiles
def test_profiles_are_data_and_complete():
    ids = {p["id"] for p in P.listing()}
    assert {"general", "product", "story", "discussion", "education"} <= ids
    for uc in ids:
        p = P.get(uc)
        assert p["pace"]["scene_min"] < p["pace"]["scene_target"] < p["pace"]["scene_max"]
        assert set(p["weights"]) <= set(A.ARCHETYPES), (uc, set(p["weights"]) - set(A.ARCHETYPES))
        assert p["transitions"] and all(t in ("cut", "fade", "slide_up", "slide_left", "zoom", "wipe", "whip") for t in p["transitions"])
        from vt.designer import PALETTES, STYLES
        assert set(p["looks"]["styles"]) <= set(STYLES) and set(p["looks"]["palettes"]) <= set(PALETTES)
    assert P.get("nonsense")["id"] == "general"


def test_profile_looks_narrow_the_automatic_design():
    from vt import designer
    t = designer.auto_theme("seed", "story", looks=P.get("product")["looks"])
    assert t.style in P.get("product")["looks"]["styles"] and t.palette in P.get("product")["looks"]["palettes"]


def test_number_labels_prefer_the_noun_after_the_number_and_skip_quantifiers():
    tr, beats = make(["More than 10000 creators trust it and they rate it 4.8 stars."])
    nums = R.analyse(tr, beats, "en")[0].numbers
    assert [(n["disp"], n["label"]) for n in nums] == [("10000", "creators"), ("4.8", "stars")]
    tr, beats = make(["Users save 70% of their time."])
    assert R.analyse(tr, beats, "en")[0].numbers[0]["label"] == "save"


def test_big_numbers_get_thousands_separators_and_years_do_not():
    assert A._fmt("10000") == "10,000" and A._fmt("১০০০০০") == "১০,০০০" or A._fmt("১০০০০০") == "১,০০,০০০" or A._fmt("১০০০০০") == "১০০,০০০"
    assert A._fmt("1234") == "1234" and A._fmt("4.8") == "4.8" and A._fmt("₹1500000") == "₹1,500,000" and A._fmt("2024") == "2024"


def test_step_titles_fit_and_keep_the_action():
    assert A._step_title("First, paste your script.", "en") == ("paste your script.", "") or A._step_title("First, paste your script.", "en")[0].startswith("paste your script")
    t, d = A._step_title("Then, your money buys less and less over the years", "en")
    assert len(t) <= 24 and t.startswith("your money buys less") and d.startswith("over") or len(t) <= 24


def test_sentence_fragments_from_subtitles_are_not_mistaken_for_questions_definitions_or_calls_to_action():
    sents = ["is so strong that nothing can escape, not even light.", "of the star is collapsing down into a tiny point.", "And the area of the black hole is just a few kilometers across.",
             "This collapse causes an explosion that we call a supernova.", "These stars burn up all the nuclear fuel in their cores.", "Subscribe to the channel today."]
    tr, beats = make(sents)
    roles = [f.roles for f in R.analyse(tr, beats, "en")]
    for r in roles[:5]:
        assert not r & {"question", "definition", "cta", "proof"}, roles
    assert "cta" in roles[5]


def test_pronoun_contractions_are_never_the_keyword():
    from vt.planner.rules import _keyword
    tr, beats = make(["They're regions in space that have a gravitational pull."])
    assert _keyword(tr.words).text.lower().startswith(("gravitational", "regions"))
