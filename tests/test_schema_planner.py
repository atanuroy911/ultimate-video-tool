import pytest
from pydantic import ValidationError

from vt.planner import plan_rules
from vt.planner.catalogue import EXAMPLES, all_icon_names, component_catalogue
from vt.schema import ELEMENT_MODELS, Scene, ScenesFile, validate_scenes


def test_every_catalogue_example_validates():
    types = {m.model_fields["type"].default for m in ELEMENT_MODELS}
    assert set(EXAMPLES) == types
    for t, ex in EXAMPLES.items():
        Scene.model_validate({"id": "s1", "beats": ["b1"], "elements": [ex]})


def test_field_limits_are_enforced():
    with pytest.raises(ValidationError):
        Scene.model_validate({"id": "s1", "beats": ["b1"], "elements": [{"type": "title", "text": "x" * 41, "at_word": "w1"}]})
    with pytest.raises(ValidationError):
        Scene.model_validate({"id": "s1", "beats": ["b1"], "elements": [{"type": "icon_row", "count": 9, "at_word": "w1"}]})
    with pytest.raises(ValidationError):  # unknown field
        Scene.model_validate({"id": "s1", "beats": ["b1"], "elements": [{"type": "tag", "text": "a", "color": "red", "at_word": "w1"}]})
    els = [{"type": "tag", "text": "a", "at_word": "w1"}] * 6
    scene = Scene.model_validate({"id": "s1", "beats": ["b1"], "elements": els})
    assert len(scene.elements) == 6  # Editing never discards valid visuals to enforce a layout suggestion.


def test_catalogue_describes_every_component():
    cat = component_catalogue()
    assert len(cat) == len(ELEMENT_MODELS) == 40
    for c in cat:
        assert c["description"] and c["use_when"] and c["example"]["type"] == c["type"]
        assert "at_word" in c["required"]


def test_rule_plan_is_valid_and_covers_all_beats(ref):
    tr, beats = ref.transcript(), ref.beats()
    sf = plan_rules(tr, beats, "paper")
    assert validate_scenes(sf, tr, beats, all_icon_names()) == []
    assert [b for s in sf.scenes for b in s.beats] == [b.id for b in beats.beats]
    assert sf.scenes[0].transition_in == "cut"


def test_validate_scenes_reports_actionable_errors(ref):
    tr, beats = ref.transcript(), ref.beats()
    sf = ScenesFile.model_validate({"scenes": [
        {"id": "s1", "beats": ["b1", "b2"], "elements": [
            {"type": "title", "text": "ক", "at_word": "w999"},                       # not a word
            {"type": "icon", "name": "no-such-icon", "at_word": "w1"},               # unknown icon
            {"type": "tag", "text": "খ", "at_word": "w10"}],                          # word is in a later beat
         "caption": {"highlight_words": ["w20"]}},
        {"id": "s2", "beats": ["b4"]},                                                # b3 and b5 uncovered
    ]})
    errs = validate_scenes(sf, tr, beats, all_icon_names())
    joined = " | ".join(errs)
    assert "w999" in joined and "no-such-icon" in joined and "outside this scene" in joined and "not covered" in joined
