import json

import numpy as np
import pytest
import soundfile as sf

from test_api import client  # noqa: F401
from vt import ingest


def j3(events):
    return json.dumps({"events": events})


def test_automatic_captions_keep_the_first_word_of_every_line(tmp_path):
    f = tmp_path / "a.json3"
    f.write_text(j3([{"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "what"}, {"utf8": " is", "tOffsetMs": 400}, {"utf8": " a", "tOffsetMs": 700}, {"utf8": " black", "tOffsetMs": 900}]},
                     {"tStartMs": 3000, "dDurationMs": 10, "segs": [{"utf8": "\n"}]},
                     {"tStartMs": 3100, "dDurationMs": 2000, "segs": [{"utf8": "hole", "tOffsetMs": 0}, {"utf8": " [Music]", "tOffsetMs": 500}, {"utf8": " really", "tOffsetMs": 900}]}]), encoding="utf-8")
    w = ingest.words_from_json3(f)
    assert [x["text"] for x in w] == ["what", "is", "a", "black", "hole", "really"]
    assert w[0]["start"] == 1.0 and w[1]["start"] == 1.4
    assert all(a["end"] > a["start"] and a["end"] <= b["start"] + 0.001 for a, b in zip(w, w[1:]))


def test_plain_cues_are_spread_over_their_time_and_rolling_repeats_are_dropped(tmp_path):
    f = tmp_path / "b.json3"
    f.write_text(j3([{"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "hello there my friend"}]},
                     {"tStartMs": 2000, "dDurationMs": 2000, "segs": [{"utf8": "this is fine"}]}]), encoding="utf-8")
    w = ingest.words_from_json3(f)
    assert [x["text"] for x in w] == "hello there my friend this is fine".split()
    assert w[3]["end"] == pytest.approx(2.0, abs=0.01) and w[4]["start"] == pytest.approx(2.0, abs=0.01)


def test_vtt_with_tags_and_hours(tmp_path):
    f = tmp_path / "c.vtt"
    f.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.000 align:start\n<c>Hello</c> <00:00:01.5><c>world</c>\n\n01:00:00.000 --> 01:00:02.000\nlater words here\n", encoding="utf-8")
    w = ingest.words_from_vtt(f)
    assert [x["text"] for x in w] == ["Hello", "world", "later", "words", "here"] and w[2]["start"] == 3600.0


def test_too_little_text_is_not_trusted(tmp_path):
    f = tmp_path / "d.json3"
    f.write_text(j3([{"tStartMs": 0, "dDurationMs": 1000, "segs": [{"utf8": "just three words"}]}]), encoding="utf-8")
    assert ingest.raw_transcript_from_subs(f, "en", 60) is None


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://x.org/a.mp3", "javascript:alert(1)", "", "http://localhost:8765/api", "http://127.0.0.1/x", "http://192.168.1.5/a.mp3", "http://[::1]/"])
def test_unsafe_or_broken_links_are_refused(url):
    with pytest.raises(ingest.IngestError):
        ingest.check_url(url)


def test_errors_are_translated_for_people():
    assert "private" in str(ingest._friendly(Exception("ERROR: Private video. Sign in if you've been granted access"))).lower()
    assert "not supported" in str(ingest._friendly(Exception("ERROR: Unsupported URL: https://x.y"))).lower()
    assert ingest._too_long({"duration": 99999}) and not ingest._too_long({"duration": 100}) and ingest._too_long({"is_live": True})


def _fake_link(monkeypatch, tmp_path, automatic):
    sf.write(str(tmp_path / "src.m4a.wav"), np.zeros(16000 * 3, dtype="float32"), 16000)
    sub = tmp_path / "src.en.json3"
    sub.write_text(j3([{"tStartMs": i * 500, "dDurationMs": 500, "segs": [{"utf8": f"word{i}"}]} for i in range(12)]), encoding="utf-8")
    monkeypatch.setattr(ingest, "fetch", lambda *a, **k: {"audio": tmp_path / "src.m4a.wav", "title": "A talk", "uploader": "Someone", "duration": 6.0, "license": "CC BY",
                                                           "url": "https://example.org/v", "subs": sub, "subs_lang": "en", "automatic": automatic})


def test_a_link_becomes_a_project_with_the_authors_subtitles(projects_dir, monkeypatch, tmp_path):
    _fake_link(monkeypatch, tmp_path, automatic=False)
    p = ingest.create_project("https://example.org/v", language="en")
    m = p.meta()
    assert m.title == "A talk" and m.origin["uploader"] == "Someone" and m.origin["subtitles"] is True
    assert len(json.loads((p.dir / "subs.raw.json").read_text(encoding="utf-8"))["words"]) == 12


def test_automatic_english_captions_are_left_to_the_speech_model_unless_asked_for(projects_dir, monkeypatch, tmp_path):
    _fake_link(monkeypatch, tmp_path, automatic=True)
    p = ingest.create_project("https://example.org/v", language="en")
    assert not (p.dir / "subs.raw.json").exists() and p.meta().origin["subtitles"] is False
    p2 = ingest.create_project("https://example.org/v", language="en", use_subs="any")
    assert (p2.dir / "subs.raw.json").exists()
    p3 = ingest.create_project("https://example.org/v", language="bn")           # no better option than YouTube's own for Bangla
    assert (p3.dir / "subs.raw.json").exists()
    asked = []
    real = ingest.fetch
    monkeypatch.setattr(ingest, "fetch", lambda *a, **k: (asked.append(k.get("want_subs")), real(*a, **k))[1])
    ingest.create_project("https://example.org/v", language="bn", use_subs="off")
    assert asked == [False]                                                        # "off" does not even download them


def test_the_api_validates_the_link_and_reports_download_errors(client, monkeypatch):
    r = client.post("/api/projects/from-link", json={"url": "http://localhost/x"})
    assert r.status_code == 400
    monkeypatch.setattr(ingest, "check_url", lambda u: u)
    monkeypatch.setattr(ingest, "create_project", lambda *a, **k: (_ for _ in ()).throw(ingest.IngestError("This video is private.")))
    job = client.post("/api/projects/from-link", json={"url": "https://example.org/v"}).json()
    import time
    for _ in range(50):
        j = client.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert j["status"] == "error" and "private" in j["error"]
