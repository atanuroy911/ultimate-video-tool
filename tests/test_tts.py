import numpy as np
import pytest
import soundfile as sf

from vt import tts
from vt.pipeline import Pipeline
from vt.project import Project


def fake_engine(monkeypatch):
    """A stand-in voice: a tone burst per letter, so durations scale with the text like real speech."""
    def synth(engine, voice, text, rate, out):
        n = max(1, len(text)) * 0.06
        t = np.arange(int(tts.SR * n)) / tts.SR
        x = 0.4 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t) ** 2)
        sf.write(str(out), np.concatenate([np.zeros(2400), x, np.zeros(2400)]).astype("float32"), tts.SR)
    monkeypatch.setattr(tts, "synth_sentence", synth)


def test_script_is_split_into_sentences_and_paragraphs():
    s = tts.split_script("একবার এক বাচ্চা ছিল। সে বলল, দাম কত? ৩.৫ টাকা!\n\nনতুন অনুচ্ছেদ।")
    assert [x["text"] for x in s] == ["একবার এক বাচ্চা ছিল।", "সে বলল, দাম কত?", "৩.৫ টাকা!", "নতুন অনুচ্ছেদ।"]
    assert [x["para_end"] for x in s] == [False, False, True, True]
    assert tts.split_script("   ") == []


def test_speakable_reads_money_and_percent():
    assert tts.speakable("দাম ৳১০০ মাত্র") == "দাম ১০০ টাকা মাত্র"
    assert "শতাংশ" in tts.speakable("৪%") and "percent" in tts.speakable("5% off")


def test_word_times_cover_the_speech_in_order(monkeypatch):
    t = np.arange(24000) / 24000
    x = np.concatenate([np.zeros(4800), 0.5 * np.sin(2 * np.pi * 200 * t), np.zeros(4800)]).astype("float32")
    wt = tts.word_times(["আমি", "একটা", "পাথর", "কিনেছি।"], x)
    assert len(wt) == 4 and wt[0][0] >= 0.19 and wt[-1][1] <= 1.22
    assert all(a < b for a, b in wt) and all(wt[i][1] <= wt[i + 1][0] + 1e-6 for i in range(3))
    assert tts.word_times([], x) == []


def test_synthesize_joins_sentences_with_pauses(tmp_path, monkeypatch):
    fake_engine(monkeypatch)
    r = tts.synthesize("এক দুই তিন। চার পাঁচ ছয়।\n\nসাত আট।", tmp_path / "o.wav")
    s = r["sentences"]
    assert len(s) == 3 and s[1]["start"] - s[0]["end"] == pytest.approx(tts.SENTENCE_GAP, abs=0.02)
    assert s[2]["start"] - s[1]["end"] == pytest.approx(tts.PARAGRAPH_GAP, abs=0.02)
    x, sr = sf.read(str(tmp_path / "o.wav"))
    assert len(x) / sr == pytest.approx(r["duration"], abs=0.05) and abs(x).max() <= 0.9
    with pytest.raises(tts.TTSError):
        tts.synthesize("  ", tmp_path / "e.wav")
    with pytest.raises(tts.TTSError):
        tts.synthesize("ক " * 4000, tmp_path / "e.wav")


def test_script_project_runs_without_speech_recognition(projects_dir, monkeypatch):
    fake_engine(monkeypatch)
    import vt.stages.asr as asr_mod
    monkeypatch.setattr(asr_mod, "transcribe", lambda *a, **k: pytest.fail("ASR must not run for a typed script"))
    p = Project.create_from_script("ট্রায়াল", "একবার এক বাচ্চা পাথর কিনল। বাবা বললেন, দাম ৳১০০।", voice_engine="edge", language="bn")
    assert p.meta().source == "script"
    Pipeline(p).run(to_stage="plan")
    tr = p.transcript()
    texts = [w.text for w in tr.words]
    assert texts[:3] == ["একবার", "এক", "বাচ্চা"] and "৳১০০।" in texts           # the script's own words and spelling
    assert p.scenes() and len(p.beats().beats) >= 2
    # editing the script re-speaks it; an unchanged script is not re-synthesised
    from vt.util import read_json, write_json
    before = p.stage_done("voice", __import__("vt.util", fromlist=["file_hash"]).file_hash(p.script_path, extra="tts-v1"))
    assert before
    spec = read_json(p.script_path); spec["text"] = "নতুন কথা।"; write_json(p.script_path, spec)
    Pipeline(p).run(to_stage="asr")
    assert read_json(p.raw_transcript_path)["words"][0]["text"] == "নতুন"


def test_recording_projects_skip_the_voice_stage(projects_dir, monkeypatch):
    ran = []
    monkeypatch.setattr(Pipeline, "stage_voice", lambda self, force=False: ran.append("voice"))
    for name in ("preprocess", "silence", "asr", "cuts", "words", "plan", "compose"):
        monkeypatch.setattr(Pipeline, f"stage_{name}", lambda self, force=False, n=name: ran.append(n))
    sf.write(str(projects_dir / "a.wav"), np.zeros(1600, dtype="float32"), 16000)
    rec = Project.create("rec", projects_dir / "a.wav")
    Pipeline(rec).run()
    assert "voice" not in ran and ran[0] == "preprocess"


