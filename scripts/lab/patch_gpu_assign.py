"""Wire GPU assignment (vt/gpuassign.py) into render, speech recognition, the stats snapshot, the API, `vt gpu` and MCP."""
from pathlib import Path

R = Path(__file__).resolve().parents[2] / "server"


def sub(path, old, new):
    p = R / path
    s = p.read_text(encoding="utf-8")
    assert old in s, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


# ---- render: the chosen card is tried first (the rest stay as fallbacks)
sub("vt/render/browser_gpu.py", "        devices.sort(key=lambda device:device[3],reverse=True)\n",
    "        devices.sort(key=lambda device:device[3],reverse=True)\n"
    "        try:                                                    # the card the person chose for rendering goes first; the others remain fallbacks\n"
    "            from .. import gpuassign\n"
    "            chosen,_why=gpuassign.resolve('render')\n"
    "            if chosen:devices.sort(key=lambda device:device[2]!=chosen['uuid'])\n"
    "        except Exception:pass\n")

# ---- speech recognition: open the model on the chosen card
sub("vt/stages/asr.py", '''        wm = WhisperModel(str(path), device="cuda" if use_cuda else "cpu", compute_type="float16" if use_cuda else "int8")''',
    '''        from .. import gpuassign

        index = gpuassign.cuda_index("speech") if use_cuda else 0                # the card chosen for speech recognition (Server page, `vt gpu`)
        wm = WhisperModel(str(path), device="cuda" if use_cuda else "cpu", device_index=index, compute_type="float16" if use_cuda else "int8")
        if use_cuda:
            progress("asr", 0.03, f"speech recognition runs on GPU {index}")''')

# ---- the snapshot: every program on each card with its own load (graphics programs too), and when it was read
S = "vt/sysstats.py"
sub(S, '''def _gpus() -> list[dict[str, Any]]:''', '''def _pmon() -> Optional[dict[int, list[dict[str, Any]]]]:
    """Per-program load on each card: `nvidia-smi pmon` lists graphics programs (the render browser) as well as compute ones, each with its own load.
    None where the driver cannot report it (Windows display cards); the compute list is used then."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "pmon", "-c", "1", "-s", "um"], capture_output=True, text=True, timeout=6, creationflags=CREATE_NO_WINDOW).stdout
    except Exception:                                                   # noqa: BLE001
        return None
    rows: dict[int, list[dict[str, Any]]] = {}
    seen_header = False
    for line in out.splitlines():
        if line.startswith("# gpu"):
            seen_header = True
            continue
        if line.startswith("#") or not line.strip() or not seen_header:
            continue
        p = line.split()
        if len(p) < 12 or not p[0].isdigit() or not p[1].isdigit():
            continue
        name = " ".join(p[11:])
        fb = _num(p[9]) or 0.0
        sm = _num(p[3])
        if name in ("Xorg", "gnome-shell", "Xwayland") or (fb < 100 and not sm):
            continue
        rows.setdefault(int(p[0]), []).append({"pid": int(p[1]), "name": name, "type": p[2], "percent": sm, "gb": round(fb / 1024, 2)})
    return rows


def _gpus() -> list[dict[str, Any]]:''')
sub(S, '''    apps = _smi(["--query-compute-apps=gpu_uuid,pid,process_name,used_memory"])
    mine, visible = _descendants(os.getpid()), _visible()''', '''    apps = _smi(["--query-compute-apps=gpu_uuid,pid,process_name,used_memory"])
    pm = _pmon()
    mine, visible = _descendants(os.getpid()), _visible()''')
sub(S, '''        procs = []
        for a in apps:
            if len(a) >= 4 and a[0] == uuid:
                pid = int(a[1]) if a[1].isdigit() else 0''', '''        procs = []
        if pm is not None:
            for q in pm.get(int(idx), []):
                procs.append({"pid": q["pid"], "label": _label(q["name"], _cmdline(q["pid"]), q["pid"] in mine), "gb": q["gb"], "percent": q["percent"], "ours": q["pid"] in mine})
        for a in ([] if pm is not None else apps):
            if len(a) >= 4 and a[0] == uuid:
                pid = int(a[1]) if a[1].isdigit() else 0''')
