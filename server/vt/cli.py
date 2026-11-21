"""Command line interface: `vt --help`."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # Bangla text and symbols on Windows consoles
    except Exception:
        pass

from . import paths  # noqa: E402
from .project import Project, list_themes  # noqa: E402

app = typer.Typer(add_completion=False, help="Voice recording -> faceless motion-graphics video.")
models_app = typer.Typer(help="Manage speech-recognition models.")
app.add_typer(models_app, name="models")
modules_app = typer.Typer(help="Inspect the director's callable modules.")
app.add_typer(modules_app, name="modules")
engine_app = typer.Typer(help="Run this computer as the engine for others: Ollama, ComfyUI and voices, offered through one address and one key.")
app.add_typer(engine_app, name="engine")
console = Console()


@modules_app.command("list")
def modules_list() -> None:
    """List the modules already available through the shared executor."""
    from .modules.defs import load
    from .modules.registry import list_modules

    load()
    table = Table("Module", "What it does", "Cost")
    for spec in list_modules():
        table.add_row(spec.id, spec.summary, spec.cost.kind)
    console.print(table)


@modules_app.command("describe")
def modules_describe(module_id: str) -> None:
    """Show the full input and output contracts of one module."""
    import json

    from .modules.defs import load
    from .modules.registry import get_module

    load()
    try:
        spec = get_module(module_id)
    except KeyError:
        raise typer.BadParameter(f"unknown module: {module_id}")
    console.print_json(json.dumps({
        "id": spec.id, "version": spec.version, "summary": spec.summary,
        "when_to_use": spec.when_to_use, "when_not_to_use": spec.when_not_to_use,
        "inputs": spec.inputs.model_json_schema(), "outputs": spec.outputs.model_json_schema(),
        "requires": spec.requires, "produces": spec.produces,
        "cost": {"kind": spec.cost.kind, "resources": spec.cost.resources},
        "effects": spec.effects, "examples": [example.__dict__ for example in spec.examples],
    }, ensure_ascii=False))


@app.command("call")
def call_module(module_id: str, project: str = typer.Option(..., "--project", help="Project id"),
                json_inputs: str = typer.Option("{}", "--json", help="Input JSON object"),
                force: bool = typer.Option(False, "--force")) -> None:
    """Call a module against one existing project and print its result as JSON."""
    import json

    from .modules.executor import Executor

    try:
        values = json.loads(json_inputs)
        if not isinstance(values, dict):
            raise ValueError("inputs must be a JSON object")
    except (ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--json")
    proj = _project(project)
    try:
        result = Executor(proj.dir).call(module_id, values, caller="person", force=force)
    except KeyError:
        raise typer.BadParameter(f"unknown module: {module_id}")
    console.print_json(result.model_dump_json())
    if not result.ok:
        raise typer.Exit(1)


@app.command("replay")
def replay_project(project: str = typer.Argument(..., help="Project id")) -> None:
    """Rebuild recorded deterministic artifacts without asking an AI."""
    import json

    from .modules.replay import replay

    proj = _project(project)
    console.print(json.dumps(replay(proj.dir), ensure_ascii=False))


def _project(pid: str) -> Project:
    p = Project(pid)
    if Path(pid).name != pid or not p.dir.resolve().is_relative_to(paths.PROJECTS.resolve()):
        console.print("[red]Invalid project id.[/red]")
        raise typer.Exit(1)
    if not p.exists():
        console.print(f"[red]No project '{pid}'.[/red] Run `vt list` to see projects.")
        raise typer.Exit(1)
    return p


def _progress_runner(fn):
    """Run fn(progress_callback) with a rich progress bar."""
    with Progress(TextColumn("[bold]{task.fields[stage]:<16}"), BarColumn(), TextColumn("{task.percentage:>3.0f}%"),
                  TextColumn("{task.fields[msg]}"), TimeElapsedColumn(), console=console, transient=False) as prog:
        task = prog.add_task("", total=100, stage="", msg="")

        def cb(stage: str, frac: float, msg: str = "") -> None:
            from .pipeline import LABELS
            prog.update(task, completed=frac * 100, stage=LABELS.get(stage, stage), msg=str(msg)[:60])

        return fn(cb)


@app.command("rules")
def rules() -> None:
    """The house rules every video follows (vt/house_rules.py): what the AI is told and the video that taught it."""
    from . import house_rules

    for r in house_rules.listing():
        typer.echo(f"{r['id']} [{', '.join(r['scopes'])}]\n  {r['say']}\n  why: {r['why']}")


@app.command()
def new(title: str = typer.Argument(..., help="Video title"),
        audio: Path = typer.Option(..., "--audio", "-a", exists=True, dir_okay=False, help="Voice recording (wav/mp3/m4a/webm)"),
        language: str = typer.Option("en", "--lang", help="en or bn"),
        aspect: str = typer.Option("9:16", "--aspect", help="9:16, 1:1 or 16:9"),
        theme: str = typer.Option("paper", "--theme"),
        pace: str = typer.Option("normal", "--pace", help="calm | normal | fast"),
        music: Optional[str] = typer.Option(None, "--music", help="bundled track id (see `vt music`)"),
        fillers: bool = typer.Option(True, "--fillers/--keep-fillers", help="remove um/uh and repeated words"),
        model: str = typer.Option("bn-medium", "--asr", help="bn-medium | large-v3 | medium | small"),
        director: str = typer.Option("best", "--director", help="best | local | claude-server | claude@DEVICE"),
        srt: Optional[Path] = typer.Option(None, "--srt", exists=True, dir_okay=False, help="the recording's own .srt: its words and timing are used, no speech recognition")) -> None:
    """Create a project from a recording."""
    opts = {"remove_fillers": fillers, "asr_model": model, "music": music, "director": director}
    proj = Project.create(title, audio, language=language, aspect=aspect, theme=theme, pace=pace, options=opts)
    if srt:
        from .ingest import attach_subtitles

        got = attach_subtitles(proj, srt, language)
        console.print(f"Subtitles: {got['lines']} lines, {got['words']} words ({got['language']}); speech recognition is skipped")
    console.print(f"[green]Created[/green] {proj.id}\nNext: vt run {proj.id}")


@app.command("link")
def from_link(url: str = typer.Argument(..., help="YouTube link or a direct link to an audio/video file (only material you may reuse)"),
              title: str = typer.Option("", "--title"), language: str = typer.Option("en", "--lang", help="language of the speech: bn or en"),
              aspect: str = typer.Option("9:16", "--aspect"), theme: str = typer.Option("paper", "--theme"),
              subs: str = typer.Option("auto", "--subs", help="auto (the author's subtitles, and automatic ones for non-English) | any | off"),
              director: str = typer.Option("best", "--director")) -> None:
    """Download the audio (and subtitles) from a link and create a project from it."""
    from . import ingest

    try:
        proj = ingest.create_project(url, language=language, title=title, use_subs=subs, aspect=aspect, theme=theme,
                                     options={"use_subtitles": subs, "director": director})
    except ingest.IngestError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    o = proj.meta().origin or {}
    console.print(f"[green]Created[/green] {proj.id} from '{o.get('title')}' ({'subtitles found' if o.get('subtitles') else 'no subtitles: speech recognition will be used'})")
    console.print(f"Next: vt run {proj.id}")


@app.command()
def script(title: str = typer.Argument(..., help="Video title"),
           text: Optional[str] = typer.Option(None, "--text", "-t", help="the script, as text"),
           file: Optional[Path] = typer.Option(None, "--file", "-f", exists=True, dir_okay=False, help="a UTF-8 text file with the script"),
           engine: str = typer.Option("edge", "--engine", help="edge (online, best Bangla) | mms (offline, non-commercial)"),
           voice: str = typer.Option("en-US-AndrewNeural", "--voice"),
           rate: float = typer.Option(1.0, "--speed", help="0.7 - 1.4"),
           language: str = typer.Option("en", "--lang", help="en or bn; the script's letters decide in the end"), aspect: str = typer.Option("9:16", "--aspect"),
           theme: str = typer.Option("paper", "--theme"), pace: str = typer.Option("normal", "--pace"),
           music: Optional[str] = typer.Option(None, "--music"), director: str = typer.Option("best", "--director")) -> None:
    """Create a project from typed text: the script is spoken by a voice, then everything else is automatic."""
    body = text if text is not None else (file.read_text(encoding="utf-8") if file else None)
    if not body or not body.strip():
        console.print("[red]Give the script with --text or --file.[/red]")
        raise typer.Exit(1)
    proj = Project.create_from_script(title, body, voice_engine=engine, voice=voice, rate=max(0.6, min(1.5, rate)), language=language,
                                      aspect=aspect, theme=theme, pace=pace, options={"music": music, "director": director})
    console.print(f"[green]Created[/green] {proj.id}\nNext: vt run {proj.id}")


@app.command("directors")
def list_directors(model: Optional[str] = typer.Option(None, "--model", help="which Claude directs: sonnet (faster) or opus (slower, the most careful); saved like the Settings page does")) -> None:
    """Show who can direct a video now and the fallback order; with --model, choose which Claude directs."""
    from .directors import listing, save_settings

    if model is not None:
        console.print(f"Claude will direct with [bold]{save_settings(model=model)['director_model']}[/bold] from the next video.")
    data = listing()
    for d in data["directors"]:
        console.print(f"[{'green' if d['available'] else 'yellow'}]{'ready' if d['available'] else 'not ready':<9}[/] {d['id']:<24} {d['label']} — {d['note']}")
    console.print("Fallback: " + " → ".join(data["order"]))


@app.command()
def run(project: str, from_stage: Optional[str] = typer.Option(None, "--from", help="re-run from this stage"),
        to_stage: Optional[str] = typer.Option(None, "--to"),
        force: bool = typer.Option(False, "--force")) -> None:
    """Run the pipeline up to a ready-to-review plan (cuts, transcript, scenes, preview)."""
    from .pipeline import Pipeline

    p = _project(project)
    try:
        _progress_runner(lambda cb: Pipeline(p, cb).run(from_stage, to_stage, force))
    except Exception as e:  # noqa: BLE001  (readable message instead of a traceback; Studio shows the same text)
        console.print(f"\n[red]Stopped:[/red] {e}")
        raise typer.Exit(1)
    sf = p.scenes()
    console.print(f"[green]Ready.[/green] {len(p.transcript().words)} words, {len(sf.scenes) if sf else 0} scenes "
                  f"(planner: {sf.planner if sf else '-'}). Review: vt studio   Render: vt render {p.id}")


@app.command()
def render(project: str,
           aspect: str = typer.Option("project", "--aspect", help="9:16 | 1:1 | 16:9 | both (all three) | project"),
           quality: str = typer.Option("looks", "--quality", help="draft | looks | delivery"),
           cpu: bool = typer.Option(False, "--cpu", help="CPU encoding instead of NVENC"),
           music: Optional[str] = typer.Option("project", "--music", help="track id, 'none', or 'project'")) -> None:
    """Render the final MP4 (voice + music + SFX)."""
    from .pipeline import export

    p = _project(project)
    meta = p.meta()
    aspects = ["9:16", "1:1", "16:9"] if aspect == "both" else [meta.aspect if aspect == "project" else aspect]
    for a in aspects:
        res = _progress_runner(lambda cb: export(p, a, quality=quality, gpu=not cpu,
                                                 music=None if music == "none" else ("__project__" if music == "project" else music),
                                                 progress=cb))
        console.print(f"[green]{a}[/green] {res['video']}  ({res['seconds']}s to render {res['duration']}s of video)")


@app.command("outline")
def outline_talk(project: str, local: bool = typer.Option(False, "--local", help="use the local AI (Ollama) even when another is chosen")) -> None:
    """Read a long talk ahead and mark its example stretches (for B-roll) and the parts that stay on the speaker (C10)."""
    from . import talk_outline

    p = Project(project)
    provider = None
    if local:
        from .ai import OllamaProvider
        provider = OllamaProvider()
    out = talk_outline.build(p, provider=provider, progress=lambda f, m: console.print(f"[dim]{m}[/dim]"))
    console.print(f"{len(out['sentences'])} sentences, {len(out['sections'])} sections, {len(out['examples'])} examples")
    for e in out["examples"]:
        console.print(f"  {e['start']:7.1f}-{e['end']:7.1f}s  {e['kind']:<13} {e['about']}")


@app.command("list")
def list_projects() -> None:
    """List projects."""
    t = Table("id", "title", "aspect", "status", "created")
    for p in Project.list_all():
        m = p.meta()
        t.add_row(m.id, m.title, m.aspect, m.status, m.created_at[:16])
    console.print(t)


@app.command()
def status(project: str) -> None:
    """Show stage status and pending Claude requests."""
    p = _project(project)
    m = p.meta()
    t = Table("stage", "done", "info")
    for s, v in m.stages.items():
        t.add_row(s, v.get("done_at", "")[:19], ", ".join(f"{k}={x}" for k, x in v.items() if k not in ("hash", "done_at")))
    console.print(f"[bold]{m.title}[/bold]  status: {m.status}")
    console.print(t)
    for r in p.requests():
        console.print(f"request {r.id}: {r.kind} {r.scene_id or ''} [{r.status}] {r.hint}")


@app.command("plan-request")
def plan_request(project: str, scene: Optional[str] = typer.Option(None, "--scene"), hint: str = typer.Option("", "--hint"),
                 alternatives: int = typer.Option(1, "--alternatives")) -> None:
    """Queue a planning request for Claude (picked up by `/vt-plan` in Claude Code)."""
    from .planning import create_request

    p = _project(project)
    r = create_request(p, "scene" if scene else "full", scene, hint, alternatives)
    console.print(f"Queued request {r.id}. In Claude Code say: [bold]plan my pending videos[/bold] (or run /vt-plan).")


@app.command()
def check(project: str, aspect: str = typer.Option("project", "--aspect")) -> None:
    """HyperFrames' pre-flight on the composition: script errors, missing files, text leaving the picture, unreadable text (no render, about 2 seconds)."""
    from .compose import FORMATS
    from .pipeline import compose_all
    from .render.hyperframes import check as hf_check

    p = _project(project)
    compose_all(p)
    a = p.meta().aspect if aspect == "project" else aspect
    r = hf_check(p.comp_dir / FORMATS[a]["tag"])
    if r.get("unavailable"):
        console.print(f"[yellow]The check could not run:[/] {r['unavailable']}")
    console.print(f"{'OK' if r['ok'] else 'PROBLEMS'}: {r['errors']} error(s), {r['warnings']} warning(s)")
    for i in r["issues"]:
        console.print(f"  [{i['severity']}] {i['area']} @ {i['time']}s: {i['message'][:140]}")


