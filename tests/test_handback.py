"""Text and cards over a picture hand the frame back: they leave after their sentence (1.5 to 3 s, pacing.dwell) or at the director's
until_word, and the rendered frame after that shows the picture again (the owner's issue, 2026-11-01: full-screen text never left)."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from vt.schema import Beat, Beats, ScenesFile, Transcript, Word


def _story(elements, backdrop=True):
    words = [Word(id=f"w{i}", text=f"word{i}", start=0.2 + i * 0.4, end=0.5 + i * 0.4) for i in range(1, 21)]
    beats = Beats(beats=[Beat(id="b1", word_ids=[f"w{i}" for i in range(1, 5)], start=0.6, end=2.1, text="one"),
                         Beat(id="b2", word_ids=[f"w{i}" for i in range(5, 21)], start=2.2, end=8.5, text="two")])
    sc = {"id": "s1", "beats": ["b1", "b2"], "layout": "stack", "elements": elements}
    if backdrop:
        sc["backdrop"] = {"media": "photo", "motion": "none"}
    return ScenesFile.model_validate({"scenes": [sc]}), Transcript(words=words), beats


def _compose(sf, tr, beats, media=None):
    from vt.compose.composer import resolve_composition
    from vt.project import load_theme

    media = media or {"photo": {"src": "media/photo.png", "kind": "image", "fx": 0.5, "fy": 0.5, "w": 900, "h": 1600, "trim": 0, "loop": False}}
    return resolve_composition(sf, tr, beats, load_theme("paper"), "9:16", 9.0, None, media=media)


def test_text_over_a_picture_leaves_after_its_sentence():
    sf, tr, beats = _story([{"type": "big_number", "value": "84%", "at_word": "w2"}])
    el = _compose(sf, tr, beats)["scenes"][0]["elements"][0]
    assert el["at"] + 1.5 <= el["until"] <= el["at"] + 3.0                # held through its sentence, then gone
    assert el["until"] <= 2.6                                             # sentence b1 ends at 2.1 s


def test_the_director_can_say_when_it_leaves():
    sf, tr, beats = _story([{"type": "title", "text": "Hold this", "at_word": "w2", "until_word": "w9"}])
    el = _compose(sf, tr, beats)["scenes"][0]["elements"][0]
    assert abs(el["until"] - (tr.by_id()["w9"].end + 0.15)) < 1e-6


def test_a_scene_without_a_picture_keeps_its_cards():
    sf, tr, beats = _story([{"type": "big_number", "value": "84%", "at_word": "w2"}], backdrop=False)
    assert "until" not in _compose(sf, tr, beats)["scenes"][0]["elements"][0]


def test_until_word_before_at_word_is_refused():
    from vt.schema import validate_scenes

    sf, tr, beats = _story([{"type": "title", "text": "x", "at_word": "w9", "until_word": "w2"}])
    assert any("comes before" in e for e in validate_scenes(sf, tr, beats, None))


@pytest.mark.slow
def test_rendered_frame_after_the_exit_shows_the_picture(tmp_path):
    from vt.compose.composer import write_composition
    from vt.project import load_theme
    from vt.render.hyperframes import BIN, snapshot

    if not BIN.exists():
        pytest.skip("HyperFrames is not installed")
    photo = tmp_path / "photo.png"
    Image.fromarray(np.full((1600, 900, 3), (40, 120, 200), "uint8")).save(photo)          # one flat blue picture: anything else on it is the card
    media = {"photo": {"src": "media/photo.png", "kind": "image", "fx": 0.5, "fy": 0.5, "w": 900, "h": 1600, "trim": 0, "loop": False, "_abs": str(photo)}}
    sf, tr, beats = _story([{"type": "big_number", "value": "84%", "label": "of people", "at_word": "w2"}])
    data = _compose(sf, tr, beats, media)
    data["captions"] = []
    until = data["scenes"][0]["elements"][0]["until"]
    idx = write_composition(tmp_path / "comp", data, load_theme("paper"))
    during, after = snapshot(idx.parent, tmp_path / "snap", [until - 0.4, until + 0.8], gpu=False)      # never the graphics card of the computer running the tests
    blue = np.array([40, 120, 200])

    def off_picture(p: Path) -> float:                    # share of the frame's centre that is not the picture
        im = np.asarray(Image.open(p).convert("RGB")).astype(int)
        h, w = im.shape[:2]
        mid = im[h // 4: 3 * h // 4, w // 6: 5 * w // 6]
        return float((np.abs(mid - blue).sum(axis=2) > 90).mean())

    assert off_picture(during) > 0.02                     # the number is on the picture
    assert off_picture(after) < 0.005                     # and then it is gone: only the picture


def test_a_long_card_scene_in_a_picture_video_gives_the_frame_back():
    words = [Word(id=f"w{i}", text=f"word{i}", start=0.2 + i * 0.4, end=0.5 + i * 0.4) for i in range(1, 31)]
    beats = Beats(beats=[Beat(id="b1", word_ids=[f"w{i}" for i in range(1, 8)], start=0.6, end=3.3, text="one"),
                         Beat(id="b2", word_ids=[f"w{i}" for i in range(8, 11)], start=3.4, end=4.5, text="two"),
                         Beat(id="b3", word_ids=[f"w{i}" for i in range(11, 31)], start=4.6, end=12.5, text="three")])
    sf = ScenesFile.model_validate({"scenes": [
        {"id": "s1", "beats": ["b1"], "layout": "stack", "elements": [], "backdrop": {"media": "photo", "motion": "none"}},
        {"id": "s2", "beats": ["b2", "b3"], "layout": "stack", "elements": [{"type": "big_number", "value": "84%", "at_word": "w8"}]}]})
    data = _compose(sf, Transcript(words=words), beats)
    card = data["scenes"][1]
    assert card["backdrop"]["media"] == "photo"                                    # the picture before it comes back
    assert card["start"] + 1.5 <= card["backdrop"]["from"] <= card["start"] + 3.6     # after the card's line, not at the scene's end
    assert card["elements"][0]["until"] == card["backdrop"]["from"]


def test_a_video_made_of_cards_keeps_its_cards():
    sf, tr, beats = _story([{"type": "big_number", "value": "84%", "at_word": "w2"}], backdrop=False)
    sc = _compose(sf, tr, beats)["scenes"][0]
    assert "backdrop" not in sc and "until" not in sc["elements"][0]
