"""Caption style per video: "auto" gives vertical videos the bold pop captions, wide ones keep the theme's own style."""
import pytest

from vt.compose.composer import compose_project
from vt.util import read_json


@pytest.mark.parametrize("choice,aspect,want,wpl", [("auto", "9:16", "pop", 3), ("auto", "16:9", None, None), ("pop", "16:9", "pop", 3), ("theme", "9:16", None, None)])
def test_caption_style_choice(ref, choice, aspect, want, wpl):
    p = ref
    m = p.meta()
    theme_style = None
    m.options.caption_style = choice
    p.save_meta(m)
    out = compose_project(p, aspect=aspect)
    cap = read_json((out if out.is_dir() else out.parent) / "data.json")["theme"]["caption"]
    from vt.project import load_theme

    theme_style = load_theme(p.scenes().theme or m.theme).caption
    assert cap["style"] == (want or theme_style.style)
    assert cap["words_per_line"] == (wpl or theme_style.words_per_line)


def test_pages_give_each_new_picture_the_whole_screen():
    from vt.compose.composer import paginate

    sc = {"id": "s1", "start": 0.0, "end": 9.0, "transition_in": "slide_up", "elements": [
        {"type": "sticker", "at": 0.0}, {"type": "tag", "at": 0.1},          # arrive together: one shot
        {"type": "sticker", "at": 0.6},                                       # too soon for a new shot
        {"type": "sticker", "at": 3.0}, {"type": "keyword", "at": 6.0}], "sfx": [{"t": 3.5, "id": "pop"}]}
    out = paginate([sc], "9:16")
    assert [len(p["elements"]) for p in out] == [3, 1, 1]
    assert [(p["start"], p["end"]) for p in out] == [(0.0, 3.0), (3.0, 6.0), (6.0, 9.0)]
    assert out[0]["id"] == "s1" and out[1]["id"] == "s1p2" and out[1]["transition_in"] == "fade" and out[1]["sfx"] == [{"t": 3.5, "id": "pop"}]
    sp = paginate([{**sc, "stick": {"x": 1}}], "9:16")          # stick figures: pages too, cut (the figures continue), never faded
    assert len(sp) == 3 and [p.get("transition_in") for p in sp[1:]] == ["cut", "cut"] and all(p.get("cont") for p in sp[1:]) and all(p["stick"] == {"x": 1} for p in sp)


def test_an_infographic_build_up_stays_on_one_screen():
    from vt.compose.composer import paginate

    # the owner's reference look: title, value card, arrow, a row of coins and a tag building up together
    sc = {"id": "s2", "start": 2.0, "end": 12.0, "elements": [{"type": t, "at": 2.0 + 2 * i} for i, t in enumerate(["title", "value_card", "arrow", "icon_row", "tag"])]}
    assert paginate([sc], "9:16") == [sc]


def test_one_list_among_separate_pictures_still_gets_pages():
    # the owner's podcast clip (2026-10-24): a list, a stamp, a tag and a sticker shared one screen at 40 % size
    from vt.compose.composer import paginate

    sc = {"id": "s10", "start": 39.5, "end": 44.8, "elements": [{"type": "list", "at": 39.9}, {"type": "keyword", "at": 40.7},
                                                                 {"type": "tag", "at": 42.3}, {"type": "sticker", "at": 44.3}]}
    assert len(paginate([sc], "9:16")) >= 3


def test_pictures_before_a_build_up_get_their_own_shot():
    # the owner's compound-interest story (2026-10-24): a piggy bank, a tag, a $100 card and 10 % were kept small on one screen
    from vt.compose.composer import paginate

    sc = {"id": "s3", "start": 3.0, "end": 12.0, "elements": [{"type": "sticker", "at": 3.2}, {"type": "tag", "at": 3.3},
                                                               {"type": "value_card", "at": 6.0}, {"type": "big_number", "at": 7.5}]}
    a, b = paginate([sc], "9:16")
    assert [e["type"] for e in a["elements"]] == ["sticker", "tag"] and a["end"] == 6.0
    assert [e["type"] for e in b["elements"]] == ["value_card", "big_number"] and b["start"] == 6.0 and b["cont"]


def test_a_long_build_up_is_cut_in_two_at_its_biggest_pause():
    from vt.compose.composer import paginate

    sc = {"id": "s3", "start": 3.76, "end": 9.78, "elements": [{"type": "sticker", "at": 3.82}, {"type": "value_card", "at": 4.78},
                                                                 {"type": "ring", "at": 5.77}, {"type": "arrow", "at": 7.78}, {"type": "value_card", "at": 8.67}]}
    out = paginate([sc], "9:16")
    assert [[e["type"] for e in p["elements"]] for p in out][-1] == ["arrow", "value_card"] and len(out) >= 2