@app.command()
def snapshot(project: str, at: str = typer.Option("1,5", "--at", help="comma-separated seconds"),
             aspect: str = typer.Option("project", "--aspect")) -> None:
    """Save PNG frames of the composition (for a quick look without rendering)."""
    from .compose import FORMATS
    from .pipeline import compose_all
    from .render.hyperframes import snapshot as snap

    p = _project(project)
    compose_all(p)
    a = p.meta().aspect if aspect == "project" else aspect
    out = p.dir / "snapshots"
    files = snap(p.comp_dir / FORMATS[a]["tag"], out, [float(x) for x in at.split(",")])
    for f in files:
        console.print(f)


ENGINE_CHOICE = "auto = use one already running here, else our own copy if installed; existing = only one already running (or the --*-url given); own = our own copy on its own port and folder; off"


@app.command()
def server(host: str = typer.Option("0.0.0.0", help="0.0.0.0 = other computers on this network may connect, by the address printed below; 127.0.0.1 = this computer only"),
           port: Optional[int] = typer.Option(None, help="default 8765, or the next free port when something else has it"),
           name: str = typer.Option("", help="a name for this server, shown to the computers that connect to it"),
           ollama: str = typer.Option("auto", help=ENGINE_CHOICE), comfy: str = typer.Option("auto", help="as --ollama"),
           ollama_url: str = typer.Option("", help="an Ollama that is not on its usual port"),
           comfy_url: str = typer.Option("", help="ComfyUI address(es), comma-separated: the first is the main server, the rest are workers"),
           gpus: str = typer.Option("", "--gpus", help="the graphics cards Video Tool may use: numbers separated by commas, all, or none. Saved: the Server page shows and changes it too"),
           open_ui: bool = typer.Option(False, "--open", help="open the Studio in this computer's browser"),
           start_at_login: bool = typer.Option(False, "--start-at-login", help="also start this server by itself from now on, the same way (Engines page: This server)"),
           trust_network: Optional[bool] = typer.Option(None, "--trust-network/--no-trust-network", help="let computers on this network connect without the key (saved; off unless you turn it on). Without it, other computers send the key shown by `vt key`")) -> None:
    """Run Video Tool: the Studio, the pipeline and the engines on one port. A computer on this network connects by typing the address printed below; no code is needed.

    Engines already installed on this computer are used as they are (nothing of them is started, stopped or changed); our own copies use their own ports and folders.
    """
    from .engines import placement

    if gpus.strip():
        from . import gpuassign

        try:
            gpuassign.change({"allowed": _spec(gpus)}, background=False)
        except ValueError as e:
            raise typer.BadParameter(str(e))
    _fence()
    if comfy == "auto" and not comfy_url:
        comfy_url = _first_run_comfy()
    console.print("Engines:")
    placed = placement.place({"ollama": ollama, "comfy": comfy}, {"ollama": ollama_url, "comfy": comfy_url}, console.print)
    for p in placed.values():
        where = ", ".join(p.urls()) or "-"
        console.print(f"  {p.engine:11} {p.source:8} {where}  [dim]{p.note}[/dim]")
    again = ["server", "--host", host] + (["--name", name] if name else [])        # how to start this same server by itself later
    for e, p in placed.items():
        again += [f"--{e}", p.source] + ([f"--{e}-url", ",".join(p.urls())] if p.source == "existing" else [])
    _serve(host, port, name, {e: p.url for e, p in placed.items() if p.source != "off"}, open_ui, again, start_at_login, trust_network)


