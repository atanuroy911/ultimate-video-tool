"""Hand edits of the voice: cut / trim / split / mute / volume in output time, undo, and the real pipeline applying them."""
import numpy as np
import pytest
import soundfile as sf

from vt import audio_edit as AE
from vt.schema import Cuts
from vt.util import read_json, write_json


def tone_project(ref, seconds=20.0):
    """The reference project with a real 440 Hz voice, a cut stage input and raw words, so the pipeline's cut stage can run."""
    sr = 16000
    t = np.arange(int(seconds * sr)) / sr
    x = (0.5 * np.sin(2 * np.pi * 440 * t)).astype("float32")
    sf.write(str(ref.master), x, sr)
    sf.write(str(ref.dir / "input.wav"), x, sr)
    write_json(ref.dir / "cuts.silence.json", {"cuts": Cuts(source_duration=seconds, keep=[(0.0, seconds)]).model_dump(), "threshold_db": -40, "silences": []})
    from vt.pipeline import Pipeline

    Pipeline(ref).stage_cuts()
    return ref


def test_output_time_maps_to_source_time():
    cuts = Cuts(source_duration=10, keep=[(0, 2), (4, 6), (8, 10)])
    assert AE.out_to_src(cuts, 0.5) == 0.5 and AE.out_to_src(cuts, 2.5) == 4.5 and AE.out_to_src(cuts, 5.5) == 9.5
    assert AE.src_ranges(cuts, 1, 3) == [(1.0, 2.0), (4.0, 5.0)]
    assert AE.src_to_out(cuts, 5.0) == 3.0


def test_cut_merges_and_restores():
    cuts = Cuts(source_duration=10, keep=[(0, 10)])
    e = AE.add_cut(AE.EMPTY, cuts, 2, 3)
    e = AE.add_cut(e, cuts, 2.9, 4)
    assert e["cuts"] == [[2.0, 4.0]]
    with pytest.raises(ValueError):
        AE.add_cut(AE.EMPTY, Cuts(source_duration=10, keep=[(0, 2)]), 5, 6)
    assert AE.restore(e, 0, "start", 0.5)["cuts"] == [[2.5, 4.0]]       # trimmed edge dragged outward
    assert AE.restore(e, 0, "end", 0.5)["cuts"] == [[2.0, 3.5]]
    assert AE.restore(e, 0)["cuts"] == []


def test_mute_gain_and_split_bookkeeping():
    cuts = Cuts(source_duration=10, keep=[(0, 10)])
    e = AE.set_mute(AE.EMPTY, cuts, 1, 3, True)
    e = AE.set_mute(e, cuts, 2, 2.5, False)
    assert e["mutes"] == [[1.0, 2.0], [2.5, 3.0]]
    g = AE.set_gain(AE.EMPTY, cuts, 1, 4, -6)
    g = AE.set_gain(g, cuts, 2, 3, +3)                                  # the new range replaces what it overlaps
    assert [(x["s"], x["e"], x["db"]) for x in g["gains"]] == [(1.0, 2.0, -6.0), (2.0, 3.0, 3.0), (3.0, 4.0, -6.0)]
    assert AE.set_gain(g, cuts, 1, 4, 0)["gains"] == []
    s = AE.add_split(AE.EMPTY, cuts, 5)
    assert s["splits"] == [5.0]
    with pytest.raises(ValueError):
        AE.add_split(s, cuts, 5.01)
    assert AE.remove_split(s, 5.0)["splits"] == []


def test_history_undo_redo(ref):
    cuts = Cuts(source_duration=10, keep=[(0, 10)])
    AE.save(ref, AE.add_cut(AE.load(ref), cuts, 1, 2))
    AE.save(ref, AE.set_mute(AE.load(ref), cuts, 4, 5, True))
    assert AE.load(ref)["mutes"] and AE.undo(ref) and not AE.load(ref)["mutes"] and AE.load(ref)["cuts"]
    assert AE.undo(ref) and not AE.load(ref)["cuts"] and not AE.undo(ref)
    assert AE.redo(ref) and AE.load(ref)["cuts"]
    AE.save(ref, AE.load(ref))                                           # a new edit clears redo
    assert not AE.redo(ref)


