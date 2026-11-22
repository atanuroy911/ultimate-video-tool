"""MCP server: lets Codex, Claude and other assistants plan, edit and render videos. Register with:

    claude mcp add video-tool -- <path-to-.venv>/Scripts/python.exe -m vt.mcp.server

The Studio queues requests; the connected assistant fetches a task (get_planning_task) and returns scenes (submit_scenes).
Never print to stdout here: stdout carries the MCP protocol.
"""
from __future__ import annotations

import functools
import inspect
import os
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Optional

from mcp.server.mcpserver import Image, MCPServer

from .. import paths, planning, scene_ops
from ..compose import FORMATS, scene_timing
from ..pipeline import Pipeline, compose_all, export
from ..planner.catalogue import catalogue_summary
from ..project import Project, list_themes, load_theme
from ..schema import ScenesFile, Theme, validate_scenes
from ..util import now_iso, read_json, write_json
from . import scope as project_scope

server = MCPServer(
    "video-tool",
    middleware=[project_scope.middleware],
    instructions=(
        "Tools for a local voice-to-video app. Typical flow: list_pending_requests -> get_planning_task -> submit_scenes "
        "(fix any returned errors and resubmit). You can also create_project from an audio file, run the pipeline, "
        "fix transcript words, edit scenes, change themes, preview a frame and render. Word ids look like 'w17'; "
        "scene ids like 's3'; beat ids like 'b5'."
    ),
)

_BG: dict[str, dict] = {}  # background jobs started from here: id -> status

# These modules do the directing work themselves and may ask the active helper
# to answer. During its own task the helper must submit the work directly.
_DIRECTOR_TASK_GUIDANCE = {
    "direct.plan_script": "Read get_script_task and write the script yourself, then call submit_script.",
    "direct.plan_scenes": "Read get_script_task and submit_script, or update_scene for a specific scene.",
    "direct.revise_script": "Use the measured findings to revise your script or update the affected scenes directly.",
    "direct.talk": "Apply the direction yourself with update_scene or submit_script.",
    "pipeline.context": "Read the project's timed transcript and work from that source.",
    "pipeline.plan": "Submit the plan yourself using the project's script, story or reel tools.",
    "plan.make": "Read get_reel_plan and apply plan.edit operations, then call plan.approve.",
    "plan.start": "Approve the finished reel plan. The server makes the video after you finish.",
    "judge.picture": "Choose an existing visual yourself using the spoken words and the library choices.",
    "judge.vision_qa": "Use preview_frames and frame_facts to inspect the cut yourself.",
    "judge.watch_and_revise": "Inspect the cut once with preview_frames and frame_facts, then apply one revision.",
    "gen.vision_check": "Inspect the supplied visual yourself in the project's preview.",
}


# Claude Code saves a tool result above about 50,000 characters to a file and tells the model to read it. A planning session has no file tools, so the model
# never saw the task (the script task is about 49,000 characters before the transcript words: found 2026-11-20). A tool may ask for more, up to 500,000.
RESULT_SIZE = {"anthropic/maxResultSizeChars": 500000}


def tool(fn):
    """Register a tool and record a heartbeat for the assistant using it."""

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        arguments = dict(inspect.signature(fn).bind(*a, **kw).arguments)
        project_scope.check_tool(fn.__name__, arguments)
        try:
            client = os.environ.get("VT_MCP_CLIENT", "assistant").strip().lower() or "assistant"
            seen = {"at": now_iso(), "tool": fn.__name__, "client": client}
            write_json(paths.mcp_seen_path(), seen)
            clients_path = paths.PROJECTS / ".mcp_clients.json"
            clients = read_json(clients_path, {}) or {}
            clients[client] = seen
            write_json(clients_path, clients)
        except Exception:
            pass
        project = arguments.get("project") or arguments.get("project_id")
        if not project:
            return fn(*a, **kw)
        from ..ai import talk

        from .. import directors

        who = directors.broker.who_directing(str(project)) or os.environ.get("VT_MCP_CLIENT", "assistant").strip().lower() or "assistant"     # the director running this session, by the name its other conversations carry
        # Validate before even logging a failed call: an invalid id must not
        # create ai_talk.jsonl in an existing directory outside the project store.
        folder, began = _proj(str(project)).dir, time.time()
        asked = {"tool": fn.__name__.removesuffix("_tool"), "arguments": arguments}
        try:
            out = fn(*a, **kw)
        except Exception as e:
            talk.record(who, "", kind="tool", prompt=asked, seconds=time.time() - began, error=f"{type(e).__name__}: {e}", folder=folder)
            raise
        talk.record(who, "", kind="tool", prompt=asked, answer=out, seconds=time.time() - began, folder=folder)
        return out

    server.tool(name=fn.__name__.removesuffix("_tool"), meta=RESULT_SIZE)(wrapper)
    return wrapper


def _proj(pid: str) -> Project:
    scoped = project_scope.current_project()
    if scoped is not None and pid != scoped:
        from mcp.shared.exceptions import MCPError

        raise MCPError(-32001, "This director may use only its own project's tools.")
    p = Project(pid)
    if Path(pid).name != pid or "\\" in pid or ":" in pid or not p.dir.resolve().is_relative_to(paths.PROJECTS.resolve()):          # one folder name: no slash of either kind, no drive
        raise ValueError("invalid project id")
    if not p.exists():
        raise ValueError(f"project '{pid}' not found. Use list_projects.")
    return p


