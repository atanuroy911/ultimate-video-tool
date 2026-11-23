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

    # the person retypes the term in the Studio (it writes the scene's own page, S4)
    page = d / "scenes" / "s1.html"
    page.write_text(page.read_text(encoding="utf-8").replace("Every minute", "Each minute"), encoding="utf-8")
    assert VS.info(proj, "9x16", comp)["edited"]
    assert VS.for_render(proj, "9x16", comp) == (d, None), "the export draws what was edited"
    assert VS.prepare(proj, "9x16", comp)["kept"], "opening again keeps the edits"
    assert "Each minute" in page.read_text(encoding="utf-8")

    # the video changes afterwards (a new plan): the export bakes it again and carries the Studio edit into it
    (comp / "data.json").write_text((comp / "data.json").read_text(encoding="utf-8").replace("more than you need", "more than enough"), encoding="utf-8")
    where, note = VS.for_render(proj, "9x16", comp)
    assert where == d and note is None, note
    assert VS.info(proj, "9x16", comp)["current"], "the Studio copy now fits the changed video"
    (comp / "data.json").write_text((comp / "data.json").read_text(encoding="utf-8").replace("more than enough", "more than plenty"), encoding="utf-8")
    again = VS.prepare(proj, "9x16", comp)
    assert not again["kept"] and again["edited"] and again["carried"] >= 1 and again["missed"] == 0, again
    assert "Each minute" in page.read_text(encoding="utf-8"), "the Studio edit is carried into the new bake"
    assert "Each minute" in (proj.dir / "studio-9x16.old" / "scenes" / "s1.html").read_text(encoding="utf-8"), "the old edits are kept aside"


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
    page = d / "scenes" / "s1.html"
    page.write_text(page.read_text(encoding="utf-8").replace("Every minute", "Each minute"), encoding="utf-8")
    data = json.loads((comp / "data.json").read_text(encoding="utf-8"))
    data["captions_enabled"] = False                                           # what a no-captions export composes
    (comp / "data.json").write_text(json.dumps(data), encoding="utf-8")
    where, note = VS.for_render(proj, "9x16", comp, captions=False)
    assert note is None and where != comp
    html = (where / "index.html").read_text(encoding="utf-8")
    assert 'captions.html"' not in html and not (where / "compositions" / "captions.html").exists()
    assert "Each minute" in (where / "scenes" / "s1.html").read_text(encoding="utf-8"), "the scene pages and their edits go along"
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
    assert term["scene"] == "s1" and "minute" in term["text"] and term["file"] == "scenes/s1.html"
    assert any(x["file"] == "compositions/captions.html" for x in ps), "caption parts are listed too"
    assert not [p.name for p in VS.folder(proj, "9x16").glob("*.html") if p.name != "index.html"], "one page at the top (HyperFrames: one root)"
    one = VS.part(proj, "9x16", "s1-defn-term")
    assert one["animation"] and all('"s1-defn-term"' in ln for ln in one["animation"])
    old = term["text"].split()[0]
    got = VS.edit(proj, "9x16", f">{old} minute<", ">Each minute<", file=term["file"])
    assert got["ok"] and got["edited"]
    with pytest.raises(ST.StudioError, match="exactly once"):
        VS.edit(proj, "9x16", "no such text", "x")
    with pytest.raises(ST.StudioError, match="composition"):
        VS.edit(proj, "9x16", 'data-composition-id="scene-s1"', 'data-x="s1"', file="scenes/s1.html")
    with pytest.raises(ST.StudioError, match="not one of them"):
        VS.edit(proj, "9x16", "a", "b", file="../outside.html")
    with pytest.raises(ST.StudioError, match="timing"):
        VS.edit(proj, "9x16", 'data-composition-id="root"', 'data-x="root"')
    assert VS.selection(proj, "9x16")["selected"] is False


def test_an_agent_edit_is_in_the_studio_history_and_can_be_undone(video, tmp_path):
    import shutil

    from vt import video_studio as VS

    proj0, comp0 = video
    proj = SimpleNamespace(id="h", dir=tmp_path / "h")
    comp = proj.dir / "composition" / "9x16"
    shutil.copytree(comp0, comp)
    VS.prepare(proj, "9x16", comp)
    part = next(x for x in VS.parts(proj, "9x16") if x["id"] == "s1-defn-term")
    page = VS.folder(proj, "9x16") / part["file"]
    before = page.read_text(encoding="utf-8")
    got = VS.recorded_edit(proj, "9x16", f">{part['text']}<", ">Each minute<", file=part["file"], label="New words for the term")
    assert got["ok"] and got["history"] == "New words for the term"
    entries = VS._history(proj, "9x16", "--limit", "5").get("entries", [])
    assert any(e["label"] == "New words for the term" and e["who"]["name"] == "Claude Code" for e in entries), entries
    undone = VS.undo(proj, "9x16")
    assert undone["ok"] and "New words" in undone["undid"]
    assert page.read_text(encoding="utf-8") == before


