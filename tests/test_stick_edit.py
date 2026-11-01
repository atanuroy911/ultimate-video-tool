"""Editing stick-figure plans: scene splits/merges keep the actions, actions can be re-timed, and the cast can be restyled."""
import pytest

from vt import scene_ops
from vt.pipeline import compose_all
from vt.planner import plan_rules
from vt.script import compile_script
from vt.script.rules_stick import rules_script


def stick_project(ref):
    tr, beats = ref.transcript(), ref.beats()
    script = rules_script(tr, beats, plan_rules(tr, beats), kind="stick")
    ref.save_scenes(compile_script(script, tr, beats, ref.meta().theme))
    return ref


def count(sf):
    return sum(len(s.stick["actions"]) for s in sf.scenes)


def test_actions_follow_their_words_through_scene_edits(ref):
    stick_project(ref)
    sf, beats = ref.scenes(), ref.beats()
    n = count(sf)
    merged = scene_ops.merge_with_next(sf, beats, sf.scenes[0].id)
    assert count(merged) == n and all(s.stick for s in merged.scenes)
    multi = next((s for s in sf.scenes if len(s.beats) > 1), None)
    if multi:
        split = scene_ops.split_scene(sf, beats, multi.id, multi.beats[1])
        assert count(split) == n
        j = [s.id for s in split.scenes].index(multi.id) + 1
        words = {w for b in beats.beats if b.id in split.scenes[j].beats for w in b.word_ids}
        assert all(a["at_word"] in words for a in split.scenes[j].stick["actions"])
        assert all(s.stick["cast"] for s in split.scenes)                 # the new scene took the characters along
    gone = scene_ops.delete_scene(sf, beats, sf.scenes[1].id)
    assert count(gone) == n


def test_actions_can_be_retimed_edited_and_deleted(ref):
    stick_project(ref)
    sf, tr, beats = ref.scenes(), ref.transcript(), ref.beats()
    sc = sf.scenes[0]
    a0 = sc.stick["actions"][0]
    scene_words = [w for b in beats.beats if b.id in sc.beats for w in b.word_ids]
    later = scene_words[-1]
    moved = scene_ops.edit_action(sf, tr, beats, sc.id, 0, {"at_word": later})
    got = [a for a in moved.scenes[0].stick["actions"] if a["do"] == a0["do"] and a["who"] == a0["who"] and a["at_word"] == later][0]
    assert got["at_word"] == later and got["start"] >= tr.by_id()[later].start - 1e-6
    with pytest.raises(scene_ops.OpError):
        scene_ops.edit_action(sf, tr, beats, sc.id, 0, {"at_word": "w999"})
    with pytest.raises(scene_ops.OpError):
        scene_ops.edit_action(sf, tr, beats, sc.id, 99, {})
    gone = scene_ops.edit_action(sf, tr, beats, sc.id, 0, None, delete=True)
    assert len(gone.scenes[0].stick["actions"]) == len(sc.stick["actions"]) - 1


def test_cast_can_be_restyled_everywhere(ref):
    stick_project(ref)
    sf = ref.scenes()
    cid = sf.scenes[0].stick["cast"][0]["id"]
    look = scene_ops.edit_cast(sf, cid, {"name": "Dr Maya", "style": {"color": "#ff0000", "accessory": "hat"}})
    for s in look.scenes:
        c = next((x for x in s.stick["cast"] if x["id"] == cid), None)
        if c is None:
            continue
        assert c["name"] == "Dr Maya" and c["style"]["color"] == "#ff0000" and c["style"]["accessory"] == "hat" and c["style"]["head"] in ("round", "oval", "square")
    with pytest.raises(scene_ops.OpError):
        scene_ops.edit_cast(sf, cid, {"style": {"color": "red"}})
    with pytest.raises(scene_ops.OpError):
        scene_ops.edit_cast(sf, "nobody", {"name": "x"})


def test_a_character_can_be_recast_as_a_cartoon_or_an_animal(ref):
    stick_project(ref)
    sf = ref.scenes()
    cid = sf.scenes[0].stick["cast"][0]["id"]
    toon = scene_ops.edit_cast(sf, cid, {"kind": "toon", "art": "jane", "style": {"height": "child", "hair": "long", "shirt": "#22aa55"}})
    c = next(x for x in toon.scenes[0].stick["cast"] if x["id"] == cid)
    assert c["kind"] == "toon" and c["art"] == "jane" and c["style"]["height"] == "child" and c["style"]["shirt"] == "#22aa55"
    animal = scene_ops.edit_cast(toon, cid, {"kind": "emoji", "emoji": "1f981"})
    assert next(x for x in animal.scenes[0].stick["cast"] if x["id"] == cid)["emoji"] == "1f981"
    with pytest.raises(scene_ops.OpError):
        scene_ops.edit_cast(sf, cid, {"kind": "toon", "art": "nobody"})


def test_endpoints_edit_actions_and_cast(ref, projects_dir):
    from fastapi.testclient import TestClient

    from vt.server.app import app

    stick_project(ref)
    c = TestClient(app)
    plan = c.get(f"/api/projects/{ref.id}/scenes").json()["plan"]
    sid = plan["scenes"][0]["id"]
    n = len(plan["scenes"][0]["stick"]["actions"])
    r = c.patch(f"/api/projects/{ref.id}/scenes/{sid}/actions/0", json={"delete": True})
    assert r.status_code == 200 and len(r.json()["plan"]["scenes"][0]["stick"]["actions"]) == n - 1
    r = c.patch(f"/api/projects/{ref.id}/scenes/{sid}/actions/0", json={"patch": {"at_word": "w999"}})
    assert r.status_code == 422
    cid = plan["scenes"][0]["stick"]["cast"][0]["id"]
    r = c.patch(f"/api/projects/{ref.id}/cast/{cid}", json={"style": {"color": "#00aa00"}})
    assert r.status_code == 200 and r.json()["plan"]["scenes"][0]["stick"]["cast"][0]["style"]["color"] == "#00aa00"
    assert c.patch(f"/api/projects/{ref.id}/cast/ghost", json={"name": "x"}).status_code == 422
