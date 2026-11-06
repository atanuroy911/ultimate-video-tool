"""Plan step E17 (human in the loop): every element can be transformed by hand, in the data and on the real page.

The data: every field validates, defaults change nothing, an element with something set is a free element (no rule moves it). The page: each field changes what the real composition draws,
measured on the element's own box and styles (a headless browser with software drawing, no graphics card; skipped when HyperFrames has no browser here), keyframes move it, and the
preview and the export are the same code."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from vt.schema import Title, Transform, has_transform

AT = 3.0
BASE = {"type": "title", "text": "Hello", "at_word": "w1", "x": 0.5, "y": 0.5}

PROBE = """(() => {
  const w = document.querySelector('.el[data-el="0"]'), position = w.closest('.free-position'), shape = w.parentElement;
  const r = w.getBoundingClientRect(), cs = getComputedStyle(position), ss = getComputedStyle(shape);
  return { box: [r.left, r.top, r.width, r.height], transform: cs.transform, origin: cs.transformOrigin, filter: cs.filter, blend: cs.mixBlendMode, opacity: cs.opacity,
           shapeDisplay: ss.display, shapeTransform: ss.transform, clip: ss.clipPath };
})()"""


# ---- the data ---------------------------------------------------------------------------------------------------------------------------------------------------------------


def test_nothing_is_set_by_default_and_an_element_without_a_transform_is_not_free():
    assert Transform().is_neutral() and not has_transform(Transform()) and not has_transform(None)
    t = Title(text="x", at_word="w1")
    assert t.transform is None and not has_transform(t.transform)


@pytest.mark.parametrize("field,value", [("stretch_x", 1.5), ("stretch_y", 0.5), ("skew_x", 20), ("skew_y", -20), ("flip_x", True), ("flip_y", True), ("pivot_x", 0), ("pivot_y", 1),
                                         ("tilt_x", 40), ("tilt_y", -40), ("blur", 8), ("blend", "multiply"), ("crop_radius", 0.5),
                                         ("warp", [[0.1, 0], [0, 0], [0, 0], [0, 0]]), ("crop", [0.1, 0, 0, 0.2])])
def test_each_field_is_something_set(field, value):
    t = Transform(**{field: value})
    assert has_transform(t) and t.model_dump(exclude_defaults=True) == {field: value}
    e = Title(text="x", at_word="w1", transform={field: value})
    assert Title.model_validate(e.model_dump()).transform == e.transform, "it round-trips"


@pytest.mark.parametrize("bad", [{"stretch_x": 0}, {"stretch_y": 9}, {"skew_x": 80}, {"tilt_y": 90}, {"blur": 100}, {"blend": "glow"}, {"pivot_x": 2}, {"warp": [[0, 0]] * 3},
                                 {"warp": [[0, 0], [0, 0], [0, 0], [0, 2]]}, {"crop": [0.6, 0, 0.6, 0]}, {"crop": [0.1, 0.1, 0.1]}, {"crop_radius": 2}, {"nonsense": 1}])
def test_a_value_that_cannot_be_drawn_is_refused_in_a_sentence(bad):
    with pytest.raises(ValueError):
        Transform(**bad)


def test_an_element_with_a_transform_is_composed_as_a_free_element():
    from vt.compose.composer import resolve_composition
    from vt.project import load_theme
    from vt.schema import Beat, Beats, ScenesFile, Transcript, Word

    words = [Word(id=f"w{i}", text=f"w{i}", start=0.3 + i * 0.4, end=0.6 + i * 0.4) for i in range(1, 5)]
    beats = Beats(beats=[Beat(id="b1", word_ids=[w.id for w in words], start=0.3, end=2.5, text="x")])

    def composed(**transform):
        sf = ScenesFile.model_validate({"planner": "claude", "scenes": [{"id": "s1", "beats": ["b1"], "elements": [{"type": "title", "text": "Hello", "at_word": "w1", **({"transform": transform} if transform else {})}]}]})
        return resolve_composition(sf, Transcript(words=words), beats, load_theme("paper"), "9:16", 3.0, None, media={})["scenes"][0]["elements"][0]

    assert not composed().get("free") and not composed(stretch_x=1).get("free"), "a neutral transform changes nothing"
    for t in ({"stretch_x": 1.2}, {"flip_y": True}, {"blur": 3}, {"blend": "screen"}, {"warp": [[0, 0.1], [0, 0], [0, 0], [0, 0]]}, {"crop": [0, 0, 0.2, 0]}):
        assert composed(**t).get("free") is True and composed(**t)["transform"], t


def test_keyframes_carry_the_new_values_and_old_ones_stay_valid():
    from vt.visual_motion import MotionPoint

    p = MotionPoint(time=1, stretch_x=2, skew_y=10, tilt_x=30, blur=4)
    assert (p.stretch_x, p.skew_y, p.tilt_x, p.blur) == (2, 10, 30, 4)
    old = MotionPoint(time=1, x=0.2, y=0.3, scale=1.1, rotation=5, opacity=0.5)
    assert (old.stretch_x, old.stretch_y, old.skew_x, old.tilt_y, old.blur) == (1, 1, 0, 0, 0), "a point written before these existed means what it meant"


# ---- the real page ----------------------------------------------------------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    """page(transform, keyframes=None, at=AT, **element): what the real composition draws for one title carrying that transform: its box on the frame and the styles of its layers."""
    from vt.compose.composer import resolve_composition, write_composition
    from vt.project import load_theme
    from vt.render import hyperframes as H
    from vt.schema import Beat, Beats, ScenesFile, Transcript, Word

    try:
        H._browser()
    except Exception as e:                                                      # noqa: BLE001
        pytest.skip(f"HyperFrames has no browser here: {str(e)[:120]}")
    root = tmp_path_factory.mktemp("transform")
    words = [Word(id=f"w{i}", text=f"w{i}", start=0.3 + i * 0.4, end=0.6 + i * 0.4) for i in range(1, 9)]
    beats = Beats(beats=[Beat(id="b1", word_ids=[w.id for w in words], start=0.3, end=4.0, text="x")])
    theme = load_theme("paper")
    seen: dict = {}

    def look(transform=None, keyframes=None, at=AT, **element):
        key = repr((transform, keyframes, at, sorted(element.items())))
        if key not in seen:
            el = {**BASE, **element, **({"transform": transform} if transform else {}), **({"keyframes": keyframes} if keyframes else {})}
            sf = ScenesFile.model_validate({"planner": "claude", "scenes": [{"id": "s1", "beats": ["b1"], "layout": "stack", "elements": [el]}]})
            data = resolve_composition(sf, Transcript(words=words), beats, theme, "9:16", 5.0, None, media={})
            data["captions"] = []
            comp = write_composition(root / f"c{len(seen)}", data, theme).parent
            seen[key] = H.probe(comp, PROBE, at)
        return seen[key]

    return look


def close(a, b, tol=2.0):
    return abs(a - b) <= tol


def test_stretch_changes_the_width_and_the_height_apart(page):
    base, wide, tall = page(), page({"stretch_x": 2}), page({"stretch_y": 2})
    assert close(wide["box"][2], base["box"][2] * 2, 4) and close(wide["box"][3], base["box"][3], 2), (base["box"], wide["box"])
    assert close(tall["box"][3], base["box"][3] * 2, 4) and close(tall["box"][2], base["box"][2], 2), (base["box"], tall["box"])


def test_a_slant_widens_the_box_the_way_a_slanted_box_is(page):
    base, slanted = page(), page({"skew_x": 30})
    expected = base["box"][2] + base["box"][3] * math.tan(math.radians(30))
    assert close(slanted["box"][2], expected, 6) and close(slanted["box"][3], base["box"][3], 2), (base["box"], slanted["box"], expected)
    up = page({"skew_y": 30})
    assert up["box"][3] > base["box"][3] + 10


def test_a_flip_mirrors_without_moving_or_resizing(page):
    base, flipped = page(), page({"flip_x": True, "flip_y": True})
    assert [round(n) for n in flipped["box"]] == [round(n) for n in base["box"]]
    numbers = [float(n) for n in flipped["transform"][flipped["transform"].index("(") + 1:-1].split(",")]
    a, d = (numbers[0], numbers[5]) if flipped["transform"].startswith("matrix3d") else (numbers[0], numbers[3])
    assert a < 0 and d < 0, flipped["transform"]


def test_the_pivot_is_what_it_turns_around(page):
    centre, left = page(rotation=90, transform={"pivot_x": 0.5, "pivot_y": 0.5}), page(rotation=90, transform={"pivot_x": 0, "pivot_y": 0.5})
    assert close(centre["box"][0] + centre["box"][2] / 2, centre["box"][0] + centre["box"][2] / 2)
    cx = lambda p: p["box"][0] + p["box"][2] / 2     # noqa: E731
    cy = lambda p: p["box"][1] + p["box"][3] / 2     # noqa: E731
    base = page(rotation=90)
    assert close(cx(centre), cx(base), 2) and close(cy(centre), cy(base), 2), "pivot in the middle is the way it always turned"
    assert abs(cx(left) - cx(centre)) > 20 or abs(cy(left) - cy(centre)) > 20, "pivot at the left edge swings it around that edge"


def test_a_tilt_foreshortens_the_box(page):
    base, away = page(), page({"tilt_x": 50})
    assert away["box"][3] < base["box"][3] * 0.9, (base["box"], away["box"])
    side = page({"tilt_y": 50})
    assert side["box"][2] < base["box"][2] * 0.9, (base["box"], side["box"])


def test_a_corner_pin_moves_the_four_corners(page):
    base = page()
    pinned = page({"warp": [[0.5, 0], [0, 0], [0, 0], [0, 0]]})                # the top left corner goes half its width to the right
    assert pinned["shapeDisplay"] == "block" and pinned["shapeTransform"].startswith("matrix3d"), pinned
    assert base["shapeDisplay"] == "contents" and base["shapeTransform"] == "none"
    far = page({"warp": [[0, 0], [0, 0], [0.3, 0.6], [0, 0]]})
    assert far["box"][3] > base["box"][3] * 1.3, (base["box"], far["box"])         # the bottom right corner goes down by 0.6 of its height


def test_a_crop_cuts_with_rounded_corners_and_blur_and_blend_are_set(page):
    cut = page({"crop": [0.1, 0.2, 0.3, 0.4], "crop_radius": 0.5})
    assert cut["clip"].startswith("inset(") and "10%" in cut["clip"] and "round" in cut["clip"], cut["clip"]
    mixed = page({"blur": 6, "blend": "multiply"})
    assert "blur(6px)" in mixed["filter"] and mixed["blend"] == "multiply"
    plain = page()
    assert plain["filter"] == "none" and plain["blend"] == "normal" and page()["clip"] == "none"


def test_keyframes_move_the_new_values_on_the_video_clock(page):
    frames = [{"time": 1.0, "x": 0.5, "y": 0.5, "stretch_x": 1, "ease": "linear"}, {"time": 4.0, "x": 0.5, "y": 0.5, "stretch_x": 3, "ease": "linear"}]
    early, middle, late = page(keyframes=frames, at=1.0), page(keyframes=frames, at=2.5), page(keyframes=frames, at=4.0)
    assert early["box"][2] < middle["box"][2] < late["box"][2] and close(late["box"][2], early["box"][2] * 3, 6), (early["box"], middle["box"], late["box"])


def test_an_old_element_draws_as_it_did(page):
    base = page()
    again = page(scale=1, rotation=0, opacity=1)
    assert [round(n) for n in again["box"]] == [round(n) for n in base["box"]]
    assert page(scale=2)["box"][2] > base["box"][2] * 1.8 and page(rotation=45)["box"][2] != base["box"][2] and float(page(opacity=0.5)["opacity"]) == 0.5


# ---- what a person has placed by hand is theirs: no rule moves it, and the export draws what the preview draws ---------------------------------------------------------------


def test_recomposing_keeps_every_field_of_a_transformed_element(ref):
    import json

    from vt.compose import compose_project
    from vt.schema import ScenesFile

    mine = {"type": "title", "text": "Mine", "at_word": ref.beats().beats[0].word_ids[0], "x": 0.4, "y": 0.3, "edited": True,
            "transform": {"stretch_x": 1.4, "skew_x": 12, "tilt_y": 20, "flip_x": True, "pivot_x": 0.2, "blur": 3, "blend": "multiply", "crop": [0.1, 0, 0, 0.2], "crop_radius": 0.3,
                          "warp": [[0, 0], [0.1, 0], [0, 0.1], [0, 0]]}}
    plan = ref.scenes().model_dump()
    plan["scenes"][0]["elements"].append(mine)
    ref.save_scenes(ScenesFile.model_validate(plan))
    for _ in range(2):                                                   # composing again changes nothing of what was set
        data = json.loads((compose_project(ref, "9:16").parent / "data.json").read_text(encoding="utf-8"))
        el = next(e for s in data["scenes"] for e in s["elements"] if e.get("text") == "Mine")
        assert el["free"] is True and el["x"] == 0.4 and el["y"] == 0.3
        assert el["transform"]["stretch_x"] == 1.4 and el["transform"]["warp"] == [[0, 0], [0.1, 0], [0, 0.1], [0, 0]] and el["transform"]["crop"] == [0.1, 0, 0, 0.2] and el["transform"]["flip_x"] is True


@pytest.fixture(scope="module")
def crowd_with_one_of_mine(tmp_path_factory):
    from vt.compose.composer import resolve_composition, write_composition
    from vt.project import load_theme
    from vt.render import hyperframes as H
    from vt.schema import Beat, Beats, ScenesFile, Transcript, Word

    try:
        H._browser()
    except Exception as e:                                                      # noqa: BLE001
        pytest.skip(f"HyperFrames has no browser here: {str(e)[:120]}")
    words = [Word(id=f"w{i}", text=f"w{i}", start=0.3 + i * 0.4, end=0.6 + i * 0.4) for i in range(1, 9)]
    beats = Beats(beats=[Beat(id="b1", word_ids=[w.id for w in words], start=0.3, end=4.0, text="x")])
    crowd = [{"type": "sticker", "emoji": "1f4b0", "label": "money", "at_word": "w1"}, {"type": "sticker", "emoji": "1f3e0", "label": "house", "at_word": "w1"},
             {"type": "sticker", "emoji": "1f697", "label": "car", "at_word": "w2"}, {"type": "tag", "text": "interest rate", "at_word": "w2"},
             {"type": "keyword", "text": "Mortgage", "at_word": "w3"}, {"type": "icon", "name": "coin", "at_word": "w3"},
             {"type": "tag", "text": "down payment", "at_word": "w4", "transform": {"blur": 1}}]               # the last tag is the person's: a blur is set, so it is placed by hand
    sf = ScenesFile.model_validate({"planner": "rules", "scenes": [{"id": "s1", "beats": ["b1"], "layout": "side", "elements": crowd}]})
    theme = load_theme("paper")
    data = resolve_composition(sf, Transcript(words=words), beats, theme, "16:9", 5.0, None, media={})
    data["captions"] = []
    comp = write_composition(tmp_path_factory.mktemp("rules") / "c", data, theme).parent
    return H.probe(comp, """(() => { const els = [...document.querySelectorAll('.el')], shown = els.map(() => false);
      for (const t of [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5]) { window.__vt.seek(t); els.forEach((w, i) => { if (getComputedStyle(w).display !== 'none') shown[i] = true; }); }
      return { guard: window.__guard || [], items: els.map((w, i) => ({ el: w.getAttribute('data-el'), type: [...w.classList].find((c) => c.startsWith('el-')).slice(3), shown: shown[i], free: !!w.closest('.free-shape') })) }; })()""", AT)


def test_no_rule_hides_or_fits_an_element_the_person_transformed(crowd_with_one_of_mine):
    look = crowd_with_one_of_mine
    assert any(g["rule"] == "too-small" and g["fix"] == "dropped" for g in look["guard"]), "the crowd trips the guard for the automatic tag, as it should"
    mine = [i for i in look["items"] if i["free"]]
    assert len(mine) == 1 and mine[0]["shown"], "the tag the person transformed stays, where the rules dropped the automatic one"
    assert not [g for g in look["guard"] if g.get("el") == mine[0]["el"]], "and the guard does not even look at it"


def test_the_export_draws_what_the_preview_draws(tmp_path):
    import numpy as np
    from PIL import Image

    from vt.compose.composer import resolve_composition, write_composition
    from vt.project import load_theme
    from vt.render import hyperframes as H
    from vt.schema import Beat, Beats, ScenesFile, Transcript, Word

    try:
        H._browser()
    except Exception as e:                                                      # noqa: BLE001
        pytest.skip(f"HyperFrames has no browser here: {str(e)[:120]}")
    words = [Word(id=f"w{i}", text=f"w{i}", start=0.3 + i * 0.4, end=0.6 + i * 0.4) for i in range(1, 9)]
    beats = Beats(beats=[Beat(id="b1", word_ids=[w.id for w in words], start=0.3, end=4.0, text="x")])
    theme = load_theme("paper")

    def make(name, **transform):
        el = {"type": "title", "text": "Hello", "at_word": "w1", "x": 0.5, "y": 0.5, **({"transform": transform} if transform else {})}
        sf = ScenesFile.model_validate({"planner": "claude", "scenes": [{"id": "s1", "beats": ["b1"], "layout": "stack", "elements": [el]}]})
        data = resolve_composition(sf, Transcript(words=words), beats, theme, "9:16", 5.0, None, media={})
        data["captions"] = []
        return write_composition(tmp_path / name, data, theme).parent

    def frames(comp, name):
        export = np.asarray(Image.open(H.snapshot(comp, tmp_path / f"{name}-snap", [AT], gpu=False)[0]).convert("RGB")).astype("int16")
        H.probe(comp, "1", AT, screenshot=tmp_path / f"{name}.png")
        preview = np.asarray(Image.open(tmp_path / f"{name}.png").convert("RGB")).astype("int16")
        return export, preview

    plain = frames(make("plain"), "plain")
    worn = frames(make("worn", warp=[[0.3, 0], [0, 0.2], [0, 0], [0, 0]], tilt_y=25, skew_x=12, crop=[0.1, 0, 0, 0.1], crop_radius=0.4, blur=2), "worn")
    for export, preview in (plain, worn):
        assert export.shape == preview.shape, (export.shape, preview.shape)
        assert float(np.abs(export - preview).mean()) < 2.5, f"the export and the preview differ by {float(np.abs(export - preview).mean()):.2f}"
    assert float(np.abs(worn[0] - plain[0]).mean()) > 0.4, "the transform really changed the export"

