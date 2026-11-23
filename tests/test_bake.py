"""O3 (docs/plans/PLAN-OPENMOTION.MD): a composition the runtime draws, baked into plain HyperFrames source, draws the same frames, with every animated
part in the source under a readable id, and nothing lost."""
from __future__ import annotations

import re

import pytest


@pytest.fixture(scope="module")
def baked(tmp_path_factory):
    from vt.bake import bake
    from vt.compose.composer import resolve_composition, write_composition
    from vt.project import load_theme
    from vt.render import hyperframes as H
    from vt.schema import Beat, Beats, ScenesFile, Transcript, Word

    try:
        H._browser()
    except Exception as e:                                                      # noqa: BLE001
        pytest.skip(f"HyperFrames has no browser here: {str(e)[:120]}")
    root = tmp_path_factory.mktemp("bake")
    words = [Word(id=f"w{i}", text=f"word{i}", start=0.2 + i * 0.3, end=0.45 + i * 0.3) for i in range(1, 30)]
    beats = Beats(beats=[Beat(id="b1", word_ids=[f"w{i}" for i in range(1, 10)], start=0.2, end=3.0, text="a"),
                         Beat(id="b2", word_ids=[f"w{i}" for i in range(10, 20)], start=3.0, end=6.0, text="b"),
                         Beat(id="b3", word_ids=[f"w{i}" for i in range(20, 30)], start=6.0, end=9.0, text="c")])
    sf = ScenesFile.model_validate({"planner": "claude", "scenes": [
        {"id": "s1", "beats": ["b1"], "layout": "stack", "elements": [{"type": "value_card", "value": "5", "label": "small settings", "at_word": "w1"}]},
        {"id": "s2", "beats": ["b2"], "layout": "stack", "transition_in": "wipe", "elements": [{"type": "definition", "term": "Every minute", "meaning": "more than most people need", "at_word": "w10"}]},
        {"id": "s3", "beats": ["b3"], "layout": "stack", "transition_in": "slide_up", "elements": [{"type": "steps", "items": [{"title": "Notifications", "detail": "never read"}, {"title": "Bright screen", "detail": ""}], "at_word": "w20"}]},
    ]})
    theme = load_theme("paper")
    data = resolve_composition(sf, Transcript(words=words), beats, theme, "9:16", 9.5, None, media={})
    comp = write_composition(root / "comp", data, theme).parent
    got = bake(comp, root / "baked")
    return comp, root / "baked", got


def test_nothing_is_lost_and_every_part_is_in_the_source(baked):
    comp, out, got = baked
    assert got["lost_count"] == 0, got["lost"]
    html = "\n".join(p.read_text(encoding="utf-8") for p in [out / "index.html", *sorted((out / "scenes").glob("*.html"))])   # the root and each scene
    assert "runtime/vt.js" not in html and "window.__VT__" not in html, "the baked page needs no runtime"
    for part in ("s1-", "s2-defn-term", "s3-step-num"):
        assert f'id="{part}' in html, part
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids)), "ids are unique"
    assert all(f'data-hf-id="hf-{i}"' in html for i in ("s2-defn-term", "s2-defn-meaning"))
    assert len(html) < 400_000


def test_each_scene_is_its_own_composition(baked):
    """S4 (docs/plans/PLAN-SCENE-TOOLS.MD): a host per scene in the root page, at the scene's window; the scene and its animation in scenes/<id>.html,
    timed from the scene's start. Nothing of a scene starts before its window."""
    comp, out, got = baked
    page = (out / "index.html").read_text(encoding="utf-8")
    assert got["scenes"] == 3 and not got["early"], got["early"]
    hosts = re.findall(r'<div id="scene-(s\d+)" data-composition-id="scene-\1" data-composition-src="scenes/\1\.html" data-start="([\d.]+)" data-duration="([\d.]+)"', page)
    assert [h[0] for h in hosts] == ["s1", "s2", "s3"], hosts
    assert float(hosts[0][1]) == 0 and 2.5 < float(hosts[1][1]) < 3.5 and 5.5 < float(hosts[2][1]) < 6.5
    s2 = (out / "scenes" / "s2.html").read_text(encoding="utf-8")
    assert 'data-composition-id="scene-s2"' in s2 and 'id="s2-defn-term"' in s2 and 'window.__timelines["scene-s2"] = ts' in s2
    assert "s2-defn-term" not in page, "the root holds no scene parts or their animation"
    starts = [float(x) for x in re.findall(r",\s*([\d.]+)\);", s2)]
    assert starts and max(starts) < 4, "scene times count from the scene's start"


def test_the_baked_page_draws_the_same_frames(baked):
    from PIL import Image, ImageChops, ImageStat

    from vt.render.hyperframes import snapshot

    comp, out, _ = baked
    times = [0.4, 1.5, 3.4, 5.0, 6.5, 8.5]
    a = sorted(snapshot(comp, comp.parent / "fa", times, gpu=False))
    b = sorted(snapshot(out, comp.parent / "fb", times, gpu=False))
    assert len(a) == len(b) == len(times)
    for t, x, y in zip(times, a, b):
        d = ImageChops.difference(Image.open(x).convert("RGB"), Image.open(y).convert("RGB"))
        assert sum(ImageStat.Stat(d).mean) / 3 < 0.05, f"frame at {t}s differs"


def test_captions_are_their_own_composition(baked):
    comp, out, _ = baked
    page = (out / "index.html").read_text(encoding="utf-8")
    caps = (out / "compositions" / "captions.html").read_text(encoding="utf-8")
    assert re.search(r'<div id="captions" data-composition-id="captions" data-composition-src="compositions/captions\.html"', page)
    assert not (out / "captions.html").exists(), "one page at the top: HyperFrames takes every top-level page with a composition for a root"
    assert 'class="cap-layer"' not in page and 'class="cap-layer"' in caps
    assert 'data-composition-id="captions"' in caps and "window.__timelines.captions = tc" in caps
