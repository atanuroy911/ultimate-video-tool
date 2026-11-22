"""W4.3: an optional extra that was skipped is said in plain words in the project (notices.json), not swallowed."""
from types import SimpleNamespace

from vt import notices, talk_outline


def test_a_notice_is_kept_once_newest_last_and_capped(tmp_path):
    p = SimpleNamespace(dir=tmp_path)
    notices.record(p, "plan", "A was skipped.", ValueError("x"))
    notices.record(p, "plan", "B was skipped.")
    notices.record(p, "plan", "A was skipped.")                       # the same message again moves to the end, once
    got = notices.load(p)
    assert [n["message"] for n in got] == ["B was skipped.", "A was skipped."]
    for i in range(60):
        notices.record(p, "x", f"m{i}")
    assert len(notices.load(p)) == notices.MAX
    notices.clear(p, "x")
    assert all(n["stage"] != "x" for n in notices.load(p))


def test_a_talk_that_cannot_be_read_ahead_says_so(tmp_path, monkeypatch):
    p = SimpleNamespace(dir=tmp_path)
    monkeypatch.setattr(talk_outline, "is_long_talk", lambda project: True)
    monkeypatch.setattr(talk_outline, "words_key", lambda project: "k")
    monkeypatch.setattr(talk_outline, "build", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("the AI is off")))
    assert talk_outline.ensure(p) is None
    got = notices.load(p)
    assert got and "could not be read ahead" in got[-1]["message"] and "RuntimeError" in got[-1]["error"]


def test_a_copied_project_folder_is_known_by_its_folder_name(tmp_path, monkeypatch):
    """A folder copied by hand keeps the old id inside project.json; the folder name wins (the dashboard showed stale cards otherwise)."""
    import json

    from vt import paths
    from vt.project import Project

    monkeypatch.setattr(paths, "PROJECTS", tmp_path)
    (tmp_path / "copy-of-a").mkdir()
    (tmp_path / "copy-of-a" / "project.json").write_text(json.dumps({"id": "a", "title": "A", "audio": "x.wav"}), encoding="utf-8")
    assert Project("copy-of-a").meta().id == "copy-of-a"


def test_a_screen_recording_keeps_graphics_off_the_slides(tmp_path, monkeypatch):
    """On a recording with no face (slides), a real graphic gets the theme background, a stray word is removed; the slide is never drawn over."""
    from types import SimpleNamespace as N

    from vt import aroll
    from vt.schema import Backdrop

    item = N(id="aroll", role="a_roll", faces=[])
    project = N(meta=lambda: N(media=[item]))
    card = N(type="definition")
    word = N(type="keyword")
    graphic = N(backdrop=Backdrop(media="aroll"), elements=[card])
    stray = N(backdrop=Backdrop(media="aroll"), elements=[word])
    plain = N(backdrop=Backdrop(media="aroll"), elements=[])
    assert aroll.keep_screen_clear(N(scenes=[graphic, stray, plain]), project) == 2
    assert graphic.backdrop is None and graphic.elements == [card]
    assert stray.backdrop.media == "aroll" and stray.elements == []
    item.faces = [[0.4, 0.2, 0.2, 0.3]]                                       # a person on screen: nothing to do
    assert aroll.keep_screen_clear(N(scenes=[N(backdrop=Backdrop(media="aroll"), elements=[word])]), project) == 0
