"""Editor destinations and library entries must agree with the production pipeline."""
import pytest

from vt import scene_ops
from vt.compose.composer import scene_timing
from vt.planner.catalogue import component_catalogue
from vt.schema import Beats, Scene, ScenesFile


def story():
    beats = Beats(beats=[dict(id=f"b{i}", start=(i-1)*2, end=i*2-.2, text=f"Sentence {i}", word_ids=[f"w{i}"]) for i in range(1, 7)])
    sf = ScenesFile(scenes=[Scene(id=f"s{i}", beats=[f"b{i*2-1}", f"b{i*2}"], elements=[dict(type="title",text=f"Visual {i}",at_word=f"w{i*2}")]) for i in range(1, 4)])
    return sf, beats


def test_scene_handle_destinations_use_renderer_clock_and_preserve_other_scenes():
    sf, beats = story()
    original = scene_timing(sf, beats, 12)
    choices = scene_ops.boundary_choices(sf, beats, 12)["s1"]
    assert [c["time"] for c in choices] == [1.9, 3.9, 5.9]
    assert [c["current"] for c in choices] == [False, True, False]
    for choice in choices:
        changed = scene_ops.move_boundary(sf, beats, "s1", choice["at_beat"])
        timing = scene_timing(changed, beats, 12)
        assert timing[0]["end"] == timing[1]["start"] == choice["time"]
        assert timing[2] == original[2]
        assert sorted(e.text for s in changed.scenes for e in s.elements) == ["Visual 1", "Visual 2", "Visual 3"]
        restored = scene_ops.move_boundary(changed, beats, "s1", "b3")
        assert scene_timing(restored, beats, 12) == original


def test_scene_edge_minimum_spacing_and_single_sentence_limit():
    sf, beats = story()
    beats.beats[1].start = .15
    assert scene_ops.boundary_choices(sf, beats, 12)["s1"][0]["time"] == .4
    two = ScenesFile(scenes=[Scene(id="s1", beats=["b1"]), Scene(id="s2", beats=["b2"])])
    assert all(c["current"] for c in scene_ops.boundary_choices(two, beats, 4)["s1"])


def test_overflowing_edge_or_merge_never_discards_visuals():
    sf, beats = story()
    sf.scenes[0].elements = [sf.scenes[0].elements[0].model_copy() for _ in range(5)]
    before = sf.model_dump()
    moved=scene_ops.move_boundary(sf,beats,"s1","b2")
    merged=scene_ops.merge_with_next(sf,beats,"s1")
    assert sum(len(sc.elements) for sc in moved.scenes)==7
    assert sum(len(sc.elements) for sc in merged.scenes)==7
    assert sf.model_dump()==before



def test_every_library_starter_validates_and_has_a_group():
    specs = component_catalogue()
    assert len(specs) == 41
    for spec in specs:
        assert spec["category"] != "More"
        Scene(id="s", beats=["b1"], elements=[spec["starter"]])


def test_shape_goes_through_director_submission_and_all_compositions(ref):
    from vt import planning
    from vt.compose import FORMATS
    from vt.util import read_json

    request = planning.create_request(ref, "full")
    task = planning.planning_task(ref, request.id)
    shape = next(s for s in task["catalogue"]["elements"] if s["type"] == "shape")
    scenes = ref.scenes().model_dump()["scenes"]
    scenes[0]["elements"] = [{**shape["starter"], "at_word": ref.beats().beats[0].word_ids[0], "shape":"circle", "label":"My shape"}]
    result = planning.submit(ref, request.id, scenes)
    assert result["ok"] and result["applied"], result
    for fmt in FORMATS.values():
        folder = ref.comp_dir / fmt["tag"]
        data = read_json(folder / "data.json")
        assert data["scenes"][0]["elements"][0]["type"] == "shape"
        assert data["scenes"][0]["elements"][0]["label"] == "My shape"
        assert "C.shape =" in (folder / "runtime" / "vt.js").read_text(encoding="utf-8")
