"""A kept plan must not outlive the words it points at (owner's Bangla sample, 2026-10-23: after recognition ran again with three
invented words removed, every word id shifted and the monkey's line showed during the wolf's refusal)."""
from vt.util import read_json, write_json


def test_a_plan_is_redone_when_recognition_moves_the_words(ref):
    from vt.pipeline import Pipeline

    p = ref
    pl = Pipeline(p)
    pl.stage_plan(True)
    assert read_json(p.dir / "plan_basis.json")
    first = p.scenes()
    assert not pl._plan_is_stale(first)

    raw = read_json(p.raw_transcript_path)                     # the same recording recognised again: one word fewer near the start
    raw["words"] = raw["words"][:2] + raw["words"][3:]
    write_json(p.raw_transcript_path, raw)
    assert pl._plan_is_stale(first)
    pl.stage_words(True)
    pl.stage_plan()
    assert read_json(p.dir / "plan_notice.json")["message"].startswith("The speech was recognised again")
    assert (p.dir / "scenes.invalid.json").exists() and not pl._plan_is_stale(p.scenes())


def test_a_spelling_fix_does_not_throw_the_plan_away(ref):
    from vt.pipeline import Pipeline

    p = ref
    pl = Pipeline(p)
    pl.stage_plan(True)
    write_json(p.dir / "edits.json", {"words": {"w3": {"text": "বদলানো"}}})       # the person fixes a word: ids stay, the raw text stays
    pl.stage_words(True)
    assert not pl._plan_is_stale(p.scenes())