_fenced = False


def _fence() -> None:
    """The first thing `vt server` and `vt studio` do: fence this program, and everything it starts, to the graphics cards the person allowed (Server page, `vt gpu allow`)."""
    global _fenced
    if _fenced:
        return
    _fenced = True
    from . import gpuassign

    if not gpuassign.apply() and not gpuassign.blocked():
        return                                                              # no NVIDIA card here, or nothing to go by: nothing to say
    d = gpuassign.describe()
    console.print("Graphics cards Video Tool may use: " + (", ".join(f"{c['index']} {c['name']}" for c in d["cards"] if c["allowed"]) or "none (the processor does the work)"))
    if d["needs_choice"]:
        console.print("  [yellow]Nobody has chosen yet, so it uses this one card only. Choose on the Server page, or with: vt gpu allow <cards|all|none>[/yellow]")


def _free_port(port: Optional[int], host: str) -> int:
    import socket

    def free(n: int) -> bool:
        with socket.socket() as s:
            return s.connect_ex(("127.0.0.1", n)) != 0

    if port:
        if not free(port):
            console.print(f"[red]Port {port} is already in use on this computer.[/red] Choose another with --port.")
            raise typer.Exit(1)
        return port
    for n in range(8765, 8800):
        if free(n):
            if n != 8765:
                console.print(f"[yellow]Port 8765 is in use by another program; using {n}.[/yellow]")
            return n
    raise typer.Exit(1)


