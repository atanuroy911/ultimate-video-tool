"""The stick-figure vocabulary of Phase 13: new verbs, places, looks, emoji actors, marks, time of day and weather are valid script words, compile into the scene, and are checked."""
import pytest

from vt.script import catalogue as C
from vt.script import compile_script, validate_script
from vt.script.examples import make
from vt.script.models import VideoScript

TEXT = ["Rafi found a lost wallet on the street and the owner thanked him warmly"]


def script(actions=None, cast=None, sets=None, camera=None):
    tr, beats = make(TEXT)
    ids = beats.beats[0].word_ids
    acts = []
    for k, a in enumerate(actions or []):
        acts.append({"at_word": ids[min(k, len(ids) - 1)], **a})
    return {"version": "1.0", "kind": "stick", "meta": {"language": "en", "aspect": "9:16"},
            "cast": cast or [{"id": "rafi", "role": "friend", "name": "Rafi"}, {"id": "owner", "role": "elder", "name": "Owner"}],
            "sets": sets or [{"id": "st", "kind": "street", "props": ["wallet"]}],
            "scenes": [{"id": "s1", "beats": [beats.beats[0].id], "set": "st", "camera": camera or {"shot": "medium", "move": "none"}, "actions": acts, "overlays": []}]}, tr, beats


def errs(*a, **k):
    d, tr, beats = script(*a, **k)
    return validate_script(d, tr, beats)


def test_the_catalogue_grew_and_every_verb_is_described():
    assert len(C.VERBS) >= 55 and len(C.SETS) >= 22 and len(C.ACCESSORIES) >= 16 and len(C.MARKS) == 8
    for v, (what, secs, req) in C.VERBS.items():
        assert what and 0.3 <= secs <= 3.0 and isinstance(req, tuple)
    for k, props in C.SETS.items():
        assert 1 <= len(props) <= 6 and len(set(props)) == len(props), k


def test_every_new_verb_validates_with_its_required_parts():
    new = {"clap": {}, "bow": {}, "laugh": {}, "cry": {}, "yawn": {}, "dance": {}, "phone": {}, "type": {}, "eat": {}, "lift": {"prop": "wallet"}, "throw": {"prop": "wallet", "target": "owner"},
           "give": {"prop": "wallet", "target": "owner"}, "chase": {"to": 0.8}, "follow": {"to": 0.3}, "sneak": {"to": 0.6}, "hide": {"target": "wallet"}, "peek": {}, "hug": {"target": "owner"},
           "argue": {}, "wave_both": {}, "mark": {"mark": "idea"}, "bounce": {}, "spin": {}, "grow": {}, "appear": {}, "fly": {"to": 0.7}}
    assert set(new) <= set(C.VERBS)
    for verb, extra in new.items():
        assert errs([{"who": "rafi", "do": verb, **extra}]) == [], verb
    assert any("needs `mark`" in e for e in errs([{"who": "rafi", "do": "mark"}]))                       # a sign must say which
    assert any("needs `prop`" in e for e in errs([{"who": "rafi", "do": "give", "target": "owner"}]))   # what is being given
    assert any("needs `to`" in e for e in errs([{"who": "rafi", "do": "chase"}]))


def test_synonyms_map_to_the_new_verbs_and_hug_is_its_own_verb():
    assert C.VERB_SYNONYMS["giggle"] == "laugh" and C.VERB_SYNONYMS["toss"] == "throw" and C.VERB_SYNONYMS["tiptoe"] == "sneak" and "hug" not in C.VERB_SYNONYMS
    assert all(v in C.VERBS for v in C.VERB_SYNONYMS.values())


def test_looks_a_child_with_a_bow_an_elder_with_a_beard_and_coloured_clothes():
    cast = [{"id": "kid", "role": "child", "name": "Kid", "style": {"height": "child", "hair": "bun", "accessory": "bow", "shirt": "#ef4444", "skin": "#f1c27d"}},
            {"id": "gran", "role": "elder", "name": "Gran", "style": {"height": "elder", "accessory": "beard", "hair": "curly", "color": "#374151"}}]
    assert errs([{"who": "kid", "do": "wave"}], cast=cast) == []
    bad = [{"id": "kid", "role": "child", "style": {"height": "giant"}}]
    assert errs([], cast=bad)                                                                         # unknown height is refused
    bad = [{"id": "kid", "role": "child", "style": {"shirt": "red"}}]
    assert errs([], cast=bad)                                                                         # a colour is a hex value


def test_an_emoji_actor_is_a_cast_member_and_needs_a_sticker_or_a_name():
    cast = [{"id": "fox", "role": "animal", "name": "Fox", "kind": "emoji", "emoji": "1f98a"}, {"id": "rafi", "role": "friend", "name": "Rafi"}]
    assert errs([{"who": "fox", "do": "bounce"}, {"who": "fox", "do": "fly", "to": 0.8}, {"who": "fox", "do": "mark", "mark": "heart"}], cast=cast) == []
    nameless = [{"id": "x", "role": "object", "kind": "emoji"}]
    assert any("emoji actor needs" in e for e in errs([], cast=nameless))


def test_places_time_of_day_and_weather_reach_the_scene():
    sets = [{"id": "st", "kind": "kitchen", "props": ["wallet"], "time": "night", "weather": "rain"}]
    d, tr, beats = script([{"who": "rafi", "do": "eat"}], sets=sets)
    assert validate_script(d, tr, beats) == []
    sf = compile_script(VideoScript.model_validate(d), tr, beats)
    st = sf.scenes[0].stick["set"]
    assert st["kind"] == "kitchen" and st["time"] == "night" and st["weather"] == "rain" and {"stove", "fridge", "plate", "wallet"} <= set(st["props"])
    assert errs([], sets=[{"id": "st", "kind": "kitchen", "time": "noon"}])
    assert errs([], sets=[{"id": "st", "kind": "kitchen", "weather": "fog"}])


def test_every_set_kind_is_valid_in_a_script_and_offers_its_props_as_targets():
    for kind, props in C.SETS.items():
        sets = [{"id": "st", "kind": kind, "props": []}]
        assert errs([{"who": "rafi", "do": "point", "target": props[0]}], sets=sets) == [], kind


def test_zoom_to_needs_a_focus_that_exists():
    assert any("needs `focus`" in e for e in errs([], camera={"shot": "close", "move": "zoom_to"}))
    assert any("camera focus 'moon'" in e for e in errs([], camera={"shot": "close", "move": "zoom_to", "focus": "moon"}))
    assert errs([], camera={"shot": "close", "move": "zoom_to", "focus": "wallet"}) == []
    assert errs([], camera={"shot": "close", "move": "zoom_to", "focus": "owner"}) == []


def test_marks_are_the_catalogued_ones_only():
    assert errs([{"who": "rafi", "do": "mark", "mark": "heart"}]) == []
    assert errs([{"who": "rafi", "do": "mark", "mark": "skull"}])