def test_studio_edits_survive_a_change_of_the_video():
    from vt.video_studio import carry

    base = '<div id="a">Hello</div>\n<div id="b">World</div>\n<script>\nt0.to(["a"].map($),{"opacity":1},0.5);\n</script>'
    mine = base.replace(">Hello<", ">Hi there<").replace('{"opacity":1},0.5', '{"opacity":1},0.9')
    new = base.replace(">World<", ">Everyone<")                       # the plan changed another part
    text, carried, missed = carry(base, mine, new)
    assert (carried, missed) == (2, 0)
    assert ">Hi there<" in text and ">Everyone<" in text and '{"opacity":1},0.9' in text
    gone = new.replace('<div id="a">Hello</div>\n', "")                # the part the person edited is no longer in the video
    text, carried, missed = carry(base, mine, gone)
    assert missed == 1 and ">Hi there<" not in text


def test_an_edit_made_before_scenes_had_their_own_pages_reaches_the_scene_page():
    """S4: a Studio copy made before each scene had its own page holds the scene's parts in index.html; when it is baked again, each edit goes to
    the page that holds its code now."""
    from vt.video_studio import carry_many

    base = '<div id="root">\n<div id="s1-scene">\n<div id="s1-term">Every minute</div>\n</div>\n</div>\n<script>\nt0.to(["s1-term"].map($),{"opacity":1},3.5);\n</script>'
    mine = base.replace(">Every minute<", ">Each minute<")
    news = {"index.html": '<div id="root">\n<div id="scene-s1" data-composition-src="scenes/s1.html"></div>\n</div>\n<script>\n</script>',
            "scenes/s1.html": '<div id="scene-s1-root">\n<div id="s1-scene">\n<div id="s1-term">Every minute</div>\n</div>\n</div>\n<script>\nts.to(["s1-term"].map($),{"opacity":1},0.5);\n</script>'}
    got, carried, missed = carry_many(base, mine, news, prefer="index.html")
    assert carried == 1 and missed == 0
    assert ">Each minute<" in got["scenes/s1.html"] and got["index.html"] == news["index.html"]


def test_a_copy_from_before_keeps_its_edits_and_ends_with_one_top_page(video, tmp_path):
    """A Studio copy made before the baselines moved into .baked/ (and the captions into compositions/): its edits are found against its old
    baselines, carried into the new bake, and the old files go, so HyperFrames sees one page at the top."""
    import shutil

    from vt import video_studio as VS

    proj0, comp0 = video
    proj = SimpleNamespace(id="m", dir=tmp_path / "m")
    comp = proj.dir / "composition" / "9x16"
    shutil.copytree(comp0, comp)
    VS.prepare(proj, "9x16", comp)
    d = VS.folder(proj, "9x16")
    shutil.move(str(d / ".baked" / "index.html"), str(d / ".baked.html"))                       # the old layout
    shutil.move(str(d / "compositions" / "captions.html"), str(d / "captions.html"))
    shutil.move(str(d / ".baked" / "compositions" / "captions.html"), str(d / ".baked-captions.html"))
    shutil.move(str(d / ".baked" / "scenes"), str(d / ".baked-scenes"))
    shutil.rmtree(d / "compositions")
    page = d / "scenes" / "s1.html"
    page.write_text(page.read_text(encoding="utf-8").replace("Every minute", "Each minute"), encoding="utf-8")
    assert VS.info(proj, "9x16", comp)["edited"], "the edit is seen against the old baseline"
    import json
    data = json.loads((comp / "data.json").read_text(encoding="utf-8"))
    data["changed_for_the_test"] = 1                                           # the video changed (the fixture's text may have changed already)
    (comp / "data.json").write_text(json.dumps(data), encoding="utf-8")
    got = VS.prepare(proj, "9x16", comp)
    assert got["carried"] >= 1 and got["missed"] == 0, got
    assert "Each minute" in page.read_text(encoding="utf-8")
    assert sorted(p.name for p in d.glob("*.html")) == ["index.html"] and not (d / ".baked-scenes").exists()
    assert (d / "compositions" / "captions.html").exists() and (d / ".baked" / "index.html").exists()