def test_pipeline_applies_cuts_mutes_and_gain_to_the_sound(ref):
    from vt.pipeline import Pipeline

    tone_project(ref)
    pl = Pipeline(ref)
    assert sf.info(str(ref.cut_audio)).duration == pytest.approx(20.0, abs=0.01)
    AE.save(ref, {"cuts": [[2.0, 4.0]], "mutes": [[6.0, 7.0]], "gains": [{"s": 8.0, "e": 9.0, "db": -6.0}], "splits": []})
    pl.stage_cuts()
    y, sr = sf.read(str(ref.cut_audio), dtype="float32")
    assert len(y) / sr == pytest.approx(18.0, abs=0.01)                    # 2 s removed and the rest closed up
    rms = lambda a, b: float(np.sqrt(np.mean(y[int(a * sr):int(b * sr)] ** 2)))
    assert rms(1, 1.8) == pytest.approx(0.354, abs=0.02)                  # untouched
    assert rms(4.2, 4.8) < 0.005                                          # the muted second (6-7 s in the source = 4-5 s out)
    assert rms(6.2, 6.8) == pytest.approx(0.354 * 0.5, abs=0.03)          # -6 dB
    assert read_json(ref.cuts_path)["keep"] == [[0.0, 2.0], [4.0, 20.0]]


def test_endpoints_cut_trim_mute_undo_end_to_end(ref, projects_dir):
    from fastapi.testclient import TestClient

    from vt.server.app import app

    tone_project(ref)
    c = TestClient(app)
    base = f"/api/projects/{ref.id}/audio"
    v = c.get(base)
    assert v.status_code == 200 and v.json()["peaks"]["v"] and v.json()["can_undo"] is False
    d0 = v.json()["duration"]
    r = c.post(base + "/cut", json={"start": 2.0, "end": 3.0}).json()
    assert r["duration"] == pytest.approx(d0 - 1.0, abs=0.01) and r["cuts"][0]["len"] == pytest.approx(1.0) and r["can_undo"]
    assert c.get(f"/api/projects/{ref.id}/scenes").json()["plan"]["scenes"]          # the plan followed the new timings
    r = c.post(base + "/restore", json={"index": 0, "side": "start", "amount": 0.4}).json()        # trim dragged outward
    assert r["duration"] == pytest.approx(d0 - 0.6, abs=0.01)
    r = c.post(base + "/mute", json={"start": 5.0, "end": 6.0, "on": True}).json()
    assert r["mutes"] and r["mutes"][0]["o1"] - r["mutes"][0]["o0"] == pytest.approx(1.0, abs=0.01)
    r = c.post(base + "/gain", json={"start": 1.0, "end": 2.0, "db": -9}).json()
    assert r["gains"][0]["db"] == -9
    r = c.post(base + "/split", json={"t": 4.0}).json()
    assert r["splits"]
    assert c.post(base + "/cut", json={"start": 100, "end": 101}).status_code == 422
    for _ in range(5):                                                    # split, gain, mute, restore, cut
        assert c.post(base + "/undo").status_code == 200
    assert c.post(base + "/undo").status_code == 409
    assert c.get(base).json()["duration"] == pytest.approx(d0, abs=0.01) and not c.get(base).json()["cuts"]
    assert c.post(base + "/redo").status_code == 200


def test_a_long_intro_before_the_first_word_is_trimmed(ref):
    from vt.pipeline import Pipeline

    tone_project(ref, 20.0)
    raw = read_json(ref.raw_transcript_path)
    assert min(w["start"] for w in raw["words"]) < 3.0
    first = 9.0
    shift = first - min(w["start"] for w in raw["words"])
    for w in raw["words"]:
        w["start"] += shift
        w["end"] += shift
    write_json(ref.raw_transcript_path, raw)
    Pipeline(ref).stage_cuts(force=True)
    assert abs(ref.cuts().keep[0][0] - (first - 0.6)) < 0.05                # 0.6 s of lead-in stays, the rest of the noise goes


def test_voice_edits_work_on_a_project_without_a_silence_stage(ref):
    from vt.pipeline import Pipeline

    tone_project(ref, 20.0)
    (ref.dir / "cuts.silence.json").unlink()
    ref.cuts_path.unlink()
    AE.save(ref, AE.add_cut(AE.EMPTY, Cuts(source_duration=20.0, keep=[(0.0, 20.0)]), 5.0, 7.0))
    Pipeline(ref).stage_cuts(force=True)
    assert abs(ref.cuts().output_duration - 18.0) < 0.1


