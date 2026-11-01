import numpy as np
import pytest
import soundfile as sf

from vt.compose import resolve_composition
from vt.planner import plan_rules
from vt.planner.catalogue import all_icon_names
from vt.project import load_theme
from vt.schema import Beat, Beats, Scene, ScenesFile, Transcript, Word, validate_scenes
from vt.visuals import emoji as emo
from vt.visuals.emphasis import SR, emphasis_scores
from vt.visuals.lexicon import MIN_Z, Lexicon
from vt.visuals.picker import is_content, pick_visuals

lex = Lexicon.get()
pytestmark = pytest.mark.skipif(not lex.ok, reason="visual lexicon not built (python scripts/build_visual_lexicon.py)")


def test_seed_dictionary_and_bangla_stemming():
    m = lex.lookup("money")
    assert m.line == "lucide:banknote" and emo.label(m.sticker) == "dollar banknote" and m.source == "seed" and m.usable()
    assert lex.lookup("পাথরটা").sticker == "1faa8"                     # পাথর + টা -> stone -> rock emoji
    assert lex.lookup("বাবাকে").sticker == lex.lookup("father").sticker  # suffix stripped, Bangla word maps to the English concept
    assert lex.lookup("টাকার").usable() and lex.lookup("dogs").line.endswith("dog")   # plural handled


def test_dictionary_covers_the_english_language_and_rejects_nonsense():
    assert len(lex.words) > 140_000                                    # essentially all WordNet lemmas are mapped
    for w in ("volcano", "telescope", "guitar", "elephant"):
        assert lex.lookup(w).usable(), w
    assert lex.lookup("qzxv") is None and lex.lookup("") is None


def test_offensive_emoji_are_never_offered():
    assert emo.emoji_key("🖕") is None and emo.emoji_key("1f595") is None and emo.emoji_key("💩") is None
    assert emo.emoji_key("💰") == "1f4b0" and emo.emoji_key("1F4B0") == "1f4b0" and emo.emoji_key("not-an-emoji") is None
    used = {m.sticker for m in (lex.lookup(w) for w in lex.words if len(w) < 7) if m and m.sticker}
    assert not (used & emo.BLOCKED)                                    # the whole dictionary, not just spot checks
    assert lex.lookup("finger").sticker != "1f595"


def synth_speech(path, spec):
    """spec: [(start, end, freq_hz, amp)] sine 'words' on silence, so the stressed word is known."""
    x = np.zeros(int(SR * (spec[-1][1] + 0.3)), dtype=np.float32)
    for s, e, f, a in spec:
        t = np.arange(int((e - s) * SR)) / SR
        x[int(s * SR): int(s * SR) + len(t)] = a * np.sin(2 * np.pi * f * t) * np.hanning(len(t)) ** 0.3
    sf.write(str(path), x, SR)


def test_emphasis_finds_the_word_that_is_louder_higher_and_longer(tmp_path):
    spec = [(0.2 + 0.5 * i, 0.2 + 0.5 * i + 0.30, 140, 0.15) for i in range(9)]
    spec[4] = (2.2, 2.9, 220, 0.5)                                     # the stressed word: louder, higher, held longer
    wav = tmp_path / "a.wav"
    synth_speech(wav, spec)
    words = [Word(id=f"w{i}", text="শব্দ" if i != 4 else "গুরুত্বপূর্ণ", start=s, end=e) for i, (s, e, _, _) in enumerate(spec)]
    sc = emphasis_scores(wav, words)
    assert max(sc, key=sc.get) == "w4" and sc["w4"] > 0.8 and np.median(list(sc.values())) < 0.6
    assert set(emphasis_scores(None, words).values()) == {0.5}         # no audio: neutral, never an error


def make_story():
    texts = ["একবার", "একটা", "বাচ্চা", "তার", "বাবাকে", "পাথর", "দিচ্ছি", "তুমি", "বাজারে", "যাও"]
    words = [Word(id=f"w{i + 1}", text=t, start=0.3 + i * 0.4, end=0.65 + i * 0.4) for i, t in enumerate(texts)]
    beats = Beats(beats=[Beat(id="b1", word_ids=[w.id for w in words[:5]], start=0.3, end=2.65, text=" ".join(texts[:5])),
                         Beat(id="b2", word_ids=[w.id for w in words[5:]], start=2.3, end=4.25, text=" ".join(texts[5:]))])
    return Transcript(words=words), beats


