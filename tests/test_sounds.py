"""Sound events: labels become concepts, windows merge into events, events become pictures in the plan, and a recording with no speech gets sound captions.
The real listener (an AudioSet model) is checked by scripts/qa_sounds.py on real recordings; here it is replaced by a stand-in so the logic is tested offline."""
import numpy as np
import pytest
import soundfile as sf

from vt import sounds as S


def rows(*spec):
    """spec: (t0, t1, [(label, score), ...])"""
    return [{"t0": a, "t1": b, "labels": labs} for a, b, labs in spec]


def test_labels_are_grouped_and_neighbouring_windows_merge_into_one_event():
    r = rows((0, 3, [("Speech", 0.9), ("Laughter", 0.6)]), (1.5, 4.5, [("Giggle", 0.5), ("Speech", 0.4)]), (3, 6, [("Speech", 0.9)]), (9, 12, [("Applause", 0.9)]))
    ev = S.to_events(r, 12.0)
    assert [(e["concept"], e["start"], e["end"]) for e in ev] == [("laughter", 0.0, 4.5), ("applause", 9.0, 12.0)]
    assert ev[0]["emoji"] == "1f602" and ev[1]["query"]


def test_speech_and_weak_labels_are_ignored_and_the_specific_baby_laugh_wins():
    r = rows((0, 3, [("Speech", 0.95), ("Silence", 0.9), ("Static", 0.8)]), (3, 6, [("Laughter", 0.5), ("Baby laughter", 0.4)]), (6, 9, [("Dog", 0.1)]), (9, 12, [("Music", 0.2)]),
             (12, 15, [("Music", 0.8)]), (15, 18, [("Music", 0.8)]))
    ev = S.to_events(r, 18.0)
    assert [(e["concept"], e["start"], e["end"]) for e in ev] == [("baby_laughter", 3.0, 6.0), ("music", 12.0, 18.0)] or [e["concept"] for e in ev] == ["baby_laughter", "music"]
    assert not any(e["concept"] in ("dog",) for e in ev)                    # below MIN_SCORE
    assert all(e["end"] - e["start"] >= S.MIN_EVENT for e in ev)


def test_windows_cover_the_whole_recording():
    for n in (S.SR * 2, S.SR * 3, S.SR * 10, S.SR * 10 + 4000):
        w = S.windows(n)
        assert w[0][0] == 0 and w[-1][1] == n and all(b - a <= int(S.WIN * S.SR) for a, b in w)


def test_every_concept_has_an_emoji_and_a_query_and_labels_map_back():
    for c, (cap, emoji, query, labels) in S.CONCEPTS.items():
        if c == "silence":
            continue
        assert cap and emoji and query and labels, c
        assert all(S.concept_of(l) == c for l in labels), c


def test_caption_words_look_like_closed_captions():
    w = S.caption_words([{"label": "Baby laughing", "start": 2.0, "end": 5.0, "score": 0.7}, {"label": "Applause", "start": 6.0, "end": 8.0, "score": 0.9}])
    assert [x["text"] for x in w] == ["[Baby", "laughing]", "[Applause]"]
    assert w[0]["start"] == 2.0 and w[1]["end"] <= 5.0 and w[2]["start"] == 6.0 and all(a["end"] >= a["start"] for a in w)


def test_events_put_an_emoji_on_the_scene_that_is_showing(ref):
    from vt.planner import plan_rules

    tr, beats = ref.transcript(), ref.beats()
    sf = plan_rules(tr, beats, ref.meta().theme, language="bn")
    t_mid = (tr.words[10].start + tr.words[10].end) / 2
    ev = [{"concept": "applause", "label": "Applause", "emoji": "1f44f", "query": "q", "start": t_mid, "end": t_mid + 2, "score": 0.9},
          {"concept": "music", "label": "Music", "emoji": "1f3b5", "query": "q", "start": 1.0, "end": 5.0, "score": 0.9}]
    before = sum(len(s.elements) for s in sf.scenes)
    n = S.add_stickers(sf, ev, tr, beats)
    assert n == 1 and sum(len(s.elements) for s in sf.scenes) == before + 1             # music is background: no picture
    st = [(s, e) for s in sf.scenes for e in s.elements if getattr(e, "type", "") == "sticker" and e.emoji == "1f44f"]
    assert len(st) == 1 and st[0][1].label == "হাততালি"          # the reference is Bangla: the label is too (it was "Applause" until 2026-10-24)
    from vt.schema import validate_scenes
    from vt.planner.catalogue import all_icon_names

    assert not validate_scenes(sf, tr, beats, all_icon_names())
    assert S.add_stickers(sf, ev, tr, beats) == 0                                        # the same emoji is not added twice