sub(S, '''    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),''', '''    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "updated_at": round(time.time(), 1),''')

# ---- API
sub("vt/server/system_routes.py", '''@router.get("/stats")
def stats() -> dict:
    return sysstats.snapshot()
''', '''@router.get("/stats")
def stats() -> dict:
    return sysstats.snapshot()


class GpuBody(BaseModel):
    primary: Optional[str] = Field(default=None, max_length=80, description="'auto' or a card (uuid, index or name)")
    render: Optional[str] = Field(default=None, max_length=80, description="'primary' or a card")
    speech: Optional[str] = Field(default=None, max_length=80, description="'primary' or a card")


@router.get("/gpus")
def gpus() -> dict:
    """The cards, the saved choice, the card each of Video Tool's own jobs uses now and why, and where the separate programs (Ollama, ComfyUI) run."""
    return gpuassign.describe()


@router.put("/gpu")
def set_gpu(body: GpuBody) -> dict:
    try:
        gpuassign.save({k: v for k, v in body.model_dump().items() if v is not None})
    except ValueError as e:
        raise HTTPException(422, str(e))
    return gpuassign.describe()
''')
sub("vt/server/system_routes.py", "from fastapi import APIRouter\n\nfrom .. import sysstats\n",
    "from typing import Optional\n\nfrom fastapi import APIRouter, HTTPException\nfrom pydantic import BaseModel, Field\n\nfrom .. import gpuassign, sysstats\n")

# ---- CLI
sub("vt/cli.py", '''@app.command()
def doctor() -> None:''', '''gpu_app = typer.Typer(help="Which graphics card each of Video Tool's own jobs uses (rendering, speech recognition).")
app.add_typer(gpu_app, name="gpu")


@gpu_app.callback(invoke_without_command=True)
def gpu_show(ctx: typer.Context) -> None:
    """Show the cards and the card each job uses now. Change with: vt gpu set render 1"""
    if ctx.invoked_subcommand:
        return
    from . import gpuassign

    d = gpuassign.describe()
    for c in d["cards"]:
        console.print(f"  {c['index']}  {c['name']}   {c['free_gb']} of {c['total_gb']} GB free, {c['load']:.0f}% load   {'' if c['allowed'] else '[dim](kept out of reach by the server launcher)[/dim]'}")
    console.print(f"  Chosen: primary = {d['saved']['primary']}, rendering = {d['saved']['render']}, speech recognition = {d['saved']['speech']}")
    for j, label in (("render", "Rendering"), ("speech", "Speech recognition")):
        v = d["jobs"][j]
        console.print(f"  {label:20} uses GPU {v['index']} {v['name']}   [dim]{v['why']}[/dim]")
    for prog, where in d["separate_programs"].items():
        console.print(f"  {prog:20} runs on " + ", ".join(f"GPU {w['index']} {w['gpu']} ({w['gb']} GB)" for w in where) + "   [dim](set where it is installed)[/dim]")


@gpu_app.command("set")
def gpu_set(job: str = typer.Argument(..., help="primary, render or speech"), card: str = typer.Argument(..., help="a card (index, name or uuid); 'auto' for primary, 'primary' for a job")) -> None:
    """Choose the card for a job, for example: vt gpu set render 1   or   vt gpu set primary auto"""
    from . import gpuassign

    try:
        gpuassign.save({job: card})
    except ValueError as e:
        raise typer.BadParameter(str(e))
    console.print(f"{job} -> {card}")


@app.command()
def doctor() -> None:''')

# ---- MCP
sub("vt/mcp/server.py", '''@tool
def project_status(project: str) -> dict:''', '''@tool
def gpu_assignment(job: str = "", gpu: str = "") -> dict:
    """Which graphics card each of Video Tool's own jobs uses (rendering, speech recognition) and where the separate programs run. To change one, pass
    job (primary, render or speech) and gpu (a card index, name or uuid; 'auto' for primary, 'primary' for a job)."""
    from .. import gpuassign

    if job and gpu:
        gpuassign.save({job: gpu})
    return gpuassign.describe()


@tool
def project_status(project: str) -> dict:''')
print("ok")