def test_picker_skips_function_words_and_picks_a_picturable_word():
    tr, beats = make_story()
    assert not is_content(tr.words[1]) and not is_content(tr.words[3])      # একটা, তার are function words
    picks = pick_visuals(tr, beats, None, use_embedder=False)
    assert picks["b1"].text in ("বাচ্চা", "বাবাকে") and picks["b1"].kind == "sticker"
    assert picks["b2"].text in ("পাথর", "বাজারে") and picks["b2"].sticker


def test_rule_planner_shows_the_stressed_word_at_the_moment_it_is_spoken():
    tr, beats = make_story()
    picks = pick_visuals(tr, beats, None, use_embedder=False)
    sf_ = plan_rules(tr, beats, "paper", picks=picks)
    assert validate_scenes(sf_, tr, beats, all_icon_names()) == []
    sc = sf_.scenes[0]
    assert sc.elements and all(e.type in ("sticker", "keyword", "icon") for e in sc.elements)
    assert any(e.at_word == picks["b1"].word_id for e in sc.elements) and sc.caption.highlight_words == [picks["b1"].word_id]
    starts = [tr.by_id()[e.at_word].start for e in sc.elements]
    assert starts == sorted(starts)                                    # several pictures per sentence, in the order they are spoken
    assert [s.tone for s in sf_.scenes] == list(range(len(sf_.scenes)))[:len(sf_.scenes)]    # tones rotate


def test_every_scene_of_a_long_plan_has_a_visual():
    texts = ["একবার", "একটা", "বাচ্চা", "বাবা", "পাথর", "বাজার", "টাকা", "ছেলে", "মহিলা", "দাম"] * 8
    words = [Word(id=f"w{i + 1}", text=t, start=i * 0.5, end=i * 0.5 + 0.4) for i, t in enumerate(texts)]
    beats = Beats(beats=[Beat(id=f"b{k + 1}", word_ids=[w.id for w in words[k * 5:(k + 1) * 5]], start=words[k * 5].start, end=words[k * 5 + 4].end, text="x")
                         for k in range(16)])
    sf_ = plan_rules(Transcript(words=words), beats, "paper", picks=pick_visuals(Transcript(words=words), beats, None, use_embedder=False))
    assert len(sf_.scenes) >= 6 and all(s.elements for s in sf_.scenes)
    assert len({e.type for s in sf_.scenes for e in s.elements}) >= 2          # not one repeated component


def test_composer_inlines_stickers_icons_from_both_sets_and_tone():
    tr, beats = make_story()
    sf_ = ScenesFile.model_validate({"scenes": [
        {"id": "s1", "beats": ["b1"], "tone": 2, "elements": [
            {"type": "sticker", "emoji": "🪨", "label": "পাথর", "at_word": "w6"} if False else {"type": "sticker", "emoji": "1faa8", "label": "পাথর", "at_word": "w1"},
            {"type": "keyword", "text": "বাবা", "icon": "tabler:coin", "emoji": "👨", "at_word": "w2"},
            {"type": "icon", "name": "lucide:coins", "at_word": "w3"}]},
        {"id": "s2", "beats": ["b2"]}]})
    assert validate_scenes(sf_, tr, beats, all_icon_names()) == []
    d = resolve_composition(sf_, tr, beats, load_theme("paper"), "9:16", 6.0)
    assert d["stickers"]["1faa8"].startswith("<svg") and "1f468" in d["stickers"]
    assert d["icons"]["tabler:coin"] and d["icons"]["lucide:coins"]
    assert d["scenes"][0]["tone"] == 2 and d["scenes"][0]["elements"][1]["emoji"] == "1f468"   # emoji character normalised to its key


def test_validation_rejects_unknown_and_blocked_visuals_with_helpful_errors():
    tr, beats = make_story()
    sf_ = ScenesFile.model_validate({"scenes": [{"id": "s1", "beats": ["b1", "b2"], "elements": [
        {"type": "sticker", "emoji": "🖕", "at_word": "w1"}, {"type": "keyword", "text": "x", "icon": "tabler:not-real", "at_word": "w2"}]}]})
    errs = " | ".join(validate_scenes(sf_, tr, beats, all_icon_names()))
    assert "unknown emoji" in errs and "unknown icon 'tabler:not-real'" in errs and "search_icons" in errs
    with pytest.raises(Exception):
        Scene.model_validate({"id": "s", "beats": ["b1"], "tone": 9})


def test_bare_icon_names_are_described_not_crashed():
    from vt.visuals.search import _describe, svg_for

    d = _describe("circle-help")
    assert d["kind"] == "icon" and d["label"] == "circle help"
    assert svg_for("circle-help")["inner"]
