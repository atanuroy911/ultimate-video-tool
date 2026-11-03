"""Your own voices: consent is required, bad recordings are refused with a reason, the files are safe, and the helper process protocol works (with a stand-in for the 3 GB model)."""
import json

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from vt import paths, tts, voices as V


@pytest.fixture()
def vdir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA", tmp_path)
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    yield tmp_path
    V.stop()


def speechlike(path, seconds=8.0, amp=0.4, sr=24000):
    t = np.arange(int(seconds * sr)) / sr
    x = amp * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))          # a voiced hum that rises and falls like syllables
    sf.write(str(path), x.astype("float32"), sr)
    return path


def test_a_voice_needs_consent_a_name_and_a_usable_recording(vdir, tmp_path):
    ok = speechlike(tmp_path / "ok.wav")
    with pytest.raises(V.VoiceError, match="permission"):
        V.add_voice(ok, "Me", consent=False)
    with pytest.raises(V.VoiceError, match="name"):
        V.add_voice(ok, "  ", consent=True)
    with pytest.raises(V.VoiceError, match="at least"):
        V.add_voice(speechlike(tmp_path / "short.wav", 2.0), "Me", True)
    with pytest.raises(V.VoiceError, match="silent"):
        V.add_voice(speechlike(tmp_path / "quiet.wav", 8.0, amp=0.005), "Me", True)
    sf.write(str(tmp_path / "clip.wav"), np.clip(np.random.randn(24000 * 8) * 3, -1, 1).astype("float32"), 24000)
    with pytest.raises(V.VoiceError, match="distorted"):
        V.add_voice(tmp_path / "clip.wav", "Me", True)
    (tmp_path / "junk.wav").write_bytes(b"not audio")
    with pytest.raises(V.VoiceError, match="could not be read"):
        V.add_voice(tmp_path / "junk.wav", "Me", True)
    assert V.list_voices() == []                                                           # nothing was kept from the refusals


def test_a_voice_is_kept_trimmed_normalised_and_listed(vdir, tmp_path):
    v = V.add_voice(speechlike(tmp_path / "long.wav", 50.0), "My Voice", True)
    assert v["id"] == "my-voice" and v["seconds"] <= V.REF_SECONDS + 0.1
    x, sr = sf.read(str(V.ref_path("my-voice")), dtype="float32")
    assert sr == 24000 and 0.85 < float(np.abs(x).max()) <= 0.91
    meta = json.loads((vdir / "voices" / "my-voice" / "voice.json").read_text(encoding="utf-8"))
    assert meta["consent"] is True and meta["name"] == "My Voice" and meta["created"]
    assert V.add_voice(speechlike(tmp_path / "again.wav"), "My Voice", True)["id"] == "my-voice-2"    # the same name does not overwrite
    assert [x["id"] for x in V.list_voices()] == ["my-voice", "my-voice-2"]
    assert V.remove_voice("my-voice") and not V.remove_voice("my-voice") and not V.remove_voice("../etc")
    with pytest.raises(V.VoiceError):
        V.ref_path("../settings")


class FakeEngine:
    """Stands in for the 1.1 GB model: two seconds of a quiet tone, or an error."""

    def __init__(self, mode="ok"):
        self.mode, self.calls = mode, []

    def speak(self, text, reference, cancel=None, progress=None, seed=None):
        from vt import clone_onnx as CO

        self.calls.append((text, len(reference)))
        if self.mode == "error":
            raise CO.CloneError("out of memory")
        t = np.arange(24000 * 2) / 24000
        if progress:
            progress(1.0)
        return (0.05 * np.sin(2 * np.pi * 220 * t)).astype("float32")


def fake_engine(monkeypatch, mode="ok"):
    eng = FakeEngine(mode)
    monkeypatch.setattr(V, "_load", lambda progress=None: eng)
    return eng


def test_the_engine_speaks_at_a_normal_level_and_its_failures_become_readable_errors(vdir, tmp_path, monkeypatch):
    V.add_voice(speechlike(tmp_path / "v.wav"), "Me", True)
    eng = fake_engine(monkeypatch)
    out = tmp_path / "o.wav"
    assert abs(V.say("Hello", "me", out) - 2.0) < 0.01 and out.exists()
    y, sr = sf.read(str(out))
    rms = 20 * np.log10(np.sqrt(np.mean(y * y)))
    assert sr == 24000 and abs(rms - V.SPEECH_DB) < 0.5 and np.abs(y).max() <= V.PEAK + 1e-6          # the model writes about -26 dB; it is brought to a normal level
    assert eng.calls[0][0] == "Hello" and eng.calls[0][1] > 24000 * 4                                  # the saved reference voice was given to the engine
    tts.synth_sentence("clone", "me", "Hello again.", 1.0, tmp_path / "t.wav")                  # through the text-to-speech engine, at 24 kHz
    x, sr = sf.read(str(tmp_path / "t.wav"))
    assert sr == tts.SR and 1.9 < len(x) / sr < 2.1
    tts.synth_sentence("clone", "me", "Faster.", 1.25, tmp_path / "t2.wav")
    x2, sr2 = sf.read(str(tmp_path / "t2.wav"))
    assert len(x2) / sr2 < len(x) / sr - 0.2                                                    # speed is applied afterwards
    fake_engine(monkeypatch, "error")
    with pytest.raises(V.VoiceError, match="out of memory"):
        V.say("Hello", "me", out)
    with pytest.raises(tts.TTSError):
        tts.synth_sentence("clone", "nobody", "x", 1.0, out)