@tool
def module_catalog_tool() -> list[dict]:
    """List callable director modules with one-line descriptions and expected cost."""
    from ..modules.defs import load
    from ..modules.registry import list_modules

    load()
    scoped = project_scope.current_project() is not None
    rows = []
    for spec in list_modules():
        row = {"id": spec.id, "summary": spec.summary, "cost": spec.cost.kind}
        if scoped and spec.id in _DIRECTOR_TASK_GUIDANCE:
            row["during_director_task"] = _DIRECTOR_TASK_GUIDANCE[spec.id]
        rows.append(row)
    return rows


@tool
def module_describe_tool(module_id: str) -> dict:
    """Get the input schema, examples and prerequisites for one director module."""
    from ..modules.defs import load
    from ..modules.registry import get_module

    load()
    try:
        spec = get_module(module_id)
    except KeyError:
        return {"error": f"unknown module: {module_id}"}
    details = {"id": spec.id, "summary": spec.summary, "when_to_use": spec.when_to_use,
            "when_not_to_use": spec.when_not_to_use, "inputs": spec.inputs.model_json_schema(),
            "outputs": spec.outputs.model_json_schema(), "requires": spec.requires,
            "produces": spec.produces, "examples": [example.__dict__ for example in spec.examples]}
    if project_scope.current_project() is not None and spec.id in _DIRECTOR_TASK_GUIDANCE:
        details["during_director_task"] = _DIRECTOR_TASK_GUIDANCE[spec.id]
    return details


@tool
def module_call_tool(project_id: str, module_id: str, inputs: dict | None = None,
                     why: str = "", force: bool = False) -> dict:
    """Call a director module on a project, with validated inputs and a recorded reason."""
    from ..modules.envelope import CallResult
    from ..modules.executor import Executor

    project = _proj(project_id)
    guidance = _DIRECTOR_TASK_GUIDANCE.get(module_id)
    if guidance and project_scope.current_project() is not None:
        return CallResult(ok=False, status="refused", summary="This module delegates work from your current directing task.",
                          fix=guidance).model_dump(mode="json")
    try:
        return Executor(project.dir).call(module_id, inputs or {},
                                          caller=os.environ.get("VT_MCP_CLIENT", "assistant"),
                                          why=why, force=force).model_dump(mode="json")
    except KeyError:
        return {"ok": False, "status": "failed", "fix": f"unknown module: {module_id}"}


def _bg(kind: str, pid: str, fn) -> str:
    jid = uuid.uuid4().hex[:8]
    st = {"id": jid, "kind": kind, "project": pid, "status": "running", "stage": "", "progress": 0.0, "message": "", "result": None, "error": None}
    _BG[jid] = st

    def progress(stage, frac, msg=""):
        st.update(stage=stage, progress=round(float(frac), 3), message=str(msg)[:120])

    def work():
        try:
            st["result"] = fn(progress)
            st["status"] = "done"
        except Exception as e:  # noqa: BLE001
            st["status"], st["error"] = "error", f"{e}\n{traceback.format_exc(limit=2)}"

    threading.Thread(target=work, daemon=True).start()
    return jid


# ------------------------------------------------------------------ planning (the main job)
@tool
def list_pending_requests() -> list[dict]:
    """Planning requests waiting for an assistant, across all projects."""
    scoped = project_scope.current_project()
    if scoped is None:
        return planning.pending()
    project = _proj(scoped)
    return [{"project": project.id, "title": project.meta().title, **request.model_dump()}
            for request in project.requests() if request.status == "queued"]


@tool
def get_planning_task(project: str, request_id: str) -> dict:
    """Everything needed to plan: rules, timed beats with word ids, the component catalogue, and the current draft. Read `instructions` first."""
    return planning.planning_task(_proj(project), request_id)


@tool
def submit_scenes(project: str, request_id: str, scenes: list[dict[str, Any]]) -> dict:
    """Submit the plan (a list of scene objects) for a request. Returns {ok, errors}; if errors, fix them and call again.
    For a 'scene' request submit one scene object (or several as alternatives) for that scene."""
    return planning.submit(_proj(project), request_id, scenes)


def _reel_plan_payload(project: Project) -> dict:
    """The complete, inexpensive reel plan plus checks a remote director can act on."""
    from ..direction import plan_doc as PD

    plan = PD.load(project.dir)
    if plan is None:
        raise ValueError("no reel plan yet; run the pipeline through the plan stage first")
    shots = PD.picture_shots(project, plan)
    issues = PD.open_picture_issues(project, plan)
    return {"project": project.id, "plan": plan.model_dump(mode="json"), "shots": shots,
            "checks": {"ok": not issues, "issues": issues, "plan_notes": PD.checks(plan)}}


@tool
def get_reel_plan(project: str) -> dict:
    """Read the complete reel plan: script moments, cast, places, full picture prompts, estimate and current checks. Makes nothing."""
    return _reel_plan_payload(_proj(project))


@tool
def check_reel_plan(project: str) -> dict:
    """Recheck a reel plan after edits. It only reports: nothing is changed in the plan. Fix every picture.place and picture.drawable issue before approving it
    (approving with one still open is your choice, and it is written down as such)."""
    return _reel_plan_payload(_proj(project))["checks"]


# ------------------------------------------------------------------ projects
@tool
def list_projects() -> list[dict]:
    """All projects with status, duration and scene count."""
    out = []
    scoped = project_scope.current_project()
    for p in ([_proj(scoped)] if scoped is not None else Project.list_all()):
        m = p.meta()
        sf = p.scenes()
        cuts = p.cuts()
        out.append({"id": m.id, "title": m.title, "status": m.status, "aspect": m.aspect, "theme": m.theme,
                    "scenes": len(sf.scenes) if sf else 0, "planner": sf.planner if sf else None,
                    "seconds": round(cuts.output_duration, 1) if cuts else None,
                    "pending_requests": len([r for r in p.requests() if r.status == "queued"])})
    return out


