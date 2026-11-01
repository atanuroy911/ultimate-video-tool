import re
import xml.dom.minidom

import pytest

from vt import art
from vt.art import concepts
from vt.schema import Beat, Beats, Transcript, Word
from vt.visuals import emoji as emo


@pytest.mark.parametrize("key", sorted(concepts.KEYS))
def test_every_drawing_is_valid_svg_in_the_emoji_frame(key):
    svg = art.svg(key)
    xml.dom.minidom.parseString(svg)                         # well-formed
    assert 'viewBox="0 0 128 128"' in svg and len(svg) < 16000
    assert emo.emoji_key(key) == key and emo.svg(key) == svg and art.label(key)
    assert not re.search(r"<script|href=|onload", svg, re.I)


def test_words_find_their_drawing_including_plurals_and_bangla():
    for word, key in {"galaxies": "art-galaxy", "Black holes": "art-black-hole", "black hole": "art-black-hole", "supernovae": "art-supernova",
                      "inflation": "art-inflation", "গ্যালাক্সি": "art-galaxy", "ডিএনএ": "art-dna", "solar system": "art-solar-system"}.items():
        assert art.lookup(word) == key, word
    assert art.lookup("table") is None and art.lookup("") is None
    assert all(v in concepts.KEYS for v in concepts.WORDS.values())


def test_unknown_art_keys_are_rejected_like_unknown_emoji():
    assert emo.emoji_key("art-does-not-exist") is None and emo.emoji_key("art-") is None


def _tr(sentence):
    ws = [Word(id=f"w{i + 1}", text=t, start=i * 0.4, end=i * 0.4 + 0.35) for i, t in enumerate(sentence.split())]
    return Transcript(words=ws), Beats(beats=[Beat(id="b1", word_ids=[w.id for w in ws], start=0, end=len(ws) * 0.4, text=sentence)])


def test_a_two_word_idea_is_drawn_once_and_its_colour_word_is_dropped():
    from vt.visuals.picker import pick_visuals
    tr, beats = _tr("Astronomers study the black hole at the centre of the galaxy.")
    p = pick_visuals(tr, beats, None, use_embedder=False)["b1"]
    assert p.sticker in ("art-black-hole", "art-galaxy")
    assert p.text.lower() != "black"
    all_ids = [p.sticker] + [e.get("sticker") for e in p.extras]
    assert "art-black-hole" in all_ids and "art-galaxy" in all_ids


def test_art_stickers_flow_into_the_composition(tmp_path):
    from vt.compose.composer import resolve_composition
    from vt.project import load_theme
    from vt.schema import ScenesFile, validate_scenes
    tr, beats = _tr("Astronomers study the black hole.")
    sf = ScenesFile.model_validate({"scenes": [{"id": "s1", "beats": ["b1"], "layout": "stack", "elements": [{"type": "sticker", "emoji": "art-black-hole", "label": "black hole", "at_word": "w4"}]}]})
    assert validate_scenes(sf, tr, beats, set()) == []
    data = resolve_composition(sf, tr, beats, load_theme("paper"), "9:16", 4.0, None)
    assert "art-black-hole" in data["stickers"] and data["stickers"]["art-black-hole"].startswith("<svg")


def test_ids_inside_drawings_are_unique_per_drawing():
    ids = {}
    for k in concepts.KEYS:
        for i in re.findall(r'id="([^"]+)"', art.svg(k)):
            assert i not in ids, f"{i} used by {ids[i]} and {k}"
            ids[i] = k
        assert all(u.split("-")[0] == "art" for u in re.findall(r"url\(#([^)]+)\)", art.svg(k)))


def test_search_offers_the_drawn_clipart_by_meaning_and_by_name():
    from vt.visuals.search import search, svg_for
    hit = search("black hole", "sticker", 5)[0]
    assert hit["hex"] == "art-black-hole" and hit["label"] == "black hole" and svg_for(hit["id"])["svg"].startswith("<svg")
    assert any(h["hex"] == "art-galaxy" for h in search("galax", None, 8))
