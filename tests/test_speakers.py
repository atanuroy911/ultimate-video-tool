import numpy as np
import pytest
import soundfile as sf

from vt.schema import Beat, Beats, Transcript, Word
from vt.stages import speakers as SP

SR = 16000


def voice(f0, formants, dur, rng, wander=0.06):
    """A vowel-like sound: harmonics of f0 shaped by formant peaks, with natural pitch wander."""
    t = np.arange(int(SR * dur)) / SR
    drift = 1 + wander * np.sin(2 * np.pi * rng.uniform(0.3, 1.2) * t + rng.uniform(0, 6)) + 0.02 * rng.standard_normal() 
    phase = 2 * np.pi * np.cumsum(f0 * drift) / SR
    x = np.zeros_like(t)
    for k in range(1, int(5000 / f0)):
        amp = sum(np.exp(-((k * f0 - fm) / 350) ** 2) for fm in formants) + 0.02
        x += amp * np.sin(k * phase)
    x *= 0.6 + 0.4 * np.sin(2 * np.pi * 3.5 * t) ** 2
    return (0.25 * x / np.abs(x).max()).astype("float32")


def conversation(order, voices, seed=0, dur=2.2):
    """audio + transcript + beats: one sentence per entry of `order`, spoken by voices[name], with pauses between."""
    rng = np.random.default_rng(seed)
    audio, words, beats, t = [np.zeros(int(SR * 0.3), dtype="float32")], [], [], 0.3
    for i, who in enumerate(order):
        f0, fm = voices[who]
        f0 = f0 * rng.uniform(0.9, 1.12)                         # every sentence has its own intonation
        audio.append(voice(f0, fm, dur, rng))
        audio.append(np.zeros(int(SR * 0.4), dtype="float32"))
        ids = []
        for k in range(4):
            w = Word(id=f"w{len(words) + 1}", text=f"x{k}", start=round(t + k * dur / 4, 3), end=round(t + (k + 1) * dur / 4 - 0.05, 3))
            words.append(w)
            ids.append(w.id)
        beats.append(Beat(id=f"b{i + 1}", word_ids=ids, start=round(t, 3), end=round(t + dur, 3), text="x x x x"))
        t += dur + 0.4
    return np.concatenate(audio), Transcript(words=words), Beats(beats=beats)


MAN = (118, (500, 1500, 2500))
WOMAN = (215, (750, 1900, 3200))


def test_two_voices_taking_turns_are_told_apart():
    audio, tr, beats = conversation(["a", "b", "a", "b", "b", "a", "b", "a"], {"a": MAN, "b": WOMAN})
    who = SP.assign(audio, tr, beats)
    assert who is not None
    got = [who[b.id] for b in beats.beats]
    assert got[0] == "Speaker 1" and got == ["Speaker 1" if x == "a" else "Speaker 2" for x in "abababab"[:0] or ["a", "b", "a", "b", "b", "a", "b", "a"]]
    out = SP.label_words(tr, beats, who)
    assert {w.speaker for w in out.words} == {"Speaker 1", "Speaker 2"} and out.words[0].speaker == "Speaker 1"


def test_one_voice_is_never_split_however_much_its_pitch_wanders():
    for seed in range(6):
        audio, tr, beats = conversation(["a"] * 8, {"a": (140, (550, 1600, 2600))}, seed=seed)
        assert SP.assign(audio, tr, beats) is None, seed
    audio, tr, beats = conversation(["a"] * 8, {"a": (125, (500, 1500, 2500))}, seed=9)
    assert SP.assign(audio, tr, beats) is None


def test_a_monologue_followed_by_another_voice_is_not_a_conversation():
    audio, tr, beats = conversation(["a"] * 6 + ["b"] * 2, {"a": MAN, "b": WOMAN})
    assert SP.assign(audio, tr, beats) is None


def test_too_little_speech_or_silence_gives_no_answer():
    audio, tr, beats = conversation(["a", "b"], {"a": MAN, "b": WOMAN})
    assert SP.assign(audio, tr, beats) is None
    assert SP.assign(np.zeros(SR * 10, dtype="float32"), tr, beats) is None


def test_recordings_get_speakers_in_the_pipeline_and_can_be_switched_off(projects_dir, monkeypatch):
    from vt.pipeline import Pipeline
    from vt.project import Project
    import vt.stages.asr as asr_mod
    audio, tr, beats = conversation(["a", "b", "a", "b", "a", "b", "b", "a"], {"a": MAN, "b": WOMAN}, seed=3)
    sf.write(str(projects_dir / "talk.wav"), audio, SR)
    raw = {"language": "en", "model": "fake", "duration": len(audio) / SR, "chunks": [], "chunks_without_speech": 0,
           "words": [{"text": f"word{i}" + ("." if i % 4 == 3 else ""), "start": w.start, "end": w.end, "conf": 1.0} for i, w in enumerate(tr.words)]}
    monkeypatch.setattr(asr_mod, "transcribe", lambda *a, **k: dict(raw))
    p = Project.create("talk", projects_dir / "talk.wav", language="en")
    Pipeline(p).run(to_stage="words")
    names = {w.speaker for w in p.transcript().words}
    assert names == {"Speaker 1", "Speaker 2"} and {b.speaker for b in p.beats().beats} == names
    off = Project.create("talk2", projects_dir / "talk.wav", language="en", options={"speakers": "off"})
    Pipeline(off).run(to_stage="words")
    assert {w.speaker for w in off.transcript().words} == {None}