def _serve(host: str, port: Optional[int], name: str, services: dict[str, str], open_ui: bool, again: Optional[list[str]] = None,
           start_at_login: bool = False, trust_network: Optional[bool] = None) -> None:
    import socket
    import threading
    import webbrowser

    import uvicorn

    _fence()
    from .engines import hub
    from .server import serve
    from .server.app import app as studio_app

    port = _free_port(port, host)
    exposed = host not in serve.LOOPBACK
    ident = hub.identity()
    if trust_network is not None:
        serve.set_trust_network(trust_network)                       # saved, so the next start keeps it
    serve.configure(key=ident["key"], name=name or ident.get("name", "") or socket.gethostname() or "Video Tool", services=services, exposed=exposed,
                    argv=again + ["--port", str(port)] if again else None, trust_network=serve.saved_trust_network())
    serve.STATE["port"] = port                                       # for addresses handed to assistants on other computers (prepare_upload)
    if start_at_login:
        for line in serve.autostart(True)["done"]:
            console.print(f"  start by itself: {line}")
    console.print(f"\n[bold]Video Tool server[/bold] on port {port}.")
    if exposed:
        for a in hub.address_hints(port):
            console.print(f"  Address: {a}")
        if serve.STATE["trust_network"]:
            console.print("  Other computers on this network connect with one of these addresses. No key is needed ([yellow]trust for this network is on[/yellow]).")
        else:
            console.print("  Other computers connect with one of these addresses and this server's key: `vt key` prints it, and the server window copies it.")
    else:
        console.print(f"  This computer only: http://127.0.0.1:{port}")
    announcer = None
    if exposed:
        from .server.discovery import Announcer

        announcer = Announcer(port).start()
        for p in announcer.problems:
            console.print(f"  [yellow]Other computers may not find this server by themselves ({p}); typing the address still works.[/yellow]")
    if open_ui:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    import logging

    from .server.serve import QuietPolling

    logging.getLogger("uvicorn.access").addFilter(QuietPolling())       # the status checks every window makes every few seconds would bury everything else in the log
    try:
        uvicorn.run(studio_app, host=host, port=port, log_level="info")
    finally:
        if announcer is not None:
            announcer.stop()


@app.command()
def assistants(action: str = typer.Argument("list", help="list, connect or disconnect"),
               which: str = typer.Argument("", help="claude-code, codex or claude-desktop (connect/disconnect; empty = every installed one)")) -> None:
    """Connect Claude Code, Codex or Claude Desktop to Video Tool (the same as Settings, AI assistants)."""
    from . import assistants as A

    if action == "list":
        for s in A.status():
            console.print(f"  {s['label']:15} {'installed' if s['installed'] else 'not found':10} {'connected (' + s['to'] + ')' if s['connected'] else 'not connected'}")
        return
    ids = [which] if which else [s["id"] for s in A.status() if s["installed"]]
    for aid in ids:
        try:
            console.print(f"  {A.LABELS.get(aid, aid)}: {getattr(A, action)(aid)['note']}")
        except (RuntimeError, ValueError, AttributeError) as e:
            console.print(f"  [red]{aid}: {e}[/red]")


@app.command()
def craft(action: str = typer.Argument("rules", help="rules or check"), project: str = typer.Argument("", help="the project id (check)"),
          area: str = typer.Option("", help="hook, sync, pacing, captions, motion, ending, sound, facts")) -> None:
    """The craft rules for high-retention videos, or what a project's plan breaks (the same as the Review page's checklist)."""
    from . import craft as C

    if action == "rules":
        for r in C.rules(area):
            console.print(f"[bold]{r['id']}[/bold] {'(measured)' if r['measured'] else ''}\n  {r['rule']}\n  [dim]{r['why']} - {r['source']}[/dim]")
        return
    from .project import Project

    rep = C.check(Project(project))
    console.print(f"Quality score: [bold]{rep['score']}[/bold]")
    for v in rep["violations"]:
        console.print(f"  {v['severity']:8} {v['t0']:6.1f}s {v['rule']}: {v['says']} -> {v['fix']}")


@app.command()
def styles(slug: str = typer.Argument("", help="a style to show in full"), use: str = typer.Option("", help="filter by what the video is for")) -> None:
    """The 66 film styles (set a project's theme to style-<slug>)."""
    from . import styles as S

    if slug:
        console.print(S.brief(slug, keep=8) or f"No style called {slug}.")
        return
    for s in S.listing(use=use):
        console.print(f"  [bold]{s['slug']:24}[/bold] {s['category']:22} {s['summary'][:90]}")


@app.command()
def key() -> None:
    """Print this computer's server key: another computer sends it to connect (unless trust for the network is on: `vt server --trust-network`)."""
    from .engines import hub

    print(hub.identity()["key"])


@app.command()
def servers(timeout: float = 2.0, as_json: bool = typer.Option(False, "--json")) -> None:
    """List the Video Tool servers on this network."""
    from .server.discovery import find

    found = find(timeout)
    if as_json:
        print(json.dumps(found, indent=2))
        return
    if not found:
        console.print("No Video Tool server answered. If one runs, type its address in the Studio (it is printed where the server started).")
    for s in found:
        console.print(f"  {s['name']}  {s['url']}")


