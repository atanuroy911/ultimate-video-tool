"""One credits text for a video (vt/credits.py): the export file, the agents' publish.credits module, the publishing description and
the exports list all carry the same lines, including a music track whose licence asks for a credit (Bensound) and a link's source."""
import json
from types import SimpleNamespace

from vt import credits as CR
from vt import paths


def _project(music="user/hope.mp3", origin=None, media=()):
    meta = SimpleNamespace(options=SimpleNamespace(music=music), origin=origin, media=list(media))
    return SimpleNamespace(meta=lambda: meta)


def _bensound(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "USER_MUSIC", tmp_path)
    (tmp_path / "hope.mp3.credit.json").write_text(json.dumps({"attribution": "Hope by Benjamin Tissot, Bensound.com", "page_url": "https://www.bensound.com/x"}), encoding="utf-8")


def test_a_bensound_track_is_credited(tmp_path, monkeypatch):
    _bensound(tmp_path, monkeypatch)
    t = CR.text(_project())
    assert "Music: Hope by Benjamin Tissot, Bensound.com https://www.bensound.com/x" in t


def test_no_music_and_own_media_need_no_credits(tmp_path, monkeypatch):
    _bensound(tmp_path, monkeypatch)
    assert CR.text(_project(music="")) == ""
    assert CR.text(_project(music="auto")) == ""
    assert CR.text(_project(), music_id="") == ""          # the export with music switched off
    assert CR.text(_project(music="lofi-01")) == ""         # the app's own CC0 tracks


def test_a_link_names_its_source(tmp_path, monkeypatch):
    _bensound(tmp_path, monkeypatch)
    t = CR.text(_project(music="", origin={"title": "Talk", "uploader": "Ann", "url": "https://example.com/v", "license": "CC BY"}))
    assert "Voice and text from: Talk by Ann" in t and "https://example.com/v" in t and "Licence: CC BY" in t


def test_the_description_carries_the_credits_once():
    d = CR.with_description("Why saving works.", "Media credits\n- Music: Hope\n")
    assert d == "Why saving works.\n\nMedia credits\n- Music: Hope"
    assert CR.with_description(d, "Media credits\n- Music: Hope\n") == d
    assert CR.with_description("Plain.", "") == "Plain."


def test_the_publishing_text_and_the_exports_list_use_it(tmp_path, monkeypatch):
    import vt.ai.publish as P

    _bensound(tmp_path, monkeypatch)
    proj = _project()
    proj.dir = tmp_path
    monkeypatch.setattr(P, "metadata", lambda project, provider=None: {"title": "T", "description": "About saving.", "hashtags": []})
    kit = P.build_kit(proj, cover=False)
    assert "Bensound.com" in kit["credits"]
    assert kit["description"].startswith("About saving.") and "Bensound.com" in kit["description"]

    from vt.server import app as A
    src = open(A.__file__, encoding="utf-8").read()
    assert '"credits": f.with_suffix(".credits.txt")' in src      # the Studio reads each export's credits from the list
