"""F7 input boundaries, using tiny fixtures and fake processors; no models or renders."""
import numpy as np
import pytest

from vt import ingest
from vt.pipeline import NO_SPEECH_MESSAGE, NoSpeechError, Pipeline
from vt.project import Project
from vt.util import read_json, write_json


@pytest.fixture()
def input_project(projects_dir, tmp_path):
    recording = tmp_path / "recording.wav"
    recording.write_bytes(b"fake media; processors in this file are replaced")
    return Project.create("Input test", recording, language="en")


@pytest.fixture()
def fake_pipeline(monkeypatch):
    from vt import gpu

    monkeypatch.setattr(gpu, "prepare", lambda: None)
    monkeypatch.setattr(Pipeline, "director", lambda self: "rules")
    monkeypatch.setattr(Pipeline, "_director_provider", lambda *args: None)


@pytest.mark.parametrize("contents", [
    "1\n00:00:03,000 --> 00:00:01,000\nBackwards.\n",
    "1\n00:00:01,000 --> 00:00:01,000\nNo duration.\n",
    "1\n00:00:61,000 --> 00:01:03,000\nInvalid seconds.\n",
    "1\n-00:00:01,000 --> 00:00:02,000\nNegative start.\n",
    "1\n00:00:01,000 -> 00:00:02,000\nWrong arrow.\n",
    "1\n00:00:00,000 --> 00:00:01,000\nValid first line.\n\n2\nWrong timing\nDo not silently drop this.\n",
    "1\n00:00:01,000 --> 00:00:02,000\n\n",
])
def test_malformed_personal_subtitles_are_refused_before_writing(input_project, tmp_path, contents):
    subtitles = tmp_path / "wrong.srt"
    subtitles.write_text(contents, encoding="utf-8")
    before = input_project.meta_path.read_bytes()

    with pytest.raises(ValueError, match="[Ss]ubtitle"):
        ingest.attach_subtitles(input_project, subtitles)

    assert input_project.meta_path.read_bytes() == before
    assert not (input_project.dir / "subs.raw.json").exists()
    assert not (input_project.dir / "subtitles.srt").exists()