@tool
def create_project(audio_path: str, title: str, language: str = "bn", aspect: str = "9:16", theme: str = "paper",
                   pace: str = "normal", music: Optional[str] = None, remove_fillers: bool = True, srt_path: str = "") -> dict:
    """Create a project from an audio or video file. audio_path is a path on the server computer, or 'upload:<id>' for a file sent with
    prepare_upload (when you run on another computer than the server). srt_path (same rules) is the recording's own .srt: its words and timing
    are used and speech recognition is skipped. Then call run_pipeline."""
    from ..server.uploads import resolve

    f = resolve(audio_path).expanduser()
    if not f.is_file():
        raise ValueError(f"file not found: {audio_path}. On another computer than the server, send it first: prepare_upload.")
    p = Project.create(title, f, language=language, aspect=aspect, theme=theme, pace=pace,
                       options={"music": music, "remove_fillers": remove_fillers})
    if srt_path:
        from ..ingest import attach_subtitles

        sub = resolve(srt_path).expanduser()
        if not sub.is_file():
            raise ValueError(f"file not found: {srt_path}")
        return {"project": p.id, "subtitles": attach_subtitles(p, sub, language), "next": "run_pipeline"}
    return {"project": p.id, "next": "run_pipeline"}


@tool
def import_link(url: str, language: str = "en", title: str = "", aspect: str = "9:16", use_subtitles: str = "auto", run: bool = True) -> dict:
    """Make a project from a link (YouTube or a direct audio/video file): downloads the audio and, when the page has them, the subtitles (their words
    replace speech recognition). Only for material the user may reuse. Runs in the background; poll job_status(job). The finished job's result names
    the project, and with run=true the pipeline has been run too."""
    from .. import ingest

    ingest.check_url(url)

    def work(cb):
        p = ingest.create_project(url, language=language, title=title, use_subs=use_subtitles, progress=lambda f, m: cb("download", f, m), aspect=aspect)
        if run:
            Pipeline(p, cb).run(None, None, False)
        return {"project": p.id, "origin": p.meta().origin}

    return {"job": _bg("import", "", work), "note": "poll job_status(job); the result has the project id"}


@tool
def run_pipeline(project: str, from_stage: Optional[str] = None, force: bool = False) -> dict:
    """Clean audio, cut silences, transcribe, build beats and a draft plan. Runs in the background; poll project_status.
    Stages in order: preprocess, silence, asr, cuts, words, plan, compose. from_stage re-runs from that stage."""
    p = _proj(project)
    jid = _bg("pipeline", project, lambda cb: (Pipeline(p, cb).run(from_stage, None, force), {"ok": True})[1])
    return {"job": jid, "note": "poll project_status(project) or job_status(job)"}


@tool
def job_status(job: str) -> dict:
    """Status of a background job started by run_pipeline or render."""
    record = _BG.get(job)
    scoped = project_scope.current_project()
    if scoped is not None and record is not None and record["project"] != scoped:
        from mcp.shared.exceptions import MCPError

        raise MCPError(-32001, "This director may read jobs only for its own project.")
    return record or {"error": "unknown job"}


@tool
def system_stats() -> dict:
    """Live numbers about the computer that does the work: processor, memory, disk, every graphics card (load, memory, temperature, which programs use it)
    and which of them Video Tool can use. Useful before starting a heavy job and when something is slow."""
    from .. import sysstats

    return sysstats.snapshot()


@tool
def gpu_assignment(job: str = "", gpu: str = "", allowed: str = "", use_own_copy_of: str = "") -> dict:
    """Which graphics cards Video Tool may use, which card each of its own jobs uses (rendering, speech recognition) and where the separate programs run. To change a job,
    pass job (primary, render or speech) and gpu (a card index, name or uuid; 'auto' for primary, 'primary' for a job). To change the cards Video Tool may use, pass
    allowed: card indexes, names or uuids separated by commas, 'all', or 'none' (the processor does the work). A card that is not allowed is never used.
    Jobs are render, speech, ai (Video Tool's own Ollama) and pictures (its own ComfyUI). The result's `engines` says where Ollama and ComfyUI run, and whether one that was already
    running sits on a card that is not allowed; to use Video Tool's own copy of it instead (the other is left as it is), pass use_own_copy_of: ollama or comfy."""
    from .. import gpuassign

    if use_own_copy_of:
        from ..engines import where

        where.use_own(use_own_copy_of, say=lambda *a: None)
    patch: dict = {}
    if allowed:
        patch["allowed"] = [] if allowed.strip().lower() == "none" else allowed
    if job and gpu:
        patch[job] = gpu
    moved = gpuassign.change(patch) if patch else []
    return {**gpuassign.describe(), "restarting": moved}


@tool
def project_status(project: str) -> dict:
    """Stage status, counts, background jobs, and queued requests for a project."""
    p = _proj(project)
    m = p.meta()
    jobs = [j for j in _BG.values() if j["project"] == project][-3:]
    return {"id": m.id, "title": m.title, "status": m.status, "stages": {k: v.get("done_at") for k, v in m.stages.items()},
            "words": len(p.transcript().words), "beats": len(p.beats().beats),
            "scenes": len(p.scenes().scenes) if p.scenes() else 0,
            "requests": [r.model_dump() for r in p.requests() if r.status == "queued"], "jobs": jobs}


