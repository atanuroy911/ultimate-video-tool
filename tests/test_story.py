"""The rule director (vt/script/story.py): a story from the words. Every case reads the storyboard it makes, not just that it is valid."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "script_eval"))
from transcripts import SETS  # noqa: E402

from vt.planner import plan_rules  # noqa: E402
from vt.script import compile_script, examples as EX  # noqa: E402
from vt.script import story as S  # noqa: E402
from vt.script.rules_stick import rules_script  # noqa: E402
from vt.script.validate import validate_script  # noqa: E402


def make(texts, lang="en"):
    tr, beats = EX.make(texts)
    sf = plan_rules(tr, beats, "paper", language=lang)
    return tr, beats, sf


def direct(texts, lang="en"):
    tr, beats, sf = make(texts, lang)
    s = S.story_script(tr, beats, sf, kind="stick", language=lang)
    return s, tr, beats


def acts(s):
    return [(a.who, a.do, a.target or a.prop or a.bubble or a.mark or "") for sc in s.scenes for a in sc.actions]


def test_a_story_gets_its_people_a_look_each_and_the_right_person_does_things():
    s, tr, beats = direct(SETS["story-wallet"])
    ids = {c.id: c for c in s.cast}
    assert "rafi" in ids and any(c.style.height == "elder" for c in s.cast)                  # the named boy, and "the owner" as an old man
    assert len({c.style.shirt for c in s.cast}) == len(s.cast)                                # different clothes
    a = acts(s)
    assert ("rafi", "lift", "wallet") in a                                                    # found a lost WALLET (not "lost")
    assert ("rafi", "think", "") in a                                                         # "He wondered": he is Rafi, the one the story is about
    assert any(w == "owner" and d in ("bow", "react") for w, d, _ in a)
    assert validate_script(s.model_dump(by_alias=True), tr, beats) == []


def test_pronouns_follow_the_person_the_story_is_about():
    s, tr, beats = direct(["Maya found a coin", "She laughed a lot", "Then Ben came and he waved"])
    a = acts(s)
    assert ("maya", "laugh", "") in a and ("ben", "wave", "") in a


def test_the_learner_asks_the_question_out_loud_and_the_host_wonders():
    s, tr, beats = direct(["Saving money is a habit", "Is that a lot of money?", "It is enough to start a small business", "So start today"])
    ids = [c.id for c in s.cast]
    assert "host" in ids and "sam" in ids
    a = acts(s)
    assert any(w == "sam" and d == "say" and "lot of money" in b for w, d, b in a)           # the question is in Sam's speech bubble
    assert any(w == "host" and d == "think" for w, d, _ in a)
    first_sam = next(i for i, (w, d, _) in enumerate(a) if w == "sam")
    assert a[first_sam][1] in ("walk_in", "say")                                              # and Sam came onto the stage to ask it


def test_a_discussion_puts_each_opinion_in_the_speakers_mouth():
    s, tr, beats = direct(SETS["discussion-remote"])
    bubbles = {(w, b) for w, d, b in acts(s) if d == "say"}
    assert ("riya", "remote work saves time") in bubbles and any(w == "sam" and "office" in b for w, b in bubbles)


def test_animals_are_actors_and_a_fable_has_no_teacher():
    s, tr, beats = direct(SETS["story-fox"])
    assert [c.kind for c in s.cast] == ["emoji"] and s.cast[0].name == "Fox"
    assert not any(c.id in ("host", "sam") for c in s.cast)
    assert {d for _, d, _ in acts(s)} <= S.ACTOR_VERBS | {"appear", "bounce"}                # only things an actor can do
    assert "grape" in s.sets[0].props                                                         # the grapes are in the picture


def test_place_time_of_day_and_weather_come_from_the_words():
    s, tr, beats = direct(["It was a stormy night and Mia could not sleep", "She went to the kitchen and cooked a meal", "Then she ate it happily"])
    kinds = [x.kind for x in s.sets]
    assert any(x.time == "night" and x.weather == "rain" for x in s.sets)
    assert "kitchen" in kinds
    assert all(sc.set in {x.id for x in s.sets} for sc in s.scenes)


def test_nobody_stands_around_no_long_gap_and_not_only_talking():
    for name, texts in SETS.items():
        lang = "bn" if name.startswith("bn") else "en"
        s, tr, beats = direct(texts, lang)
        assert validate_script(s.model_dump(by_alias=True), tr, beats) == [], name
        words = tr.by_id()
        pts = sorted([beats.beats[0].start, beats.beats[-1].end] + [words[a.at_word].start for sc in s.scenes for a in sc.actions] + [words[o["at_word"]].start for sc in s.scenes for o in sc.overlays]
                     + [b.start for sc in s.scenes for b in beats.beats if b.id == sc.beats[0]])
        gap = max(y - x for x, y in zip(pts, pts[1:]))
        assert gap <= 2.6, (name, gap)
        verbs = [a.do for sc in s.scenes for a in sc.actions]
        talk = sum(1 for v in verbs if v in ("say", "explain", "idle")) / max(1, len(verbs))
        assert talk <= 0.6, (name, talk)
        assert len({a.do for sc in s.scenes for a in sc.actions}) >= 3, name
        assert len(s.cast) >= 1 and len(s.sets) >= 1


def test_every_scene_with_people_on_stage_has_an_action_for_each_of_them():
    s, tr, beats = direct(SETS["story-wallet"])
    for sc in s.scenes[1:]:
        who = {a.who for a in sc.actions}
        assert who, sc.id                                                                     # the engine draws only those with an action in the scene


def test_the_same_text_always_gives_the_same_story():
    a, tr, beats = direct(SETS["story-wallet"])
    b, _, _ = direct(SETS["story-wallet"])
    assert a.model_dump_json() == b.model_dump_json()


def test_it_compiles_into_scenes_with_props_places_and_marks():
    s, tr, beats = direct(SETS["story-wallet"])
    sf = compile_script(s, tr, beats)
    st = sf.scenes[0].stick
    assert st and st["set"]["kind"] == "street" and "wallet" in st["set"]["props"] and st["cast"] and st["actions"]


def test_stick_mode_uses_it_and_falls_back_to_the_plain_director_if_it_ever_fails(monkeypatch):
    tr, beats, sf = make(SETS["story-wallet"])
    assert len(rules_script(tr, beats, sf, kind="stick").cast) >= 2                           # the story director
    monkeypatch.setattr(S, "story_script", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    plain = rules_script(tr, beats, sf, kind="stick")
    assert [c.id for c in plain.cast] == ["maya"]                                              # a video is never lost to the director
    assert validate_script(plain.model_dump(by_alias=True), tr, beats) == []


def test_the_look_of_a_character_is_valid_for_the_engine():
    s, tr, beats = direct(["The old king and the thief and a little girl met", "The doctor and the farmer came too", "They all danced"])
    assert len(s.cast) >= 3
    for c in s.cast:
        assert c.role in S.C.ROLES
    assert validate_script(s.model_dump(by_alias=True), tr, beats) == []
