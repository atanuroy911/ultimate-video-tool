"""Animals are not played by people (owner, 2026-10-24)."""
from vt.script.animals import animal_of, animalize
from vt.script.models import VideoScript


def test_animal_words_in_both_languages():
    assert animal_of("The old Lion") == "1f981" and animal_of("little mouse") == "1f42d" and animal_of("two foxes") == "1f98a"
    assert animal_of("নেকড়ে") == "1f43a" and animal_of("বকটা") == "1f426" and animal_of("বাঁদর ভাই") == "1f412"
    assert animal_of("Father") is None and animal_of("শিক্ষক") is None


def test_the_cast_keeps_people_and_turns_animals_into_animal_actors():
    s = VideoScript.model_validate({"kind": "stick", "cast": [{"id": "lion", "name": "Lion"}, {"id": "mouse", "name": "ইঁদুর"}, {"id": "hunter", "name": "Hunter"}],
                                   "scenes": [{"id": "s1", "beats": ["b1"]}]})
    out, n = animalize(s)
    kinds = {c.id: (c.kind, c.emoji) for c in out.cast}
    assert n == 2 and kinds["lion"] == ("emoji", "1f981") and kinds["mouse"] == ("emoji", "1f42d") and kinds["hunter"] == ("person", None)
