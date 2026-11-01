import pytest

from vt import designer
from vt.designer import PALETTES, STYLES, build_theme, contrast, surprise


@pytest.mark.parametrize("style", list(STYLES))
@pytest.mark.parametrize("palette", list(PALETTES))
def test_every_style_and_palette_is_valid_and_readable(style, palette):
    t = build_theme(style, palette)
    c = t.color
    assert contrast(c.ink, c.bg) >= 4.5 and contrast(c.caption_ink, c.caption_bg) >= 4.5
    assert contrast(c.highlight_ink, c.highlight_bg) >= 4.5 and contrast(c.tag_ink, c.tag_bg) >= 4.5
    assert t.style == style and t.palette == palette


def test_surprise_is_reproducible_and_dark_filter_works():
    assert surprise(7).model_dump() == surprise(7).model_dump()
    assert len({surprise(i).label for i in range(30)}) > 8
    assert all(PALETTES[surprise(i, dark=True).palette]["dark"] for i in range(10))


def test_overrides_and_catalogue():
    t = build_theme("soft", "mint", name="mine", overrides={"shape": {"radius": 12}, "currency": "$"})
    assert t.name == "mine" and t.shape.radius == 12 and t.currency == "$" and t.shape.shadow.blur > 0
    with pytest.raises(ValueError):
        build_theme("nope", "mint")
    cat = designer.catalogue()
    assert len(cat["styles"]) >= 10 and len(cat["palettes"]) >= 18


def test_hue_shift_keeps_text_readable():
    t = designer.hue_shift(build_theme("brutalist", "marigold"), 120)
    assert t.color.accent != "#f26a1f" and contrast(t.color.highlight_ink, t.color.highlight_bg) >= 4.5