# ------------------------------------------------------------------ transcript + scenes
@tool
def get_transcript(project: str) -> dict:
    """Beats with timed word ids ('w17:থাকবে@15.82') plus words flagged for review (low confidence)."""
    p = _proj(project)
    tr = p.transcript()
    words = tr.by_id()
    return {"language": tr.language,
            "beats": [{"id": b.id, "text": b.text, "start": round(b.start, 2), "end": round(b.end, 2),
                       "words": [f"{w}:{words[w].text}@{words[w].start:.2f}" for w in b.word_ids if w in words]} for b in p.beats().beats],
            "review": [{"id": w.id, "text": w.text, "conf": w.conf} for w in tr.words if w.flag == "review"]}


@tool
def fix_word(project: str, word_id: str, text: Optional[str] = None, cut: Optional[bool] = None) -> dict:
    """Correct a word's spelling (text) or remove/restore it (cut). Captions update everywhere."""
    p = _proj(project)
    path = p.dir / "edits.json"
    edits = read_json(path, {"words": {}}) or {"words": {}}
    cur = edits["words"].get(word_id, {})
    if text is not None:
        cur["text"] = text.strip()
    if cut is not None:
        cur["cut"] = cut
    edits["words"][word_id] = cur
    write_json(path, edits)
    pl = Pipeline(p)
    pl.stage_words()
    pl.stage_plan()
    compose_all(p)
    return {"ok": True, "edits": edits["words"][word_id]}


@tool
def add_glossary_term(project: str, term: str, replacement: str) -> dict:
    """Always replace `term` with `replacement` in this project's transcript (e.g. 'ইয়েল্ড' for 'yield')."""
    p = _proj(project)
    g = read_json(p.glossary_path, {}) or {}
    g[term.strip()] = replacement.strip()
    write_json(p.glossary_path, g)
    pl = Pipeline(p)
    pl.stage_words()
    pl.stage_plan()
    compose_all(p)
    return {"glossary": p.glossary()}


@tool
def get_scenes(project: str) -> dict:
    """The current plan (scenes.json) with each scene's time range."""
    p = _proj(project)
    sf = p.scenes()
    if not sf:
        raise ValueError("no plan yet; run_pipeline first")
    cuts = p.cuts()
    dur = cuts.output_duration if cuts else max((w.end for w in p.transcript().kept()), default=1.0) + 0.5
    times = {s["id"]: (s["start"], s["end"]) for s in scene_timing(sf, p.beats(), dur)}
    plan = sf.model_dump(exclude_none=True)
    for s in plan["scenes"]:
        if s["id"] in times:
            s["time"] = list(times[s["id"]])
    return plan


@tool
def update_scene(project: str, scene_id: str, patch: dict[str, Any]) -> dict:
    """Change a scene directly: patch may contain layout, transition_in, elements (full replacement list), caption. Every element takes x and y (its centre, 0-1 of the frame), scale, rotation and entrance ("none" is already in place, no fade). In a cartoon, each cast member takes x, y (height of the feet) and arrive (seconds after the cartoon appears, 0 is already there); move characters this way rather than moving the whole set. caption.y moves this scene's captions."""
    p = _proj(project)
    sf = p.scenes()
    if not sf:
        raise ValueError("no plan yet")
    new = scene_ops.patch_scene(sf, scene_id, patch)
    errs = validate_scenes(new, p.transcript(), p.beats(), None)
    if errs:
        return {"ok": False, "errors": errs[:10]}
    write_json(p.dir / "scenes.prev.json", sf.model_dump(exclude_none=True))
    p.save_scenes(new.model_copy(update={"planner": "manual" if new.planner == "rules" else new.planner}))
    compose_all(p)
    return {"ok": True}


@tool
def list_media(project: str) -> list[dict]:
    """The project's media bin (pictures, GIFs, clips): id, kind, caption, size. Use these ids in device / media_frame elements or scene backdrops."""
    p = _proj(project)
    return [{"id": m.id, "kind": m.kind, "caption": m.caption, "width": m.width, "height": m.height, "duration": m.duration, "source": m.source} for m in p.meta().media]


@tool
def prepare_upload(filename: str, size_bytes: int) -> dict:
    """Send a file from YOUR computer to the Video Tool server (needed when you run on another computer than the server; harmless otherwise).
    Run the returned `command` in your shell (it sends the file with a one-time ticket; no key needed), then pass `ref` ('upload:<id>') as
    audio_path to create_project or file_path to add_media."""
    from ..engines import hub
    from ..server import serve
    from ..server.uploads import new_ticketed

    up = new_ticketed(Path(filename).name, int(size_bytes))
    port = serve.STATE.get("port")
    if not port:
        return {"ref": f"upload:{up['id']}", "note": "This server runs on your computer: pass the file's own path instead (no upload needed)."}
    base = hub.address_hints(int(port))[0]
    url = f"{base}/api/uploads/{up['id']}/file?ticket={up['ticket']}"
    return {"ref": f"upload:{up['id']}", "url": url,
            "command": f'curl -sS --fail -T "{filename}" "{url}"',
            "windows_powershell": f'Invoke-WebRequest -Method Put -InFile "{filename}" -Uri "{url}"',
            "then": "When the command finishes, use ref as audio_path (create_project) or file_path (add_media)."}


@tool
def add_media(project: str, file_path: str, caption: str = "") -> dict:
    """Add a picture, GIF or video clip to the project's media bin: a path on the server computer, or 'upload:<id>' from prepare_upload.
    Give a caption with words from the sentence it belongs to."""
    from ..director import media as M
    from ..server.uploads import resolve

    p = _proj(project)
    try:
        item = M.add_media(p, resolve(file_path), caption=caption)
    except M.MediaError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "id": item.id, "kind": item.kind}


@tool
def house_rules() -> list[dict]:
    """The house rules every plan must follow (who may cover a face, one language on screen, show each thing once ...). submit_scenes and
    submit_story check them and name the rule ([rule-id]) when a plan breaks one."""
    from .. import house_rules as H

    return H.listing()


