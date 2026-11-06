"""Live numbers about the computer that does the work: processor, memory, disk and every graphics card, and which of them Video Tool is using.

One function, `snapshot()`, behind the Studio's System panel (`GET /api/system/stats`), `vt system` and the MCP tool `system_stats`. The same
code runs on a processing server and on a computer that has everything installed locally.

No extra packages: Linux reads /proc, Windows asks the system through ctypes, graphics cards come from `nvidia-smi` (when there is one).
Every part is optional: a number that cannot be read is None, never an error. Cards are read at most once a second, however many windows ask.
"""
from __future__ import annotations

import ctypes
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from .util import CREATE_NO_WINDOW

_lock = threading.Lock()
_cpu = {"idle": 0, "total": 0, "wall": 0.0, "proc": 0.0, "percent": 0.0, "proc_percent": 0.0}
_gpu_cache: dict[str, Any] = {"at": 0.0, "value": None}
_engine_cache: dict[str, Any] = {"at": 0.0, "value": None}
GB = 1e9


# ----------------------------------------------------------------------------------------------------------------------- processor
def _cpu_times() -> Optional[tuple[int, int]]:
    """(idle, total) counters of the whole computer."""
    try:
        if sys.platform.startswith("linux"):
            parts = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:9]]
            return parts[3] + parts[4], sum(parts)                    # idle + iowait, everything
        if sys.platform == "win32":
            idle, kernel, user = (ctypes.c_ulonglong() for _ in range(3))
            if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                return idle.value, kernel.value + user.value          # kernel time includes idle time
    except Exception:                                                   # noqa: BLE001
        pass
    return None


def _cpu_percent() -> Optional[float]:
    """Use since the last call (about a second apart when a window polls). The very first call measures over a short pause."""
    now = _cpu_times()
    if now is None:
        try:
            return round(min(100.0, os.getloadavg()[0] / (os.cpu_count() or 1) * 100), 1)
        except (OSError, AttributeError):
            return None
    with _lock:
        if _cpu["total"] == 0 or time.time() - _cpu["wall"] > 30:
            _cpu["idle"], _cpu["total"], _cpu["wall"] = now[0], now[1], time.time()
            time.sleep(0.2)
            now = _cpu_times() or now
        di, dt = now[0] - _cpu["idle"], now[1] - _cpu["total"]
        if dt > 0:
            _cpu["percent"] = round(max(0.0, min(100.0, (1 - di / dt) * 100)), 1)
        _cpu["idle"], _cpu["total"], _cpu["wall"] = now[0], now[1], time.time()
        return _cpu["percent"]


def _cpu_model() -> str:
    try:
        if sys.platform.startswith("linux"):
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
        if sys.platform == "win32":
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
    except Exception:                                                   # noqa: BLE001
        pass
    return platform.processor() or "Processor"


# ----------------------------------------------------------------------------------------------------------------------- memory
class _MemStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def _memory() -> dict[str, Optional[float]]:
    total = avail = swap_total = swap_free = None
    try:
        if sys.platform.startswith("linux"):
            info = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0]) * 1024
            total, avail = info.get("MemTotal"), info.get("MemAvailable")
            swap_total, swap_free = info.get("SwapTotal"), info.get("SwapFree")
        elif sys.platform == "win32":
            m = _MemStatus()
            m.dwLength = ctypes.sizeof(m)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                total, avail = m.ullTotalPhys, m.ullAvailPhys          # (the page file is a commit limit on Windows, not a swap figure: left out)
    except Exception:                                                   # noqa: BLE001
        pass
    used = (total - avail) if total is not None and avail is not None else None
    return {"total_gb": _gb(total), "used_gb": _gb(used), "available_gb": _gb(avail),
            "percent": round(used / total * 100, 1) if used is not None and total else None,
            "swap_total_gb": _gb(swap_total), "swap_used_gb": _gb(swap_total - swap_free) if swap_total is not None and swap_free is not None else None}


def _gb(n: Optional[float]) -> Optional[float]:
    return None if n is None else round(n / GB, 2)


class _ProcMem(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def _own_memory() -> Optional[float]:
    """This server process's memory in GB."""
    try:
        if sys.platform.startswith("linux"):
            return round(int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") / GB, 2)
        if sys.platform == "win32":
            pm = _ProcMem()
            pm.cb = ctypes.sizeof(pm)
            ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ProcMem), ctypes.c_ulong]     # 64-bit handles
            h = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pm), pm.cb):
                return round(pm.WorkingSetSize / GB, 2)
    except Exception:                                                   # noqa: BLE001
        pass
    return None


