"""Phase 2 core adapters stay equivalent to the functions and stages they wrap."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import soundfile as sf

from vt.modules.defs import load
from vt.modules.executor import Executor
from vt.modules.registry import get_module
from vt.pipeline import Pipeline
from vt.project import Project
from vt.util import write_json


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_core_catalogue_has_canonical_adapters():
    load()
    for module_id in (
        "audio.speak_script", "audio.clean", "audio.find_silences", "asr.transcribe",
        "asr.from_subtitles",
        "audio.cut", "audio.events", "text.build_transcript", "audio.tighten",
        "audio.detect_language", "audio.pause_sentences", "text.rank_sentences", "project.options",
        "audio.edit",
        "audio.emphasis",
        "audio.voices", "audio.clone_voice",
        "audio.speakers",
        "understand.highlights", "publish.shorts_slice",
        "fill.placeholder", "fill.text_card", "fill.user_media", "fill.still_zoom", "fill.speaker",
        "understand.context", "understand.roles", "direct.plan_scenes", "direct.choose_music",
        "understand.key_terms", "understand.usecase",
        "direct.learn_taste", "direct.taste_hint",
        "text.tidy_for_screen", "timeline.compose",
        "timeline.captions", "timeline.motion", "timeline.contrast",
        "timeline.validate", "timeline.heartbeat",
        "timeline.layers",
        "timeline.edit_scene",
        "gen.status", "gen.workflows", "gen.free_memory", "gen.cancel", "gen.video_from_image",
        "gen.cutout", "timeline.thumbs",
        "render.export", "publish.kit",
        "render.snapshot", "render.silent",
        "publish.credits",
        "sound.sfx_place", "audio.beats", "cut.snap_beat",
        "sound.sounds_to_pictures",
        "meta.health", "meta.hardware", "meta.models",
        "meta.catalog", "meta.describe", "meta.state", "meta.dry_run", "meta.undo",
        "meta.wait", "meta.cancel", "meta.note",
        "judge.script", "direct.critique", "direct.enrich", "judge.scorecard",
        "project.add_media", "project.remove_media", "project.add_sound",
        "project.load_theme", "design.build_theme",
        "sound.music_pick", "timeline.theme", "text.polish", "understand.media",
        "direct.write_copy", "timeline.compile",
        "audio.speak_sentence", "direct.plan_script",
        "direct.talk", "judge.vision_qa", "judge.picture",
        "understand.faces", "understand.people", "understand.video_shots",
        "understand.visual_for_word", "text.fix", "sound.mix",
        "project.create", "project.fetch_link", "direct.revise_script",
    ):
        assert get_module(module_id).id == module_id


def test_audio_clean_is_byte_equivalent_to_legacy_stage(projects_dir, tmp_path):
    source = tmp_path / "voice.wav"
    t = np.arange(24000, dtype=np.float32) / 24000
    sf.write(str(source), 0.04 * np.sin(2 * np.pi * 220 * t), 24000)
    classic = Project.create("classic clean", source, language="en", pid="classic-clean")
    wrapped = Project.create("wrapped clean", source, language="en", pid="wrapped-clean")
    Pipeline(classic).stage_preprocess()
    result = Executor(wrapped.dir).call("audio.clean", {"force": False})
    assert result.ok, result.fix
    assert _hash(classic.master) == _hash(wrapped.master)
    assert _hash(classic.asr_wav) == _hash(wrapped.asr_wav)


def test_language_pause_and_rank_match_existing_algorithms(tmp_path):
    from vt.langdetect import from_text
    from vt.pausesplit import boundaries
    from vt.saliency import lexrank, mmr_select, similarity_matrix

    executor = Executor(tmp_path)
    language = executor.call("audio.detect_language", {"text": "আমি আজকে বাজারে যাব"})
    assert language.output["language"] == from_text("আমি আজকে বাজারে যাব") == "bn"

    words = [
        {"text": "hello", "start": 0.0, "end": 0.2},
        {"text": "world", "start": 0.3, "end": 0.5},
        {"text": "again", "start": 1.8, "end": 2.0},
    ]
    executor.ws.put_json("transcript.raw", {"words": words}, call_id="seed")
    pauses = executor.call("audio.pause_sentences", {})
    assert pauses.output["boundaries"] == boundaries(words)

    sentences = ["Cats sleep on mats.", "Cats rest on rugs.", "Rockets cross space."]
    ranked = executor.call("text.rank_sentences", {"sentences": sentences, "keep": 2})
    scores = lexrank(sentences)
    assert ranked.output["scores"] == scores
    assert ranked.output["selected"] == mmr_select(scores, similarity_matrix(sentences), 2)


def test_project_options_validates_and_preserves_project(projects_dir, tmp_path):
    source = tmp_path / "quiet.wav"
    sf.write(str(source), np.zeros(2400, dtype=np.float32), 24000)
    project = Project.create("options", source, language="bn", theme="paper", pid="options")
    result = Executor(project.dir).call("project.options", {
        "language": "en", "aspect": "16:9", "pace": "fast",
        "options": {"remove_fillers": False},
    })
    assert result.ok, result.fix
    meta = project.meta()
    assert (meta.language, meta.aspect, meta.pace) == ("en", "16:9", "fast")
    assert meta.options.remove_fillers is False and meta.title == "options"


def test_asr_alias_uses_existing_subtitle_path_without_a_model(projects_dir, tmp_path):
    source = tmp_path / "speech.wav"
    sf.write(str(source), np.zeros(24000, dtype=np.float32), 24000)
    project = Project.create("subtitles", source, language="en", pid="subtitles")
    Pipeline(project).stage_preprocess()
    Pipeline(project).stage_silence()
    write_json(project.dir / "subs.raw.json", {"words": [
        {"text": "hello", "start": 0.1, "end": 0.4},
        {"text": "world", "start": 0.5, "end": 0.9},
    ]})
    result = Executor(project.dir).call("asr.transcribe", {"force": False})
    assert result.ok, result.fix
    assert project.raw_transcript_path.exists()
    assert result.output == {"stage": "asr"}


def test_understanding_direction_and_compose_aliases_run_on_reference(ref):
    executor = Executor(ref.dir)
    context = executor.call("understand.context", {"force": False})
    assert context.ok, context.fix
    roles = executor.call("understand.roles", {})
    assert roles.ok and len(roles.output["sentences"]) == len(ref.beats().beats)
    plan = executor.call("direct.plan_scenes", {"force": False})
    assert plan.ok, plan.fix
    composed = executor.call("timeline.compose", {"force": False})
    assert composed.ok, composed.fix
    assert (ref.comp_dir / "9x16" / "data.json").exists()


def test_tidy_and_music_are_equivalent_to_existing_functions(tmp_path):
    from vt.director.phrases import tidy
    from vt.musicpick import pick

    executor = Executor(tmp_path)
    phrase = executor.call("text.tidy_for_screen", {
        "text": "This is a very useful idea", "max_chars": 20,
    })
    assert phrase.output["text"] == tidy("This is a very useful idea", max_chars=20)
    music = executor.call("direct.choose_music", {"mood": "story", "seed": "same"})
    assert music.output["track"] == pick("story", "same")


def test_publish_kit_uses_existing_grounded_rule_fallback(ref):
    from vt.ai.publish import rule_metadata

    expected = rule_metadata(ref)
    result = Executor(ref.dir).call("publish.kit", {"cover": False})
    assert result.ok, result.fix
    for key in ("title", "description", "hashtags", "hook"):
        assert result.output["kit"][key] == expected[key]
    assert (ref.dir / "publish.json").exists()


def test_render_export_adapter_passes_validated_options_and_tracks_exports(ref, monkeypatch):
    seen = {}

    def fake_export(project, **kwargs):
        seen.update(kwargs)
        project.exports_dir.mkdir(parents=True, exist_ok=True)
        video = project.exports_dir / "fake.mp4"
        srt = project.exports_dir / "fake.srt"
        video.write_bytes(b"video")
        srt.write_text("subtitle", encoding="utf-8")
        return {"video": str(video), "srt": str(srt), "seconds": 0.2, "duration": 17.5}

    monkeypatch.setattr("vt.pipeline.export", fake_export)
    result = Executor(ref.dir).call("render.export", {
        "aspect": "1:1", "quality": "fast", "gpu": False, "captions": False,
    })
    assert result.ok, result.fix
    assert seen["aspect"] == "1:1" and seen["quality"] == "fast"
    assert seen["gpu"] is False and seen["captions"] is False
    assert result.artifacts[0]["type"] == "render.final"
    assert not list((ref.dir / ".vt" / "history" / "render.final").glob("*"))


def test_meta_adapters_use_existing_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setattr("vt.doctor.run_checks", lambda: [{"ok": True, "detail": "ready", "fix": ""}])
    monkeypatch.setattr("vt.gpu.gpu_info", lambda: {"available": False, "backend": "cpu"})
    monkeypatch.setattr("vt.stages.asr.list_models", lambda: [{"id": "tiny", "installed": True}])
    monkeypatch.setattr("vt.llm.status", lambda: {"available": True, "model": "local"})
    monkeypatch.setattr("vt.ai.providers.provider_status", lambda: {"available": False})
    monkeypatch.setattr("vt.models.ready", lambda model_id: model_id == "kokoro")
    monkeypatch.setattr("vt.models.missing_bytes", lambda model_id: 0 if model_id == "kokoro" else 10)

    executor = Executor(tmp_path)
    health = executor.call("meta.health", {})
    hardware = executor.call("meta.hardware", {})
    models = executor.call("meta.models", {})
    assert health.ok and health.output["checks"][0]["detail"] == "ready"
    assert hardware.ok and hardware.output["hardware"]["backend"] == "cpu"
    assert models.ok and models.output["speech"][0]["id"] == "tiny"
    assert {row["id"] for row in models.output["downloadable"]} == set(__import__("vt.models", fromlist=["MODELS"]).MODELS)


def test_meta_catalog_describe_state_dry_run_and_undo(tmp_path):
    executor = Executor(tmp_path)
    catalogue = executor.call("meta.catalog", {"group": "audio", "toolbox": "autonomous"})
    assert catalogue.ok and catalogue.output["modules"]
    assert all(row["id"].startswith("audio.") for row in catalogue.output["modules"])
    described = executor.call("meta.describe", {"module_id": "audio.detect_language"})
    assert described.ok and described.output["module"]["inputs"]["properties"]["text"]

    executor.ws.put_json("direction", {"goal": "first"}, call_id="seed-1")
    executor.ws.put_json("direction", {"goal": "second"}, call_id="seed-2")
    state = executor.call("meta.state", {"artifact_type": "direction"})
    assert state.ok and state.output["value"]["goal"] == "second"
    dry = executor.call("meta.dry_run", {"calls": [
        {"module": "audio.detect_language", "inputs": {"text": "hello"}},
        {"module": "missing.module", "inputs": {}},
    ]})
    assert dry.ok and dry.output["valid"] is False and len(dry.output["calls"]) == 2
    undone = executor.call("meta.undo", {"artifact_type": "direction"})
    assert undone.ok and executor.ws.read_json("direction")["goal"] == "first"


def test_meta_wait_cancel_and_note(tmp_path, monkeypatch):
    from vt.modules.envelope import CallResult

    monkeypatch.setattr("vt.modules.tickets.wait", lambda ticket, timeout: CallResult(ok=True, status="ok", summary="done"))
    monkeypatch.setattr("vt.modules.tickets.cancel", lambda ticket: True)
    executor = Executor(tmp_path)
    waited = executor.call("meta.wait", {"ticket": "t123", "timeout": 1})
    cancelled = executor.call("meta.cancel", {"ticket": "t123"})
    noted = executor.call("meta.note", {"text": "Keep the quiet opening."})
    assert waited.ok and waited.output["result"]["status"] == "ok"
    assert cancelled.ok and cancelled.output["cancelled"] is True
    assert noted.ok and noted.summary == "Keep the quiet opening."


def test_project_media_and_sound_adapters_use_existing_importers(projects_dir, tmp_path):
    from PIL import Image

    source = tmp_path / "source.wav"
    picture = tmp_path / "owner-picture.png"
    sound = tmp_path / "owner-sound.wav"
    sf.write(str(source), np.zeros(2400, dtype=np.float32), 24000)
    sf.write(str(sound), np.zeros(4800, dtype=np.float32), 24000)
    Image.new("RGB", (80, 60), (20, 80, 140)).save(picture)
    project = Project.create("media modules", source, language="en", pid="media-modules")
    executor = Executor(project.dir)

    added = executor.call("project.add_media", {"file": str(picture), "caption": "Owner picture", "tags": ["owner"]})
    assert added.ok, added.fix
    assert added.output["item"]["kind"] == "image"
    assert (project.dir / added.output["item"]["file"]).exists()
    assert {ref["type"] for ref in added.artifacts} == {"project.meta", "media.bin"}
    assert executor.ws.stale("project.meta") is False

    audio = executor.call("project.add_sound", {"file": str(sound), "caption": "Owner sound"})
    assert audio.ok, audio.fix
    assert audio.output["item"]["kind"] == "audio"
    removed = executor.call("project.remove_media", {"media_id": added.output["item"]["id"]})
    assert removed.ok and removed.output["removed"] is True
    assert all(item.id != added.output["item"]["id"] for item in project.meta().media)


def test_theme_adapters_equal_existing_theme_functions(tmp_path):
    from vt.designer import build_theme
    from vt.project import load_theme

    executor = Executor(tmp_path)
    loaded = executor.call("project.load_theme", {"name": "paper"})
    built = executor.call("design.build_theme", {"style": "clean", "palette": "sky"})
    assert loaded.ok and loaded.output["theme"] == load_theme("paper").model_dump(mode="json")
    assert built.ok and built.output["theme"] == build_theme("clean", "sky").model_dump(mode="json")


def test_audio_edit_adapter_matches_existing_operations(ref):
    from vt import audio_edit as legacy
    from vt.schema import Cuts

    cuts = Cuts(source_duration=10, keep=[(0, 10)])
    write_json(ref.cuts_path, cuts.model_dump(mode="json"))
    result = Executor(ref.dir).call("audio.edit", {
        "operation": "gain", "start": 1.0, "end": 3.0, "db": -6.0,
    })
    expected = legacy.set_gain(legacy.EMPTY, cuts, 1.0, 3.0, -6.0)
    assert result.ok, result.fix
    assert result.output["edits"] == expected == legacy.load(ref)
    undone = Executor(ref.dir).call("audio.edit", {"operation": "undo"})
    assert undone.ok and undone.output["changed"] is True
    assert legacy.load(ref) == legacy.EMPTY


def test_subtitle_adapter_matches_existing_parser(tmp_path):
    from vt.ingest import raw_transcript_from_subs

    captions = tmp_path / "captions.vtt"
    captions.write_text("""WEBVTT