@app.command()
def studio(host: str = "127.0.0.1", port: int = 8765, no_open: bool = typer.Option(False, "--no-open")) -> None:
    """Start the Studio web app on this computer (`vt server` on 127.0.0.1; the engines stay as set on the Engines page)."""
    _serve(host, port, "", {}, not no_open)


@app.command("serve-engine")
def serve_engine(host: str = "0.0.0.0", port: int = 8790, name: str = typer.Option("", help="a name for this computer, shown to the one that pairs")) -> None:
    """Offer this computer's voices and speech recognition to another computer running Video Tool. Prints a one-time pairing code."""
    import uvicorn

    from .engines.server import create_app, new_secrets

    key, code = new_secrets()
    console.print(f"[bold]Engine server[/bold] on port {port}. On the other computer: Settings, Engines, Another Video Tool computer.")
    console.print(f"Address: http://<address of this computer>:{port}")
    console.print(f"Pairing code (works once): [bold]{code}[/bold]")
    uvicorn.run(create_app(key=key, pairing_code=code, name=name or "Video Tool engine"), host=host, port=port, log_level="warning")


def _engine_list(engines: str) -> list[str]:
    out = [e.strip() for e in engines.split(",") if e.strip()]
    bad = [e for e in out if e not in ("ollama", "comfy")]
    if bad:
        raise typer.BadParameter(f"unknown engine(s): {', '.join(bad)} (choose from ollama, comfy)")
    return out


@engine_app.command("plan")
def engine_plan(engines: str = typer.Option("ollama,comfy", help="comma-separated: ollama, comfy"),
                bundles: str = typer.Option("pictures", help="comfy model sets: pictures, clips"), models: str = typer.Option("", help="folder for the big model files"),
                json_out: bool = typer.Option(False, "--json", help="machine-readable")) -> None:
    """Show what `vt engine setup` would download. Touches nothing."""
    from .engines import hardware, hub

    plans = hub.plan(_engine_list(engines), [b for b in bundles.split(",") if b], models)
    if json_out:
        print(hub.dump({"hardware": hardware.detect(), "plans": plans}))
        return
    console.print(f"[bold]This computer:[/bold] {hardware.detect()['summary']}")
    for p in plans:
        console.print(f"\n[bold]{p['engine']}[/bold]  {p['total_gb']} GB")
        for it in p["items"]:
            console.print(f"  {'[green]have[/green]' if it['done'] else '[yellow]need[/yellow]'}  {it['name']}  {it['size_gb']} GB")
        for pr in p["problems"]:
            console.print(f"  [red]{pr}[/red]")


@engine_app.command("setup")
def engine_setup(engines: str = typer.Option("ollama,comfy", help="comma-separated: ollama, comfy"), bundles: str = typer.Option("pictures", help="comfy model sets: pictures, clips"),
                 models: str = typer.Option("", help="folder for the big model files"), yes: bool = typer.Option(False, "--yes", help="do it (without this, only show the plan)")) -> None:
    """Download and set up Ollama, ComfyUI and their models on THIS computer. Resumable: run it again after any interruption."""
    from .engines import hub

    want = _engine_list(engines)
    bl = [b for b in bundles.split(",") if b]
    engine_plan(engines, bundles, models, False)
    if not yes:
        console.print("\n[yellow]nothing was changed[/yellow]: add --yes to download and install")
        raise typer.Exit(0)
    last = {"line": ""}

    def progress(name: str, frac: float, msg: str = "") -> None:
        line = f"{name:11} {int(frac * 100):3d}%  {msg}"
        if line != last["line"]:
            last["line"] = line
            console.print(line)

    res = hub.setup(want, bl, progress, models)
    for e, r in res.items():
        console.print(f"{'[green]ok[/green]' if r['ok'] else '[red]FAILED[/red]'}  {e}: {r['note']}")
    raise typer.Exit(0 if all(r["ok"] for r in res.values()) else 1)


@engine_app.command("run")
def engine_run(host: str = "0.0.0.0", port: int = 8790, name: str = typer.Option("", help="a name for this computer, shown to the one that pairs"),
               engines: str = typer.Option("ollama,comfy", help="services to start and offer; use '' to offer only voices"),
               start: bool = typer.Option(True, "--start/--no-start", help="start the installed services first")) -> None:
    """Start the services, then offer them to other computers. Prints the address and a one-time pairing code; stays running."""
    import uvicorn

    _fence()                                                                # the services it starts keep to the graphics cards the person allowed
    from .engines import hub
    from .engines.server import create_app

    want = _engine_list(engines) if engines else []
    if start and want:
        console.print("Starting services:")
        hub.start_services(want, console.print)
    ident = hub.identity()
    code = hub.new_code()
    console.print(f"\n[bold]Video Tool Engine[/bold] on port {port}. On the other computer: Settings, Engines, Another Video Tool computer.")
    for a in hub.address_hints(port):
        console.print(f"  Address: {a}")
    console.print(f"  Pairing code (works once): [bold]{code}[/bold]    (another one: `vt engine pair`)")
    uvicorn.run(create_app(key=ident["key"], pairing_code=code, name=name or ident.get("name", "") or "Video Tool engine", services=hub.service_urls(want)), host=host, port=port, log_level="warning")


@engine_app.command("pair")
def engine_pair(port: int = 8790) -> None:
    """Print a new pairing code for another computer (asks the running engine on this computer)."""
    import httpx

    try:
        r = httpx.post(f"http://127.0.0.1:{port}/v1/admin/new-code", timeout=5)
        r.raise_for_status()
    except Exception as e:                                                               # noqa: BLE001
        console.print(f"[red]The engine is not running on port {port}[/red] ({type(e).__name__}). Start it with `vt engine run`.")
        raise typer.Exit(1)
    console.print(f"Pairing code (works once): [bold]{r.json()['code']}[/bold]")


@engine_app.command("status")
def engine_status() -> None:
    """Which services answer on this computer."""
    from .engines import hub

    st = hub.status()
    for n, v in st["services"].items():
        console.print(f"{'[green]up[/green]  ' if v['up'] else '[red]down[/red]'}  {n}  {v['url']}")
    console.print(f"data: {st['data']}")


