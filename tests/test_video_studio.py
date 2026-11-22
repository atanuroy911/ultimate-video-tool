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
