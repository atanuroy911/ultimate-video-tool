"""The direction harness (docs/ROADMAP.md P4-12): rhythm measured the same way for the example reels and for our videos."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("eval_direction", ROOT / "scripts" / "eval_direction.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


def test_the_reels_are_read_with_their_rhythm():
    rows = E.reference_rows()
    assert len(rows) >= 8 and all(r["source"] == "reel" for r in rows)
    busy = [r for r in rows if r["changes"] >= E.BUSY]
    assert len(busy) >= 3
    r3 = next(r for r in rows if r["name"] == "reel-3")
    assert r3["changes"] == 30 and 1.5 < r3["median_gap_s"] < 2.5 and r3["words_per_change"] and r3["changes_per_sentence"]


def test_the_gap_between_changes_is_the_middle_one():
    assert E.gap([1.0, 3.0, 4.0, 9.0]) == 2.0 and E.gap([2.0]) == 0.0 and E.gap([]) == 0.0


def test_counting_words_and_sentences():
    assert E.sentences("One. Two! Three? Four") == 4 and E.sentences("") == 1
    assert E.words("Pay $200 now, 20% down.") == 5


def test_ours_is_placed_against_the_busy_reels_and_missing_numbers_are_said():
    refs = E.reference_rows()
    ours = [E.row("ours", duration=30, swaps=12, median=3, longest=0.5, first=0.5, n_words=96, n_sent=8, source="ours", events=[0.5 + 2.5 * i for i in range(12)])]
    text = "\n".join(E.compare(refs, ours))
    assert "ours" in text and "range" in text and "words under one picture: ours 8.0" in text
    assert E.compare([], ours) == ["Nothing to compare yet."]


def test_the_word_test_is_pending_until_the_owner_marks_a_reel(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "SET", tmp_path)
    assert "pending" in E.marks_status()
    (tmp_path / "marks.json").write_text('[{"reel": "reel-3", "sentence_no": 1, "sentence": "x", "word": "five"}, {"reel": "reel-3", "sentence_no": 2, "sentence": "y", "word": ""}]', encoding="utf-8")
    assert "1 of 2 sentences are marked" in E.marks_status()


def test_the_seeded_set_exists_with_a_template_for_the_owner():
    import json

    assert (ROOT / "tests" / "direction_set" / "reels.json").exists()
    t = json.loads((ROOT / "tests" / "direction_set" / "marks.template.json").read_text(encoding="utf-8"))
    assert len(t) > 20 and all(m["word"] == "" for m in t)          # nothing is pretended to be marked
