"""Tests for AI YouTube Shorts & Virality Highlight Detection."""
import pytest
import wave
from vt import paths
from vt.project import Project
from vt.shorts.splitter import slice_short_project
from vt.util import read_json, write_json
from vt.shorts.detector import (
    SentenceUnit,
    dedupe_highlights,
    detect_highlights,
    group_words_into_sentences,
    rule_fallback_highlights,
    snap_to_sentence_boundaries,
)


def test_group_words_into_sentences():
    words = [
        {"text": "Most", "start": 0.0, "end": 0.3},
        {"text": "people", "start": 0.35, "end": 0.7},
        {"text": "fail", "start": 0.75, "end": 1.1},
        {"text": "at", "start": 1.15, "end": 1.3},
        {"text": "this.", "start": 1.35, "end": 1.8},
        {"text": "Why?", "start": 2.2, "end": 2.6},
        {"text": "Because", "start": 2.7, "end": 3.0},
        {"text": "they", "start": 3.05, "end": 3.3},
        {"text": "lack", "start": 3.35, "end": 3.7},
        {"text": "consistency.", "start": 3.75, "end": 4.5},
    ]

    sentences = group_words_into_sentences(words)
    assert len(sentences) == 3
    assert sentences[0].text == "Most people fail at this."
    assert sentences[0].start == 0.0
    assert sentences[0].end == 1.8
    assert sentences[1].text == "Why?"
    assert sentences[1].start == 2.2
    assert sentences[1].end == 2.6
    assert sentences[2].text == "Because they lack consistency."


def test_dedupe_highlights_overlap():
    highlights = [
        {"title": "High Score Clip", "start_time": 10.0, "end_time": 50.0, "score": 95},
        {"title": "Overlapping Clip", "start_time": 15.0, "end_time": 45.0, "score": 80},
        {"title": "Non-overlapping Clip", "start_time": 60.0, "end_time": 100.0, "score": 88},
    ]

    deduped = dedupe_highlights(highlights, max_overlap_ratio=0.5)
    assert len(deduped) == 2
    titles = [h["title"] for h in deduped]
    assert "High Score Clip" in titles
    assert "Non-overlapping Clip" in titles
    assert "Overlapping Clip" not in titles


def test_snap_to_sentence_boundaries():
    sentences = [
        SentenceUnit(text="Sentence one.", start=10.2, end=14.8, words=[]),
        SentenceUnit(text="Sentence two.", start=15.1, end=20.5, words=[]),
        SentenceUnit(text="Sentence three.", start=21.0, end=42.0, words=[]),
    ]

    # LLM returned fuzzy times around 10.0 and 41.5
    raw_highlights = [
        {"title": "Clip", "start_time": 10.0, "end_time": 41.5, "score": 90}
    ]

    snapped = snap_to_sentence_boundaries(raw_highlights, sentences, duration=60.0)
    assert len(snapped) == 1
    assert snapped[0]["start_time"] == 10.2
    assert snapped[0]["end_time"] == 42.0


def test_rule_fallback_highlights():
    # Construct 120 seconds of dummy sentences
    sentences = []
    t = 0.0
    for i in range(20):
        t_end = t + 5.0
        txt = f"Sentence {i} with a secret reveal and high curiosity!"
        sentences.append(SentenceUnit(text=txt, start=t, end=t_end, words=[]))
        t = t_end + 0.5

    candidates = rule_fallback_highlights(sentences, duration=110.0, num_clips=3)
    assert len(candidates) >= 1
    for c in candidates:
        assert "start_time" in c
        assert "end_time" in c
        assert c["score"] >= 40
        assert c["duration"] >= 20.0


def test_detect_highlights_end_to_end():
    words = []
    t = 0.0
    for i in range(30):
        words.append({"text": f"word{i}", "start": t, "end": t + 0.4})
        t += 0.5
    words[-1]["text"] = "final."

    res = detect_highlights({"words": words, "duration": 15.0}, num_clips=2)
    assert "highlights" in res
    assert "content_info" in res
    assert res["total_duration"] == 15.0


def test_shorts_api_endpoints(ref):
    from fastapi.testclient import TestClient
    from vt.server.app import app

    with TestClient(app) as client:
        # GET shorts for reference project
        res = client.get("/api/projects/reference/shorts")
        assert res.status_code == 200
        data = res.json()
        assert "highlights" in data


def test_short_slicer_rebases_words_and_preserves_origin(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROJECTS", tmp_path / "projects")
    audio = tmp_path / "speech.wav"
    with wave.open(str(audio), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 16000 * 3)
    parent = Project.create("Long recording", audio, language="en")
    words = [{"text":"first", "start":0.1,"end":0.3}, {"text":"middle", "start":1.2,"end":1.5}, {"text":"last", "start":2.2,"end":2.5}]
    write_json(parent.raw_transcript_path, {"language":"en","words":words})
    child = slice_short_project(parent.id, {"title":"Middle clip","start_time":1.0,"end_time":2.0,"score":90}, run_pipeline=False, caption_style="box", aroll="off")
    rebased = read_json(child.raw_transcript_path)["words"]
    assert len(rebased) == 1
    assert rebased[0]["start"] == .2
    assert child.meta().origin["short"]["parent_id"] == parent.id
    assert child.meta().aspect == "9:16"
    assert child.meta().options.caption_style == "box"
    assert child.meta().options.aroll == "off"
    assert child.input_audio.exists()