@engine_app.command("find")
def engine_find(host: str = typer.Argument("127.0.0.1", help="this computer, or another one's address (192.168.1.20, or host:port)"),
                deep: bool = typer.Option(False, "--deep", help="try every port from 1024, not only the usual ones (about half a minute)")) -> None:
    """Every ComfyUI and Ollama at an address: the card each runs on and the picture set that fits it. Touches nothing."""
    from .engines import discover

    found = discover.scan(host, deep=deep)
    console.print(f"[bold]{found['host']}[/bold]  {len(found['instances'])} found ({found['ports_tried']} ports tried)")
    for i, inst in enumerate(found["instances"], 1):
        if inst["engine"] == "comfy":
            f = inst["fit"]
            pub = f"  [yellow]published at {inst['public']}[/yellow]" if inst.get("public") else ""
            console.print(f"  {i}. ComfyUI {inst['version']}  {inst['url']}  {inst['gpu'] or 'no card'} {inst['size_gb']} GB, RAM {inst['ram_gb']:.0f} GB{pub}")
            console.print(f"     pictures: {f['label'] or 'none'}  [dim]{f['why']}[/dim]")
            for w in f["warnings"]:
                console.print(f"     [yellow]{w}[/yellow]")
        else:
            console.print(f"  {i}. Ollama {inst['version']}  {inst['url']}  models: {', '.join(inst['models'][:6]) or 'none yet'}")
    if not any(i["engine"] == "comfy" for i in found["instances"]):
        console.print("No ComfyUI found. `vt engine setup --engines comfy` installs our own (its own folder and port).")


@engine_app.command("use")
def engine_use(url: str = typer.Argument(..., help="the ComfyUI to make pictures with, e.g. http://127.0.0.1:8188"),
               recipe: str = typer.Option("", help="a picture set (zimage-full, zimage-fp8, zimage-fp8-small-text, zimage-nvfp4); default: the one that fits its card"),
               yes: bool = typer.Option(False, "--yes", help="download without asking")) -> None:
    """Make that ComfyUI ready: download the picture set that fits its card into its own model folders, check the workflow, and use it."""
    from .engines import prepare

    try:
        p = prepare.plan(url, recipe)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"{p['url']}  {p['instance']['gpu']} {p['instance']['vram_gb']:.0f} GB  ->  [bold]{p['label']}[/bold]")
    for x in p["files"]:
        console.print(f"  {'have' if x['have'] else 'get '}  {x['file']:42} {x['gb']:5.1f} GB  [dim]{x['to'] if not x['have'] else ''}[/dim]")
    for m in p["problems"]:
        console.print(f"[red]{m}[/red]")
    if p["problems"]:
        raise typer.Exit(1)
    if p["download_gb"] and not yes and not typer.confirm(f"Download {p['download_gb']} GB?", default=True):
        raise typer.Exit(0)
    last = [-1]

    def say(f: float, m: str) -> None:
        if int(f * 20) != last[0]:
            last[0] = int(f * 20)
            console.print(f"  {int(f * 100):3d}%  {m}")
    try:
        prepare.prepare(url, recipe, say)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Ready.[/green] Pictures are drawn on {p['url']} with {p['label']}.")


def _first_run_comfy() -> str:
    """The first `vt server` on a computer, asked in the terminal: use a ComfyUI already running here (which one), or install our own. Returns its URL, or ""."""
    from . import paths
    from .engines import discover, prepare
    from .util import read_json

    if (read_json(paths.SETTINGS, {}) or {}).get("picture_recipe") or not sys.stdin.isatty():
        return ""
    comfy = [i for i in discover.scan("127.0.0.1")["instances"] if i["engine"] == "comfy"]
    if not comfy:
        console.print("No ComfyUI runs on this computer. Install Video Tool's own (its own folder and port): `vt engine setup --engines comfy`, or on the Engines page.")
        return ""
    console.print("ComfyUI already runs here:")
    for n, inst in enumerate(comfy, 1):
        pub = f", published at {inst['public']}" if inst.get("public") else ""
        console.print(f"  {n}. {inst['url']}  {inst['gpu']} {inst['size_gb']} GB{pub}  ->  {inst['fit']['label'] or 'no picture set fits'}")
    pick = typer.prompt(f"Use which one for pictures? (1-{len(comfy)}, or 0 to install our own instead)", default="1")
    if not pick.isdigit() or not 1 <= int(pick) <= len(comfy):
        return ""
    url = comfy[int(pick) - 1]["url"]
    plan = prepare.plan(url)
    if plan["download_gb"] and not typer.confirm(f"It needs {plan['download_gb']} GB of models, put in its own model folders. Download now?", default=True):
        prepare.use(url, plan["recipe"])
        return url
    prepare.prepare(url, progress=lambda f, m: console.print(f"  {int(f * 100):3d}%  {m}") if int(f * 100) % 10 == 0 else None)
    return url


@engine_app.command("service")
def engine_service(install: bool = typer.Option(False, "--install", help="do it (without this, only show what would be written)"), remove: bool = typer.Option(False, "--remove"),
                   port: int = 8790, name: str = "") -> None:
    """Start the engine automatically: a scheduled task (Windows), a user service (Linux) or a launch agent (macOS)."""
    from .engines import hub

    spec = hub.service_files(port=port, name=name)
    if remove:
        for cmd in spec.get("remove", []):
            import subprocess

            subprocess.run(cmd, check=False)
        console.print("removed")
        return
    for path, text in spec["files"].items():
        console.print(f"[bold]{path}[/bold]\n{text}")
    for cmd in spec["commands"]:
        console.print("  $ " + " ".join(cmd))
    console.print(spec["note"])
    if not install:
        console.print("[yellow]nothing was changed[/yellow]: add --install to do it")
        return
    for line in hub.apply_service(spec):
        console.print("  " + line)


@app.command()
def migrate(source: Path = typer.Option(..., "--from", help="the old folder (a developer checkout) holding projects/, voices/, models/, settings.json"),
            yes: bool = typer.Option(False, "--yes", help="do it (without this, only show what would be copied)"),
            no_models: bool = typer.Option(False, "--no-models", help="leave the downloaded models behind (they are fetched again when needed)")) -> None:
    """Copy your data from an old folder into the data folder this app uses (VT_DATA). Nothing is deleted or overwritten; models are hard-linked."""
    from . import migrate as MG, paths

    if not source.is_dir():
        raise typer.BadParameter(f"{source} is not a folder")
    try:
        rep = MG.plan(source, paths.DATA, models=not no_models)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    console.print(MG.describe(rep))
    if not rep.items:
        console.print("nothing to copy")
        return
    if not yes:
        console.print("[yellow]dry run[/yellow]: add --yes to copy")
        return
    rep = MG.run(source, paths.DATA, models=not no_models)
    console.print(MG.describe(rep))
    for e in rep.errors[:10]:
        console.print(f"[red]{e}[/red]")
    raise typer.Exit(1 if rep.errors else 0)


