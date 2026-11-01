"""language "auto": the person only speaks (or types); the app decides Bangla or English."""
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from vt import langdetect


def test_pick_respects_allowed_languages():
    probs = [("hi", 0.6), ("bn", 0.2), ("en", 0.15)]
    assert langdetect.pick(probs)[0] == "hi"
    assert langdetect.pick(probs, ["bn", "en"])[0] == "bn"
    assert langdetect.pick([("en", 0.9), ("bn", 0.05)], ["bn", "en"])[0] == "en"


def test_asr_stage_detects_and_remembers_the_language(projects_dir, tmp_path, monkeypatch):
    from vt.pipeline import Pipeline
    from vt.project import Project

    wav = tmp_path / "in.wav"
    sf.write(wav, np.zeros(16000, dtype="float32"), 16000)
    p = Project.create("Auto", wav, language="auto")
    seen = {}

    def fake(path, progress=None, allowed=None):
        seen["allowed"] = allowed
        return "en", 0.8

    monkeypatch.setattr(langdetect, "from_audio", fake)
    meta = Pipeline(p)._detect_language()
    assert meta.language == "en" and p.meta().language == "en" and seen["allowed"] == ["bn", "en"]

    def broken(*a, **k):
        raise RuntimeError("no model, no network")

    p.update_meta(language="auto")
    monkeypatch.setattr(langdetect, "from_audio", broken)
    assert Pipeline(p)._detect_language().language == "bn"


@pytest.mark.parametrize("text,lang,voice_prefix", [("আমি আজ একটা গল্প বলব।", "bn", "bn-"), ("Today I will tell you a story.", "en", "en-")])
def test_script_auto_language_picks_a_matching_voice(projects_dir, text, lang, voice_prefix):
    from vt.server.app import app

    with TestClient(app) as c:
        r = c.post("/api/projects/from-script", json={"title": "x", "script": text, "language": "auto", "start": False})
        assert r.status_code == 200, r.text
        from vt.project import Project
        from vt.util import read_json

        p = Project(r.json()["project"]["id"])
        assert p.meta().language == lang
        assert read_json(p.script_path)["voice"].startswith(voice_prefix)       # the default Bangla voice was swapped for an English one