def test_a_bad_replacement_keeps_the_existing_subtitles(input_project, tmp_path):
    good = tmp_path / "good.srt"
    good.write_text("1\n00:00:00,000 --> 00:00:01,000\nKeep these words.\n", encoding="utf-8")
    ingest.attach_subtitles(input_project, good)
    kept = {p.name: p.read_bytes() for p in input_project.dir.iterdir() if p.is_file()}
    good.write_text("1\n00:00:02,000 --> 00:00:01,000\nBad replacement.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="[Ss]ubtitle"):
        ingest.attach_subtitles(input_project, good)

    assert {p.name: p.read_bytes() for p in input_project.dir.iterdir() if p.is_file()} == kept


def test_subtitle_encoding_error_is_actionable(input_project, tmp_path):
    subtitles = tmp_path / "wrong.srt"
    subtitles.write_bytes(b"1\n00:00:00,000 --> 00:00:01,000\n\xff\xfe\n")
    with pytest.raises(ValueError, match="UTF-8"):
        ingest.attach_subtitles(input_project, subtitles)


def test_malformed_subtitle_upload_creates_no_project_or_job(projects_dir, monkeypatch):
    from fastapi.testclient import TestClient
    import vt.server.app as api

    started = []
    monkeypatch.setattr(api, "start_pipeline", lambda *args: started.append(args))
    monkeypatch.setattr(api, "_inspect", lambda path: {"mode": "audio", "has_picture": False})
    before = Project.list_all()
    client = TestClient(api.app)  # No lifespan: do not start discovery services for an in-process API test.
    result = client.post("/api/projects", files={"audio": ("recording.wav", b"fake media"),
                                                   "subtitles": ("wrong.srt", b"1\n00:00:02,000 --> 00:00:01,000\nWrong.\n")},
                         data={"title": "Invalid subtitles", "start": "true"})
    assert result.status_code == 400 and "Subtitle" in result.json()["detail"]
    assert Project.list_all() == before
    assert list(projects_dir.iterdir()) == []
    assert started == []


def test_valid_subtitle_upload_still_attaches_after_preflight(projects_dir, monkeypatch):
    from fastapi.testclient import TestClient
    import vt.server.app as api

    monkeypatch.setattr(api, "_inspect", lambda path: {"mode": "audio", "has_picture": False})
    monkeypatch.setattr(api, "_set_usecase", lambda project, *args: project)
    monkeypatch.setattr(api, "_set_kind", lambda *args: None)
    client = TestClient(api.app)
    result = client.post("/api/projects", files={"audio": ("recording.wav", b"fake media"),
                                                   "subtitles": ("words.srt", b"1\n00:00:00,000 --> 00:00:01,000\nHello there.\n")},
                         data={"title": "Good subtitles", "start": "false"})
    assert result.status_code == 200, result.text
    project = Project(result.json()["project"]["id"])
    assert result.json()["job"] is None
    assert [word["text"] for word in read_json(project.dir / "subs.raw.json")["words"]] == ["Hello", "there."]
    assert (project.dir / "subtitles.srt").is_file()


def test_valid_vtt_metadata_identifiers_settings_and_bangla_are_kept(input_project, tmp_path):
    subtitles = tmp_path / "লেখা 😀.vtt"
    subtitles.write_text("\ufeffWEBVTT\nKind: captions\n\nNOTE a comment\nnot a cue\n\nSTYLE\n::cue { color: white; }\n\n"
                         "opening\n00:00:00.500 --> 00:00:02.000 align:start position:10%\nহ্যালো <b>বিশ্ব</b>\n\n"
                         "ending\n00:02.100 --> 00:03.000\nHello world.\n", encoding="utf-8")
    result = ingest.attach_subtitles(input_project, subtitles, "auto")
    assert result == {"lines": 2, "words": 4, "language": "bn"}
    raw = read_json(input_project.dir / "subs.raw.json")
    assert raw["exact"] and raw["words"][0]["start"] == 0.5 and raw["words"][-1]["end"] == 3
    assert input_project.meta().origin["subtitle_file"] == subtitles.name


@pytest.mark.parametrize("downloaded", [[], {"events": None}, {"events": [None]}, {"events": [{"segs": "wrong shape"}]}])
def test_malformed_downloaded_captions_fall_back_to_recognition(tmp_path, downloaded):
    subtitles = tmp_path / "download.json3"
    write_json(subtitles, downloaded)
    assert ingest.raw_transcript_from_subs(subtitles, "en", 10) is None


@pytest.mark.parametrize("decoder_error", [
    "Invalid data found when processing input",
    "moov atom not found",
    "Output file #0 does not contain any stream",
])
def test_corrupt_media_has_a_plain_error_and_can_be_retried(input_project, fake_pipeline, monkeypatch, decoder_error):
    from vt.stages import audio

    def fail(*args, **kwargs):
        raise RuntimeError("command failed (1): ffmpeg -i private-recording.wav\n" + decoder_error)

    monkeypatch.setattr(audio, "preprocess", fail)
    with pytest.raises(RuntimeError, match="This recording could not be read") as error:
        Pipeline(input_project).run(to_stage="preprocess")
    assert "Try" in str(error.value) and "command failed" not in str(error.value)
    assert input_project.meta().status == "error"
    assert "preprocess" not in input_project.meta().stages
    assert not input_project.scenes_path.exists()

    def repair(src, master, asr_wav, **kwargs):
        master.write_bytes(b"fake decoded master")
        asr_wav.write_bytes(b"fake decoded speech input")

    monkeypatch.setattr(audio, "preprocess", repair)
    Pipeline(input_project).run(to_stage="preprocess")
    assert input_project.meta().status == "planned"
    assert "preprocess" in input_project.meta().stages


def test_preprocess_infrastructure_errors_keep_their_actual_reason(input_project, fake_pipeline, monkeypatch):
    from vt.stages import audio

    def fail(*args, **kwargs):
        raise RuntimeError("There is not enough space on the disk.")

    monkeypatch.setattr(audio, "preprocess", fail)
    with pytest.raises(RuntimeError, match="not enough space"):
        Pipeline(input_project).run(to_stage="preprocess")
    assert input_project.meta().status == "error"


def test_silence_has_a_plain_recoverable_error_without_a_model(input_project, fake_pipeline, monkeypatch):
    from vt.stages import asr, audio

    input_project.asr_wav.write_bytes(b"fake silence")
    monkeypatch.setattr(audio, "find_silences", lambda *args, **kwargs: ([(0.0, 4.0)], 4.0, -40.0, np.full(400, -90.0)))
    requested = []

    def recognize(*args, **kwargs):
        requested.append(kwargs["chunks"])
        return {"words": [], "duration": 4.0}

    monkeypatch.setattr(asr, "transcribe", recognize)
    monkeypatch.setattr(Pipeline, "_captions_from_sounds", lambda *args: None)
    with pytest.raises(NoSpeechError, match="No speech was found") as error:
        Pipeline(input_project).run(from_stage="asr", to_stage="asr")
    assert str(error.value) == NO_SPEECH_MESSAGE
    assert requested == [[]]
    assert input_project.meta().status == "error"
    assert not input_project.raw_transcript_path.exists()
    assert not input_project.scenes_path.exists()


def test_two_hours_are_chunked_with_bounded_windows_without_decoding_audio(input_project, fake_pipeline, monkeypatch):
    from vt.stages import asr, audio

    duration = 2 * 60 * 60
    input_project.asr_wav.write_bytes(b"metadata only; not a two-hour recording")
    monkeypatch.setattr(audio, "find_silences", lambda *args, **kwargs: ([], duration, -40.0, None))
    monkeypatch.setattr(Pipeline, "_captions_from_sounds", lambda *args: None)
    requested = []

    def recognize(*args, **kwargs):
        requested.extend(kwargs["chunks"])
        return {"duration": duration, "words": [{"text": "Start", "start": 0.1, "end": 0.5},
                                                   {"text": "End", "start": duration - 1.0, "end": duration - 0.5}]}

    monkeypatch.setattr(asr, "transcribe", recognize)
    Pipeline(input_project).run(from_stage="asr", to_stage="asr")
    assert len(requested) == 480
    assert requested[0][0] == 0 and requested[-1][1] == duration
    assert all(0 < end - start <= 15.301 for start, end in requested)
    assert all(next_start <= end for (_, end), (next_start, _) in zip(requested, requested[1:]))
    assert read_json(input_project.raw_transcript_path)["duration"] == duration
    assert input_project.meta().status == "planned"
    assert "120 minutes" in ingest._too_long({"duration": duration})  # links retain their existing 60-minute download limit


def test_one_word_script_survives_voice_timing_and_produces_a_valid_rule_scene(projects_dir, monkeypatch):
    from vt import tts
    from vt.planner import plan_rules
    from vt.planner.catalogue import all_icon_names
    from vt.schema import Cuts, validate_scenes
    from vt.stages import asr, audio, words

    project = Project.create_from_script("One word", "Hello!", language="en", options={"voice_direction": "off"})

    def speak(text, output, **kwargs):
        assert text == "Hello!"
        output.write_bytes(b"fake spoken word")
        return {"duration": 1.0, "engine": "edge", "sentences": [{"words": [{"text": text, "start": 0.1, "end": 0.8}]}]}

    def forbid(*args, **kwargs):
        raise AssertionError("Speech recognition must not run for a typed script")

    monkeypatch.setattr(tts, "synthesize", speak)
    monkeypatch.setattr(asr, "transcribe", forbid)
    monkeypatch.setattr(audio, "find_silences", lambda *args, **kwargs: ([], 1.0, -40.0, None))
    Pipeline(project).stage_voice()
    Pipeline(project).stage_asr()
    transcript = words.build_transcript(read_json(project.raw_transcript_path), Cuts(source_duration=1.0, keep=[(0.0, 1.0)]), language="en")
    beats = words.build_beats(transcript)
    scenes = plan_rules(transcript, beats, language="en", picks={})
    assert [word.text for word in transcript.words] == ["Hello!"]
    assert len(beats.beats) == len(scenes.scenes) == 1
    assert not validate_scenes(scenes, transcript, beats, all_icon_names())


@pytest.mark.parametrize("title", ["লেখা 😀 東京", "../folder/../../quotes ' & $ ;", "CON", "...", "clip.", "a" * 39 + ".truncated", "<script>alert(1)</script>"])
def test_unusual_titles_stay_readable_and_cannot_escape_the_project_store(projects_dir, tmp_path, title):
    source = tmp_path / "রেকর্ডিং 😀.WAV"
    source.write_bytes(b"fake media")
    project = Project.create(title, source)
    second = Project.create(title, source)
    assert project.dir.resolve().parent == projects_dir.resolve()
    assert second.dir.resolve().parent == projects_dir.resolve()
    assert project.id != second.id
    assert project.meta().title == title
    assert project.input_audio.name == "input.wav"
    assert project.input_audio.read_bytes() == b"fake media"
    assert not project.id.endswith(".")