def test_level_brings_any_voice_to_speech_level_without_clipping():
    quiet = (0.01 * np.sin(np.arange(24000) * 0.05)).astype("float32")
    loud = (0.99 * np.sin(np.arange(24000) * 0.05)).astype("float32")
    spiky = quiet.copy()
    spiky[100] = 0.9
    for x in (quiet, loud, spiky):
        y = V.level(x)
        assert np.abs(y).max() <= V.PEAK + 1e-6
    assert abs(20 * np.log10(np.sqrt(np.mean(V.level(quiet) ** 2))) - V.SPEECH_DB) < 0.5
    assert not V.level(np.zeros(100, "float32")).any() and len(V.level(np.zeros(0, "float32"))) == 0


def test_the_model_is_fetched_on_first_use_and_a_failed_fetch_is_a_readable_error(vdir, tmp_path, monkeypatch):
    from vt import models

    V.add_voice(speechlike(tmp_path / "v.wav"), "Me", True)
    V.stop()

    def no_network(model_id, progress=None, cancel=None):
        raise models.ModelError("Voice cloning has to be downloaded once (about 1123 MB). Connect to the internet and try again.")
    monkeypatch.setattr(models, "ensure", no_network)
    with pytest.raises(V.VoiceError, match="downloaded once"):
        V.say("Hello", "me", tmp_path / "x.wav")


def test_the_engine_list_shows_my_voices_and_what_is_missing(vdir, tmp_path, monkeypatch):
    e = next(x for x in tts.list_engines() if x["id"] == "clone")
    assert e["voices"] == [] and e["available"] is False                                       # nothing to speak with until a voice is added
    V.add_voice(speechlike(tmp_path / "v.wav"), "Me", True)
    e = next(x for x in tts.list_engines() if x["id"] == "clone")
    assert e["available"] is True and e["voices"][0]["id"] == "me"


def test_the_api_adds_lists_serves_and_deletes_voices(vdir, tmp_path):
    from vt.server.app import app

    c = TestClient(app)
    f = speechlike(tmp_path / "up.wav")
    no = c.post("/api/my-voices", files={"file": ("up.wav", f.read_bytes(), "audio/wav")}, data={"name": "Me", "consent": "false"})
    assert no.status_code == 422 and "permission" in json.dumps(no.json())
    ok = c.post("/api/my-voices", files={"file": ("up.wav", f.read_bytes(), "audio/wav")}, data={"name": "Me", "consent": "true"}).json()
    assert ok["id"] == "me" and c.get("/api/my-voices").json()["voices"][0]["name"] == "Me"
    assert c.get("/api/my-voices/me/sample").status_code == 200 and c.get("/api/my-voices/..%2f..%2fsettings/sample").status_code in (404, 422)
    assert c.delete("/api/my-voices/me").status_code == 200 and c.delete("/api/my-voices/me").status_code == 404


def test_overdub_says_the_words_again_in_my_voice_mutes_the_original_and_places_it(vdir, tmp_path, monkeypatch, ref):
    import time

    from vt import audio_edit as AE, layers as L
    from vt.server.app import app

    sf.write(str(ref.master), np.zeros(24000 * 20, dtype="float32") + 0.1, 24000)
    V.add_voice(speechlike(tmp_path / "v.wav"), "Me", True)
    fake_engine(monkeypatch)
    c = TestClient(app)
    dur = ref.cuts().output_duration
    bad = c.post("/api/projects/reference/voice/overdub", json={"text": " ", "voice": "me", "start": 1, "end": 2})
    assert bad.status_code == 422
    assert c.post("/api/projects/reference/voice/overdub", json={"text": "x", "voice": "nobody", "start": 1, "end": 2}).status_code == 404
    assert c.post("/api/projects/reference/voice/overdub", json={"text": "x", "voice": "me", "start": 5, "end": 4}).status_code == 422
    assert c.post("/api/projects/reference/voice/overdub", json={"text": "x", "voice": "me", "start": 1, "end": dur + 50}).status_code == 422
    job = c.post("/api/projects/reference/voice/overdub", json={"text": "The right word", "voice": "me", "start": 2.0, "end": 4.0}).json()
    for _ in range(300):
        j = c.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.2)
    assert j["status"] == "done", j
    doc = L.load(ref)
    clip = next(x for x in doc["clips"] if x["type"] == "audio")
    assert clip["start"] == 2.0 and abs(clip["dur"] - 2.0) < 0.2 and any(t["name"] == "My voice" for t in doc["tracks"])
    assert AE.load(ref)["mutes"]                                                                     # the original words are silenced
    assert L.audio_clips(ref)[0]["path"].endswith(".m4a")                                           # and the new ones go into the mix
    # A second one stays at the requested time on its own track; it never silently slides later.
    job2 = c.post("/api/projects/reference/voice/overdub", json={"text": "Another", "voice": "me", "start": 2.5, "end": 4.5, "mute": False}).json()
    for _ in range(300):
        j = c.get(f"/api/jobs/{job2['id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.2)
    assert j["status"] == "done", j
    clips = sorted((x for x in L.load(ref)["clips"] if x["type"] == "audio"), key=lambda x: x["start"])
    assert len(clips) == 2 and clips[1]["start"] == 2.5 and clips[1]["track"] != clips[0]["track"]
