import json

import pytest

from vt import designer, llm
from vt.planner import plan_rules
from vt.planner import llm_plan
from vt.planner.catalogue import all_icon_names
from vt.planner.rules import detect_currency, localize_digits
from vt.schema import Beat, Beats, Transcript, Word, validate_scenes
from vt.visuals import emoji as emo
from vt.visuals.lexicon import Lexicon

pytestmark = pytest.mark.skipif(not Lexicon.get().ok, reason="visual lexicon not built")


def story(text_beats, t=0.3):
    words, beats = [], []
    for bi, text in enumerate(text_beats):
        ids = []
        for tok in text.split():
            w = Word(id=f"w{len(words) + 1}", text=tok, start=t, end=t + 0.3)
            words.append(w)
            ids.append(w.id)
            t += 0.35
        beats.append(Beat(id=f"b{bi + 1}", word_ids=ids, start=words[len(words) - len(ids)].start, end=t, text=text))
    return Transcript(words=words), Beats(beats=beats)


def test_english_numbers_use_latin_digits_and_the_spoken_currency():
    tr, beats = story(["One man said it was worth 500 rupees.", "Another said 1000 dollars."])
    sf = plan_rules(tr, beats, "paper", language="en")
    cards = [e for s in sf.scenes for e in s.elements if e.type == "value_card"]
    assert cards and cards[0].value == "₹500" and not any(ch in cards[0].value for ch in "০১২৩৪৫৬৭৮৯৳")
    assert localize_digits("১০০", "en") == "100" and localize_digits("100", "bn") == "১০০"
    assert detect_currency(tr, "en") == "₹" and detect_currency(Transcript(words=[Word(id="w1", text="hi", start=0, end=1)]), "en") == "$"
    bn = plan_rules(*story(["দাম একশো টাকা"]), "paper", language="bn")
    assert any(getattr(e, "value", "").startswith("৳") for s in bn.scenes for e in s.elements)


def test_one_sentence_with_several_ideas_gets_several_pictures():
    tr, beats = story(["His son was lazy and careless and sleepy"])
    sf = plan_rules(tr, beats, "paper", language="en")
    assert len(sf.scenes[0].elements) >= 2


class FakeModel:
    """Stands in for the language model: always picks the first real option of the first two words of every sentence."""
    def __init__(self, garbage=False):
        self.calls, self.garbage = 0, garbage

    def __call__(self, messages, schema, **kw):
        self.calls += 1
        user = messages[-1]["content"]
        if "BRIEF" in schema.get("properties", {}) or "topic" in schema.get("properties", {}):
            return {"topic": "t", "summary": "A boy and a watch.", "mood": "story", "characters": ["boy"], "place": "village"}
        if self.garbage:
            return {"sentences": [{"beat": b, "pictures": [{"word_id": schema["properties"]["sentences"]["items"]["properties"]["pictures"]["items"]["properties"]["word_id"]["enum"][0], "choice": "text"}]}
                                  for b in schema["properties"]["sentences"]["items"]["properties"]["beat"]["enum"]]}
        out = {}
        for line in user.splitlines():
            line = line.strip()
            if line.startswith("[b") and "->" in line:
                beat = line[1:line.index("]")]
                wid = line.split("] ")[1].split(":")[0]
                first = line.split("->")[1].split(",")[0].strip().split("=")[0]
                out.setdefault(beat, []).append({"word_id": wid, "choice": first})
        return {"sentences": [{"beat": b, "pictures": out.get(b, [])[:2]} for b in schema["properties"]["sentences"]["items"]["properties"]["beat"]["enum"]]}


def test_llm_planner_only_uses_real_options_and_stays_valid(monkeypatch):
    tr, beats = story(["The boy opened the cupboard", "He took the watch to the market", "The father smiled gently"])
    monkeypatch.setattr(llm, "chat_json", FakeModel())
    sf = llm_plan.plan_llm(tr, beats, "paper", "en", None)
    assert validate_scenes(sf, tr, beats, all_icon_names()) == []
    assert sf.planner == "llm"
    for s in sf.scenes:
        for e in s.elements:
            if e.type == "sticker":
                assert emo.emoji_key(e.emoji)                                 # never invented, never a blocked emoji


def test_a_misbehaving_model_cannot_break_the_plan(monkeypatch):
    tr, beats = story(["The boy opened the cupboard", "He took the watch to the market"])
    monkeypatch.setattr(llm, "chat_json", FakeModel(garbage=True))
    sf = llm_plan.plan_llm(tr, beats, "paper", "en", None)
    assert validate_scenes(sf, tr, beats, all_icon_names()) == []


def test_model_going_away_raises_so_the_pipeline_can_fall_back(monkeypatch):
    tr, beats = story(["The boy opened the cupboard", "He took the watch", "The father smiled", "Then they left", "The market was far", "It rained"] * 2)
    def boom(*a, **k):
        if "topic" in a[1].get("properties", {}):
            return {"topic": "t", "summary": "s", "mood": "story"}
        raise llm.LLMUnavailable("down")
    monkeypatch.setattr(llm, "chat_json", boom)
    with pytest.raises(llm.LLMUnavailable):
        llm_plan.plan_llm(tr, beats, "paper", "en", None)


def test_installed_model_choice_prefers_general_text_models():
    pick = llm.choose_installed
    assert pick(["qwen2.5vl:7b", "moondream:latest", "llama3:8b", "gemma4:latest", "qwen2.5-coder:7b", "nomic-embed-text:latest"]) == "gemma4:latest"
    assert pick(["qwen2.5vl:7b", "nomic-embed-text:latest", "qwen2.5-coder:14b"]) is None
    assert pick(["llama3:8b", "phi3:latest"]) == "llama3:8b"


def test_llm_off_or_unreachable_falls_back_to_rules(tmp_path, monkeypatch):
    from vt.pipeline import Pipeline
    from vt.project import Project
    import numpy as np, soundfile as sf_
    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "auto", "ollama_url": "http://127.0.0.1:9", "ollama_model": "", "llm_auto_download": False})
    monkeypatch.setattr(llm, "reachable", lambda *a, **k: False)
    with pytest.raises(llm.LLMUnavailable):
        llm.ensure_ready()
    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "off", "ollama_url": "", "ollama_model": "", "llm_auto_download": False})
    with pytest.raises(llm.LLMUnavailable):
        llm.ensure_ready()


def test_auto_design_matches_the_mood_and_is_stable():
    a = designer.auto_theme("video-1", "tech")
    assert a.style in designer.MOOD_LOOKS["tech"][0] and a.palette in designer.MOOD_LOOKS["tech"][1]
    assert designer.auto_theme("video-1", "tech").model_dump() == a.model_dump()
    assert len({designer.auto_theme(f"v{i}", "story").label for i in range(25)}) >= 8       # different videos look different
    assert designer.auto_theme("x", "unknown-mood").style in designer.STYLES
