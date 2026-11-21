"""Short-lived credentials for a director's one-project MCP session."""
from __future__ import annotations

import re
import secrets
import threading
import time
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from mcp.shared.exceptions import MCPError

HEADER = "x-vt-director-token"
_lock = threading.RLock()
_tokens: dict[str, tuple[str, float]] = {}
_current: ContextVar[tuple[str, str] | None] = ContextVar("vt_mcp_project", default=None)
_READ_SHARED = {"module_catalog", "module_describe", "house_rules", "search_icons", "list_components",
                "list_themes", "get_theme", "list_projects", "list_pending_requests", "job_status"}
_PROJECT_TOOLS = set("""
module_call get_planning_task submit_scenes get_reel_plan check_reel_plan run_pipeline project_status get_transcript
fix_word add_glossary_term get_scenes update_scene list_media list_scene_types show_scene_as request_regenerate
get_preview_frame render get_script_task submit_script get_story_task submit_story get_current_script
get_director_notes frame_facts preview_frames
list_shots get_shot write_shot set_scene_shot set_shot_edits get_shot_frame make_picture speak
""".split())
# Exact ids are deliberate. A new module must be reviewed before a task token
# may call it; a project_id argument alone does not make a capability scoped.
_PROJECT_MODULES = set("""
asr.from_subtitles asr.transcribe
audio.align_words audio.beats audio.clean audio.cut audio.detect_language audio.edit audio.emphasis audio.events
audio.find_retakes audio.find_silences audio.pause_sentences audio.prosody audio.saliency audio.speak_script
audio.speak_sentence audio.speakers audio.tighten audio.voices
craft.check craft.rules cut.apply cut.propose cut.reel_slots cut.snap_beat cut.snap_quiet cut.validate design.build_theme
direct.choose_music direct.critique direct.enrich direct.improve_hook direct.plan_scenes direct.plan_script
direct.revise_script direct.scene_settings direct.set_direction direct.set_style direct.talk direct.write_copy direct.write_prompt
fill.character_scene fill.generated_clip fill.generated_still fill.graphic fill.illustration fill.placeholder
fill.speaker fill.sticker_icon fill.still_zoom fill.stock fill.text_card fill.user_media
gen.cutout gen.fit_clip gen.status gen.video_from_image gen.vision_check gen.workflows
judge.facts judge.impact_alignment judge.picture judge.scorecard judge.script judge.video judge.vision_qa judge.watch_and_revise
meta.ask_human meta.budget meta.catalog meta.describe meta.dry_run meta.finish meta.hardware meta.health meta.models
meta.note meta.redo meta.state meta.undo
pipeline.aroll pipeline.asr pipeline.compose pipeline.context pipeline.cuts pipeline.plan pipeline.preprocess
pipeline.silence pipeline.sounds pipeline.tighten pipeline.voice pipeline.words
plan.approve plan.decline plan.edit plan.estimate plan.make plan.preview_moment plan.start plan.status plan.wait
project.add_sound project.inspect_source project.load_theme project.options project.remove_media
publish.credits publish.kit publish.shorts_slice
render.export render.preview render.silent render.snapshot
sound.mix sound.music_pick sound.sfx_place sound.sounds_to_pictures
style.get style.list style.motion_kit style.story_kit
text.build_transcript text.fix text.polish text.rank_sentences text.tidy_for_screen
timeline.captions timeline.compile timeline.compose timeline.contrast timeline.edit_scene timeline.heartbeat
timeline.layers timeline.motion timeline.place timeline.theme timeline.thumbs timeline.validate
understand.context understand.faces understand.highlights understand.impact_map understand.key_terms understand.media
understand.people understand.read_script understand.roles understand.usecase understand.video_shots understand.visual_for_word
voice.describe voice.design voice.list voice.speak voice.speak_script
""".split())
_MODULE_FILES = {
    "asr.from_subtitles": {"file"},
    "project.add_sound": {"file"},
    "understand.faces": {"frame"}, "understand.people": {"frame"},
    "gen.fit_clip": {"video"}, "gen.vision_check": {"frame"},
    "judge.scorecard": {"video", "voice"}, "judge.video": {"video"},
    "judge.vision_qa": {"video"}, "judge.watch_and_revise": {"video"},
    "sound.mix": {"video", "voice", "music", "sfx"},
}