@app.command()
def themes() -> None:
    """List themes."""
    for t in list_themes():
        console.print(f"{t.name}  ({t.label})  accent {t.color.accent}  caption {t.caption.style}")


@app.command()
def music() -> None:
    """List bundled music tracks."""
    from .util import read_json

    for m in read_json(paths.MUSIC / "index.json", []):
        console.print(f"{m['id']:<14} {m['mood']:<10} {m['bpm']} bpm  {m['title']}")


@app.command()
def demo(project_id: str = "reference") -> None:
    """Build the reference-frame fixture project (no speech recognition needed)."""
    where = next((d for d in (paths.ROOT / "samples", paths.ROOT.parent / "samples") if (d / "build_reference.py").exists()), None)
    if where is None:                                     # an installed server has no samples folder: the demo is a developer's fixture
        console.print("The demo needs the samples folder of a source checkout (samples/build_reference.py); this installation has none.")
        raise typer.Exit(1)
    sys.path.insert(0, str(where))
    import build_reference  # type: ignore

    build_reference.main(project_id)
    from .pipeline import compose_all

    compose_all(Project(project_id))
    console.print(f"Built project '{project_id}'. Render it: vt render {project_id} --aspect both")


@models_app.command("list")
def models_list() -> None:
    from .stages import asr

    t = Table("model", "installed", "note")
    for m in asr.list_models():
        t.add_row(m["key"], "yes" if m["installed"] else "no", m["note"])
    console.print(t)


@models_app.command("pull")
def models_pull(key: str) -> None:
    """Download (and convert) a model, e.g. `vt models pull bn-medium`."""
    from .stages import asr

    _progress_runner(lambda cb: asr.ensure_model(key, cb))
    console.print(f"[green]{key} ready[/green] at {asr.model_dir(key)}")


def _bar(percent, width=22):
    p = 0 if percent is None else max(0.0, min(100.0, float(percent)))
    n = round(p / 100 * width)
    return "|" + "#" * n + "." * (width - n) + "|"


@app.command("system")
def system_cmd(watch: bool = typer.Option(False, "--watch", "-w", help="keep refreshing every 2 seconds (Ctrl+C stops)"),
               as_json: bool = typer.Option(False, "--json", help="print the raw numbers")) -> None:
    """How busy this computer is: processor, memory, disk, every graphics card, and which one Video Tool is using. Same numbers as the Studio's System panel."""
    import time

    from . import sysstats

    while True:
        s = sysstats.snapshot()
        if as_json:
            console.print_json(json.dumps(s))
        else:
            if watch:
                console.clear()
            c, m, d = s["cpu"], s["memory"], s["disk"]
            console.print(f"[bold]{s['host']['name']}[/bold]  {s['host']['os']}")
            console.print(f"  Processor  {_bar(c['percent'])} {c['percent']}%   {c['model']}, {c['cores']} threads   (Video Tool: {c['video_tool_percent']}%)")
            console.print(f"  Memory     {_bar(m['percent'])} {m['used_gb']} of {m['total_gb']} GB   (Video Tool: {m['video_tool_gb']} GB)")
            console.print(f"  Disk       {_bar(d['percent'])} {d['free_gb']} GB free of {d['total_gb']} GB   {d['path']}")
            for g in s["gpus"]:
                use = "Video Tool can use it" if g["usable_by_video_tool"] else "kept free for other programs"
                console.print(f"  GPU {g['index']}     {_bar(g['percent'])} {g['percent']}%   memory {g['memory_used_gb']}/{g['memory_total_gb']} GB   {g['temperature_c']} C   {g['name']}   [dim]{use}[/dim]")
                for p in g["programs"]:
                    console.print(f"            {p['label']}  {p['gb']} GB{'  (Video Tool)' if p['ours'] else ''}")
            e = s["engines"]
            if "comfy" in e:
                console.print(f"  ComfyUI    {'draws on ' + ', '.join(x['name'] or '?' for x in e['comfy'].get('gpus', [])) if e['comfy'].get('ok') else 'not answering'}")
            if "ollama" in e:
                loaded = ", ".join(f"{x['model']} ({x['gb_on_card']} GB on the card)" for x in e["ollama"].get("loaded", [])) if e["ollama"].get("ok") else "not answering"
                console.print(f"  Ollama     {loaded or 'nothing loaded'}")
        if not watch:
            return
        try:
            time.sleep(2)
        except KeyboardInterrupt:
            return


gpu_app = typer.Typer(help="Which graphics card each of Video Tool's own jobs uses (rendering, speech recognition).")
app.add_typer(gpu_app, name="gpu")


@gpu_app.callback(invoke_without_command=True)
def gpu_show(ctx: typer.Context) -> None:
    """Show the cards and the card each job uses now. Change with: vt gpu set render 1"""
    if ctx.invoked_subcommand:
        return
    from . import gpuassign

    d = gpuassign.describe()
    for c in d["cards"]:
        busy = ", ".join(f"{p['label']} {p['gb']} GB" for p in c["using"] if not p["ours"])
        console.print(f"  {c['index']}  {c['name']}   {c['free_gb']} of {c['total_gb']} GB free, {c['load']:.0f}% load   {'[green]Video Tool may use it[/green]' if c['allowed'] else '[dim](Video Tool does not use it)[/dim]'}" + (f"   [dim]in use by {busy}[/dim]" if busy else ""))
    if d["needs_choice"]:
        console.print("  [yellow]Nobody has chosen which cards Video Tool may use, so it uses one card only. Choose with: vt gpu allow 1   (or: vt gpu allow all)[/yellow]")
    console.print(f"  Chosen: primary = {d['saved']['primary']}, rendering = {d['saved']['render']}, speech recognition = {d['saved']['speech']}")
    for j, label in (("render", "Rendering"), ("speech", "Speech recognition")):
        v = d["jobs"][j]
        console.print(f"  {label:20} uses GPU {v['index']} {v['name']}   [dim]{v['why']}[/dim]")
    for e in d["engines"]:
        console.print(f"  [{'yellow' if e['offer_own'] else 'dim'}]{e['message']}[/]" + (f"  [bold]Use Video Tool's own copy: vt gpu own {e['id']}[/bold]" if e["offer_own"] and e["own_installed"] else ""))


