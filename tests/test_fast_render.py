"""C11: a long recording is split into plain stretches (cut from the A-roll) and designed stretches (drawn); a drawn stretch gets a page with only
what it shows."""
import json

from vt.render import fast as F


def _scene(i, s, e, aroll=True, elements=()):
    return {"id": f"s{i}", "start": s, "end": e, "backdrop": {"media": "aroll"} if aroll else None, "elements": list(elements)}


def test_runs_join_plain_scenes_and_draw_short_plain_gaps_with_their_neighbours():
    data = {"duration": 30.0, "layers": [], "scenes": [
        _scene(1, 0.2, 5, True), _scene(2, 5, 10, True),                 # plain 0-10
        _scene(3, 10, 12, False),                                         # designed
        _scene(4, 12, 13.5, True),                                        # plain but only 1.5 s: drawn with its neighbours
        _scene(5, 13.5, 16, True, [{"type": "keyword"}]),                 # an element: designed
        _scene(6, 16, 30, True)]}                                         # plain
    assert F.runs(data) == [("plain", 0.0, 10.0), ("designed", 10.0, 16.0), ("plain", 16.0, 30.0)]
    assert round(F.plain_share(F.runs(data)), 2) == 0.8


def test_a_layer_over_a_plain_scene_makes_it_designed():
    data = {"duration": 10.0, "scenes": [_scene(1, 0, 10)], "layers": [{"clips": [{"start": 2.0, "dur": 3.0}]}]}
    assert F.runs(data) == [("designed", 0.0, 10.0)]


def test_a_drawn_stretch_keeps_only_what_is_near_it():
    d = {"scenes": [_scene(1, 0, 5), _scene(2, 5, 10), _scene(3, 50, 60)], "captions": [{"start": 1, "end": 2}, {"start": 5, "end": 6}, {"start": 55, "end": 56}],
         "cues": [{"at": 1}], "layers": [{"clips": [{"start": 6, "dur": 1}, {"start": 40, "dur": 1}]}]}
    html = "<html><script>window.__VT__ = " + json.dumps(d) + ";</script></html>"
    out = F._prune(html, 4.0, 9.0)
    got = json.loads(out.split("window.__VT__ = ")[1].split(";</script>")[0])
    assert got["captions"] == [{"start": 5, "end": 6}]
    assert [s["id"] for s in got["scenes"]] == ["s1", "s2"]
    assert got["cues"] == [] and len(got["layers"][0]["clips"]) == 1


def test_ass_captions_are_shifted_to_the_stretch_and_coloured_by_the_theme():
    theme = {"color": {"caption_ink": "#1a1a1a", "caption_bg": "#ffffff", "highlight_bg": "#f26a1f"}, "caption": {"size": 58}, "font": {"caption": ["Inter"]}}
    caps = [{"start": 10.0, "end": 11.5, "words": [{"text": "an"}, {"text": "interesting", "hl": True}]}, {"start": 30.0, "end": 31.0, "words": [{"text": "later"}]}]
    text = F.ass(caps, theme, {"width": 1920, "height": 1080}, 9.0, 20.0)
    assert "Dialogue: 0,0:00:01.00,0:00:02.50,Cap,,0,0,0,,an {\\c&H001F6AF2}interesting{\\c&H001A1A1A}" in text
    assert "later" not in text and "Style: Cap,Inter," in text
