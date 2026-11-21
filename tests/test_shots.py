"""Code-native shots (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD, C1): a shot is HTML an agent wrote, plus the visual editor's overrides, which are checked,
written in as CSS and text without touching the shot's code, and rendered by our renderer with the shot's own animation intact."""
import shutil
from pathlib import Path

import pytest

from vt import shots

SPIKE = Path(__file__).resolve().parents[1] / "docs" / "dev" / "spikes" / "html-shot"


@pytest.fixture()
def shot(tmp_path):
    d = tmp_path / "shots" / "intro"
    d.mkdir(parents=True)
    for name in ("index.html", "shot.json"):
        shutil.copy(SPIKE / name, d / name)
    return d


def test_a_shot_says_what_it_is_and_which_elements_can_be_selected(shot):
    i = shots.info(shot)
    assert (i["duration"], i["width"], i["height"], i["root"]) == (3.0, 1920, 1080, "root")
    assert [k["name"] for k in i["knobs"]] == ["--bg", "--ink", "--accent", "--title-size"]
    assert shots.ids_in((shot / "index.html").read_text(encoding="utf-8")) == ["orb", "title", "sub", "bar"]


def test_a_shot_without_a_timed_root_is_refused(tmp_path):
    (tmp_path / "index.html").write_text("<html><body><div>no root</div></body></html>", encoding="utf-8")
    with pytest.raises(shots.ShotError, match="data-composition-id"):
        shots.info(tmp_path)


def test_overrides_become_css_that_adds_to_the_animation():
    o = shots.check_overrides({"knobs": {"--accent": "#22c55e"},
                               "elements": {"title": {"x": 10, "y": -40.5, "scale": 1.2, "rotate": 3, "style": {"fontWeight": "700", "opacity": 0.5}},
                                            "bar": {"hidden": True}}})
    css = shots.overrides_css(o)
    assert ":root{--accent:#22c55e !important;}" in css
    assert '[data-vt-id="title"]{translate:10px -40.5px !important;scale:1.2 !important;rotate:3deg !important;font-weight:700 !important;opacity:0.5 !important;}' in css
    assert '[data-vt-id="bar"]{display:none !important;}' in css
    assert "transform" not in css, "the shot animates transform; the editor uses translate/scale/rotate so both apply"


@pytest.mark.parametrize("bad", [
    {"knobs": {"accent": "red"}},                                            # not a CSS variable
    {"knobs": {"--accent": "red;} body{display:none"}},                     # breaking out of the rule
    {"knobs": {"--accent": "url(</style><script>alert(1)</script>)"}},
    {"elements": {"title\"]{}": {"x": 1}}},                                  # a selector break-out in the id
    {"elements": {"title": {"onclick": "x"}}},                               # a field the editor does not have
    {"elements": {"title": {"style": {"color": "red; background:url(x)"}}}},
    {"elements": {"title": {"style": {"position": "fixed"}}}},
    {"elements": {"title": {"x": float("nan")}}},
    {"elements": {"title": {"scale": 0}}},
    {"elements": {"title": {"hidden": "yes"}}},
    {"elements": {"title": {"text": "x" * 3000}}},
    {"timing": {}},
])
def test_overrides_that_could_break_the_page_are_refused(bad):
    with pytest.raises(shots.ShotError):
        shots.check_overrides(bad)


def test_build_adds_the_csp_the_css_and_the_text_before_the_shots_script(shot, tmp_path):
    shots.save_overrides(shot, {"elements": {"title": {"text": "Sleep is a habit </script><b>x"}}, "knobs": {"--bg": "#fffaf0"}})
    out = shots.build(shot, tmp_path / "build")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'http-equiv="Content-Security-Policy"' in html and "default-src 'self'" in html
    assert html.index('<style id="vt-overrides">') < html.index("</head>")
    assert "Sleep is a habit <\\/script><b>x" in html, "the text cannot close the script"
    assert html.index("Sleep is a habit") < html.index('<script src="runtime/gsap.min.js">'), "text first, then the timeline that may measure it"
    assert (out / "runtime" / "gsap.min.js").exists() and (out / "fonts" / "fonts.css").exists()
    original = (shot / "index.html").read_text(encoding="utf-8")
    assert "Sleep is a habit" not in original, "the visual editor never rewrites the shot's code"


def test_saved_overrides_are_read_back_checked(shot):
    shots.save_overrides(shot, {"elements": {"orb": {"x": -140, "scale": 0.8}}})
    assert shots.read_json(shot / "overrides.json", {})["elements"]["orb"] == {"x": -140.0, "scale": 0.8}
    (shot / "overrides.json").write_text('{"elements": {"orb": {"x": "1px; color:red"}}}', encoding="utf-8")
    with pytest.raises(shots.ShotError):
        shots.build(shot, shot.parent / "b")


@pytest.mark.slow
@pytest.mark.browser
def test_the_rendered_frame_shows_the_edits_and_is_the_same_every_time(shot, tmp_path):
    from PIL import Image

    edits = {"knobs": {"--bg": "#fffaf0", "--accent": "#22c55e"}, "elements": {"title": {"text": "Sleep is a habit", "y": -40}, "sub": {"hidden": True}}}
    a = shots.frames(shot, tmp_path / "a", [2.0], overrides=edits)
    b = shots.frames(shot, tmp_path / "b", [2.0], overrides=edits)
    plain = shots.frames(shot, tmp_path / "plain", [2.0], overrides={})
    assert a and b and plain
    ia, ib, ip = (Image.open(p).convert("RGB") for p in (a[0], b[0], plain[0]))
    assert list(ia.getdata()) == list(ib.getdata()), "the same moment draws the same pixels twice"
    corner = (10, 10)
    assert ip.getpixel(corner) == (15, 18, 38), "the shot's own background"
    assert ia.getpixel(corner) == (255, 250, 240), "the knob changed the background"
    w, h = ia.size
    orb = ia.getpixel((int(1570 * w / 1920), int(560 * h / 1080)))
    assert orb[1] > orb[0] and orb[1] > orb[2], f"the accent knob made the orb green: {orb}"
    sub_row = [ia.getpixel((int(x * w / 1920), int(585 * h / 1080))) for x in range(170, 900, 20)]
    assert all(px == (255, 250, 240) for px in sub_row), "the hidden subtitle is gone"
