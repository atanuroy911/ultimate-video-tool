"""Calls the HyperFrames CLI (Node) to render a composition folder to a silent MP4.

Telemetry and cloud features are switched off through environment variables; everything runs locally.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable, Optional

from .. import paths
from ..util import find_tool, run

BIN = paths.RENDERER / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
_PROGRESS = re.compile(r"@hf-progress\s+(\{.*\})")
STALL_SECONDS = 300.0                     # no output from the renderer for this long: it is stuck, stop it and (for the GPU attempt) try the CPU


def use_product_binaries() -> dict[str, str]:
    """In the installed product the renderer must use the program's own ffmpeg, ffprobe and Chrome (in `bin/`), never whatever happens to be on the user's PC. Sets the variables
    HyperFrames reads (only when the product's copy exists; otherwise HyperFrames finds its own) and returns what it set."""
    from ..util import tool_dirs, find_tool

    got: dict[str, str] = {}
    for var, name in (("HYPERFRAMES_FFMPEG_PATH", "ffmpeg"), ("HYPERFRAMES_FFPROBE_PATH", "ffprobe")):
        for d in tool_dirs():
            f = d / (name + (".exe" if os.name == "nt" else ""))
            if f.is_file():
                got[var] = str(f)
                break
        if var not in got:
            try:
                got[var] = find_tool(name)
            except Exception:
                pass
    for d in tool_dirs():
        chrome = next(iter(sorted((d / "chrome").glob("**/chrome-headless-shell" + (".exe" if os.name == "nt" else "")))), None) if (d / "chrome").is_dir() else None
        if chrome:
            got["HYPERFRAMES_BROWSER_PATH"] = got["PRODUCER_HEADLESS_SHELL_PATH"] = str(chrome)
            break
    for k, v in got.items():
        os.environ[k] = v
    return got


use_product_binaries()


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["HYPERFRAMES_NO_TELEMETRY"] = "1"
    env["DO_NOT_TRACK"] = "1"
    return env


def hyperframes_cmd(*args: str) -> list[str]:
    if not BIN.exists():
        raise RuntimeError("HyperFrames is not installed. Run `npm install` inside the renderer/ folder.")
    return [find_tool("node"), str(BIN), *args]


def render_silent(comp_dir: Path, out: Path, *, fps: int = 30, quality: str = "looks", gpu: bool = True,
                  workers: str | int = "auto", on_progress: Optional[Callable[[float, str], None]] = None) -> Path:
    """Render comp_dir/index.html to out (H.264, no audio). Uses GPU encoder (NVENC) and hardware browser GPU when requested, falling back to CPU if needed."""
    out.parent.mkdir(parents=True, exist_ok=True)
    configured_workers=os.environ.get('VT_RENDER_WORKERS','')
    if workers=='auto' and configured_workers.isdigit() and 1<=int(configured_workers)<=16:
        workers=int(configured_workers)
    from .browser_gpu import nvidia_render_device,browser_environment
    device=nvidia_render_device() if gpu else None
    acceleration={'gpu_requested':gpu,'selected_device':device,'attempts':[],'warnings':[]}
    report=out.with_suffix('.acceleration.json')
    log=out.with_suffix('.render.log')
    def save_report():
        from ..util import write_json
        write_json(report,acceleration)

    def attempt(use_gpu: bool) -> None:
        args = ["render", str(comp_dir), "-o", str(out), "-f", str(fps), "-q", quality, "-w", str(workers), "--no-best-effort"]
        if (comp_dir/'data.json').exists():
            composition=json.loads((comp_dir/'data.json').read_text(encoding='utf-8'))
            if composition.get('screen_recording'):args.extend(['--video-frame-format','png'])
        extra_env: dict[str, str] = {
            "HYPERFRAMES_NO_TELEMETRY": "1",
            "DO_NOT_TRACK": "1",
        }
        if use_gpu:
            args.extend(["--gpu", "--browser-gpu"])
            extra_env["PRODUCER_BROWSER_GPU_MODE"] = "hardware"
            extra_env["PRODUCER_EXPERIMENTAL_FAST_CAPTURE"] = "true"
            extra_env["PRODUCER_ALLOW_SOFTWARE_FALLBACK"] = "true"
            extra_env.update(browser_environment(comp_dir/'.renderer',device))
            if on_progress:on_progress(0,'Using available graphics acceleration'+(' · '+device['name'] if device else ''))
        else:
            args.append("--no-browser-gpu")
            extra_env["PRODUCER_BROWSER_GPU_MODE"] = "software"

        def on_line(line: str) -> None:
            with log.open('a',encoding='utf-8') as stream:stream.write(line+'\n')
            if 'browserGpuMode probe' in line:
                acceleration['browser_probe']=line
                save_report()
            if any(marker in line for marker in ('UNVERIFIED','silently fall back','probe failed','probe → software')):
                acceleration['warnings'].append(line)
                save_report()
                if on_progress:on_progress(0,'Graphics acceleration needs attention. See the export acceleration report for the reason.')
            m = _PROGRESS.search(line)
            if m and on_progress:
                try:
                    d = json.loads(m.group(1))
                    on_progress(min(1.0, float(d.get("pct", 0)) / 100.0), str(d.get("code", "")))
                except (ValueError, TypeError):
                    pass

        old = {k: os.environ.get(k) for k in extra_env}
        os.environ.update(extra_env)
        try:
            acceleration['attempts'].append({'gpu_requested':use_gpu})
            save_report()
            run(hyperframes_cmd(*args), on_line=on_line, stall_seconds=STALL_SECONDS)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    try:
        attempt(gpu)
    except RuntimeError as e:
        if not gpu:
            raise
        import logging
        logging.getLogger(__name__).warning("GPU hardware render failed (%s); falling back to CPU software render", e)
        acceleration['warnings'].append('GPU render failed: '+str(e))
        save_report()
        if on_progress:on_progress(0,'GPU rendering failed; continuing on CPU. '+str(e).splitlines()[0][:180])
        if out.exists():
            out.unlink()
        attempt(False)
    if not out.exists():
        raise RuntimeError("render finished but no output file was produced")
    save_report()
    return out


def snapshot(comp_dir: Path, out_dir: Path, times: list[float], gpu: bool = True) -> list[Path]:
    """Capture PNG frames at the given times (seconds). Used by the Studio thumbnails and the MCP preview tool."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    args = ["snapshot", str(comp_dir), "--at", ",".join(f"{t:.3f}" for t in times), "-o", str(out_dir), "--describe", "false", "--no-end"]
    if gpu:
        args.append("--browser-gpu")
    old_env = {k: os.environ.get(k) for k in ("HYPERFRAMES_NO_TELEMETRY", "DO_NOT_TRACK", "PRODUCER_BROWSER_GPU_MODE")}
    os.environ.update({"HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1", "PRODUCER_BROWSER_GPU_MODE": "hardware" if gpu else "software"})
    try:
        run(hyperframes_cmd(*args))
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return sorted(out_dir.glob("frame-*.png"))