DIALOGUE = "Riya: I think schools should start later. Teenagers need sleep.\nSam: Parents would disagree about that.\nIt makes mornings hard.\nRiya: Sleep matters more."


def test_dialogue_is_recognised_and_plain_scripts_are_not():
    d = tts.parse_dialogue(DIALOGUE)
    assert [x[0] for x in d] == ["Riya", "Sam", "Riya"] and d[1][1] == "Parents would disagree about that. It makes mornings hard."
    assert tts.parse_dialogue("Note: this is one speaker only.\nAnd more text.") is None          # one name is not a conversation
    assert tts.parse_dialogue("Visit https://example.com today") is None
    assert tts.parse_dialogue("একজন: আমি\nআরেকজন: তুমি")[1][0] == "আরেকজন"
    s = tts.split_script(DIALOGUE)
    assert [x["speaker"] for x in s] == ["Riya", "Riya", "Sam", "Sam", "Riya"] and s[1]["para_end"] and s[0]["text"] == "I think schools should start later."


def test_each_speaker_gets_a_different_voice():
    v = tts.assign_voices("edge", "bn-BD-NabanitaNeural", ["A", "B", "C"])
    assert v["A"] == "bn-BD-NabanitaNeural" and v["B"] == "bn-BD-PradeepNeural" and len(set(v.values())) == 3
    assert tts.assign_voices("edge", "en-US-GuyNeural", ["x", "y"])["y"].startswith("en-") and tts.assign_voices("mms", "ben", ["a", "b"]) == {"a": "ben", "b": "ben"}


def test_dialogue_voices_timing_and_speakers_reach_the_beats(projects_dir, monkeypatch):
    used = []
    base = tts.synth_sentence
    fake_engine(monkeypatch)
    inner = tts.synth_sentence
    monkeypatch.setattr(tts, "synth_sentence", lambda engine, voice, text, rate, out: (used.append(voice), inner(engine, voice, text, rate, out))[1])
    p = Project.create_from_script("talk", DIALOGUE, voice_engine="edge", voice="en-US-AriaNeural", language="en")
    Pipeline(p).run(to_stage="plan")
    assert len(set(used)) == 2 and used[0] != used[2]                                # Riya and Sam do not share a voice
    tr = p.transcript()
    assert {w.speaker for w in tr.words} == {"Riya", "Sam"}
    beats = p.beats().beats
    assert all(len({tr.by_id()[i].speaker for i in b.word_ids}) == 1 for b in beats)  # a beat never mixes speakers
    assert [b.speaker for b in beats][0] == "Riya" and "Sam" in [b.speaker for b in beats]
    sf = p.scenes()
    assert {s.archetype for s in sf.scenes} == {"speaker"}                           # auto use case: two speakers = a discussion
    assert [e.name for s in sf.scenes for e in s.elements] == [b.speaker for b in beats] or len(sf.scenes) <= len(beats)
    assert read_json_usecase(p) == "discussion"


def read_json_usecase(p):
    import json
    return json.loads((p.dir / "usecase.json").read_text(encoding="utf-8"))["used"]


def test_kokoro_is_listed_with_its_voices_and_says_what_is_missing():
    from vt import tts

    e = next(x for x in tts.list_engines() if x["id"] == "kokoro")
    assert e["offline"] and {v["lang"] for v in e["voices"]} == {"en", "hi"} and "Apache" in e["licence"]
    assert e["available"] in (True, False)


def test_a_half_downloaded_kokoro_file_is_refused_and_removed(tmp_path, monkeypatch):
    import httpx
    from vt import paths, tts

    class Fake:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        status_code = 200
        def raise_for_status(self): pass
        def iter_bytes(self, n): yield b"x" * 1000
    monkeypatch.setattr(paths, "MODELS", tmp_path / "models")
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: Fake())
    with pytest.raises(tts.TTSError, match="damaged"):
        tts.ensure_kokoro()
    assert not list((paths.MODELS / "kokoro").glob("*.part")) and not tts.kokoro_ready()


@pytest.mark.models
@pytest.mark.network
@pytest.mark.slow
def test_kokoro_really_speaks_english_offline(tmp_path):
    """Downloads the real model (about 120 MB) and checks the audio is speech-length, audible, and not clipped."""
    import numpy as np
    import soundfile as sf
    from vt import tts

    out = tmp_path / "k.wav"
    tts.synth_sentence("kokoro", "af_heart", "Hello. This is a short test of the offline voice.", 1.0, out)
    x, sr = sf.read(str(out), dtype="float32")
    assert sr == tts.SR and 2.0 < len(x) / sr < 8.0 and 0.02 < float(np.sqrt(np.mean(x ** 2))) < 0.5 and float(np.abs(x).max()) < 1.0
