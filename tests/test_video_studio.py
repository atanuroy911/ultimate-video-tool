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

    # the video changes afterwards (a new plan): the export bakes it again and carries the Studio edit into it
    (comp / "data.json").write_text((comp / "data.json").read_text(encoding="utf-8").replace("more than you need", "more than enough"), encoding="utf-8")
    where, note = VS.for_render(proj, "9x16", comp)
    assert where == d and note is None, note
    assert VS.info(proj, "9x16", comp)["current"], "the Studio copy now fits the changed video"
    (comp / "data.json").write_text((comp / "data.json").read_text(encoding="utf-8").replace("more than enough", "more than plenty"), encoding="utf-8")
    again = VS.prepare(proj, "9x16", comp)
    assert not again["kept"] and again["edited"] and again["carried"] >= 1 and again["missed"] == 0, again
    assert "Each minute" in page.read_text(encoding="utf-8"), "the Studio edit is carried into the new bake"
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


def test_an_agent_edit_is_in_the_studio_history_and_can_be_undone(video, tmp_path):
    import shutil

    from vt import video_studio as VS

    proj0, comp0 = video
    proj = SimpleNamespace(id="h", dir=tmp_path / "h")
    comp = proj.dir / "composition" / "9x16"
    shutil.copytree(comp0, comp)
    VS.prepare(proj, "9x16", comp)
    page = VS.folder(proj, "9x16") / "index.html"
    before = page.read_text(encoding="utf-8")
    term = next(x for x in VS.parts(proj, "9x16") if x["id"] == "s1-defn-term")["text"]
    got = VS.recorded_edit(proj, "9x16", f">{term}<", ">Each minute<", label="New words for the term")
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
