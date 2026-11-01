"""The voice modules (docs/plans/PLAN-VOICESTUDIO.MD V2): one set of verbs over every voice engine, with the engines replaced by fakes."""
import numpy as np
import pytest
import soundfile as sf

from vt import tts
from vt.modules.defs import load
from vt.modules.executor import Executor
from vt.modules.registry import get_module, lint_registry
from vt.modules.workspace import KNOWN_ARTIFACTS

IDS = ("voice.list", "voice.speak", "voice.speak_script", "voice.describe", "voice.design", "voice.clone")


@pytest.fixture()
def ex(tmp_path):
    load()
    (tmp_path / "project.json").write_text("{}", encoding="utf-8")
    return Executor(tmp_path)


def wav(path, seconds=1.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), (np.sin(np.linspace(0, 440 * seconds, int(24000 * seconds))) * 0.1).astype("float32"), 24000)


def test_the_voice_modules_are_registered_and_lint_clean():
    load()
    assert all(get_module(i).plain_name for i in IDS)
    assert lint_registry(known_artifacts=KNOWN_ARTIFACTS) == []
    for i in ("voice.speak", "voice.speak_script", "voice.list"):
        assert "autonomous" in get_module(i).toolboxes                  # an outside director can use them
    assert "autonomous" not in get_module("voice.clone").toolboxes      # cloning is the person's call


def test_listing_flattens_every_ready_engine_and_filters_by_language(ex, monkeypatch):
    monkeypatch.setattr(tts, "list_engines", lambda: [
        {"id": "kokoro", "label": "Kokoro", "available": True, "voices": [{"id": "af_heart", "label": "Heart", "lang": "en"}, {"id": "hf_alpha", "label": "Alpha", "lang": "hi"}]},
        {"id": "edge", "label": "Edge", "available": True, "voices": [{"id": "bn-BD-NabanitaNeural", "label": "Nabanita", "lang": "bn"}]},
        {"id": "mms", "label": "MMS", "available": False, "voices": [{"id": "x", "label": "x", "lang": "bn"}]},
    ])
    r = ex.call("voice.list", {"language": "bn"}, caller="claude", why="choose")
    assert r.ok and [v["id"] for v in r.output["voices"]] == ["edge:bn-BD-NabanitaNeural"] and r.output["engines"] == ["kokoro", "edge"]
    assert len(ex.call("voice.list", {}, caller="claude", why="all").output["voices"]) == 3


def test_speaking_a_sentence_writes_a_sound_in_the_project(ex, monkeypatch, tmp_path):
    seen = {}

    def fake(engine, voice, text, rate, out, instruction="", language="en"):
        seen.update(engine=engine, voice=voice, text=text, rate=rate, instruction=instruction, language=language)
        wav(out, 1.5)

    monkeypatch.setattr(tts, "synth_sentence", fake)
    r = ex.call("voice.speak", {"text": "Hello there.", "voice": "kokoro:af_heart", "rate": 1.1, "instruction": "warm"}, caller="claude", why="a line")
    assert r.ok and r.output["engine"] == "kokoro" and 1.4 < r.output["seconds"] < 1.6 and (tmp_path / r.output["audio"]).exists()
    assert seen == {"engine": "kokoro", "voice": "af_heart", "text": "Hello there.", "rate": 1.1, "instruction": "warm", "language": "en"}


def test_a_voice_that_fails_says_why_and_is_not_swapped_for_another(ex, monkeypatch):
    def broken(*a, **k):
        raise tts.TTSError("The voice server does not answer.")

    monkeypatch.setattr(tts, "synth_sentence", broken)
    r = ex.call("voice.speak", {"text": "Hello.", "voice": "voicestudio:x"}, caller="claude", why="a line")
    assert not r.ok and "does not answer" in r.fix


def test_a_whole_script_comes_back_with_the_real_time_of_every_word(ex, monkeypatch, tmp_path):
    def fake(text, out, *, engine, voice, rate, language=""):
        wav(out, 2.0)
        return {"engine": engine, "voice": voice, "duration": 2.0, "sentences": [{"text": "One.", "start": 0, "end": 1, "words": [{"text": "One", "start": 0.1, "end": 0.6}]},
                                                                               {"text": "Two.", "start": 1, "end": 2, "words": [{"text": "Two", "start": 1.1, "end": 1.6}]}]}

    monkeypatch.setattr(tts, "synthesize", fake)
    r = ex.call("voice.speak_script", {"text": "One. Two.", "voice": "edge:en-US-AriaNeural"}, caller="claude", why="the voice step")
    assert r.ok and r.output["sentences"] == 2 and [w["text"] for w in r.output["words"]] == ["One", "Two"] and r.output["seconds"] == 2.0 and (tmp_path / r.output["audio"]).exists()


def test_describing_a_voice_maps_words_to_what_the_engine_is_asked(ex):
    r = ex.call("voice.describe", {"description": "a deep older man, whispering"}, caller="person", why="what does this mean")
    assert r.ok and "male" in r.output["instruction"] and "elderly" in r.output["instruction"] and "whisper" in r.output["instruction"]
    assert r.output["voice"] == "comfyvoice:design:a deep older man, whispering"


def test_designing_a_voice_speaks_a_sample(ex, monkeypatch, tmp_path):
    seen = {}

    def fake(engine, voice, text, rate, out, instruction="", language="en"):
        seen.update(engine=engine, voice=voice, instruction=instruction)
        wav(out, 1.2)

    monkeypatch.setattr(tts, "synth_sentence", fake)
    r = ex.call("voice.design", {"description": "a bright young woman"}, caller="person", why="hear it")
    assert r.ok and seen["engine"] == "comfyvoice" and seen["voice"] == "design:a bright young woman" and "female" in seen["instruction"]
    assert r.output["voice"] == "comfyvoice:design:a bright young woman" and (tmp_path / r.output["audio"]).exists()


def test_cloning_needs_consent_and_a_real_recording(ex, monkeypatch, tmp_path):
    from vt import voices

    monkeypatch.setattr(voices, "voices_dir", lambda: tmp_path / "voices")
    wav(tmp_path / "me.wav", 14.0)
    no = ex.call("voice.clone", {"audio": "me.wav", "name": "Me", "consent": False}, caller="person", why="clone")
    assert not no.ok and "permission" in no.fix
    missing = ex.call("voice.clone", {"audio": "nothing.wav", "name": "Me", "consent": True}, caller="person", why="clone")
    assert not missing.ok and "no recording" in missing.fix.lower()
