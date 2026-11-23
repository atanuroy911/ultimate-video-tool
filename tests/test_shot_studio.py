"""O2: a shot edited in the HyperFrames Studio (docs/plans/PLAN-OPENMOTION.MD). The working copy, taking the edits back, and the real Studio starting."""
from __future__ import annotations

import json
import urllib.request

import pytest

from vt import shot_studio as ST
from vt import shots as SH

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>#t{position:absolute;left:10px;top:20px}</style></head><body>
<div id="root" data-composition-id="root" data-start="0" data-duration="2" data-width="1080" data-height="1920">
<div id="t" data-vt-id="t">Hello</div></div>
<script src="runtime/gsap.min.js"></script><script>window.__timelines={root:gsap.timeline({paused:true})};</script></body></html>"""


def _shot(tmp_path):
    d = tmp_path / "shots" / "s1"
    d.mkdir(parents=True)
    (d / "index.html").write_text(PAGE, encoding="utf-8")
    (d / "overrides.json").write_text(json.dumps({"version": 1, "knobs": {}, "elements": {"t": {"x": 40}}}), encoding="utf-8")
    return d


def test_working_copy_shows_theme_and_edits_and_they_never_come_back(tmp_path):
    d = _shot(tmp_path)
    work = ST.prepare(d, {"--vt-bg": "#101010"})
    html = (work / "index.html").read_text(encoding="utf-8")
    assert ST.BEGIN in html and "--vt-bg:#101010" in html and 'translate:40px 0px' in html
    assert (work / "runtime" / "gsap.min.js").exists()
    # the person retypes the title in the Studio
    (work / "index.html").write_text(html.replace(">Hello<", ">Hi there<"), encoding="utf-8")
    got = ST.take_back(d, work)
    assert got == {"saved": True, "changed": True, "assets": []}
    back = (d / "index.html").read_text(encoding="utf-8")
    assert "Hi there" in back and ST.BEGIN not in back and "vt-theme" not in back and "translate" not in back
    assert SH.info(d)["duration"] == 2


def test_broken_edit_is_refused_and_new_pictures_come_back(tmp_path):
    d = _shot(tmp_path)
    work = ST.prepare(d)
    (work / "assets").mkdir()
    (work / "assets" / "logo.png").write_bytes(b"png")
    assert ST.take_back(d, work)["assets"] == ["assets/logo.png"]
    (work / "index.html").write_text("<html><body>no root</body></html>", encoding="utf-8")
    got = ST.take_back(d, work)
    assert got["saved"] is False and "timed" in got["reason"]
    assert "Hello" in (d / "index.html").read_text(encoding="utf-8")


def test_real_studio_starts_on_localhost_and_stops(tmp_path):
    from vt.render.hyperframes import BIN

    if not BIN.exists():
        pytest.skip("HyperFrames is not installed")
    d = _shot(tmp_path)
    try:
        s = ST.open_shot("p/s1", d)
        assert s["open"] and s["url"].startswith("http://127.0.0.1:")
        with urllib.request.urlopen(f"http://127.0.0.1:{s['port']}/", timeout=10) as r:
            assert r.status == 200
        assert ST.status()["key"] == "p/s1"
        assert ST.open_shot("p/s1", d)["port"] == s["port"], "opening the same shot again reuses the running Studio"
    finally:
        out = ST.close()
    assert out["open"] is False and out["saved"] is True
    assert ST.status() == {"open": False}


def test_a_change_made_elsewhere_is_never_overwritten(tmp_path):
    d = _shot(tmp_path)
    synced = (d / "index.html").read_text(encoding="utf-8")
    work = ST.prepare(d)
    # nothing edited in the Studio, but Claude changed the shot meanwhile: closing keeps Claude's change
    (d / "index.html").write_text(PAGE.replace("Hello", "From Claude"), encoding="utf-8")
    assert ST.take_back(d, work, synced) == {"saved": True, "changed": False, "assets": []}
    assert "From Claude" in (d / "index.html").read_text(encoding="utf-8")
    # both changed: the shot keeps Claude's change, the Studio's version is set aside
    (work / "index.html").write_text((work / "index.html").read_text(encoding="utf-8").replace(">Hello<", ">From the Studio<"), encoding="utf-8")
    got = ST.take_back(d, work, synced)
    assert got["saved"] is False and got["conflict"] is True
    assert "From Claude" in (d / "index.html").read_text(encoding="utf-8")
    assert "From the Studio" in (d / "studio-conflict.html").read_text(encoding="utf-8")
