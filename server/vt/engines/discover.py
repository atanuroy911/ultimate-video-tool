"""Find every ComfyUI and Ollama a computer runs: on this computer or at an address, on any port, and the card each one uses.

    scan("127.0.0.1")              the usual ports, fast
    scan("192.168.1.20", deep=True) every port from 1024 up (about half a minute on a home network)

Each instance answers its own API (ComfyUI /system_stats, Ollama /api/version), so a ComfyUI on port 8443 is found as surely as one on 8188.
When the instance runs on the computer doing the scan, more is read from the system: the folder it runs from, the card it is pinned to
(CUDA_VISIBLE_DEVICES), the service that starts it, and whether a Cloudflare tunnel publishes it to the internet. A published one is marked,
so the person sees that someone else may be using it before choosing it.

Nothing found here is started, stopped or changed.
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

import httpx

from . import fit

COMFY_PORTS = [*range(8188, 8200), *range(8288, 8300), 8000, 8080, 8888, 7860, 3000, 5000]
OLLAMA_PORTS = [11434, *range(11435, 11440), *range(11444, 11450)]
LOCAL = ("127.0.0.1", "localhost", "::1", "0.0.0.0")


def is_local(host: str) -> bool:
    if host in LOCAL:
        return True
    try:
        mine = {i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None)}
        return host in mine
    except OSError:
        return False


def _open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def open_ports(host: str, ports: list[int], timeout: float = 0.35, workers: int = 256) -> list[int]:
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return [p for p, ok in zip(ports, ex.map(lambda p: _open(host, p, timeout), ports)) if ok]


def _get(url: str, timeout: float = 2.5) -> Optional[Any]:
    try:
        r = httpx.get(url, timeout=timeout)
        return r.json() if r.status_code == 200 else None
    except Exception:                                                   # noqa: BLE001
        return None


def probe_comfy(url: str) -> Optional[dict]:
    stats = _get(url + "/system_stats")
    if not isinstance(stats, dict) or "system" not in stats or "devices" not in stats:
        return None
    card = fit.card_from_stats(stats)
    folders = _get(url + "/internal/folder_paths") or {}
    queue = _get(url + "/queue") or {}
    cuda = [d for d in stats.get("devices", []) if str(d.get("type", "")).lower() == "cuda"]
    choice = fit.choose(card)
    return {"engine": "comfy", "url": url, "version": stats["system"].get("comfyui_version", ""), "python": stats["system"].get("python_version", "").split(" ")[0],
            "pytorch": stats["system"].get("pytorch_version", ""), "gpu": card.name or ("processor only" if not cuda else ""), "gpus": [fit.gpu_name(d.get("name", "")) for d in cuda],
            "vram_gb": card.vram_gb, "size_gb": card.size, "vram_free_gb": card.vram_free_gb, "ram_gb": card.ram_gb, "ram_free_gb": card.ram_free_gb, "compute": card.compute,
            "busy": bool(queue.get("queue_running") or queue.get("queue_pending")), "model_folders": {k: v for k, v in folders.items() if isinstance(v, list)},
            "argv": stats["system"].get("argv", []), "fit": choice.public()}


def probe_ollama(url: str) -> Optional[dict]:
    v = _get(url + "/api/version")
    if not isinstance(v, dict) or "version" not in v:
        return None
    try:                                                                # Open WebUI and others answer /api/version too; Ollama says so at /
        if "ollama is running" not in httpx.get(url + "/", timeout=2.5).text.lower():
            return None
    except Exception:                                                   # noqa: BLE001
        return None
    tags = _get(url + "/api/tags") or {}
    ps = _get(url + "/api/ps") or {}
    return {"engine": "ollama", "url": url, "version": v["version"], "models": [m.get("name") for m in tags.get("models", [])],
            "loaded": [{"model": m.get("name"), "vram_gb": round(m.get("size_vram", 0) / 1e9, 1)} for m in ps.get("models", [])]}


# ----------------------------------------------------------------------------- what only the computer itself can tell
def _listeners() -> dict[int, int]:
    """port -> pid of the process listening on it (Linux: ss; Windows: netstat). Empty when the tools are not there."""
    out: dict[int, int] = {}
    try:
        if os.name == "nt":
            txt = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=10).stdout
            for m in re.finditer(r"TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)", txt):
                out.setdefault(int(m.group(1)), int(m.group(2)))
        else:
            txt = subprocess.run(["ss", "-ltnpH"], capture_output=True, text=True, timeout=10).stdout
            for line in txt.splitlines():
                m = re.search(r":(\d+)\s.*pid=(\d+)", line)
                if m:
                    out.setdefault(int(m.group(1)), int(m.group(2)))
    except Exception:                                                   # noqa: BLE001
        pass
    return out


def _process(pid: int) -> dict:
    """Linux only: the command line, the folder main.py lives in, the pinned card, the systemd unit."""
    info: dict[str, Any] = {"pid": pid}
    proc = Path(f"/proc/{pid}")
    try:
        argv = (proc / "cmdline").read_bytes().split(b"\0")
        argv = [a.decode("utf-8", "replace") for a in argv if a]
        info["cmdline"] = " ".join(argv)[:400]
        main = next((a for a in argv if a.endswith("main.py")), "")
        if main:
            info["folder"] = str(Path(main if Path(main).is_absolute() else Path(os.readlink(proc / "cwd")) / main).parent)
    except OSError:
        pass
    try:
        env = dict(kv.split("=", 1) for kv in (proc / "environ").read_bytes().decode("utf-8", "replace").split("\0") if "=" in kv)
        if "CUDA_VISIBLE_DEVICES" in env:
            info["cuda_visible_devices"] = env["CUDA_VISIBLE_DEVICES"]
    except OSError:
        pass
    try:
        cg = (proc / "cgroup").read_text()
        m = re.search(r"/([\w@.\-]+\.service)", cg)
        if m:
            info["service"] = m.group(1)
    except OSError:
        pass
    return info


def tunnel_dirs() -> list[Path]:
    return [Path("/etc/cloudflared"), Path.home() / ".cloudflared", Path(os.environ.get("USERPROFILE", "")) / ".cloudflared"]


def tunnels() -> dict[int, str]:
    """port -> public hostname, for every Cloudflare tunnel ingress rule found on this computer (cloudflared's config.yml)."""
    out: dict[int, str] = {}
    for d in tunnel_dirs():
        try:
            files = list(d.glob("*.yml")) + list(d.glob("*.yaml"))
        except OSError:
            continue
        for f in files:
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            host = ""
            for line in txt.splitlines():
                m = re.search(r"hostname:\s*(\S+)", line)
                if m:
                    host = m.group(1)
                m = re.search(r"service:\s*https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]):(\d+)", line)
                if m and host:
                    out.setdefault(int(m.group(1)), host)
                    host = ""
    return out


# ----------------------------------------------------------------------------- the scan
def scan(host: str = "127.0.0.1", *, deep: bool = False, ports: Optional[list[int]] = None) -> dict:
    """Every ComfyUI and Ollama at `host`. `deep` tries every port from 1024; `ports` adds ports to try."""
    host = (host or "127.0.0.1").strip()
    host = re.sub(r"^https?://", "", host).split("/")[0]
    if ":" in host and not host.startswith("["):
        try:
            ipaddress.ip_address(host)                                  # a bare IPv6 address
        except ValueError:
            host, extra = host.rsplit(":", 1)                           # host:port typed: try that port too
            ports = [*(ports or []), int(extra)] if extra.isdigit() else ports
    candidates = sorted(set(COMFY_PORTS + OLLAMA_PORTS + list(ports or [])))
    if deep:
        candidates = sorted(set(candidates) | set(range(1024, 65536)))
    found_ports = open_ports(host, candidates, timeout=0.6 if not deep else 0.3)
    base = f"http://{'[' + host + ']' if ':' in host else host}"
    local = is_local(host)
    listeners = _listeners() if local else {}
    published = tunnels() if local else {}

    def look(port: int) -> Optional[dict]:
        url = f"{base}:{port}"
        return probe_comfy(url) or probe_ollama(url)

    with ThreadPoolExecutor(max_workers=32) as ex:
        found = [x for x in ex.map(look, found_ports) if x]
    for inst in found:
        port = int(inst["url"].rsplit(":", 1)[1])
        inst["port"] = port
        inst["local"] = local
        if port in published:
            inst["public"] = published[port]
        if port in listeners:
            inst["process"] = _process(listeners[port]) if os.name != "nt" else {"pid": listeners[port]}
        inst["ours"] = _ours(inst)
    found.sort(key=lambda i: (i["engine"] != "comfy", i["port"]))
    return {"host": host, "local": local, "deep": deep, "ports_tried": len(candidates), "instances": found, "gpus": _gpus() if local else []}


def _ours(inst: dict) -> bool:
    """A copy Video Tool installed (its own folder under the data folder), as opposed to one the person had already."""
    from .. import paths

    folder = (inst.get("process") or {}).get("folder", "")
    return bool(folder) and str(paths.DATA) in folder


def _gpus() -> list[dict]:
    from .hardware import gpus

    return gpus()