00:00:00.000 --> 00:00:04.000
one two three four five six seven eight nine ten
""", encoding="utf-8")
    expected = raw_transcript_from_subs(captions, "en", 10.0)
    result = Executor(tmp_path).call("asr.from_subtitles", {
        "file": str(captions), "language": "en", "duration": 10.0,
    })
    assert result.ok, result.fix
    assert result.output == expected
    assert Executor(tmp_path).ws.read_json("transcript.raw") == expected


def test_emphasis_adapter_matches_existing_signal_measure(ref):
    from vt.visuals.emphasis import emphasis_scores

    expected = emphasis_scores(ref.cut_audio, ref.transcript().words)
    result = Executor(ref.dir).call("audio.emphasis", {"audio": "cut"})
    assert result.ok, result.fix
    assert result.output["scores"] == expected


def test_key_terms_and_usecase_match_existing_rules(ref):
    from vt.director.plan import detect_usecase
    from vt.director.roles import analyse
    from vt.visuals.terms import norm, score, topic_counts

    tr, beats, meta = ref.transcript(), ref.beats(), ref.meta()
    topics = topic_counts(word.text for word in tr.words if not word.cut)
    expected_terms = {}
    for word in tr.words:
        value, term = score(word.text, topics), norm(word.text)
        if not word.cut and term and value >= 0.42:
            row = {"text": word.text, "word_id": word.id, "score": round(value, 6)}
            if term not in expected_terms or row["score"] > expected_terms[term]["score"]:
                expected_terms[term] = row
    terms = Executor(ref.dir).call("understand.key_terms", {})
    usecase = Executor(ref.dir).call("understand.usecase", {})
    assert terms.ok and terms.output["terms"] == sorted(expected_terms.values(), key=lambda row: (-row["score"], row["word_id"]))
    assert usecase.ok and usecase.output["usecase"] == detect_usecase(analyse(tr, beats, meta.language), bool(meta.media))


def test_publish_credits_matches_existing_collector(ref):
    from vt.director.stock import credits_text

    expected = credits_text(ref)
    result = Executor(ref.dir).call("publish.credits", {})
    assert result.ok, result.fix
    assert result.output["text"] == expected
    assert (ref.exports_dir / "credits.txt").read_text(encoding="utf-8") == expected


def test_sound_caption_adapter_matches_existing_helper(tmp_path):
    from vt.sounds import caption_words

    events = [{"label": "Baby laughing", "concept": "baby_laughter", "start": 1.0, "end": 2.5, "score": 0.9}]
    expected = caption_words(events)
    result = Executor(tmp_path).call("sound.sounds_to_pictures", {"events": events})
    assert result.ok and result.output["caption_words"] == expected


def test_taste_adapters_wrap_local_preference_store(tmp_path, monkeypatch):
    from vt import paths, taste

    monkeypatch.setattr(paths, "DATA", tmp_path / "data")
    monkeypatch.setattr(paths, "GLOBAL_GLOSSARY", tmp_path / "data" / "glossary.json")
    executor = Executor(tmp_path / "project")
    first = executor.call("direct.learn_taste", {"kind": "choice", "choice": "theme", "value": "paper"})
    second = executor.call("direct.learn_taste", {"kind": "choice", "choice": "theme", "value": "paper"})
    executor.call("direct.learn_taste", {"kind": "note", "value": "Use fewer text cards."})
    hint = executor.call("direct.taste_hint", {})
    assert first.ok and first.output["learned"] is False
    assert second.ok and second.output["preference"] == "paper"
    assert hint.ok and hint.output["hint"] == taste.director_hint()


def test_caption_and_motion_adapters_match_composer_helpers(ref):
    from copy import deepcopy
    from vt.compose.composer import build_caption_chunks, to_srt
    from vt.compose.motion import apply

    words = [word for word in ref.transcript().words if not word.cut]
    expected_chunks = build_caption_chunks(words, 5, 36, {words[0].id})
    captions = Executor(ref.dir).call("timeline.captions", {
        "words_per_line": 5, "max_chars": 36, "highlight_ids": [words[0].id],
    })
    assert captions.ok and captions.output == {"chunks": expected_chunks, "srt": to_srt(expected_chunks)}

    data = {"scenes": [{"id": "s1", "elements": [{"type": "title", "text": "Hello"}]},
                       {"id": "s2", "elements": [{"type": "keyword", "text": "World"}]}]}
    expected_motion = apply(deepcopy(data), "auto", "fixed")
    motion = Executor(ref.dir).call("timeline.motion", {"composition": data, "level": "auto", "seed": "fixed"})
    assert motion.ok and motion.output["composition"] == expected_motion


def test_contrast_adapter_matches_existing_media_decision(projects_dir, tmp_path):
    from PIL import Image
    from vt.director.contrast import decide_for_media

    source = tmp_path / "contrast-source.wav"
    picture = tmp_path / "dark.png"
    sf.write(str(source), np.zeros(2400, dtype=np.float32), 24000)
    Image.new("RGB", (120, 180), (20, 25, 30)).save(picture)
    project = Project.create("contrast", source, language="en", pid="contrast-module")
    executor = Executor(project.dir)
    media = executor.call("project.add_media", {"file": str(picture), "caption": "Dark owner photo"})
    media_id = media.output["item"]["id"]
    expected = decide_for_media(project, media_id, "9:16", "stack", 0.0, None, 0.0).model_dump(mode="json")
    result = executor.call("timeline.contrast", {"media_id": media_id, "aspect": "9:16"})
    assert result.ok, result.fix
    assert result.output["scrim"] == expected


def test_timeline_validation_and_heartbeat_wrap_existing_rules(ref):
    from copy import deepcopy
    from vt.director.heartbeat import add_heartbeats, still_scenes
    from vt.schema import validate_scenes

    scenes = ref.scenes()
    assert scenes is not None
    tr, beats, meta = ref.transcript(), ref.beats(), ref.meta()
    expected_problems = validate_scenes(scenes, tr, beats, None, {item.id for item in meta.media})
    checked = Executor(ref.dir).call("timeline.validate", {})
    assert checked.ok and checked.output == {"valid": not expected_problems, "problems": expected_problems}

    expected_scenes = deepcopy(scenes)
    expected_added = add_heartbeats(expected_scenes, tr, beats, meta.aspect)
    expected_still = still_scenes(expected_scenes, tr, beats, meta.aspect)
    changed = Executor(ref.dir).call("timeline.heartbeat", {})
    assert changed.ok, changed.fix
    assert changed.output == {"added": expected_added, "still_scenes": expected_still}
    assert ref.scenes().model_dump(exclude_none=True) == expected_scenes.model_dump(exclude_none=True)


def test_script_judge_and_critic_match_existing_scores(ref):
    from vt.script import script_from_scenes
    from vt.script.critic import review
    from vt.script.score import score

    script = script_from_scenes(ref.scenes(), language=ref.meta().language).model_dump(by_alias=True, mode="json")
    write_json(ref.dir / "video_script.json", script)
    expected_score = score(script, ref.transcript(), ref.beats())
    expected_review = review(script, ref.transcript(), ref.beats())
    executor = Executor(ref.dir)
    scored = executor.call("judge.script", {})
    critiqued = executor.call("direct.critique", {})
    assert scored.ok and scored.output["scores"] == expected_score
    assert critiqued.ok and critiqued.output["report"] == expected_review
    assert executor.ws.read_json("direct.report")["report"] == expected_review


def test_script_enrich_matches_existing_rule_enricher(ref):
    from vt.script import script_from_scenes
    from vt.script.critic import enrich

    model = script_from_scenes(ref.scenes(), language=ref.meta().language)
    expected, count = enrich(model, ref.transcript(), ref.beats())
    write_json(ref.dir / "video_script.json", model.model_dump(by_alias=True, exclude_none=True, mode="json"))
    result = Executor(ref.dir).call("direct.enrich", {})
    assert result.ok, result.fix
    assert result.output["added"] == count
    assert result.output["script"] == expected.model_dump(by_alias=True, exclude_none=True, mode="json")
    assert ref.dir.joinpath("video_script.json").exists()


def test_generation_control_adapters_wrap_comfy_clients(tmp_path, monkeypatch):
    from vt.comfy import workflows as workflow_module

    class Client:
        def __init__(self, url): self.url, self.closed, self.freed, self.cancelled = url, False, False, None
        def status(self): return {"ok": True, "url": self.url, "devices": [], "queue_running": 0, "queue_pending": 0}
        def object_info(self): return {}
        def free_memory(self): self.freed = True
        def interrupt(self, prompt_id): self.cancelled = prompt_id
        def close(self): self.closed = True

    monkeypatch.setattr("vt.comfy.ComfyClient", Client)
    monkeypatch.setattr("vt.comfy.gpu_share.release_ollama_models", lambda url: ["local-model"])
    executor = Executor(tmp_path)
    expected_workflows = [workflow.public() for workflow in workflow_module.list_workflows()]
    workflows = executor.call("gen.workflows", {})
    status = executor.call("gen.status", {"url": "http://gpu:8188"})
    freed = executor.call("gen.free_memory", {"url": "http://gpu:8188", "ollama_url": "http://gpu:11434"})
    cancelled = executor.call("gen.cancel", {"url": "http://gpu:8188", "prompt_id": "mine"})
    assert workflows.ok and workflows.output["workflows"] == expected_workflows
    assert status.ok and status.output["status"]["ok"] is True
    assert freed.ok and freed.output["ollama_models"] == ["local-model"]
    assert cancelled.ok and cancelled.output["cancelled"] is True


def test_video_generation_adapter_passes_existing_generation_contract(projects_dir, tmp_path, monkeypatch):
    from PIL import Image
    from vt.schema import MediaItem

    source = tmp_path / "gen-source.wav"
    picture = tmp_path / "first.png"
    sf.write(str(source), np.zeros(2400, dtype=np.float32), 24000)
    Image.new("RGB", (64, 96), (30, 60, 90)).save(picture)
    project = Project.create("generation", source, language="en", pid="generation-module")
    executor = Executor(project.dir)
    first = executor.call("project.add_media", {"file": str(picture), "caption": "Owner flower"}).output["item"]
    seen = {}

    class Client:
        def __init__(self, url): seen["url"] = url
        def close(self): seen["closed"] = True

    def fake_generate(project_arg, client, workflow, image, prompt, **kwargs):
        seen.update({"project": project_arg.id, "workflow": workflow, "image": image, "prompt": prompt, **kwargs})
        item = MediaItem(id="made-clip", file="media/made-clip.mp4", kind="video", role="b_roll", source="comfyui")
        (project_arg.dir / item.file).write_bytes(b"clip")
        meta = project_arg.meta(); meta.media.append(item); project_arg.save_meta(meta)
        record = {"workflow": "fake", "seed": kwargs["seed"]}
        write_json(project_arg.dir / "comfy_clips.json", {"clips": [record]})
        return item, record

    monkeypatch.setattr("vt.comfy.ComfyClient", Client)
    monkeypatch.setattr("vt.comfy.load_workflow", lambda workflow_id: {"id": workflow_id})
    monkeypatch.setattr("vt.comfy.generate_clip", fake_generate)
    result = executor.call("gen.video_from_image", {
        "media_id": first["id"], "prompt": "The supplied flower moves gently", "workflow": "fake",
        "aspect": "9:16", "seconds": 3, "seed": 12, "url": "http://gpu:8188",
    })
    assert result.ok, result.fix
    assert result.output["media"]["id"] == "made-clip" and result.output["record"]["seed"] == 12
    assert seen["project"] == project.id and seen["prompt"] == "The supplied flower moves gently" and seen["closed"] is True


def test_cutout_adapter_keeps_original_and_uses_existing_media_import(projects_dir, tmp_path, monkeypatch):
    from PIL import Image

    source = tmp_path / "cutout-source.wav"
    picture = tmp_path / "subject.png"
    sf.write(str(source), np.zeros(2400, dtype=np.float32), 24000)
    Image.new("RGB", (40, 60), (100, 120, 140)).save(picture)
    project = Project.create("cutout", source, language="en", pid="cutout-module")
    executor = Executor(project.dir)
    original = executor.call("project.add_media", {"file": str(picture), "caption": "Owner subject"}).output["item"]

    monkeypatch.setattr("vt.cutout.available", lambda: True)
    monkeypatch.setattr("vt.cutout.ensure_model", lambda progress=None: tmp_path / "model.onnx")

    def fake_cut_out(src, dst):
        Image.open(src).convert("RGBA").save(dst)
        return {"kept": 0.75}

    monkeypatch.setattr("vt.cutout.cut_out", fake_cut_out)
    result = executor.call("gen.cutout", {"media_id": original["id"]})
    assert result.ok, result.fix
    assert result.output["kept"] == 0.75 and result.output["media"]["source"] == "cutout"
    assert {item.id for item in project.meta().media} >= {original["id"], result.output["media"]["id"]}


def test_thumbnail_adapter_wraps_existing_builder(ref, monkeypatch):
    expected = {"hash": "same", "scenes": {"s1": "s1.png"}}

    def fake_thumbs(project, aspect):
        folder = project.dir / "thumbs" / "9x16"
        folder.mkdir(parents=True, exist_ok=True)
        write_json(folder / "manifest.json", expected)
        (folder / "s1.png").write_bytes(b"png")
        assert aspect == "9:16"
        return expected

    monkeypatch.setattr("vt.thumbs.make_thumbnails", fake_thumbs)
    result = Executor(ref.dir).call("timeline.thumbs", {"aspect": "9:16"})
    assert result.ok, result.fix
    assert result.output["manifest"] == expected and result.artifacts[0]["type"] == "timeline.thumbs"


def test_snapshot_and_silent_render_adapters_pass_existing_options(ref, monkeypatch):
    seen = {}

    def fake_snapshot(comp_dir, out_dir, times, gpu=True):
        seen["snapshot"] = (comp_dir, list(times), gpu)
        out_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for index, _ in enumerate(times):
            path = out_dir / f"frame-{index:04d}.png"
            path.write_bytes(b"png")
            files.append(path)
        return files

    def fake_silent(comp_dir, out, **kwargs):
        seen["silent"] = (comp_dir, kwargs)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"video")
        return out

    monkeypatch.setattr("vt.render.hyperframes.snapshot", fake_snapshot)
    monkeypatch.setattr("vt.render.hyperframes.render_silent", fake_silent)
    executor = Executor(ref.dir)
    snapshots = executor.call("render.snapshot", {"times": [0.5, 2.0], "aspect": "9:16", "gpu": False})
    silent = executor.call("render.silent", {"aspect": "9:16", "fps": 24, "quality": "fast", "gpu": False, "workers": 2})
    assert snapshots.ok and len(snapshots.output["files"]) == 2
    assert seen["snapshot"][1:] == ([0.5, 2.0], False)
    assert silent.ok and silent.output["video"].endswith("module-silent.mp4")
    assert seen["silent"][1]["fps"] == 24 and seen["silent"][1]["quality"] == "fast" and seen["silent"][1]["gpu"] is False


def test_layers_adapter_matches_existing_validation_and_history(ref):
    from vt import layers as legacy

    document = {
        "v": 1,
        "tracks": [{"id": "titles", "name": "Titles", "kind": "visual"}],
        "clips": [{"id": "hello", "track": "titles", "type": "text", "start": 0.5, "dur": 2.0,
                   "text": "Grounded title", "x": 0.5, "y": 0.3}],
    }
    duration = max(beat.end for beat in ref.beats().beats)
    expected, errors = legacy.validate(document, duration, legacy.media_kinds(ref))
    assert not errors
    executor = Executor(ref.dir)
    saved = executor.call("timeline.layers", {"operation": "set", "document": document, "duration": duration})
    assert saved.ok and saved.output["document"] == expected and saved.output["can_undo"] is True
    undone = executor.call("timeline.layers", {"operation": "undo"})
    assert undone.ok and undone.output["document"] == legacy.EMPTY and undone.output["can_redo"] is True
    redone = executor.call("timeline.layers", {"operation": "redo"})
    assert redone.ok and redone.output["document"] == expected


def test_scene_edit_adapter_matches_existing_patch(ref):
    from vt.scene_ops import patch_scene

    current = ref.scenes()
    target = current.scenes[0]
    expected = patch_scene(current, target.id, {"layout": "hero"})
    result = Executor(ref.dir).call("timeline.edit_scene", {
        "operation": "patch", "scene_id": target.id, "patch": {"layout": "hero"},
    })
    assert result.ok, result.fix
    assert result.output["scenes"] == len(expected.scenes)
    assert ref.scenes().model_dump(exclude_none=True) == expected.model_dump(exclude_none=True)


def test_voice_catalogue_and_registration_wrap_existing_store(tmp_path, monkeypatch):
    expected = [{"id": "roy", "name": "Roy", "seconds": 12.0, "created": "now", "consent": True}]
    monkeypatch.setattr("vt.voices.list_voices", lambda: expected)
    monkeypatch.setattr("vt.voices.add_voice", lambda path, name, consent: {"id": "roy", "name": name, "seconds": 12.0})
    executor = Executor(tmp_path)
    listed = executor.call("audio.voices", {})
    added = executor.call("audio.clone_voice", {"file": str(tmp_path / "voice.wav"), "name": "Roy", "consent": True})
    assert listed.ok and listed.output["voices"] == expected
    assert added.ok and added.output["voice"] == {"id": "roy", "name": "Roy", "seconds": 12.0}


def test_speaker_adapter_labels_with_existing_helper(ref, monkeypatch):
    from vt.stages.speakers import label_words

    mapping = {beat.id: ("Speaker 1" if index % 2 == 0 else "Speaker 2") for index, beat in enumerate(ref.beats().beats)}
    expected = label_words(ref.transcript(), ref.beats(), mapping)
    monkeypatch.setattr("vt.stages.speakers.assign", lambda audio, transcript, beats: mapping)
    monkeypatch.setattr("vt.visuals.emphasis.load_mono16k", lambda path: np.zeros(16000, dtype=np.float32))
    result = Executor(ref.dir).call("audio.speakers", {})
    assert result.ok, result.fix
    assert result.output["speakers"] == mapping
    assert ref.transcript().model_dump() == expected.model_dump()


def test_retention_scorecard_adapter_passes_existing_inputs(tmp_path, monkeypatch):
    seen = {}
    expected = {"score": 82, "worst": [{"time": 3.2}]}

    def fake_scorecard(video, aspect, composition=None, voice=None):
        seen.update(video=video, aspect=aspect, composition=composition, voice=voice)
        return expected

    monkeypatch.setattr("vt.retention.scorecard", fake_scorecard)
    result = Executor(tmp_path).call("judge.scorecard", {
        "video": str(tmp_path / "draft.mp4"), "aspect": "16:9",
        "composition": {"scenes": []}, "voice": str(tmp_path / "voice.wav"),
    })
    assert result.ok and result.output["card"] == expected
    assert seen["aspect"] == "16:9" and seen["composition"] == {"scenes": []}
    assert Executor(tmp_path).ws.read_json("judge.scorecard")["card"] == expected


def test_shorts_detection_and_slice_adapters_wrap_existing_flows(ref, monkeypatch):
    expected = {"highlights": [{"start_time": 1.0, "end_time": 20.0, "title": "Moment"}],
                "content_info": {"content_type": "story"}, "total_duration": 30.0}
    seen = {}

    def fake_detect(transcript, count, progress_cb=None, audio_path=None, sound_events=None):
        seen.update(count=count, audio=audio_path, sounds=sound_events)
        return expected

    class Child:
        id = "child-short"
        dir = ref.dir.parent / id

    def fake_slice(parent_pid, highlight, index, run_pipeline, aroll, caption_style):
        seen.update(parent=parent_pid, highlight=highlight, index=index, pipeline=run_pipeline,
                    aroll=aroll, caption_style=caption_style)
        return Child()

    monkeypatch.setattr("vt.shorts.detector.detect_highlights", fake_detect)
    monkeypatch.setattr("vt.shorts.splitter.slice_short_project", fake_slice)
    executor = Executor(ref.dir)
    detected = executor.call("understand.highlights", {"count": 3, "use_audio_signals": False})
    sliced = executor.call("publish.shorts_slice", {"highlight": expected["highlights"][0], "run_pipeline": False})
    assert detected.ok and detected.output == expected and executor.ws.read_json("shorts.candidates") == expected
    assert sliced.ok and sliced.output["project_id"] == "child-short"
    assert seen["parent"] == ref.id and seen["pipeline"] is False


def test_slot_fragment_placeholder_and_grounded_text_contract(tmp_path):
    slot = {"id": "sl1", "start": 0.0, "end": 2.0,
            "words": [{"id": "w1", "text": "Gravity", "start": 0.2, "end": 0.8}],
            "sentence_id": "b1", "impact": {"word_id": "w1", "time": 0.2, "kind": "stress", "strength": 0.8, "why": "stressed"}}
    executor = Executor(tmp_path)
    placeholder = executor.call("fill.placeholder", {"slot": slot})
    card = executor.call("fill.text_card", {"slot": slot, "text": "Gravity"})
    invented = executor.call("fill.text_card", {"slot": slot, "text": "Invented claim"})
    assert placeholder.ok and placeholder.output["slot_id"] == "sl1" and placeholder.output["items"][0]["type"] == "placeholder"
    assert card.ok and card.output["items"][0]["text"] == "Gravity"
    assert not invented.ok and "spoken words" in invented.fix


def test_media_fill_fragments_are_editable_and_use_project_media(projects_dir, tmp_path):
    from PIL import Image

    source = tmp_path / "fill-source.wav"
    picture = tmp_path / "fill.png"
    sf.write(str(source), np.zeros(2400, dtype=np.float32), 24000)
    Image.new("RGB", (60, 90), (80, 100, 120)).save(picture)
    project = Project.create("fill", source, language="en", pid="fill-module")
    executor = Executor(project.dir)
    item = executor.call("project.add_media", {"file": str(picture), "caption": "Owner image"}).output["item"]
    slot = {"id": "sl1", "start": 0.0, "end": 3.0, "impact": {"time": 1.0}}
    media = executor.call("fill.user_media", {"slot": slot, "media_id": item["id"]})
    zoom = executor.call("fill.still_zoom", {"slot": slot, "media_id": item["id"], "motion": "pan_left"})
    assert media.ok and media.output["items"][0]["media"] == item["id"]
    assert zoom.ok and zoom.output["items"][0]["anim"] == "pan_left"
    meta = project.meta(); meta.media[0].role = "a_roll"; project.save_meta(meta)
    speaker = executor.call("fill.speaker", {"slot": slot})
    assert speaker.ok and speaker.output["items"][0]["type"] == "speaker"


def test_sound_cues_and_beat_snap_match_existing_helpers(tmp_path):
    import numpy as np
    from vt.beatsync import snap
    from vt.cues import build_cues

    scenes = [{"start": 0.0, "transition_in": "cut", "elements": [], "sfx": []},
              {"start": 1.0, "transition_in": "slide_up", "elements": [], "sfx": []}]
    executor = Executor(tmp_path)
    cues = executor.call("sound.sfx_place", {"scenes": scenes})
    assert cues.output["cues"] == build_cues(scenes)
    values = {"time": 1.12, "beats": [1.0, 1.5], "earliest": 0.8, "latest": 1.3}
    snapped = executor.call("cut.snap_beat", values)
    assert snapped.output["time"] == snap(1.12, np.asarray([1.0, 1.5]), 0.8, 1.3)


def test_music_and_theme_adapters_match_existing_helpers(ref):
    from vt.musicpick import pick
    from vt.project import load_theme

    executor = Executor(ref.dir)
    music = executor.call("sound.music_pick", {"mood": "story", "seed": "stable"})
    theme = executor.call("timeline.theme", {"name": ref.meta().theme})
    assert music.ok and music.output["track"] == pick("story", "stable")
    assert theme.ok and theme.output["theme"] == load_theme(ref.meta().theme).model_dump(mode="json")


def test_polish_media_and_copy_adapters_pass_through_existing_services(ref, monkeypatch):
    suggestions = [{"word_id": "w1", "from": "Codax", "to": "Codex"}]
    described = {"described": ["m1"], "skipped": 0, "error": None}
    kit = {"title": "Title", "description": "Description", "hashtags": ["video"],
           "hook": "Watch this", "source": "rules"}

    def fake_suggest(project):
        assert project.id == ref.id
        write_json(project.dir / "polish.json", suggestions)
        return suggestions

    monkeypatch.setattr("vt.ai.polish.suggest", fake_suggest)
    monkeypatch.setattr("vt.ai.media_tags.describe_project",
                        lambda project, only_missing=True: described)
    monkeypatch.setattr("vt.ai.publish.metadata", lambda project: kit)
    (ref.dir / "media").mkdir(exist_ok=True)
    executor = Executor(ref.dir)
    polished = executor.call("text.polish", {})
    media = executor.call("understand.media", {"only_missing": True})
    copy = executor.call("direct.write_copy", {})
    assert polished.ok and polished.output["suggestions"] == suggestions
    assert executor.ws.read_json("text.polish") == suggestions
    assert media.ok and media.output["result"] == described
    assert copy.ok and copy.output["kit"] == kit


def test_timeline_compile_is_identical_to_existing_compiler(ref):
    from vt.script import compile_script, script_from_scenes

    script = script_from_scenes(ref.scenes(), language=ref.meta().language,
                                aspect=ref.meta().aspect, title=ref.meta().title)
    write_json(ref.dir / "video_script.json", script.model_dump(by_alias=True, mode="json"))
    expected = compile_script(script, ref.transcript(), ref.beats(), ref.meta().theme)
    result = Executor(ref.dir).call("timeline.compile", {})
    assert result.ok, result.fix
    assert result.output["scenes"] == len(expected.scenes)
    assert ref.scenes().model_dump(exclude_none=True) == expected.model_dump(exclude_none=True)


def test_speak_sentence_wraps_synthesis_and_measures_written_audio(tmp_path, monkeypatch):
    def fake_synth(engine, voice, text, rate, out):
        assert (engine, voice, text, rate) == ("edge", "voice", "Hello world", 1.0)
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out), np.ones(12000, dtype=np.float32) * 0.1, 24000)

    monkeypatch.setattr("vt.tts.synth_sentence", fake_synth)
    result = Executor(tmp_path).call("audio.speak_sentence", {
        "text": "Hello world", "engine": "edge", "voice": "voice", "rate": 1.0,
    })
    assert result.ok, result.fix
    assert result.output["wav"] == "speech/sentence.wav"
    assert result.output["seconds"] == 0.5 and len(result.output["words"]) == 2


def test_plan_script_adapter_writes_exact_existing_planner_result(ref, monkeypatch):
    from vt.script import script_from_scenes

    expected = script_from_scenes(ref.scenes(), language=ref.meta().language)
    seen = {}

    def fake_plan(transcript, beats, **kwargs):
        seen.update(kwargs)
        return expected, "rules (test)"

    monkeypatch.setattr("vt.script.planner.plan_script", fake_plan)
    result = Executor(ref.dir).call("direct.plan_script", {"kind": "stick", "use_ai": False})
    assert result.ok, result.fix
    assert result.output == {"how": "rules (test)", "scenes": len(expected.scenes)}
    assert seen["draft"].model_dump() == ref.scenes().model_dump()
    assert Executor(ref.dir).ws.read_json("script.video") == expected.model_dump(by_alias=True, exclude_none=True, mode="json")


def test_talk_and_vision_judges_delegate_to_existing_functions(ref, monkeypatch):
    seen = {}

    def fake_talk(project, message):
        seen["talk"] = (project.id, message)
        return {"ok": True, "reply": "Changed one scene."}

    report = {"bad": [], "scenes": [], "at": "now", "model": "pixels"}

    def fake_qa(project, video=None, max_scenes=0):
        seen["qa"] = (project.id, video, max_scenes)
        write_json(project.dir / "qa.json", report)
        return report

    def fake_picture(word, sentence, candidates, workdir):
        seen["picture"] = (word, sentence, candidates, workdir)
        return 1

    monkeypatch.setattr("vt.script.chat.talk", fake_talk)
    monkeypatch.setattr("vt.ai.vision.qa_project", fake_qa)
    monkeypatch.setattr("vt.ai.vision.judge_picture", fake_picture)
    executor = Executor(ref.dir)
    talked = executor.call("direct.talk", {"message": "More action"})
    qa = executor.call("judge.vision_qa", {"max_scenes": 2})
    picture = executor.call("judge.picture", {
        "word": "apple", "sentence": "Eat an apple.",
        "candidates": [{"kind": "icon", "id": "fruit"}, {"kind": "icon", "id": "apple"}],
    })
    assert talked.ok and talked.output == {"ok": True, "reply": "Changed one scene."}
    assert qa.ok and qa.output["report"] == report and seen["qa"][2] == 2
    assert picture.ok and picture.output["choice"] == 1


def test_face_people_and_shot_adapters_wrap_existing_analysis(tmp_path, monkeypatch):
    from PIL import Image

    frame = tmp_path / "frame.png"
    Image.new("RGB", (20, 30), "white").save(frame)
    monkeypatch.setattr("vt.director.media.detect_faces", lambda rgb: [[0.1, 0.2, 0.3, 0.4]])
    monkeypatch.setattr("vt.people.person_mask", lambda rgb, face, use_model: np.ones((30, 20), dtype=bool))
    faces = Executor(tmp_path).call("understand.faces", {"frame": str(frame)})
    people = Executor(tmp_path).call("understand.people", {"frame": str(frame), "use_model": False})
    assert faces.ok and faces.output["faces"] == [[0.1, 0.2, 0.3, 0.4]]
    assert people.ok and people.output["occupied"]

    video = tmp_path / "input.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr("vt.aroll.shot_track", lambda path, duration: [[0.0, duration, 0.5, 0.4, 0.6]])
    shots = Executor(tmp_path).call("understand.video_shots", {"duration": 4.0})
    assert shots.ok and shots.output["shots"] == [[0.0, 4.0, 0.5, 0.4, 0.6]]


def test_visual_word_and_text_fix_adapters_delegate(ref, monkeypatch):
    from vt.visuals.picker import Pick

    pick = Pick(beat="b1", word_id="w1", text="apple", kind="icon", line="apple", score=0.8)
    monkeypatch.setattr("vt.visuals.picker.pick_visuals", lambda tr, beats, use_embedder=True: {"w1": pick})
    visual = Executor(ref.dir).call("understand.visual_for_word", {"use_embedder": False})
    assert visual.ok and visual.output["picks"]["w1"]["line"] == "apple"

    before = ref.transcript().model_dump()
    monkeypatch.setattr("vt.pipeline.Pipeline.stage_words", lambda self: None)
    fixed = Executor(ref.dir).call("text.fix", {"operation": "word", "word_id": "w1", "text": "Codex"})
    assert fixed.ok and fixed.output["edit"] == {"text": "Codex"}
    assert ref.transcript().model_dump() == before


def test_sound_mix_adapter_passes_existing_mux_options(tmp_path, monkeypatch):
    seen = {}
    video, voice = tmp_path / "silent.mp4", tmp_path / "voice.wav"
    video.write_bytes(b"video"); voice.write_bytes(b"voice")

    def fake_mix(v, a, out, **kwargs):
        seen.update(video=v, voice=a, **kwargs)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mixed")
        return out

    monkeypatch.setattr("vt.render.mux.mix_and_mux", fake_mix)
    result = Executor(tmp_path).call("sound.mix", {"video": str(video), "voice": str(voice),
                                                   "duration": 2.5, "gpu": False, "clean_voice": True})
    assert result.ok, result.fix
    assert result.output["video"] == "exports/module-mix.mp4"
    assert seen["duration"] == 2.5 and seen["gpu"] is False and seen["clean_voice"] is True


def test_project_creation_and_link_adapters_wrap_existing_entrypoints(tmp_path, monkeypatch):
    class Made:
        id = "made-project"
        dir = tmp_path / id

    seen = {}

    def fake_create(title, source, **kwargs):
        seen["create"] = (title, source, kwargs)
        return Made()

    def fake_link(url, **kwargs):
        seen["link"] = (url, kwargs)
        return Made()

    monkeypatch.setattr("vt.project.Project.create", fake_create)
    monkeypatch.setattr("vt.ingest.create_project", fake_link)
    source = tmp_path / "voice.wav"; source.write_bytes(b"voice")
    executor = Executor(tmp_path)
    created = executor.call("project.create", {"source": str(source), "title": "Demo"})
    linked = executor.call("project.fetch_link", {"url": "https://www.youtube.com/watch?v=example"})
    assert created.ok and created.output["project_id"] == "made-project"
    assert seen["create"][1] == source
    assert linked.ok and linked.output["project_id"] == "made-project" and seen["link"][1]["want_video"] is True


def test_revise_script_adapter_keeps_exact_existing_revision(ref, monkeypatch):
    from vt.script import script_from_scenes

    original = script_from_scenes(ref.scenes(), language=ref.meta().language)
    write_json(ref.dir / "video_script.json", original.model_dump(by_alias=True, exclude_none=True, mode="json"))
    monkeypatch.setattr("vt.script.planner.revise", lambda script, *args: script)
    result = Executor(ref.dir).call("direct.revise_script", {"notes": "Keep the opening active."})
    assert result.ok, result.fix
    assert result.output == {"changed": False, "scenes": len(original.scenes)}
