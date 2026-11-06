"""Wire vt/sysstats.py into the API, the `vt system` command and the MCP tool."""
from pathlib import Path

R = Path(__file__).resolve().parents[2] / "server"


def sub(path, old, new):
    p = R / path
    s = p.read_text(encoding="utf-8")
    assert old in s, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


(R / "vt/server/system_routes.py").write_text('''"""The computer's live numbers for the Studio's System panel (vt/sysstats.py): processor, memory, disk, every graphics card and which one is in use."""
from fastapi import APIRouter

from .. import sysstats

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/stats")
def stats() -> dict:
    return sysstats.snapshot()
''', encoding="utf-8")

sub("vt/server/app.py", '''from .uploads import router as uploads_router  # chunked uploads that survive a dropped connection
app.include_router(uploads_router)''', '''from .uploads import router as uploads_router  # chunked uploads that survive a dropped connection
app.include_router(uploads_router)
from .system_routes import router as system_router  # live processor, memory and graphics-card numbers
app.include_router(system_router)''')

sub("vt/cli.py", '''@app.command()
def doctor() -> None:''', '''def _bar(percent, width=22):
    p = 0 if percent is None else max(0.0, min(100.0, float(percent)))
    n = round(p / 100 * width)
    return "[" + "#" * n + "." * (width - n) + "]"


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


@app.command()
def doctor() -> None:''')

sub("vt/mcp/server.py", '''@tool
def project_status(project: str) -> dict:''', '''@tool
def system_stats() -> dict:
    """Live numbers about the computer that does the work: processor, memory, disk, every graphics card (load, memory, temperature, which programs use it)
    and which of them Video Tool can use. Useful before starting a heavy job and when something is slow."""
    from .. import sysstats

    return sysstats.snapshot()


@tool
def project_status(project: str) -> dict:''')
print("ok")