@tool
def list_scene_types(project: str, scene_id: str) -> list[dict]:
    """The kinds of scene this scene's sentences can be shown as (chart, steps, cartoon, picture...), best fit first. Only possible types are listed."""
    from ..director.plan import options_for_scene

    p = _proj(project)
    sf = p.scenes()
    sc = next((s for s in (sf.scenes if sf else []) if s.id == scene_id), None)
    if not sc:
        raise ValueError(f"scene '{scene_id}' not found")
    return options_for_scene(p.transcript(), p.beats(), sc, **planning.director_args(p))


@tool
def show_scene_as(project: str, scene_id: str, scene_type: str, media: Optional[str] = None) -> dict:
    """Rebuild one scene as another kind (e.g. 'line_trend', 'steps', 'cartoon', 'media_hero') from what was said. For the picture types pass a media id."""
    from ..director.contrast import decide_for_media
    from ..director.plan import reshow

    p = _proj(project)
    sf = p.scenes()
    if not sf:
        raise ValueError("no plan yet")
    sc = next((s for s in sf.scenes if s.id == scene_id), None)
    if not sc:
        raise ValueError(f"scene '{scene_id}' not found")
    try:
        new = reshow(p.transcript(), p.beats(), sc, scene_type, aspect=p.meta().aspect, media_id=media, scrim_fn=lambda m, a, l, t0, t1: decide_for_media(p, m, a, l, t0, t1),
                     **planning.director_args(p))
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    out = sf.model_copy(update={"scenes": [new if s.id == scene_id else s for s in sf.scenes], "planner": "manual" if sf.planner == "rules" else sf.planner})
    write_json(p.dir / "scenes.prev.json", sf.model_dump(exclude_none=True))
    p.save_scenes(out)
    compose_all(p)
    return {"ok": True, "scene": new.model_dump(exclude_none=True)}


@tool
def request_regenerate(project: str, scene_id: str, hint: str = "", alternatives: int = 1) -> dict:
    """Queue a re-plan of one scene. Returns the request id for get_planning_task."""
    r = planning.create_request(_proj(project), "scene", scene_id, hint, alternatives)
    return {"request_id": r.id}


