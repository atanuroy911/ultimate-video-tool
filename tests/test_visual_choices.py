"""C8 library choices are grounded, bounded, and never start a model or network call."""
from types import SimpleNamespace

import pytest

from vt.visuals import choices, picker, search, translate


@pytest.fixture()
def library(monkeypatch):
    docs = [{"id": "emoji:1fa99", "en": "coin", "bn": "মুদ্রা", "kind": "sticker"},
            {"id": "emoji:1f3ea", "en": "shop", "bn": "দোকান", "kind": "sticker"}]
    monkeypatch.setattr(search, "_docs", lambda: docs)
    monkeypatch.setattr(search.Lexicon, "get", lambda: SimpleNamespace(ok=False, lookup=lambda q: None))
    monkeypatch.setattr(search.emo, "emoji_key", lambda key: key)
    monkeypatch.setattr(search.emo, "index", lambda: {"1fa99": {"en": "coin"}, "1f3ea": {"en": "shop"}})
    monkeypatch.setattr(search, "svg_for", lambda vid: {})
    monkeypatch.setattr(picker, "_embedder", lambda: pytest.fail("prompt choices must not start an embedding model"))
    monkeypatch.setattr(translate, "prefetch", lambda *a: pytest.fail("prompt choices must not request translations"))
    monkeypatch.setattr(picker, "is_content", lambda word: word.text not in {"the", "a", "and", "in"})
    return docs


def test_real_search_results_supply_exact_fields_and_values(library):
    rows = choices.for_text("the coin and shop coin")
    assert rows == [{"word": "coin", "options": [{"type": "sticker", "field": "emoji", "value": "1fa99", "label": "coin"}]},
                    {"word": "shop", "options": [{"type": "sticker", "field": "emoji", "value": "1f3ea", "label": "shop"}]}]
    assert choices.for_text("মুদ্রা দোকান"), "Bangla keyword matching also stays local"


def test_missing_library_never_breaks_prompt_construction(monkeypatch):
    monkeypatch.setattr(search, "search", lambda *a, **k: (_ for _ in ()).throw(OSError("library unavailable")))
    assert choices.prompt([("s1", "coin shop")]) == ""


def test_options_and_total_prompt_size_are_bounded(library, monkeypatch):
    monkeypatch.setattr(search, "search", lambda *a, **k: [{"id": "lucide:coins", "label": "x" * 500}] * 100)
    terms = choices.for_text("coin shop apple banana grape plum pear lemon")
    assert len(terms) <= choices.MAX_TERMS
    assert all(len(row["options"]) <= choices.MAX_OPTIONS for row in terms)
    assert all(len(option["label"]) <= 80 for row in terms for option in row["options"])
    assert all(option["field"] == "name" and option["value"] == "lucide:coins" for row in terms for option in row["options"])
    text = choices.prompt([(f"b{i}", "coin shop apple banana") for i in range(500)])
    assert len(text) < choices.MAX_PROMPT + 1000
    assert len(text.splitlines()) <= choices.MAX_GROUPS + 1


def test_planning_and_single_revision_receive_the_same_real_choices(ref, library):
    from vt.director_review import _scene_prompt
    from vt.script.prompt import build_prompt

    beats = ref.beats().model_copy(deep=True)
    beats.beats[0].text = "coin shop"
    _, plan = build_prompt(ref.transcript(), beats, with_examples=False)
    fact = "element 0 covers 70% of Maya's face."
    review = _scene_prompt(ref.scenes().scenes[0], "coin shop", [fact])
    for prompt in (plan, review):
        assert '"value": "1fa99"' in prompt and '"label": "coin"' in prompt
        assert '"value": "1f3ea"' in prompt and '"label": "shop"' in prompt
        assert "instead of guessing an emoji code" in prompt
    assert review.index(fact) < review.index("REAL VISUAL CHOICES")