def test_a_pasted_sentence_keeps_the_times_of_the_words_that_match():
    from vt import transcript_edit as TE

    old = [("w1", "the"), ("w2", "cat"), ("w3", "sat"), ("w4", "down")]
    assert TE.align(old, "the cat sat down") == {}
    assert TE.align(old, "The cat, sat down.") == {"w1": {"text": "The"}, "w2": {"text": "cat,"}, "w4": {"text": "down."}}   # spelling and punctuation follow the paste
    assert TE.align(old, "the dog sat down") == {"w2": {"text": "dog"}}
    assert TE.align(old, "the cat down") == {"w3": {"drop": True}}                                                       # a missing word is dropped
    assert TE.align(old, "the cat sat very quietly down") == {"w3": {"text": "sat very quietly"}}                       # inserted words ride on the word before
    assert TE.align(old, "so the cat sat down")["w1"] == {"text": "so the"}
    assert TE.align(old, "a big dog slept")  # nothing matches: every word is spread, none is lost silently
    rep = TE.align([("w1", "x"), ("w2", "y"), ("w3", "z")], "one two three four five")
    assert rep == {"w1": {"text": "one"}, "w2": {"text": "two"}, "w3": {"text": "three four five"}}
    shorter = TE.align([("w1", "x"), ("w2", "y"), ("w3", "z")], "one")
    assert shorter == {"w1": {"text": "one"}, "w2": {"drop": True}, "w3": {"drop": True}}



def test_the_clean_voice_switch_lowers_the_noise_between_words(tmp_path):
    """Real speech (samples/audio) with hiss and mains hum added: the speech-to-pause ratio must improve a lot, and the speech must stay audible."""
    import subprocess
    from pathlib import Path

    from vt.render.mux import mix_and_mux
    from vt.util import find_tool

    src = Path(__file__).resolve().parents[1] / "samples" / "audio" / "long_48s.mp3"
    if not src.exists():
        pytest.skip("samples/audio/long_48s.mp3 is not here")
    ff = find_tool("ffmpeg")
    wav = tmp_path / "clean.wav"
    subprocess.run([ff, "-y", "-v", "error", "-t", "20", "-i", str(src), "-ac", "1", "-ar", "48000", str(wav)], check=True)
    x, sr = sf.read(str(wav), dtype="float32")
    rms = lambda a: float(np.sqrt(np.mean(a ** 2)))                                          # noqa: E731
    rng = np.random.default_rng(2)
    noisy = x + rng.standard_normal(len(x)).astype("float32") * rms(x[np.abs(x) > 0.02]) * 0.08 + 0.03 * np.sin(2 * np.pi * 50 * np.arange(len(x)) / sr).astype("float32")
    sf.write(str(tmp_path / "noisy.wav"), noisy, sr)
    hop = int(0.02 * sr)
    n = len(x) // hop
    fr = np.array([rms(x[i * hop:(i + 1) * hop]) for i in range(n)])                           # the CLEAN speech says where the pauses and the talking are
    pause, talk = fr <= np.percentile(fr, 20), (fr >= np.percentile(fr, 60)) & (fr > 0.01)
    silent = tmp_path / "s.mp4"
    subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10:d=20", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(silent)], check=True)

    def ratio(out):
        raw = subprocess.run([ff, "-v", "error", "-i", str(out), "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True).stdout
        y = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        m = min(n, len(y) // hop)
        f2 = np.array([rms(y[i * hop:(i + 1) * hop]) for i in range(m)])
        return 20 * np.log10(f2[talk[:m]].mean() / f2[pause[:m]].mean()), f2[talk[:m]].mean()
    plain, cleaned = tmp_path / "plain.mp4", tmp_path / "clean.mp4"
    mix_and_mux(silent, tmp_path / "noisy.wav", plain, duration=20.0, gpu=False)
    mix_and_mux(silent, tmp_path / "noisy.wav", cleaned, duration=20.0, gpu=False, clean_voice=True)
    (r0, l0), (r1, l1) = ratio(plain), ratio(cleaned)
    assert r1 > r0 + 8, (r0, r1)                                                                # at least 8 dB cleaner between the words
    assert l1 > 0.5 * l0, (l0, l1)                                                              # and the speech did not disappear
