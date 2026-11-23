"""O4 (docs/plans/PLAN-OPENMOTION.MD): the whole video edited in the HyperFrames Studio. Baked into studio-<shape>/, edits told apart from none, the
export draws the edited folder only while it was baked from the same composition, and older edits are kept aside, never thrown away."""
from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    from vt.compose.composer import resolve_composition, write_composition
    from vt.project import load_theme
    from vt.render import hyperframes as H
    from vt.schema import Beat, Beats, ScenesFile, Transcript, Word

    try:
        H._browser()
    except Exception as e:                                                      # noqa: BLE001
        pytest.skip(f"HyperFrames has no browser here: {str(e)[:120]}")
    root = tmp_path_factory.mktemp("vstudio")
    words = [Word(id=f"w{i}", text=f"word{i}", start=0.2 + i * 0.3, end=0.45 + i * 0.3) for i in range(1, 12)]
    beats = Beats(beats=[Beat(id="b1", word_ids=[f"w{i}" for i in range(1, 12)], start=0.2, end=3.6, text="a")])
    sf = ScenesFile.model_validate({"planner": "claude", "scenes": [
        {"id": "s1", "beats": ["b1"], "layout": "stack", "elements": [{"type": "definition", "term": "Every minute", "meaning": "more than you need", "at_word": "w1"}]}]})
    theme = load_theme("paper")
    data = resolve_composition(sf, Transcript(words=words), beats, theme, "9:16", 4.0, None, media={})
    proj = SimpleNamespace(id="p", dir=root / "p")
    comp = write_composition(proj.dir / "composition" / "9x16", data, theme).parent
    return proj, comp


def test_bake_edit_render_and_a_changed_video(video):
    from vt import video_studio as VS

    proj, comp = video
    assert VS.for_render(proj, "9x16", comp) == (comp, None), "no Studio edits: the export draws the composition"
    got = VS.prepare(proj, "9x16", comp)
    assert got["baked"] and got["current"] and not got["edited"] and got["lost_count"] == 0
    d = VS.folder(proj, "9x16")
    assert VS.for_render(proj, "9x16", comp) == (comp, None), "baked but not edited: nothing changes"

    # the person retypes the term in the Studio (it writes the folder's index.html)
    page = d / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace("Every minute", "Each minute"), encoding="utf-8")
    assert VS.info(proj, "9x16", comp)["edited"]
    assert VS.for_render(proj, "9x16", comp) == (d, None), "the export draws what was edited"
    assert VS.prepare(proj, "9x16", comp)["kept"], "opening again keeps the edits"
    assert "Each minute" in page.read_text(encoding="utf-8")

    # the video changes afterwards (a new plan): the edits no longer fit it
    (comp / "data.json").write_text((comp / "data.json").read_text(encoding="utf-8").replace("more than you need", "more than enough"), encoding="utf-8")
    where, note = VS.for_render(proj, "9x16", comp)
    assert where == comp and "changed after it was edited in the Studio" in note
    again = VS.prepare(proj, "9x16", comp)
    assert not again["kept"] and not again["edited"]
    assert "Each minute" in (proj.dir / "studio-9x16.old" / "index.html").read_text(encoding="utf-8"), "the old edits are kept aside"


def test_an_export_without_captions_keeps_the_studio_edits(video, tmp_path):
    import json
    import shutil

    from vt import video_studio as VS

    proj0, comp0 = video
    proj = type(proj0)(id="q", dir=tmp_path / "q")
    comp = proj.dir / "composition" / "9x16"
    shutil.copytree(comp0, comp)
    VS.prepare(proj, "9x16", comp)
    d = VS.folder(proj, "9x16")
    page = d / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace("Every minute", "Each minute"), encoding="utf-8")
    data = json.loads((comp / "data.json").read_text(encoding="utf-8"))
    data["captions_enabled"] = False                                           # what a no-captions export composes
    (comp / "data.json").write_text(json.dumps(data), encoding="utf-8")
    where, note = VS.for_render(proj, "9x16", comp, captions=False)
    assert note is None and where != comp
    html = (where / "index.html").read_text(encoding="utf-8")
    assert "Each minute" in html and "data-composition-src" not in html and not (where / "captions.html").exists()
    assert VS.for_render(proj, "9x16", comp)[0] == d, "with captions the Studio folder itself is drawn"


def test_a_video_the_bake_cannot_hold_is_not_offered(tmp_path, monkeypatch):
    from vt import shot_studio as ST
    from vt import video_studio as VS

    proj = SimpleNamespace(id="s", dir=tmp_path / "s")
    comp = proj.dir / "composition" / "9x16"
    comp.mkdir(parents=True)
    (comp / "data.json").write_text("{}", encoding="utf-8")

    def fake_bake(src, out):
        out.mkdir(parents=True)
        (out / "index.html").write_text("<html></html>", encoding="utf-8")
        return {"lost": [{"what": "a callback on a tween"}] * 17, "lost_count": 17}

    monkeypatch.setattr(VS, "bake", fake_bake)
    with pytest.raises(ST.StudioError, match="17 animation step"):
        VS.prepare(proj, "9x16", comp)
    assert not VS.folder(proj, "9x16").exists(), "nothing is left for an export to draw"


def test_agents_read_and_change_the_studio_copy(video, tmp_path):
    import shutil

    from vt import shot_studio as ST
    from vt import video_studio as VS

    proj0, comp0 = video
    proj = SimpleNamespace(id="a", dir=tmp_path / "a")
    comp = proj.dir / "composition" / "9x16"
    shutil.copytree(comp0, comp)
    VS.prepare(proj, "9x16", comp)
    ps = VS.parts(proj, "9x16")
    term = next(x for x in ps if x["id"] == "s1-defn-term")
    assert term["scene"] == "s1" and "minute" in term["text"]
    assert any(x["file"] == "captions.html" for x in ps), "caption parts are listed too"
    one = VS.part(proj, "9x16", "s1-defn-term")
    assert one["animation"] and all('"s1-defn-term"' in ln for ln in one["animation"])
    old = term["text"].split()[0]
    got = VS.edit(proj, "9x16", f">{old} minute<", ">Each minute<")
    assert got["ok"] and got["edited"]
    with pytest.raises(ST.StudioError, match="exactly once"):
        VS.edit(proj, "9x16", "no such text", "x")
    with pytest.raises(ST.StudioError, match="timing"):
        VS.edit(proj, "9x16", 'data-composition-id="root"', 'data-x="root"')
    assert VS.selection(proj, "9x16")["selected"] is False
