import pytest

from vt.visuals import translate
from vt.visuals.lexicon import Lexicon

pytestmark = pytest.mark.skipif(not Lexicon.get().ok, reason="visual lexicon not built")


def test_translated_word_reaches_the_english_dictionary(monkeypatch):
    monkeypatch.setattr(translate, "_mem", {"bn:জাদুঘর": "museum", "bn:ঝড়": "storm"})
    m = Lexicon.get().lookup("জাদুঘর")
    assert m and m.usable() and m.source == "dict" and m.line
    assert Lexicon.get().lookup("ঝড়").line.endswith("tornado") or Lexicon.get().lookup("ঝড়").sticker


def test_no_cache_and_no_network_is_a_clean_miss(monkeypatch):
    monkeypatch.setattr(translate, "_mem", {})
    monkeypatch.setenv("VT_TRANSLATE", "0")
    assert translate.prefetch(["জাদুঘর"]) == 0 and translate.cached("জাদুঘর") is None
