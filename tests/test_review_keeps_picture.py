"""The director's one look at its cut (vt/director_review.py) revises the picture; it never takes the picture away.

Seen on 2026-11-15 with the Local AI directing: every scene of six videos ended with no element at all, captions on an empty background. Three things
let it happen: a scene laid out as several pages was looked at once per page, each look judged on a frame from before the previous look's changes;
"remove element 0, then set element 0" was read as a removal plus a change to a hole; and nothing refused a revision that left a scene empty."""
from __future__ import annotations

import json

from vt import director_review as R
from vt.schema import Scene


def _scene() -> Scene:
    return Scene.model_validate({"id": "s1", "beats": ["b1"], "layout": "stack", "elements": [
        {"type": "title", "text": "Most", "at_word": "w1"},
        {"type": "sticker", "emoji": "1f4b5", "label": "money", "at_word": "w5"},
        {"type": "sticker", "emoji": "1f522", "label": "thousand", "at_word": "w18"},
    ]})


def test_removing_every_element_is_refused_and_reported():
    sc = _scene()
    new, skipped = R.apply_changes(sc, [{"element": 0, "remove": True}, {"element": 1, "remove": True}, {"element": 2, "remove": True}])
    assert len(new.elements) == 3
    assert any("only its caption" in s for s in skipped)


def test_removing_some_elements_still_works():
    new, skipped = R.apply_changes(_scene(), [{"element": 1, "remove": True}])
    assert [e.type for e in new.elements] == ["title", "sticker"] and new.elements[1].label == "thousand"
    assert skipped == []


def test_remove_then_set_on_one_element_is_a_replacement():
    """The model's habit: "remove 1" and then "set 1 to a better emoji". The new fields decide; the element is not removed."""
    new, skipped = R.apply_changes(_scene(), [{"element": 1, "remove": True}, {"element": 1, "set": {"emoji": "1f437", "label": "saving"}}])
    assert len(new.elements) == 3 and new.elements[1].emoji == "1f437" and new.elements[1].label == "saving"
    assert skipped == []


def test_a_refused_replacement_leaves_the_element_not_a_hole():
    new, skipped = R.apply_changes(_scene(), [{"element": 0, "remove": True}, {"element": 0, "set": {"type": "text", "text": "x"}}])
    assert len(new.elements) == 3 and new.elements[0].text == "Most"
    assert skipped and "element 0" in skipped[0]


def test_the_prompt_names_each_elements_type():
    text = R._scene_prompt(_scene(), "Most people think saving money")
    listed = json.loads(text.split("another moment of the scene):\n", 1)[1].split("\n\nREAL VISUAL")[0])
    assert [e["type"] for e in listed] == ["title", "sticker", "sticker"]
    assert "You cannot add an element" in R.SYSTEM and "never remove everything a scene shows" in R.SYSTEM


def test_one_look_per_scene_on_the_page_that_shows_the_most(tmp_path):
    """A scene split into pages s1, s1p2, s1p3 by the composer is looked at once, where most of it is on screen."""
    from vt.util import write_json

    data = {"scenes": [
        {"id": "s1", "start": 0.0, "end": 1.4, "elements": [{"type": "title", "at": 0.0}]},
        {"id": "s1p2", "src": "s1", "start": 1.4, "end": 4.0, "elements": [{"type": "title", "at": 0.0}, {"type": "sticker", "at": 1.4}, {"type": "sticker", "at": 2.0}]},
        {"id": "s1p3", "src": "s1", "start": 4.0, "end": 6.0, "elements": [{"type": "sticker", "at": 4.0}]},
        {"id": "s2", "start": 6.0, "end": 9.0, "elements": [{"type": "icon", "at": 6.2}]},
    ]}
    write_json(tmp_path / "data.json", data)
    sf = type("SF", (), {"scenes": [type("S", (), {"id": "s1"})(), type("S", (), {"id": "s2"})()]})()
    times = R._frame_times(tmp_path, sf)
    assert [sid for sid, _ in times] == ["s1", "s2"]
    assert 1.4 <= times[0][1] <= 4.0, times