def issue(project: str, *, ttl: float = 86400) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", project) or project in (".", ".."):
        raise ValueError("invalid project id")
    token = "vtd_" + secrets.token_urlsafe(32)
    with _lock:
        now = time.monotonic()
        for old, (_, expires) in list(_tokens.items()):
            if expires <= now:
                _tokens.pop(old, None)
        _tokens[token] = (project, now + max(0, ttl))
    return token


def revoke(token: str) -> None:
    with _lock:
        _tokens.pop(token, None)


def project_for(token: str) -> str | None:
    with _lock:
        lease = _tokens.get(token)
        if lease is not None and lease[1] > time.monotonic():
            return lease[0]
        _tokens.pop(token, None)
    return None


def current_project() -> str | None:
    current = _current.get()
    if current is None:
        return None
    token, project = current
    if project_for(token) != project:
        raise MCPError(-32001, "This director's project credential has expired. Start the task again.")
    return project


async def middleware(ctx, call_next):
    """The SDK carries the actual HTTP request on each message, including resumed sessions."""
    request = getattr(ctx, "request", None)
    token = (request.headers.get(HEADER, "") if request is not None else "")
    project = project_for(token) if token else None
    if token and project is None:
        raise MCPError(-32001, "This director's project credential has expired. Start the task again.")
    if project is not None and getattr(request, "scope", None) is not None and request.scope.get("vt_scoped") is not True:       # only the server's own door (server/serve.py Guard) says a director's request was checked
        raise MCPError(-32001, "This director's project could not be confirmed by the server. Start the task again.")
    marker = _current.set((token, project) if project is not None else None)
    try:
        return await call_next(ctx)
    finally:
        _current.reset(marker)


def check_tool(name: str, arguments: dict[str, Any]) -> None:
    """Fail closed for global writes and future tools without an explicit project."""
    project = current_project()
    if project is None:
        return
    name = name.removesuffix("_tool")
    targets = [arguments[key] for key in ("project", "project_id") if key in arguments]
    if targets:
        if any(target != project for target in targets):
            raise MCPError(-32001, "This director may use only its own project's tools.")
        if name == "run_pipeline":
            raise MCPError(-32001, "This video's pipeline is already waiting for your direction. Submit the script, story or reel plan, then finish your task.")
        if name == "add_media":
            raise MCPError(-32001, "Adding server files requires the person's project media controls.")
        if name not in _PROJECT_TOOLS:
            raise MCPError(-32001, "This tool has not been approved for a director's project session.")
        _check_file_inputs(arguments, project)
        if name == "module_call":
            module = str(arguments.get("module_id", ""))
            if module not in _PROJECT_MODULES:
                raise MCPError(-32001, "This module has not been approved for a director's project session.")
            inputs = arguments.get("inputs") or {}
            _check_file_inputs(inputs, project, _MODULE_FILES.get(module, set()))
            if module in ("meta.state", "meta.undo", "meta.redo") and inputs.get("artifact_type"):
                from ..modules.workspace import KNOWN_ARTIFACTS

                if inputs["artifact_type"] not in KNOWN_ARTIFACTS:
                    raise MCPError(-32001, "Choose a known artifact inside the director's project.")
            if module in ("project.load_theme", "timeline.theme"):
                _check_theme(inputs.get("name", ""))
        return
    if name not in _READ_SHARED:
        raise MCPError(-32001, "This tool changes data outside the director's project.")
    if name == "get_theme":
        _check_theme(arguments.get("name", ""))


def _check_theme(name: str) -> None:
    from .. import paths

    if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in (".", ".."):
        raise MCPError(-32001, "Choose a registered theme for this project.")
    if not (paths.THEMES / name / "theme.json").resolve().is_relative_to(paths.THEMES.resolve()):
        raise MCPError(-32001, "Choose a registered theme for this project.")


def _check_file_inputs(value: Any, project: str, file_fields: set[str] | None = None) -> None:
    from .. import paths

    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and (key.endswith("_path") or key in ("path", "file", "folder", "directory", "dest", "destination", "output")
                                          or key in (file_fields or set())) and item:
                file = Path(item)
                if not file.is_absolute() or not file.resolve().is_relative_to((paths.PROJECTS / project).resolve()):
                    raise MCPError(-32001, "Use an absolute file path inside this director's own project.")
            _check_file_inputs(item, project)
    elif isinstance(value, list):
        for item in value:
            _check_file_inputs(item, project)
