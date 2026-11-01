"""Illustrated cartoon characters (vt/art/toon.py, art from Cartoon Studio, Apache-2.0)."""
from vt.art import toon
from vt.script.models import VideoScript


def test_every_bundled_character_can_talk():
    chars = toon.characters()
    assert set(chars) >= {"bill", "jane", "max", "ted"}
    for name, f in chars.items():
        s = f.read_text(encoding="utf-8")
        assert s.count('class="mouth-group') >= 9 or s.count("mouth-group mouth-") >= 9, name


def test_the_rig_replaces_the_drawn_mouth_below_the_eyes():
    svg = ('<svg viewBox="0 0 1000 1000">'
           '<path d="M400 300 L460 300 L460 360 L400 360 Z" fill="#000"/><path d="M540 300 L600 300 L600 360 L540 360 Z" fill="#000"/>'   # eyes
           '<path d="M450 480 L550 480 L550 500 L450 500 Z" fill="rgb(10,10,10)"/>'                                                         # mouth
           '<path d="M0 900 L1000 900 L1000 920 L0 920 Z" fill="#000"/></svg>')                                                             # ground
    out, ok = toon.rig(svg)
    assert ok and "mouth-rig" in out and "M450 480" not in out and "M0 900" in out
    assert toon.rig(out) == (out, True)                                                                                                  # idempotent


def test_toonify_casts_illustrated_characters_and_paints_places():
    s = VideoScript.model_validate({"kind": "stick", "cast": [{"id": "father", "name": "Father"}, {"id": "boy", "name": "Boy", "style": {"height": "child"}},
                                                             {"id": "mom", "name": "Mother"}, {"id": "dog", "kind": "emoji", "emoji": "1f415", "name": "Dog"}],
                                   "sets": [{"id": "s", "kind": "street"}, {"id": "h", "kind": "home"}, {"id": "l", "kind": "lab"}],
                                   "scenes": [{"id": "s1", "beats": ["b1"]}]})
    t = toon.toonify(s)
    arts = {c.id: (c.kind, c.art) for c in t.cast}
    assert arts["mom"] == ("toon", "jane") and arts["dog"] == ("toon", "max")
    assert {arts["father"][1], arts["boy"][1]} == {"bill", "ted"}                     # two different drawings for two people
    assert [x.art for x in t.sets] == ["street", "living_room", None] and t.kind == "cartoon"