@gpu_app.command("allow")
def gpu_allow(cards: list[str] = typer.Argument(..., help="the cards Video Tool may use (index, name or uuid), or 'all', or 'none'")) -> None:
    """Choose the cards Video Tool may use, for example: vt gpu allow 1   or   vt gpu allow 0 1   or   vt gpu allow none (the processor does the work). Nothing else is ever used."""
    from . import gpuassign

    try:
        moved = gpuassign.change({"allowed": [] if [x.lower() for x in cards] == ["none"] else cards}, background=False)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    d = gpuassign.describe()
    console.print("Video Tool may use: " + (", ".join(f"{c['index']} {c['name']}" for c in d["cards"] if c["allowed"]) or "no card (the processor)") + ". A running server needs a restart to apply this to programs it has already started.")
    for e in moved:
        console.print(f"  Video Tool's own {e} was restarted on its new card.")


def _spec(text: str) -> list[str] | str:
    """What a person typed for the cards: 'none' is the empty list, anything else goes to gpuassign as it is ('all', or numbers, names and uuids separated by commas or spaces)."""
    return [] if text.strip().lower() == "none" else text


@gpu_app.command("setup")
def gpu_setup(gpus: str = typer.Option("", "--gpus", help="the cards Video Tool may use: numbers separated by commas, all, or none"),
              ask: Optional[bool] = typer.Option(None, "--ask/--no-ask", help="ask in this terminal when there are two or more cards and nobody has chosen (default: only when there is a terminal)")) -> None:
    """The setup question for a terminal (used by the install scripts and Docker): with two or more graphics cards, which may Video Tool use? A flag answers it; otherwise it
    asks when a person is there, and when nobody is it keeps the safe default (one card only) and says how to change it. With one card it only says which it uses."""
    from . import gpuassign

    try:
        if gpus.strip():
            gpuassign.change({"allowed": _spec(gpus)}, background=False)
        elif gpuassign.needs_choice() and (sys.stdin.isatty() if ask is None else ask):
            d = gpuassign.describe()
            console.print("This computer has more than one graphics card:")
            for c in d["cards"]:
                busy = ", ".join(f"{p['label']} {p['gb']} GB" for p in c["using"] if not p["ours"])
                console.print(f"  {c['index']}  {c['name']}   {c['free_gb']} of {c['total_gb']} GB free" + (f"   in use by {busy}" if busy else ""))
            answer = typer.prompt("Which may Video Tool use? Numbers separated by commas, 'all', or 'none'. Press Enter for one card only", default="", show_default=False)
            if answer.strip():
                gpuassign.change({"allowed": _spec(answer)}, background=False)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    d = gpuassign.describe()
    if not d["cards"]:
        console.print("No NVIDIA graphics card here: the processor does everything.")
        return
    console.print("Video Tool may use: " + (", ".join(f"{c['index']} {c['name']}" for c in d["cards"] if c["allowed"]) or "no card (the processor does everything)") + ".")
    if d["needs_choice"]:
        console.print("  Nobody has chosen, so it uses this one card only. To choose: vt gpu allow <cards|all|none>, or on the Server page.")


@gpu_app.command("own")
def gpu_own(engine: str = typer.Argument(..., help="ollama or comfy")) -> None:
    """Use Video Tool's own copy of Ollama or ComfyUI instead of the one that was already running (that one is left exactly as it is). It starts on the card chosen for it."""
    from .engines import where

    try:
        got = where.use_own(engine, say=console.print)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    console.print(f"{engine}: {got['source']} at {got['url']}  [dim]{got['note']}[/dim]")


@gpu_app.command("set")
def gpu_set(job: str = typer.Argument(..., help="primary, render or speech"), card: str = typer.Argument(..., help="a card (index, name or uuid); 'auto' for primary, 'primary' for a job")) -> None:
    """Choose the card for a job, for example: vt gpu set render 1   or   vt gpu set primary auto"""
    from . import gpuassign

    try:
        moved = gpuassign.change({job: card}, background=False)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    console.print(f"{job} -> {card}")
    for e in moved:
        console.print(f"  Video Tool's own {e} was restarted on its new card.")


@app.command()
def doctor() -> None:
    """Check that everything needed is installed."""
    from .doctor import run_checks

    rows = run_checks()
    t = Table("check", "", "detail", "fix")
    for r in rows:
        t.add_row(r["name"], "[green]ok[/green]" if r["ok"] else "[red]missing[/red]", r["detail"], r["fix"])
    console.print(t)
    if not all(r["ok"] for r in rows if r["name"] not in ("FFmpeg NVENC", "CUDA (CTranslate2)", "Studio build")):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()


catalog_app = typer.Typer(help="The free media catalogue: licences, sources and a validation status for every file.")
app.add_typer(catalog_app, name="catalog")


@catalog_app.command("list")
def catalog_list(kind: str = typer.Option("", help="video | audio | image")) -> None:
    from .director import catalog as CT

    es = [e for e in CT.load() if not kind or e["kind"] == kind]
    for e in es:
        console.print(f"{'ok ' if e.get('status') == 'ok' else 'BAD'} {e['kind']:5} {e.get('role', ''):7} {e['id']:48} {e.get('licence', '')[:22]:22} {e['title'][:40]}")
    console.print(CT.summary(es))


@catalog_app.command("validate")
def catalog_validate(only_failed: bool = typer.Option(False, help="re-check only the entries that failed")) -> None:
    """Download and decode every entry again; links that went bad are marked failed."""
    from .director import catalog as CT

    es = CT.refresh(lambda m: console.print(m), discover=False, only_failed=only_failed)
    console.print(CT.summary(es))


@catalog_app.command("refresh")
def catalog_refresh() -> None:
    """Search the Internet Archive and Wikimedia Commons for more free media, then validate everything."""
    from .director import catalog as CT

    es = CT.refresh(lambda m: console.print(m), discover=True)
    console.print(CT.summary(es))
