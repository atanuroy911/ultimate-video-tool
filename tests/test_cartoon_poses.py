"""C3/C4 cartoon vocabulary and deterministic character descriptions, without rendering."""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from vt.schema import Beat, Beats, CastMember, Cartoon, Scene, ScenesFile, Transcript, Word
from vt.script.prompt import cartoon_choices
from vt.script.story_kit import apply_story_kit


@pytest.mark.parametrize("pose", ["idle", "run", "laugh", "count", "confused", "ride"])
def test_new_cartoon_pose_roundtrips_and_is_offered_to_the_director(pose):
    cartoon = Cartoon(at_word="w1", cast=[{"who": "woman", "pose": pose}], cues=[{"pose": pose}])
    assert Cartoon.model_validate(cartoon.model_dump()).cast[0].pose == pose
    assert pose in cartoon_choices()


@pytest.mark.parametrize("expression", ["laugh", "confused"])
def test_new_expressions_are_real_schema_values(expression):
    assert CastMember(expression=expression).expression == expression
    assert expression in cartoon_choices()


def test_explicit_colors_and_old_woman_roundtrip_while_legacy_colors_stay_automatic():
    assert CastMember(name="Maya").hair == CastMember(name="Maya").clothes == ""
    member = CastMember(who="old_woman", name="Maya", hair="#e0d7ce", clothes="#8758ab")
    assert CastMember.model_validate(member.model_dump()) == member
    for field in ("hair", "clothes"):
        with pytest.raises(ValidationError):
            CastMember(**{field: "url(https://example.org/color)"})


def test_requested_count_five_is_preserved_in_the_story_kit_cue():
    tr = Transcript(words=[Word(id="w1", text="Five", start=0, end=1)])
    beats = Beats(beats=[Beat(id="b1", word_ids=["w1"], start=0, end=2, text="Five")])
    timeline = {"cast": [{"id": "maya", "name": "Maya", "style": {}}],
                "actions": [{"who": "maya", "do": "count", "count": 5, "start": 0, "end": 1.5}]}
    plan = ScenesFile(scenes=[Scene(id="s1", beats=["b1"], stick=timeline)])
    cartoon = apply_story_kit(plan, SimpleNamespace(kind="cartoon", scenes=[]), tr, beats, "classic", motifs=False).scenes[0].elements[0]
    assert cartoon.cues[0].count == 5
    assert CastMember(pose="count", count=5).count == 5
    with pytest.raises(ValidationError):
        CastMember(pose="count", count=6)


@pytest.mark.parametrize("verb", ["idle", "run", "laugh", "count", "confused", "ride"])
def test_story_kit_preserves_real_poses_emotions_and_clothes(verb):
    tr = Transcript(words=[Word(id="w1", text="Maya", start=0, end=1)])
    beats = Beats(beats=[Beat(id="b1", word_ids=["w1"], start=0, end=2, text="Maya")])
    timeline = {"cast": [{"id": "maya", "name": "Maya", "role": "elder", "style": {"height": "elder", "hair": "bun", "shirt": "#8758ab"}}],
                "actions": [{"who": "maya", "do": verb, "emotion": "confused", "start": 0, "end": 1}], "set": {"kind": "home"}}
    plan = ScenesFile(scenes=[Scene(id="s1", beats=["b1"], stick=timeline)])
    changed = apply_story_kit(plan, SimpleNamespace(kind="cartoon", scenes=[]), tr, beats, "classic", motifs=False)
    cartoon = changed.scenes[0].elements[0]
    assert cartoon.cast[0].who == "old_woman"
    assert cartoon.cast[0].clothes == "#8758ab"
    assert cartoon.cues[0].pose == verb
    assert cartoon.cues[0].expression == "confused"