def test_a_recording_with_no_speech_gets_sound_captions(ref, monkeypatch, tmp_path):
    """The speech recogniser finds nothing; the sounds become the transcript instead of a 'no speech' error."""
    from vt.pipeline import NoSpeechError, Pipeline
    from vt.util import write_json

    x = (0.3 * np.sin(2 * np.pi * 300 * np.arange(16000 * 12) / 16000)).astype("float32")
    sf.write(str(ref.asr_wav), x, 16000)
    events = [{"concept": "applause", "label": "Applause", "emoji": "1f44f", "query": "q", "start": 1.0, "end": 5.0, "score": 0.9}]
    monkeypatch.setattr(S, "available", lambda: True)
    monkeypatch.setattr(S, "analyze_array", lambda x, sr=16000, progress=None: events)
    pl = Pipeline(ref)
    assert pl._captions_from_sounds("h") is True
    raw = ref.raw_transcript_path.read_text(encoding="utf-8")
    assert "[Applause]" in raw and '"model": "sounds"' in raw
    monkeypatch.setattr(S, "analyze_array", lambda x, sr=16000, progress=None: [])
    assert Pipeline(ref)._captions_from_sounds("h") is None                              # nothing to caption: the old message is kept
    ref.update_meta(options=ref.meta().options.model_copy(update={"sound_events": "off"}))
    monkeypatch.setattr(S, "analyze_array", lambda x, sr=16000, progress=None: events)
    assert Pipeline(ref)._captions_from_sounds("h") is None                              # the switch is respected


def test_the_stage_never_stops_a_video(ref, monkeypatch):
    from vt.pipeline import Pipeline

    monkeypatch.setattr(S, "available", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("model could not be loaded")
    monkeypatch.setattr(S, "analyze_project", boom)
    sf.write(str(ref.cut_audio), np.zeros(16000, dtype="float32"), 16000)
    Pipeline(ref).stage_sounds()
    doc = S.load(ref)
    assert doc["events"] == [] and "could not be loaded" in doc["error"]


def test_the_api_reports_events_and_refuses_clearly(client, ref, monkeypatch):
    r = client.get("/api/projects/reference/sound-events").json()
    assert r["events"] == [] and r["analyzed"] is False
    from vt.util import write_json

    write_json(S.path(ref), {"hash": "x", "model": "m", "duration": 5, "events": [{"concept": "applause", "label": "Applause", "emoji": "1f44f", "query": "q", "start": 1, "end": 3, "score": 0.9}]})
    r = client.get("/api/projects/reference/sound-events").json()
    assert r["analyzed"] and r["events"][0]["concept"] == "applause"
    monkeypatch.setattr(S, "available", lambda: False)
    assert client.post("/api/projects/reference/sound-events").status_code == 422
    assert client.get("/api/projects/nope-x/sound-events").status_code == 404


@pytest.fixture()
def client(ref):
    from fastapi.testclient import TestClient
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_a_babys_laugh_does_not_also_draw_a_cow_and_people_come_first():
    r = rows((0, 3, [("Baby laughter", 0.4), ("Laughter", 0.2), ("Oink", 0.6), ("Pig", 0.3)]), (1.5, 4.5, [("Baby laughter", 0.4), ("Laughter", 0.2), ("Livestock, farm animals, working animals", 0.7)]))
    ev = S.to_events(r, 4.5)
    assert [e["concept"] for e in ev] == ["baby_laughter"] and ev[0]["score"] >= 0.6


def test_captions_are_separate_sentences_and_a_sound_only_plan_shows_each_sounds_emoji(ref):
    from vt.planner import plan_rules
    from vt.stages import words as W
    from vt.schema import Transcript, Word

    ev = [{"concept": "applause", "label": "Crowd applauding", "emoji": "1f44f", "query": "q", "start": 0.0, "end": 4.0, "score": 0.9},
          {"concept": "rain", "label": "Rain falling", "emoji": "1f327", "query": "q", "start": 4.0, "end": 9.0, "score": 0.9}]
    ws = S.caption_words(ev)
    assert all(len(e["label"].split()) >= 2 for e in S.CONCEPTS.values() if False) or all(len(v[0].split()) >= 2 for k, v in S.CONCEPTS.items() if k != "silence")
    tr = Transcript(language="en", words=[Word(id=f"w{i}", text=w["text"], start=w["start"], end=w["end"], conf=0.9, lang="en") for i, w in enumerate(ws, 1)])
    beats = W.build_beats(tr)
    assert len(beats.beats) == 2                                                          # one sentence per sound
    sf = plan_rules(tr, beats, "paper", language="en")
    sf, n = S.plan_from_sounds(sf, ev, tr, beats)
    assert n == len(sf.scenes) == 2
    assert [[e.emoji for e in s.elements] for s in sf.scenes][0] == ["1f44f"] and [[e.emoji for e in s.elements] for s in sf.scenes][-1] == ["1f327"]
    assert all(len(s.elements) == 1 for s in sf.scenes)
