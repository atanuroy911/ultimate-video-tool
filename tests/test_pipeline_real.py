"""Integration tests with the real speech model (slow, need the downloaded Bangla model and a few seconds of GPU/CPU).
Skipped automatically when the model is not installed (vt models pull bn-medium)."""
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

pytestmark = [pytest.mark.slow, pytest.mark.models]
SAMPLES = Path(__file__).resolve().parents[1] / "samples" / "audio"


@pytest.fixture(scope="module", autouse=True)
def _needs_model():
    from vt.stages import asr

    if not (asr.model_dir("bn-medium") / "model.bin").exists():
        pytest.skip("Bangla model not downloaded (vt models pull bn-medium)")


def _project(projects_dir, audio: Path, title="t"):
    from vt.project import Project

    return Project.create(title, audio, pace="normal", options={"remove_fillers": True})


def test_noise_and_silence_are_reported_as_no_speech(projects_dir, tmp_path):
    from vt.pipeline import NoSpeechError, Pipeline

    rng = np.random.default_rng(3)
    for name, data in {"silence": np.zeros(16000 * 4, dtype=np.float32),
                       "noise": (0.05 * rng.normal(size=16000 * 4)).astype(np.float32)}.items():
        wav = tmp_path / f"{name}.wav"
        sf.write(str(wav), data, 16000)
        p = _project(projects_dir, wav, name)
        with pytest.raises(NoSpeechError):
            Pipeline(p).run()
        assert p.meta().status == "error"
        assert not p.scenes_path.exists()          # nothing half-built is left looking valid


def test_bangla_clip_end_to_end(projects_dir):
    clip = SAMPLES / "bn_plain.mp3"
    if not clip.exists():
        pytest.skip("run scripts/make_sample_audio.py first")
    from vt.pipeline import Pipeline, compose_all
    from vt.planner.catalogue import all_icon_names
    from vt.schema import validate_scenes

    p = _project(projects_dir, clip)
    Pipeline(p).run()
    tr = p.transcript()
    words = tr.kept()
    assert len(words) >= 26
    assert words[0].text == "yield" and words[0].start < 0.5       # first word present and timed at the speech onset (default policy: Latin letters)
    assert all(a.end <= b.start + 1e-6 for a, b in zip(words, words[1:]))
    assert all(0.04 <= w.end - w.start <= 2.5 for w in words)      # no word swallows a whole pause
    cuts = p.cuts()
    assert cuts.output_duration < cuts.source_duration - 2         # the long TTS pauses were cut
    assert words[-1].end <= cuts.output_duration + 0.01
    sf_ = p.scenes()
    assert validate_scenes(sf_, tr, p.beats(), all_icon_names()) == []
    assert (p.comp_dir / "9x16" / "data.json").exists() and (p.comp_dir / "16x9" / "data.json").exists()
    # a second run does no work (every stage is cached by input hash)
    before = {k: v["done_at"] for k, v in p.meta().stages.items()}
    Pipeline(p).run()
    assert {k: v["done_at"] for k, v in p.meta().stages.items()} == before


def test_long_recording_is_not_truncated_at_whisper_windows(projects_dir, tmp_path):
    a, b = SAMPLES / "bn_plain.mp3", SAMPLES / "banglish.mp3"
    if not (a.exists() and b.exists()):
        pytest.skip("run scripts/make_sample_audio.py first")
    import subprocess

    long = tmp_path / "long.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(a), "-i", str(b), "-i", str(a), "-filter_complex",
                    "[0:a]aresample=24000,apad=pad_dur=1[a];[1:a]aresample=24000,apad=pad_dur=1[b];[2:a]aresample=24000[c];[a][b][c]concat=n=3:v=0:a=1[o]",
                    "-map", "[o]", str(long)], check=True)
    from vt.pipeline import Pipeline

    p = _project(projects_dir, long, "long")
    Pipeline(p).run(to_stage="words")
    n = len(p.transcript().kept())
    assert n >= 92, f"only {n} of ~99 words survived: long audio is being truncated (30 s window regression)"
