"""The four files nothing tested (docs/ROADMAP.md P10-14): the environment doctor, the icon registry, the word terms, and the Shorts prompts."""
import json

import jsonschema
import pytest

from vt import doctor
from vt.shorts import prompts
from vt.visuals import icons, terms


# ----------------------------------------------------------------------------- vt/doctor.py
def test_the_doctor_reports_every_check_with_a_fix_for_each_failure(monkeypatch):
    rows = doctor.run_checks()
    names = [r["name"] for r in rows]
    assert len(names) == len(set(names)) and {"Python 3.11", "FFmpeg", "Node 20+", "Voices (script to speech)", "Local AI (scene planner)"} <= set(names)
    for r in rows:
        assert set(r) == {"name", "ok", "detail", "fix"} and isinstance(r["ok"], bool)
        assert r["ok"] or r["fix"], f"{r['name']} fails without saying how to fix it"
        assert not r["ok"] or r["fix"] == ""


def test_a_check_that_raises_is_a_failed_row_not_a_crash(monkeypatch):
    def boom(name):
        raise FileNotFoundError("no such tool\nsecond line that must not appear")

    monkeypatch.setattr(doctor, "find_tool", boom)
    rows = {r["name"]: r for r in doctor.run_checks()}
    assert rows["FFmpeg"]["ok"] is False and rows["FFmpeg"]["detail"] == "no such tool" and rows["FFmpeg"]["fix"]
    assert rows["Python 3.11"]["ok"] in (True, False)                       # the others still ran


# ----------------------------------------------------------------------------- vt/visuals/icons.py
def test_icon_names_resolve_across_both_sets(tmp_path, monkeypatch):
    from vt import paths

    (tmp_path / "lucide.json").write_text(json.dumps({"coins": "<circle/>", "house": "<path d='h'/>"}), encoding="utf-8")
    (tmp_path / "tabler.json").write_text(json.dumps({"coin": "<g/>"}), encoding="utf-8")
    monkeypatch.setattr(paths, "ICONS", tmp_path)
    for f in (icons._lucide, icons._tabler, icons.all_names):
        f.cache_clear()
    try:
        assert icons.canonical("coins") == "lucide:coins" and icons.canonical("tabler:coin") == "tabler:coin"
        assert icons.all_names() == frozenset({"coins", "house", "lucide:coins", "lucide:house", "tabler:coin"})
        assert icons.inner("coins") == "<circle/>" and icons.inner("lucide:house") == "<path d='h'/>" and icons.inner("tabler:coin") == "<g/>"
        assert icons.inner("nonsense") is None and icons.inner("tabler:nonsense") is None
    finally:
        for f in (icons._lucide, icons._tabler, icons.all_names):
            f.cache_clear()


def test_the_real_icon_set_has_the_common_names():
    icons.all_names.cache_clear()
    names = icons.all_names()
    assert {"coins", "lucide:coins"} <= names and len(names) > 500


# ----------------------------------------------------------------------------- vt/visuals/terms.py
def test_words_are_normalised_for_lookup():
    assert terms.norm("  “Money,”  ") == "money" and terms.norm("It’s") == "it's" and terms.norm("(Bank).") == "bank"


def test_noun_share_separates_things_from_actions():
    assert terms.noun_share("house") > terms.noun_share("run")
    assert terms.noun_share("zzzzqq") == 0.5 and terms.noun_share("zzzzqq বাংলা".split()[1]) == 0.6              # unknown words: a guess, a little higher for Bangla
    assert terms.BN_RE.search("বাংলা") and not terms.BN_RE.search("bangla")


def test_ing_words_that_are_things_stay_nouns():
    assert "building" in terms.ING_NOUNS and "savings" in terms.ING_NOUNS
    s = terms.shares("savings")
    assert s is None or s[0] >= 0.3


def test_common_words_are_not_key_terms_and_concrete_topic_words_are():
    assert terms.zipf("the") > terms.zipf("mortgage") > 0
    assert terms.score("12") == 0.0 and terms.score("of") == 0.0 and terms.score("the") < 0.3           # a number or two letters: nothing; "the" is far too common to stand out
    assert not terms.is_key_term("thing") and not terms.is_key_term("the") and not terms.is_key_term("people")
    assert terms.is_key_term("mortgage") and terms.is_key_term("lighthouse")
    assert 0.0 <= terms.score("mortgage") <= 1.0


def test_the_topic_of_a_text_lifts_its_words():
    topics = terms.topic_counts(["mortgage", "mortgage", "mortgage", "bank", "bank", "weather"])
    assert topics["mortgage"] == 3 and topics["bank"] == 2
    assert terms.score("mortgage", topics) >= terms.score("mortgage")


def test_the_variants_of_a_word_are_tried_in_order():
    assert terms._variants("companies")[:2] == ["companies", "company"] and "walk" in terms._variants("walked") and terms._variants("is") == ["is"]


# ----------------------------------------------------------------------------- vt/shorts/prompts.py
def test_the_content_type_answer_has_a_schema_that_the_prompt_asks_for():
    jsonschema.validate({"content_type": "podcast", "density": "high"}, prompts.CONTENT_TYPE_SCHEMA)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"content_type": "podcast"}, prompts.CONTENT_TYPE_SCHEMA)
    assert "content_type" in prompts.CONTENT_TYPE_PROMPT and "JSON only" in prompts.CONTENT_TYPE_PROMPT


def test_the_highlight_prompt_fills_in_and_asks_for_the_fields_its_schema_requires():
    text = prompts.HIGHLIGHT_SYSTEM_PROMPT.format(virality_criteria=prompts.VIRALITY_CRITERIA, content_type="podcast", density="high", min_clips=5)
    assert "{" not in text.replace("{\"highlights\"", "").replace("}", "") or "highlights" in text
    required = prompts.HIGHLIGHTS_SCHEMA["properties"]["highlights"]["items"]["required"]
    for field in required:
        assert field in text, field                                         # the prompt names every field the schema demands
    assert "5 most viral" in text and "Never cut mid-sentence" in text and "HOOK" in text


def test_a_good_answer_validates_and_a_bad_one_does_not():
    good = {"highlights": [{"title": "Nobody tells you this", "start_time": 12.0, "end_time": 58.5, "score": 91, "hook_sentence": "Nobody tells you this.", "virality_reason": "A strong hook."}]}
    jsonschema.validate(good, prompts.HIGHLIGHTS_SCHEMA)
    for bad in ({"highlights": [{**good["highlights"][0], "score": 101}]}, {"highlights": [{k: v for k, v in good["highlights"][0].items() if k != "title"}]}, {"clips": []}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, prompts.HIGHLIGHTS_SCHEMA)
