import pytest

from vt import planning, scene_ops
from vt.planner import plan_rules
from vt.planner.catalogue import EXAMPLES, all_icon_names
from vt.schema import validate_scenes


def valid(p, sf):
    return validate_scenes(sf, p.transcript(), p.beats(), all_icon_names()) == []


def test_split_keeps_elements_with_their_beats(ref):
    sf, beats = ref.scenes(), ref.beats()
    n = len(sf.scenes[1].elements)
    out = scene_ops.split_scene(sf, beats, "s2", "b4")  # s2 spans b2..b4
    assert valid(ref, out) and len(out.scenes) == len(sf.scenes) + 1
    a, b = out.scenes[1], out.scenes[2]
    assert a.beats == ["b2", "b3"] and b.beats == ["b4"]
    assert len(a.elements) + len(b.elements) == n            # nothing lost, each element lives where its word is
    assert all(e.at_word in {w for bid in a.beats for w in next(x for x in beats.beats if x.id == bid).word_ids} for e in a.elements)
    with pytest.raises(scene_ops.OpError):
        scene_ops.split_scene(sf, beats, "s2", "b2")        # cannot split at the first beat


def test_merge_delete_move_boundary_stay_valid(ref):
    sf, beats = ref.scenes(), ref.beats()
    merged = scene_ops.merge_with_next(sf, beats, "s1")
    assert valid(ref, merged) and len(merged.scenes) == 2 and merged.scenes[0].beats == ["b1", "b2", "b3", "b4"]
    deleted = scene_ops.delete_scene(sf, beats, "s2")
    assert valid(ref, deleted) and [s.id for s in deleted.scenes] == ["s1", "s3"]
    assert deleted.scenes[0].beats == ["b1", "b2", "b3", "b4"]
    moved = scene_ops.move_boundary(sf, beats, "s1", "b3")   # next scene (s2) now starts at b3
    assert valid(ref, moved) and moved.scenes[0].beats == ["b1", "b2"] and moved.scenes[1].beats[0] == "b3"
    with pytest.raises(scene_ops.OpError):
        scene_ops.merge_with_next(sf, beats, "s3")


def test_patch_scene_validates(ref):
    sf = ref.scenes()
    out = scene_ops.patch_scene(sf, "s1", {"layout": "hero", "transition_in": "zoom"})
    assert out.scenes[0].layout == "hero"
    with pytest.raises(scene_ops.OpError):
        scene_ops.patch_scene(sf, "s1", {"beats": ["b2"]})
    with pytest.raises(scene_ops.OpError):
        scene_ops.patch_scene(sf, "s1", {"layout": "diagonal"})


def test_claude_round_trip_full_plan(ref):
    req = planning.create_request(ref, "full")
    assert ref.meta().status == "waiting_for_claude"
    assert [r["id"] for r in planning.pending()] == [req.id]

    task = planning.planning_task(ref, req.id)
    assert "Cover EVERY beat" in task["instructions"]
    assert task["beats"][0]["words"][0].startswith("w1:")            # compact timed words
    assert {e["type"] for e in task["catalogue"]["elements"]} == set(EXAMPLES)

    # a bad submission returns concrete errors and changes nothing
    before = ref.scenes_path.read_text(encoding="utf-8")
    bad = [{"id": "s1", "beats": ["b1"], "elements": [{"type": "title", "text": "x", "at_word": "w999"}]}]
    res = planning.submit(ref, req.id, bad)
    assert res["ok"] is False and any("w999" in e for e in res["errors"]) and any("not covered" in e for e in res["errors"])
    assert ref.scenes_path.read_text(encoding="utf-8") == before
    assert planning.pending()  # still queued

    # a good plan applies, is marked as Claude's, previous plan is kept for undo, request closes
    good = plan_rules(ref.transcript(), ref.beats()).model_dump(exclude_none=True)["scenes"]
    res = planning.submit(ref, req.id, good)
    assert res["ok"] and res["applied"]
    assert ref.scenes().planner == "claude"
    assert (ref.dir / "scenes.prev.json").exists()
    assert planning.pending() == [] and ref.meta().status == "planned"
    assert (ref.comp_dir / "9x16" / "data.json").exists()           # preview recomposed immediately


def test_scene_regeneration_with_alternatives(ref):
    req = planning.create_request(ref, "scene", "s3", hint="make it a bar chart", alternatives=2)
    task = planning.planning_task(ref, req.id)
    assert task["target_scene"]["id"] == "s3" and task["previous_scene"]["id"] == "s2" and task["next_scene"] is None
    w = ref.beats().beats[-1].word_ids[0]  # first word of the last sentence
    alts = [
        {"id": "x", "beats": ["ignored"], "elements": [{"type": "big_number", "value": "৩", "unit": "%", "at_word": w}]},
        {"id": "y", "beats": ["ignored"], "elements": [{"type": "tag", "text": "নেট", "at_word": w}], "layout": "hero"},
    ]
    res = planning.submit(ref, req.id, alts)
    assert res["ok"] and res["applied"] is False
    assert len(planning.alternatives(ref, req.id)) == 2
    sf = planning.apply_alternative(ref, req.id, 1)
    s3 = next(s for s in sf.scenes if s.id == "s3")
    assert s3.layout == "hero" and s3.beats == ["b5"] and s3.elements[0].type == "tag"  # beats/id forced to the original scene's


def test_duplicate_requests_replace_each_other(ref):
    a = planning.create_request(ref, "scene", "s1", "one")
    b = planning.create_request(ref, "scene", "s1", "two")
    ids = [r.id for r in ref.requests()]
    assert ids == [b.id] and a.id not in ids
    with pytest.raises(ValueError):
        planning.create_request(ref, "scene", "nope")


def test_claude_plans_get_their_text_contrast_checked_and_see_the_media_bin(ref, tmp_path):
    import numpy as np
    from PIL import Image
    from vt import planning
    from vt.director.media import add_media
    ys, xs = np.mgrid[0:600, 0:400]
    a = (((ys // 16 + xs // 16) % 2) * 255).astype("uint8")
    Image.fromarray(np.stack([a, a, a], axis=-1)).save(tmp_path / "busy.png")
    item = add_media(ref, tmp_path / "busy.png", caption="a busy photo")
    req = planning.create_request(ref, "full")
    task = planning.planning_task(ref, req.id)
    assert task["media_bin"][0]["id"] == item.id and task["usecase"]["used"] and "scene_types" in task["usecase"]
    tr, beats = ref.transcript(), ref.beats()
    scenes = [{"id": f"s{i + 1}", "beats": [b.id], "elements": [{"type": "title", "text": "x", "at_word": b.word_ids[0]}]} for i, b in enumerate(beats.beats)]
    # Claude asks for a backdrop but does not (and cannot) decide the scrim: the engine does
    scenes[0]["backdrop"] = {"media": item.id, "motion": "kenburns", "scrim": {"ink": "dark", "kind": "none", "strength": 0.0, "ratio": 99}}
    scenes[0]["layout"] = "lower"
    out = planning.submit(ref, req.id, scenes)
    assert out["ok"], out
    bd = ref.scenes().scenes[0].backdrop
    assert bd.scrim.kind in ("gradient", "panel") and bd.scrim.ratio >= 4.5                  # a busy photo needed help, whatever Claude claimed
    bad = [dict(s) for s in scenes]
    bad[0] = {**scenes[0], "backdrop": {"media": "ghost"}}
    req2 = planning.create_request(ref, "full")
    res = planning.submit(ref, req2.id, bad)
    assert res["ok"] is False and any("not in the project's media bin" in e for e in res["errors"])
