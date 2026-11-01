"""Plans (hand edits or Claude's) must survive transcript edits and re-cuts; replacement is the last resort."""
from vt import planning
from vt.pipeline import Pipeline, remap_scenes, repair_scenes
from vt.planner.catalogue import all_icon_names
from vt.schema import Beats, validate_scenes
from vt.util import read_json, write_json


def valid(p):
    return validate_scenes(p.scenes(), p.transcript(), p.beats(), all_icon_names()) == []


def test_word_text_edit_keeps_the_plan_untouched(ref):
    before = ref.scenes().model_dump()
    write_json(ref.dir / "edits.json", {"words": {"w20": {"text": "বদলানো"}}})
    pl = Pipeline(ref)
    pl.stage_words()
    pl.stage_plan()
    assert ref.scenes().model_dump() == before and ref.scenes().planner == "manual"
    assert not (ref.dir / "plan_notice.json").exists()


def test_recut_that_moves_sentence_boundaries_remaps_instead_of_replacing(ref):
    """Cutting the sentence-final word 'কী?' merges sentence 1 into sentence 2; the plan must be remapped, not thrown away."""
    claude_plan = ref.scenes().model_copy(update={"planner": "claude"})
    ref.save_scenes(claude_plan)
    old_ids = [b.id for b in ref.beats().beats]
    write_json(ref.dir / "edits.json", {"words": {"w3": {"cut": True}}})
    pl = Pipeline(ref)
    pl.stage_words()
    assert [b.id for b in ref.beats().beats] != old_ids or ref.beats().beats[0].text != "ইয়েল্ড মানে কী?"
    assert (ref.dir / "beats.prev.json").exists()
    pl.stage_plan()
    sf = ref.scenes()
    assert valid(ref)
    assert sf.planner == "claude"                              # still the user's/Claude's plan, not a rules draft
    assert not (ref.dir / "plan_notice.json").exists()
    kinds = [e.type for s in sf.scenes for e in s.elements]
    assert "value_card" in kinds and "compare" in kinds       # visuals were kept


def test_unrecoverable_plan_is_replaced_but_backed_up_and_announced(ref):
    ref.save_scenes(ref.scenes().model_copy(update={"planner": "claude"}))
    (ref.dir / "beats.prev.json").unlink(missing_ok=True)
    # beats the plan has never heard of, and no previous beats to remap from
    beats = ref.beats().model_dump()
    for i, b in enumerate(beats["beats"]):
        b["id"] = f"x{i}"
    write_json(ref.beats_path, beats)
    Pipeline(ref).stage_plan()
    assert valid(ref) and ref.scenes().planner == "rules"
    assert (ref.dir / "scenes.invalid.json").exists()
    assert "no longer fits" in read_json(ref.dir / "plan_notice.json")["message"]


def test_remap_keeps_scene_order_and_drops_emptied_scenes(ref):
    sf, old = ref.scenes(), ref.beats()
    # new sentences: everything in one beat -> every scene except the one owning most words disappears
    ws = [w for b in old.beats for w in b.word_ids]
    one = Beats.model_validate({"beats": [{"id": "b1", "word_ids": ws, "start": 0.0, "end": 9.0, "text": "x"}]})
    out = remap_scenes(sf, old, one)
    assert len(out.scenes) == 1 and out.scenes[0].beats == ["b1"]