def _own_cpu_percent() -> Optional[float]:
    """This server process's share of the whole processor, since the last call."""
    now, wall = time.process_time(), time.time()
    with _lock:
        if _cpu["wall"] and _cpu["proc"] and wall > _cpu.get("proc_wall", 0):
            d = wall - _cpu.get("proc_wall", wall)
            if d > 0.2:
                _cpu["proc_percent"] = round(max(0.0, min(100.0, (now - _cpu["proc"]) / d / (os.cpu_count() or 1) * 100)), 1)
        if wall - _cpu.get("proc_wall", 0) > 0.2:
            _cpu["proc"], _cpu["proc_wall"] = now, wall
        return _cpu["proc_percent"]


# ----------------------------------------------------------------------------------------------------------------------- graphics cards
def _smi(args: list[str]) -> list[list[str]]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        out = subprocess.run([exe, *args, "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW).stdout
    except Exception:                                                   # noqa: BLE001
        return []
    return [[c.strip() for c in line.split(",")] for line in out.splitlines() if line.strip()]


def _num(v: str) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None                                                     # "[N/A]", "[Not Supported]"


def _visible(rows: list[dict[str, Any]], programs: dict[str, list[dict[str, Any]]]) -> Optional[set[str]]:
    """The cards Video Tool may use (the person's list within the launcher's fence, vt/gpuassign.py), as uuids, worked out from the cards and programs this reading has just
    found: asking gpuassign to read them again would ask for what is being read, and what it says depends on it. None = all of them, when that cannot be told."""
    try:
        from . import gpuassign

        cards = [{"index": r["index"], "name": r["name"], "uuid": r["uuid"], "free_gb": round(r["memory_total_gb"] - r["memory_used_gb"], 1),
                  "total_gb": r["memory_total_gb"], "load": r["percent"] or 0.0} for r in rows]
        return {c["uuid"] for c in gpuassign.allowed(cards, programs)}
    except Exception:                                                   # noqa: BLE001
        raw = os.environ.get("CUDA_VISIBLE_DEVICES")
        return None if raw is None else {x.strip() for x in raw.split(",") if x.strip()}


def _descendants(root: int) -> set[int]:
    """This process and everything it started (Linux), to tell which card programs are Video Tool's own (the renderer, speech recognition)."""
    found = {root}
    if not sys.platform.startswith("linux"):
        return found
    try:
        parent = {}
        for p in Path("/proc").iterdir():
            if p.name.isdigit():
                try:
                    parent[int(p.name)] = int(Path(p, "stat").read_text().rsplit(")", 1)[1].split()[1])
                except (OSError, ValueError, IndexError):
                    continue
        grew = True
        while grew:
            grew = False
            for pid, ppid in parent.items():
                if ppid in found and pid not in found:
                    found.add(pid)
                    grew = True
    except OSError:
        pass
    return found


def _label(name: str, cmdline: str, ours: bool = False) -> str:
    n = (name or "").lower()
    c = (cmdline or "").lower()
    if "llama-server" in n or "ollama" in n or "ollama" in c:
        return "Ollama"
    if "comfyui" in c:
        return "ComfyUI"
    if ours:                                                            # only our own programs get our names: a browser on the same card is just a browser
        return "Video renderer" if ("chrome" in n or "headless_shell" in n or "chrome" in c) else "Video Tool"
    return Path(name).name or "Program"


def _cmdline(pid: int) -> str:
    try:
        if sys.platform.startswith("linux"):
            return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")[:300]
    except OSError:
        pass
    return ""


def _pmon() -> Optional[dict[int, list[dict[str, Any]]]]:
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


def _gpus() -> list[dict[str, Any]]:
    with _lock:
        if _gpu_cache["value"] is not None and time.time() - _gpu_cache["at"] < 1.0:
            return _gpu_cache["value"]
    rows = _smi(["--query-gpu=index,name,uuid,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw,power.limit,clocks.sm,encoder.stats.sessionCount"]) \
        or _smi(["--query-gpu=index,name,uuid,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw,power.limit,clocks.sm"])
    apps = _smi(["--query-compute-apps=gpu_uuid,pid,process_name,used_memory"])
    pm = _pmon()
    mine = _descendants(os.getpid())
    out = []
    for r in rows:
        if len(r) < 11:
            continue
        idx, name, uuid = r[0], r[1], r[2]
        procs = []
        if pm is not None:
            for q in pm.get(int(idx), []):
                procs.append({"pid": q["pid"], "label": _label(q["name"], _cmdline(q["pid"]), q["pid"] in mine), "gb": q["gb"], "percent": q["percent"], "ours": q["pid"] in mine})
        for a in ([] if pm is not None else apps):
            if len(a) >= 4 and a[0] == uuid:
                pid = int(a[1]) if a[1].isdigit() else 0
                procs.append({"pid": pid, "label": _label(a[2], _cmdline(pid), pid in mine), "gb": round((_num(a[3]) or 0) / 1024, 2), "ours": pid in mine})
        out.append({"index": int(idx), "name": name, "uuid": uuid, "percent": _num(r[3]), "memory_percent": _num(r[4]),
                    "memory_used_gb": round((_num(r[5]) or 0) / 1024, 2), "memory_total_gb": round((_num(r[6]) or 0) / 1024, 2),
                    "temperature_c": _num(r[7]), "power_w": _num(r[8]), "power_limit_w": _num(r[9]), "clock_mhz": _num(r[10]),
                    "usable_by_video_tool": True, "programs": procs})
    visible = _visible(out, {g["uuid"]: g["programs"] for g in out})
    for g in out:
        g["usable_by_video_tool"] = visible is None or str(g["index"]) in visible or g["uuid"] in visible
    with _lock:
        _gpu_cache.update(at=time.time(), value=out)
    return out


# ----------------------------------------------------------------------------------------------------------------------- the engines Video Tool talks to
def _engines() -> dict[str, Any]:
    """Which card ComfyUI draws on and what Ollama has loaded (the picture and language engines Video Tool uses). Asked at most every 3 seconds."""
    with _lock:
        if _engine_cache["value"] is not None and time.time() - _engine_cache["at"] < 3.0:
            return _engine_cache["value"]
    out: dict[str, Any] = {}
    try:
        from .engines import store

        comfy, ollama = store.load("comfy"), store.load("ollama")
    except Exception:                                                   # noqa: BLE001
        comfy = ollama = None
    if comfy is not None and comfy.mode != "off" and comfy.url:
        try:
            s = httpx.get(comfy.url.rstrip("/") + "/system_stats", timeout=1.5).json()
            dev = [d for d in s.get("devices", []) if str(d.get("type", "")).lower() == "cuda"]
            out["comfy"] = {"url": comfy.url, "ok": True, "version": s.get("system", {}).get("comfyui_version"),
                            "gpus": [{"name": d.get("name", "").split(" : ")[0].split(" ", 1)[-1] if d.get("name", "").startswith("cuda:") else d.get("name"),
                                      "vram_free_gb": _gb(d.get("vram_free")), "vram_total_gb": _gb(d.get("vram_total"))} for d in dev],
                            "ram_free_gb": _gb(s.get("system", {}).get("ram_free"))}
        except Exception as e:                                          # noqa: BLE001
            out["comfy"] = {"url": comfy.url, "ok": False, "why": type(e).__name__}
    if ollama is not None and ollama.mode != "off" and ollama.url:
        try:
            ps = httpx.get(ollama.url.rstrip("/") + "/api/ps", timeout=1.5).json()
            out["ollama"] = {"url": ollama.url, "ok": True, "loaded": [{"model": m.get("name"), "gb_on_card": _gb(m.get("size_vram")), "gb_total": _gb(m.get("size"))}
                                                                        for m in ps.get("models", [])]}
        except Exception as e:                                          # noqa: BLE001
            out["ollama"] = {"url": ollama.url, "ok": False, "why": type(e).__name__}
    with _lock:
        _engine_cache.update(at=time.time(), value=out)
    return out


# ----------------------------------------------------------------------------------------------------------------------- the snapshot
def snapshot(data_dir: Optional[Path] = None) -> dict[str, Any]:
    """Everything the System panel shows, as plain numbers (see the module text)."""
    from . import paths

    path = Path(data_dir or paths.DATA)
    probe = path if path.exists() else path.parent if path.parent.exists() else Path.home()
    try:
        du = shutil.disk_usage(probe)
        disk = {"path": str(path), "total_gb": _gb(du.total), "free_gb": _gb(du.free), "percent": round((du.total - du.free) / du.total * 100, 1)}
    except OSError:
        disk = {"path": str(path), "total_gb": None, "free_gb": None, "percent": None}
    percent = _cpu_percent()
    gpus = _gpus()
    using = [g["name"] for g in gpus if g["usable_by_video_tool"]]
    ours = [g["name"] for g in gpus if any(p["ours"] or p["label"] in ("Video renderer", "Video Tool") for p in g["programs"])]   # ComfyUI and Ollama are services of their own: they show on the card but are not Video Tool
    others = [g["name"] for g in gpus if g["usable_by_video_tool"] and (g["percent"] or 0) >= 5 and g["name"] not in ours]
    try:
        from . import gpuassign

        assignment = {j: (gpuassign.resolve(j)[0] or {}).get("index") for j in gpuassign.JOBS}
        needs_choice = gpuassign.needs_choice()
    except Exception:                                                   # noqa: BLE001
        assignment, needs_choice = {}, False
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "updated_at": round(time.time(), 1), "host": {"name": socket.gethostname(), "os": f"{platform.system()} {platform.release()}", "pid": os.getpid()},
            "cpu": {"model": _cpu_model(), "cores": os.cpu_count(), "percent": percent, "video_tool_percent": _own_cpu_percent()},
            "memory": {**_memory(), "video_tool_gb": _own_memory()}, "disk": disk, "gpus": gpus, "engines": _engines(),
            "assignment": assignment, "needs_gpu_choice": needs_choice,
            "summary": {"gpus_video_tool_can_use": using, "gpu_in_use": ours, "busy_with_other_programs": others}}
