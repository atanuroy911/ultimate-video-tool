"""What this computer can do, in plain words, and what the setup should suggest for each engine (docs/plans/PLAN-ENGINES-AND-SETUP.MD section 3.2, step 1)."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .. import paths
from ..util import CREATE_NO_WINDOW


def _ram_gb() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().total / 1e9, 1)
    except Exception:                                                                   # noqa: BLE001
        pass
    try:
        if os.name == "nt":
            import ctypes

            class MEM(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("p", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong), ("c", ctypes.c_ulonglong),
                            ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong), ("f", ctypes.c_ulonglong)]

            m = MEM()
            m.l = ctypes.sizeof(MEM)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))                # type: ignore[attr-defined]
            return round(m.total / 1e9, 1)
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1)
    except Exception:                                                                   # noqa: BLE001
        return 0.0


def gpus() -> list[dict[str, Any]]:
    """NVIDIA cards from nvidia-smi: name, memory in GB, compute capability (which decides the PyTorch build and whether bf16 works)."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "--query-gpu=index,name,memory.total,compute_cap", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW).stdout
    except Exception:                                                                   # noqa: BLE001
        return []
    cards = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4:
            try:
                cc = float(parts[3])
            except ValueError:
                cc = 0.0
            cards.append({"index": int(parts[0]), "name": parts[1], "memory_gb": round(float(parts[2]) / 1024, 1), "compute": cc, "bf16": cc >= 8.0})
    return cards


def detect(data_dir: Path | None = None) -> dict[str, Any]:
    target = Path(data_dir or paths.DATA)
    probe = target if target.exists() else target.parent if target.parent.exists() else Path.home()
    free = shutil.disk_usage(probe).free / 1e9
    cards = gpus()
    best = max(cards, key=lambda g: g["memory_gb"], default=None)
    return {"os": platform.system(), "machine": platform.machine(), "cpu_cores": os.cpu_count() or 1, "ram_gb": _ram_gb(), "disk_free_gb": round(free, 1), "data_dir": str(target),
            "gpus": cards, "best_gpu": best, "summary": summary(cards, free)}


def summary(cards: list[dict], free_gb: float) -> str:
    if not cards:
        return "This computer has no NVIDIA graphics card. Pictures and voices will be slow here, so connecting a server (or using the built-in voices and simple pictures) is the better choice."
    g = max(cards, key=lambda c: c["memory_gb"])
    if g["memory_gb"] >= 12:
        what = "make pictures, voices and short clips"
    elif g["memory_gb"] >= 8:
        what = "make pictures and voices"
    else:
        what = "make voices; pictures will be slow"
    low = f" Only {free_gb:.0f} GB of disk is free, which is tight for the models." if free_gb < 60 else ""
    return f"Your graphics card ({g['name']}, {g['memory_gb']:.0f} GB) can {what}.{low}"


def recommend(hw: dict[str, Any]) -> dict[str, str]:
    """engine id -> 'local' | 'remote' | 'off': a pre-selected card in step 3. The person can change every one."""
    g = hw.get("best_gpu")
    gb = g["memory_gb"] if g else 0
    return {"ollama": "local" if (gb >= 8 or hw.get("ram_gb", 0) >= 16) else "remote",
            "comfy": "local" if gb >= 12 else "remote",
            "vtengine": "off"}