# ------------------------------------------------------------------ design
@tool
def search_icons(query: str, kind: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Find icons/stickers by meaning, in English or Bangla (e.g. 'পাথর', 'savings', 'old woman'). kind: 'icon' (line icons, ids like
    'lucide:coins'), 'sticker' (colour emoji, use the hex) or omit for both. Searches 8,000 visuals; offensive emoji are never returned."""
    from ..visuals.search import search

    return search(query, kind, max(1, min(limit, 30)))


@tool
def list_components() -> dict:
    """Component catalogue: element types with fields, limits and examples; layouts, transitions, icon names."""
    return catalogue_summary()


@tool
def list_themes_tool() -> list[dict]:
    """Available themes (name, label, key colours, caption style)."""
    return [{"name": t.name, "label": t.label, "accent": t.color.accent, "bg": t.color.bg, "caption": t.caption.style,
             "motion": t.motion.preset} for t in list_themes()]


@tool
def get_theme(name: str) -> dict:
    """Full theme JSON."""
    return load_theme(name).model_dump(exclude_none=True)


def _merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


@tool
def update_theme(name: str, patch: dict[str, Any], save_as: Optional[str] = None) -> dict:
    """Deep-merge `patch` into a theme (e.g. {"color": {"accent": "#0a84ff"}}). Built-in themes (paper, dark-neon, minimal)
    must be saved under a new name with save_as."""
    base = load_theme(name).model_dump(exclude_none=True)
    target = save_as or name
    if target in ("paper", "dark-neon", "minimal"):
        return {"ok": False, "errors": ["built-in themes are read-only; pass save_as='my-theme'"]}
    merged = _merge(base, patch)
    merged["name"] = target
    t = Theme.model_validate(merged)
    write_json(paths.THEMES / target / "theme.json", t.model_dump(exclude_none=True))
    for p in Project.list_all():
        sf = p.scenes()
        if sf and sf.theme == target:
            compose_all(p)
    return {"ok": True, "theme": target}


# ------------------------------------------------------------------ preview + render
@tool
def get_preview_frame(project: str, time_seconds: float, aspect: Optional[str] = None) -> Image:
    """A PNG of the video at a given time so you can look at the result and adjust. Takes a few seconds."""
    from ..render.hyperframes import snapshot

    p = _proj(project)
    a = aspect or p.meta().aspect
    compose_all(p)
    out = p.dir / "snapshots"
    files = snapshot(p.comp_dir / FORMATS[a]["tag"], out, [float(time_seconds)])
    if not files:
        raise RuntimeError("could not capture a frame")
    return Image(path=str(files[0]))


@tool
def render(project: str, aspect: Optional[str] = None, quality: str = "looks") -> dict:
    """Render the final MP4 (+ .srt) in the background. quality: draft | looks | delivery. Poll job_status."""
    p = _proj(project)
    a = aspect or p.meta().aspect
    jid = _bg("render", project, lambda cb: export(p, a, quality=quality, progress=cb))
    return {"job": jid}


# ------------------------------------------------------------------ Video Script (any assistant: Claude, ChatGPT, ...)
@tool
def get_script_task(project: str, kind: str = "", hint: str = "") -> dict:
    """Read once for the timed transcript, catalogue and schema, then call submit_script. Scoped tasks use the concise brief.
    kind: stick | emoji | explainer | infographic | cartoon | mixed (empty = the project's kind)."""
    from ..script import service

    p = _proj(project)
    if kind and kind not in ("stick", "emoji", "explainer", "infographic", "cartoon", "mixed"):
        raise ValueError("kind must be stick, explainer, infographic, cartoon or mixed")
    if kind:
        service.set_script_kind(p, kind)
    return service.script_task(p, kind or None, hint, compact=project_scope.current_project() is not None)


@tool
def submit_script(project: str, script: dict[str, Any]) -> dict:
    """Submit the Video Script (the JSON object from get_script_task). It is validated and compiled into the plan.
    Returns {ok, errors, repairs}. Nothing is changed behind your back: whatever the app would have had to change in what you wrote (a word id moved, a text cut short, a value it does not
    know left out, scenes restructured) comes back as an error to fix, and the small things it filled in (a synonym, a default side) come back in `repairs`. If there are errors,
    fix exactly those and submit again."""
    from ..script import service

    p = _proj(project)
    script = {k: v for k, v in script.items() if k != "edits_since_this_script"}     # get_current_script's note, not part of a script
    res = service.apply_script(p, script, planner="assistant" if os.environ.get("VT_MCP_CLIENT") == "codex" else "claude", strict=True)
    if res.get("ok"):                                          # the editor's verdict comes back with every accepted script
        res["director_notes"] = get_director_notes(project)
    return res


@tool
def get_story_task(project: str) -> dict:
    """Cartoon 2 (story) videos: the designer rules, the catalog of everything that can be drawn, the timed captions, the cast and the current
    story as one JSON spec (absolute seconds). Edit the spec and call submit_story."""
    from ..story import service

    return service.story_task(_proj(project))


@tool
def submit_story(project: str, story: dict[str, Any]) -> dict:
    """Submit a whole Cartoon 2 story (the spec from get_story_task, edited). It is validated and becomes the plan. Returns {ok, errors}; fix and resubmit."""
    from ..story import service

    p = _proj(project)
    changed_by = "assistant" if os.environ.get("VT_MCP_CLIENT") == "codex" else "claude"
    res = service.submit_story(p, story, planner=changed_by)
    if res.get("ok"):
        from ..directors import record

        record(p, changed_by, requested=p.meta().options.director or "best")
    return res


@tool
def get_current_script(project: str) -> dict:
    """Return the current Video Script so an assistant can revise and resubmit it. `edits_since_this_script` lists the scenes changed afterwards (update_scene, the
    frame check, the person's own edits) with what they are now: submitting a new script replaces them, so carry over the ones you want to keep."""
    from ..script.service import current_script, edits_since_script

    p = _proj(project)
    script = current_script(p)
    if script is None:
        if project_scope.current_project() is not None:
            return {"script": None, "next": "No script has been submitted. Use get_script_task, then submit_script."}
        raise ValueError("no Video Script yet; call get_script_task, then submit_script")
    return {**script, "edits_since_this_script": edits_since_script(p)}


@tool
def get_director_notes(project: str) -> dict:
    """An editor's review of the current Video Script: a score (0-100), metrics (longest still stretch, talk share, verbs, cast and places
    used, camera moves) and scene-by-scene notes with a suggested fix. Fix the notes and submit_script again until there are none."""
    from ..script.critic import review
    from ..script.models import VideoScript
    from ..script.service import current_script

    p = _proj(project)
    data = current_script(p)
    if not data:
        raise ValueError("no Video Script yet; call get_script_task, then submit_script")
    return review(VideoScript.model_validate(data), p.transcript(), p.beats())


@tool
def frame_facts(project: str, times: list[float], aspect: Optional[str] = None) -> dict:
    """What covers what at these moments, measured on the real page: which element or caption covers how much of each character's face, what is outside the frame,
    what overlaps. Use it with preview_frames: the numbers catch what the eye misses. It changes nothing."""
    from ..render.hyperframes import frame_facts as measure

    p = _proj(project)
    return measure(p.comp_dir / FORMATS[aspect or p.meta().aspect]["tag"], [float(t) for t in times[:12]])


@tool
def preview_frames(project: str, times: list[float], aspect: Optional[str] = None) -> list[Image]:
    """PNG frames at several moments (seconds). A-roll frames come from a fresh render so the speaker is visible. Max 6."""
    from ..render.hyperframes import snapshot

    p = _proj(project)
    a = aspect or p.meta().aspect
    if any(s.backdrop and s.backdrop.media == "aroll" for s in (p.scenes().scenes if p.scenes() else [])):
        from ..util import find_tool, run

        tag = FORMATS[a]["tag"]
        exports = sorted(p.exports_dir.glob(f"*-{tag}-*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not exports or exports[0].stat().st_mtime < p.scenes_path.stat().st_mtime:
            raise ValueError("A-roll snapshots omit video frames. Render this plan first, then call preview_frames to inspect the finished MP4.")
        out_dir = p.dir / "snapshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for i, at in enumerate(times[:6]):
            frame = out_dir / f"rendered-{i:02d}-at-{float(at):.2f}s.png"
            run([find_tool("ffmpeg"), "-y", "-v", "error", "-ss", str(float(at)), "-i", str(exports[0]), "-frames:v", "1", str(frame)])
            files.append(frame)
        return [Image(path=str(f)) for f in files]
    compose_all(p)
    files = snapshot(p.comp_dir / FORMATS[a]["tag"], p.dir / "snapshots", [float(t) for t in times[:6]])
    return [Image(path=str(f)) for f in files]


# ------------------------------------------------------------------ code-native shots (PLAN-CODE-NATIVE-EDITOR C2 to C5)
def _frame_of(p: Project) -> Optional[tuple[int, int]]:
    f = FORMATS.get(p.meta().aspect)
    return (f["width"], f["height"]) if f else None


@tool
def list_shots(project: str) -> list[dict]:
    """The video's code-native shots: id, title, size, duration, and the knobs the person can change. A shot is an HTML page with its own animation, drawn behind one scene."""
    from .. import shots as SH

    return SH.list_shots(_proj(project))


@tool
def get_shot(project: str, shot_id: str) -> dict:
    """One shot: its HTML (html), the ids a person can select (ids), the knobs (knobs) and the person's visual edits (overrides: text, position, colour ... kept apart from the code)."""
    from .. import shots as SH

    d = SH.shot_dir(_proj(project), shot_id)
    if not (d / "index.html").exists():
        raise ValueError(f"no shot '{shot_id}'; list_shots shows what the video has")
    html = (d / "index.html").read_text(encoding="utf-8")
    return {**SH.info(d), "html": html, "ids": SH.ids_in(html), "overrides": SH.check_overrides(SH.read_json(d / "overrides.json", {}))}


@tool
def write_shot(project: str, shot_id: str, html: str, title: str = "", knobs: Optional[list[dict]] = None) -> dict:
    """Create or replace a shot's HTML. Follow the SHOTS rules in get_script_task: a root with data-composition-id/data-start/data-duration/data-width/data-height matching this video's frame,
    data-vt-id on every text and main shape, motion only on a paused GSAP timeline in window.__timelines, no network. knobs: [{name: '--accent', label: 'Ring', kind: 'colour'}].
    Returns {ok, errors}; fix exactly those and write again. The person's visual edits are kept. Then use set_scene_shot to show it behind a scene."""
    from .. import shots as SH
    from ..script.models import ShotKnob

    p = _proj(project)
    errs = SH.problems(shot_id, html, aspect_size=_frame_of(p))
    try:
        ks = [ShotKnob.model_validate(k).model_dump() for k in (knobs or [])]
    except Exception as e:                                          # noqa: BLE001  a validation error is the answer
        errs.append(f"knobs: {str(e)[:200]}")
        ks = []
    if errs:
        return {"ok": False, "errors": errs}
    d = SH.shot_dir(p, shot_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(html, encoding="utf-8")
    meta = SH.read_json(d / "shot.json", {})
    meta.update(title=title or meta.get("title") or shot_id, knobs=ks if knobs is not None else meta.get("knobs", []), made_by=os.environ.get("VT_MCP_CLIENT", "assistant"))
    write_json(d / "shot.json", meta)
    if any(s.shot == shot_id for s in (p.scenes().scenes if p.scenes() else [])):
        compose_all(p)
    return {"ok": True, "ids": SH.ids_in(html)}


@tool
def set_scene_shot(project: str, scene_id: str, shot_id: Optional[str] = None, clear_elements: bool = False) -> dict:
    """Show a shot full-frame behind a scene (the scene's captions stay on top), or pass no shot_id to draw the scene the usual way again.
    The scene's own elements (titles, icons, cards) still draw ON TOP of the shot. When the shot replaces them, pass clear_elements=true
    (Ctrl+Z in the editor brings them back); the answer lists the elements left on top so you can decide."""
    from .. import shots as SH

    p = _proj(project)
    sf = p.scenes()
    if not sf:
        raise ValueError("no plan yet")
    if scene_id not in {s.id for s in sf.scenes}:
        raise ValueError(f"no scene '{scene_id}'")
    if shot_id and not (SH.shot_dir(p, shot_id) / "index.html").exists():
        raise ValueError(f"no shot '{shot_id}'; write_shot first")
    write_json(p.dir / "scenes.prev.json", sf.model_dump(exclude_none=True))
    change = {"shot": shot_id or None, **({"elements": []} if clear_elements and shot_id else {})}
    p.save_scenes(sf.model_copy(update={"scenes": [s.model_copy(update=change) if s.id == scene_id else s for s in sf.scenes],
                                         "planner": "manual" if sf.planner == "rules" else sf.planner}))
    compose_all(p)
    left = [] if (clear_elements or not shot_id) else [f"{getattr(e, 'type', '')}: {str(getattr(e, 'text', '') or getattr(e, 'label', '') or '')[:40]}"
                                                         for e in next(s for s in sf.scenes if s.id == scene_id).elements]
    return {"ok": True, **({"elements_on_top": left, "note": "These still draw over the shot. If the shot replaces them, call again with clear_elements=true."} if left else {})}


@tool
def set_shot_edits(project: str, shot_id: str, overrides: dict) -> dict:
    """Change a shot the way the person does in the editor, without touching its code: {knobs: {'--accent': '#22c55e'}, elements: {'title': {text, x, y, scale, rotate, hidden, style: {color, fontSize,
    fontWeight, opacity}}}}. Replaces all of the shot's edits (read them with get_shot first to keep the person's)."""
    from .. import shots as SH

    p = _proj(project)
    d = SH.shot_dir(p, shot_id)
    if not (d / "index.html").exists():
        raise ValueError(f"no shot '{shot_id}'")
    try:
        saved = SH.save_overrides(d, overrides)
    except SH.ShotError as e:
        return {"ok": False, "errors": [str(e)]}
    if any(s.shot == shot_id for s in (p.scenes().scenes if p.scenes() else [])):
        compose_all(p)
    return {"ok": True, "overrides": saved}


@tool
def get_shot_frame(project: str, shot_id: str, time_seconds: float = 0.0) -> Image:
    """A PNG of one shot on its own at a moment (seconds from the shot's start), with the person's edits. Look at it after write_shot."""
    from .. import shots as SH

    p = _proj(project)
    d = SH.shot_dir(p, shot_id)
    if not (d / "index.html").exists():
        raise ValueError(f"no shot '{shot_id}'")
    dur = SH.info(d)["duration"]
    got = SH.frames(d, d / "frames", [min(max(0.0, float(time_seconds)), max(0.0, dur - 0.001))], theme=SH.theme_vars(p))
    if not got:
        raise RuntimeError("could not capture a frame")
    return Image(path=str(got[0]))


@tool
def make_picture(project: str, prompt: str, aspect: str = "", seed: int = 1) -> dict:
    """Draw one picture with the picture engine on this computer (ComfyUI) and put it in the project's media bin. About 15 s on a 6 GB card, 30 s the first time.
    Say what it shows in plain words. Use the returned media id in a shot (assets) or a scene (show_scene_as). Fails in words when no picture engine runs."""
    from ..comfy import ComfyClient, ComfyError, generate_still, picture_workflow
    from ..server.comfy_routes import comfy_url

    p = _proj(project)
    client = ComfyClient(comfy_url())
    try:
        try:
            item, rec = generate_still(p, client, picture_workflow(object_info=client.object_info()), prompt.strip()[:600], aspect=aspect or p.meta().aspect, seed=int(seed), caption=prompt[:80])
        except ComfyError as e:
            return {"ok": False, "error": str(e)[:300]}
    finally:
        client.close()
    return {"ok": True, "media": item.id, "file": item.file if hasattr(item, "file") else "", "seconds": rec.get("seconds_taken"), "size": rec.get("size")}


@tool
def speak(project: str, text: str, voice: str = "af_heart", engine: str = "kokoro", rate: float = 1.0) -> dict:
    """Speak English text with a voice on this computer (Kokoro by default; voices such as af_heart, am_michael, bf_emma). Saves a WAV in the project's
    agent_audio folder and returns its path, duration and word times. About 1.5x real time on the processor, 20 s the first time."""
    import re

    from .. import tts

    p = _proj(project)
    out_dir = p.dir / "agent_audio"
    out_dir.mkdir(exist_ok=True)
    name = re.sub(r"[^a-z0-9]+", "-", text.lower())[:30].strip("-") or "speech"
    out = out_dir / f"{name}-{voice}.wav"
    try:
        res = tts.synthesize(text, out, engine=engine, voice=voice, rate=float(rate), language="en")
    except tts.TTSError as e:
        return {"ok": False, "error": str(e)[:300]}
    return {"ok": True, "file": str(out.relative_to(p.dir)), "duration": res.get("duration"), "engine": res.get("engine"), "voice": res.get("voice")}


@tool
def ask_local(question: str, context: str = "") -> dict:
    """Ask the small language model on this computer (Ollama) a short question: rewrite a line, shorten a caption, name something, translate a sentence.
    Free and private, but small: do not ask it to write shots or plan a video. Fails in words when Ollama is not running."""
    from .. import llm

    try:
        out = llm.chat_json([{"role": "system", "content": "Answer briefly and plainly. Reply as JSON with one field, answer."},
                             {"role": "user", "content": (context.strip()[:4000] + chr(10) * 2 if context.strip() else "") + question.strip()[:2000]}],
                            {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}, num_ctx=4096, max_tokens=600, timeout=180)
    except llm.LLMUnavailable as e:
        return {"ok": False, "error": str(e)[:300]}
    return {"ok": True, "answer": str(out.get("answer", ""))[:2000], "model": llm.model_name()}


@server.prompt(name="plan_this_video", description="Plan every pending video request")
def plan_this_video() -> str:
    return ("Plan all pending Video Tool requests: call list_pending_requests; for each, get_planning_task, then submit_scenes (fix returned errors "
            "and resubmit); then check two or three frames with preview_frames and fix problems with update_scene.")


@server.prompt(name="make_stick_figure_video", description="Direct a stick-figure video for a project")
def make_stick_figure_video(project: str) -> str:
    return (f"Make project '{project}' a stick-figure video: call get_script_task(project='{project}', kind='stick'), write the Video Script it asks for, "
            "call submit_script and fix any errors, then check frames with preview_frames.")


@server.prompt(name="direct_whole_video", description="Direct and render a complete video with Codex, Claude or another MCP assistant")
def direct_whole_video(project: str, brief: str = "") -> str:
    return (f"Direct the whole Video Tool project '{project}'. First call project_status and get_script_task(project='{project}', hint={brief!r}). "
            "Read the timed transcript and schema, write a complete Video Script covering every beat, then call submit_script. "
            "Fix any returned errors and resubmit. Call get_director_notes and improve the script until there are no serious issues. "
            "Call render and poll job_status, then check representative frames with preview_frames. Adjust and rerender if needed. "
            "Tell the user which export was made and any factual points that need their review.")


@server.prompt(name="improve_scene", description="Improve one scene of a project")
def improve_scene(project: str, scene_id: str) -> str:
    return (f"Look at scene {scene_id} of project '{project}' (get_scenes, preview_frames). Improve it: use list_scene_types / show_scene_as or "
            "update_scene so the picture fits what is said. Do not invent facts.")


@server.resource("vt://catalogue", name="catalogue", description="Component catalogue (element types, fields, limits, examples)", mime_type="application/json")
def res_catalogue() -> str:
    import json

    return json.dumps(catalogue_summary(), ensure_ascii=False)


@server.resource("vt://script-schema", name="script-schema", description="JSON Schema of the Video Script", mime_type="application/json")
def res_script_schema() -> str:
    import json

    from ..script import to_json_schema

    return json.dumps(to_json_schema(), ensure_ascii=False)


def main() -> None:
    import sys

    if "--http" in sys.argv:
        from .http import run_http

        run_http(server, port=int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8766)
        return
    server.run("stdio")


if __name__ == "__main__":
    main()
