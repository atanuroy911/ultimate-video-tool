"""A number where the story engine draws text must never stop a render (found 2026-11-21: Qwen 3.5 wrote a "steps" element with items 3, 6, 9, 12;
the drawing called .split on a number and the render was blocked). The check writes a number as text and says so; anything else goes back to the director."""
from vt.story.engine_validate import validate


def spec(element):
    return {"meta": {"total": 4.0}, "characters": {}, "captions": [{"s": 0, "e": 4, "t": "three six nine twelve"}],
            "scenes": [{"s": 0, "e": 4, "bg": {"type": "plain"}, "elements": [element]}]}


def test_numbers_in_text_fields_are_written_as_text_and_noted():
    notes = []
    fixed, errors, _ = validate(spec({"type": "steps", "items": [3, 6, 9.5, "twelve"], "at": 0.5}), notes=notes)
    assert not errors
    assert fixed["scenes"][0]["elements"][0]["items"] == ["3", "6", "9.5", "twelve"]
    assert any("written as text" in n["says"] and n["meaning"] is False for n in notes)
    fixed, errors, _ = validate(spec({"type": "title", "text": 300, "at": 0.5}))
    assert not errors and fixed["scenes"][0]["elements"][0]["text"] == "300"


def test_other_wrong_types_go_back_to_the_director():
    _, errors, _ = validate(spec({"type": "steps", "items": [{"a": 1}, "two"], "at": 0.5}))
    assert any('"items" must be text' in e for e in errors)
    _, errors, _ = validate(spec({"type": "title", "text": ["a", "b"], "at": 0.5}))
    assert any('"text" must be text' in e for e in errors)
    _, errors, _ = validate(spec({"type": "title", "text": True, "at": 0.5}))
    assert errors, "true/false is not a number to write"
