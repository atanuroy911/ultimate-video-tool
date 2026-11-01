"""The free media catalogue: licence filter, validation by really downloading and decoding, failures marked (never hidden), install into a project / the music folder,
credits. A small local HTTP server serves real files (made with ffmpeg) so the whole download + ffprobe + decode path runs for real; what these tests do NOT prove is
that the external sites still serve the catalogue's files: `vt catalog validate` does that."""
import functools
import http.server
import subprocess
import threading

import pytest

from vt.director import catalog as C
from vt.util import find_tool


@pytest.fixture(scope="module")
def media_server(tmp_path_factory):
    d = tmp_path_factory.mktemp("srv")
    ff = find_tool("ffmpeg")
    run = lambda *a: subprocess.run([ff, "-y", "-v", "error", *a], check=True)  # noqa: E731
    run("-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "clip.mp4"))
    run("-f", "lavfi", "-i", "sine=frequency=330:duration=3", "-c:a", "libmp3lame", str(d / "tone.mp3"))
    run("-f", "lavfi", "-i", "testsrc=size=64x64:rate=1:duration=1", "-frames:v", "1", str(d / "pic.png"))
    (d / "notmedia.mp4").write_bytes(b"<html>this is not a video</html>")
    (d / "truncated.mp4").write_bytes((d / "clip.mp4").read_bytes()[:1500])
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def entry(url, kind="video", **kw):
    return {"id": kw.pop("id", "t-1"), "kind": kind, "role": "clip", "title": "Test file", "source": "test", "page_url": "http://example.invalid/page", "url": url,
            "licence": "CC0", "licence_url": "", "creator": "Tester", "attribution": "“Test file” by Tester (CC0)", "tags": ["clip"], **kw}


def test_licence_filter():
    for ok in ("CC0", "CC0 / Public domain", "Public domain", "CC BY 4.0", "CC BY 3.0", "PDM 1.0", "Creative Commons Attribution 4.0"):
        assert C.licence_ok(ok), ok
    for bad in ("CC BY-NC 4.0", "CC BY-ND 2.0", "CC BY-SA 4.0", "CC BY-SA 3.0", "All rights reserved", "", "Non-commercial use only"):
        assert not C.licence_ok(bad), bad


def test_good_files_validate_and_report_their_real_format(media_server):
    v = C.validate(entry(media_server + "/clip.mp4"))
    assert v["status"] == "ok" and v["format"]["video"]["width"] == 320 and v["format"]["video"]["codec"] == "h264" and v["format"]["audio"]["codec"] == "aac"
    assert v["format"]["duration"] == pytest.approx(2.0, abs=0.2) and v["validated_at"]
    a = C.validate(entry(media_server + "/tone.mp3", kind="audio"))
    assert a["status"] == "ok" and a["format"]["audio"]["channels"] >= 1 and a["format"]["video"] is None
    i = C.validate(entry(media_server + "/pic.png", kind="image"))
    assert i["status"] == "ok"


def test_bad_files_are_marked_failed_with_a_reason(media_server):
    missing = C.validate(entry(media_server + "/nope.mp4"))
    assert missing["status"] == "failed" and "404" in missing["error"]
    junk = C.validate(entry(media_server + "/notmedia.mp4"))
    assert junk["status"] == "failed" and junk["error"]
    cut = C.validate(entry(media_server + "/truncated.mp4"))
    assert cut["status"] == "failed"
    wrong = C.validate(entry(media_server + "/tone.mp3", kind="video"))
    assert wrong["status"] == "failed" and "no video stream" in wrong["error"]
    gone = C.validate(entry("http://127.0.0.1:9/never.mp4"))
    assert gone["status"] == "failed"


def test_size_limit_is_enforced(media_server, monkeypatch):
    monkeypatch.setitem(C.MAX_MB, "video", 0)
    v = C.validate(entry(media_server + "/clip.mp4"))
    assert v["status"] == "failed" and "larger" in v["error"]


def test_install_into_a_project_and_the_credits(media_server, ref, tmp_path, monkeypatch):
    from vt.director import stock

    monkeypatch.setattr(C, "CATALOG", tmp_path / "catalog.json")
    C.save([entry(media_server + "/clip.mp4", id="clip-1"), entry(media_server + "/pic.png", kind="image", id="pic-1"), entry(media_server + "/nope.mp4", id="bad-1")])
    m = C.install_media(ref, "clip-1")
    assert m.kind == "video" and m.source == "test" and "Tester" in m.credit and m.licence == "CC0" and (ref.dir / m.file).exists()
    p = C.install_media(ref, "pic-1")
    assert p.kind == "image"
    txt = stock.credits_text(ref)
    assert "Tester" in txt and "clip-1" in txt or m.id in txt
    with pytest.raises(C.CatalogError) as e:
        C.install_media(ref, "bad-1")
    assert "marks it as failed" in str(e.value)
    assert next(x for x in C.load() if x["id"] == "bad-1")["status"] == "failed"              # the catalogue itself learned that the link is dead
    with pytest.raises(C.CatalogError):
        C.install_media(ref, "nope")


def test_install_music_and_its_credit_line(media_server, tmp_path, monkeypatch):
    from vt import paths

    monkeypatch.setattr(C, "CATALOG", tmp_path / "catalog.json")
    monkeypatch.setattr(paths, "USER_MUSIC", tmp_path / "music")
    C.save([entry(media_server + "/tone.mp3", kind="audio", id="song-1", role="music")])
    mid = C.install_music("song-1")
    assert mid == "user/song-1.mp3" and (tmp_path / "music" / "song-1.mp3").exists()
    assert "Tester" in C.music_credit(mid) and C.music_credit("calm-01") == "" and C.music_credit(None) == ""
    with pytest.raises(C.CatalogError):
        C.install_music("nope")


def test_catalog_endpoints(media_server, ref, projects_dir, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from vt import paths
    from vt.server.app import app

    monkeypatch.setattr(C, "CATALOG", tmp_path / "catalog.json")
    monkeypatch.setattr(paths, "USER_MUSIC", tmp_path / "music")
    C.save([entry(media_server + "/clip.mp4", id="clip-1", status="ok"), entry(media_server + "/tone.mp3", kind="audio", id="song-1", role="music", status="ok"),
            entry(media_server + "/nope.mp4", id="bad-1", status="ok")])
    c = TestClient(app)
    j = c.get("/api/catalog").json()
    assert len(j["entries"]) == 3 and j["summary"]["total"] == 3 and "url" not in j["entries"][0]            # the download address is not sent to the page
    assert [e["id"] for e in c.get("/api/catalog?kind=audio").json()["entries"]] == ["song-1"]
    assert c.post(f"/api/projects/{ref.id}/catalog/clip-1/add").status_code == 200
    r = c.post(f"/api/projects/{ref.id}/catalog/bad-1/add")
    assert r.status_code == 502 and "marks it as failed" in r.text
    r = c.post(f"/api/projects/{ref.id}/catalog/song-1/add")                                                # audio goes to the project's sounds (for the layers), not the picture bin
    assert r.status_code == 200 and r.json()["kind"] == "audio"
    assert [m["id"] for m in c.get(f"/api/projects/{ref.id}/sounds").json()] == [r.json()["id"]]
    assert r.json()["id"] not in [m["id"] for m in c.get(f"/api/projects/{ref.id}/media").json()]
    assert c.post("/api/catalog/song-1/music").json()["music"] == "user/song-1.mp3"
    assert c.post("/api/catalog/clip-1/music").status_code == 422
    assert c.post("/api/catalog/ghost/check").status_code == 404
    assert c.post("/api/catalog/clip-1/check").json()["status"] == "ok"
    assert c.post("/api/catalog/ghost/project").status_code == 404
    assert c.post("/api/catalog/clip-1/project").status_code == 422


def test_the_contact_in_the_user_agent_is_configurable(monkeypatch):
    monkeypatch.setenv("VT_CATALOG_CONTACT", "mailto:owner@example.com")
    assert "owner@example.com" in C._ua()["User-Agent"]
    monkeypatch.delenv("VT_CATALOG_CONTACT")
    assert "(" in C._ua()["User-Agent"] and "http" in C._ua()["User-Agent"]
