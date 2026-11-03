"""Which build of the GPU libraries fits this computer: every NVIDIA GPU and driver gets the newest one it can run, anything else the CPU build.

    python -m vt.gpu_detect            prints the flavour (cu128 / cu124 / cu118 / cpu); the installers sync that extra (pyproject.toml)
    python -m vt.gpu_detect --explain  and why

Flavours (PyTorch wheel builds; ONNX Runtime and CTranslate2 load the CUDA 12 libraries that come with torch, vt/gpu.py):
  cu128  torch 2.7  CUDA 12.8  driver >= 570  compute capability 7.5 and up; the only one that runs RTX 50 (Blackwell, 10.0 / 12.0)
  cu124  torch 2.6  CUDA 12.4  driver >= 525  compute capability 5.0 to 9.0 (Maxwell to Hopper)            the default
  cu118  torch 2.6  CUDA 11.8  driver >= 452  compute capability 3.7 to 9.0; speech recognition runs on the CPU (it needs CUDA 12)
  cpu    no NVIDIA GPU, a GPU too old (Kepler 3.0/3.5 and before), or a driver too old for any of the above; macOS (Apple GPUs use MPS)
Pure decision logic (`choose`) is separate from asking the machine (`detect`), so it is tested on any computer.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

FLAVOURS = ("cu128", "cu124", "cu118", "cpu")
NEEDS = {                      # minimum driver (major.minor), compute capability range [lo, hi]
    "cu128": ((570, 0), (7.5, 12.9)),
    "cu124": ((525, 60), (5.0, 9.0)),
    "cu118": ((452, 39), (3.7, 9.0)),
}
# when nvidia-smi is too old to report compute capability: by product name
NAME_CC = [(r"RTX\s*50\d\d|B100|B200|GB\d", 12.0), (r"RTX\s*40\d\d|L4\b|L40|RTX\s*\d000 Ada", 8.9), (r"H100|H200|GH200", 9.0),
           (r"RTX\s*30\d\d|A100|A10\b|A30|A40|A16|A2\b|RTX A\d", 8.6), (r"RTX\s*20\d\d|GTX\s*16\d\d|T4\b|Quadro RTX|TITAN RTX", 7.5),
           (r"V100|TITAN V", 7.0), (r"GTX\s*10\d\d|P100|P40|P4\b|TITAN X", 6.1), (r"GTX\s*9\d\d|M60|M40|GTX\s*750", 5.2),
           (r"K80", 3.7), (r"GTX\s*7[0-6]\d|K40|K20|GT\s*7\d\d", 3.5)]


@dataclass
class Gpu:
    name: str
    cc: Optional[float]                       # compute capability, e.g. 8.9
    driver: tuple[int, int] = (0, 0)


@dataclass
class Decision:
    flavour: str
    gpus: list[Gpu] = field(default_factory=list)
    why: str = ""
    asr_on_gpu: bool = True


def _driver(v: str) -> tuple[int, int]:
    m = re.match(r"(\d+)\.(\d+)", v.strip())
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _cc_from_name(name: str) -> Optional[float]:
    for pat, cc in NAME_CC:
        if re.search(pat, name, re.I):
            return cc
    return None


def choose(gpus: list[Gpu], platform: str = sys.platform) -> Decision:
    """The newest flavour that every listed GPU (the ones the app will use) can run."""
    if platform == "darwin":
        return Decision("cpu", gpus, "macOS: no CUDA; Apple GPUs are used through MPS where the libraries support it.", False)
    usable = [g for g in gpus if g.cc is not None]
    if not usable:
        return Decision("cpu", gpus, "No NVIDIA GPU was found." if not gpus else "The GPU's model could not be identified.", False)
    for fl in ("cu128", "cu124", "cu118"):
        (dmin, (lo, hi)) = NEEDS[fl]
        if all(g.driver >= dmin and lo <= g.cc <= hi for g in usable):
            if fl == "cu128" and all(g.cc <= 9.0 for g in usable) and all(g.driver >= NEEDS["cu124"][0] for g in usable):
                continue                                          # cu124 already runs these GPUs and has the widest support; cu128 is for Blackwell
            names = ", ".join(f"{g.name} ({g.cc:g})" for g in usable)
            why = {"cu128": f"{names}: needs CUDA 12.8 (Blackwell, or newest driver).",
                   "cu124": f"{names}: CUDA 12.4 build.",
                   "cu118": f"{names}: the driver is older than 525, so the CUDA 11.8 build; speech recognition runs on the CPU. "
                            "Updating the NVIDIA driver makes it faster."}[fl]
            return Decision(fl, gpus, why, fl != "cu118")
    worst = min(usable, key=lambda g: (g.cc, g.driver))
    if max(g.cc for g in usable) > 9.0 and worst.cc < 7.5:
        return Decision("cpu", gpus, "These GPUs need different builds (an RTX 50 needs CUDA 12.8, which no longer supports the older card). "
                                     "Set CUDA_VISIBLE_DEVICES to the newer GPU to use it.", False)
    if worst.cc < 3.7:
        return Decision("cpu", gpus, f"{worst.name} (compute {worst.cc:g}) is older than any GPU build supports; everything runs on the CPU.", False)
    return Decision("cpu", gpus, f"The NVIDIA driver {worst.driver[0]}.{worst.driver[1]} is too old for any GPU build; update it to use the GPU.", False)


def detect() -> list[Gpu]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        for cand in (r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe", "/usr/bin/nvidia-smi"):
            if shutil.os.path.exists(cand):
                exe = cand
                break
    if not exe:
        return []
    def q(fields: str) -> list[list[str]]:
        r = subprocess.run([exe, f"--query-gpu={fields}", "--format=csv,noheader"], capture_output=True, text=True, timeout=20)
        return [[c.strip() for c in line.split(",")] for line in r.stdout.splitlines() if line.strip()] if r.returncode == 0 else []
    rows = q("name,compute_cap,driver_version")
    if rows and len(rows[0]) == 3:
        return [Gpu(n, float(c) if re.fullmatch(r"\d+(\.\d+)?", c) else _cc_from_name(n), _driver(d)) for n, c, d in rows]
    return [Gpu(n, _cc_from_name(n), _driver(d)) for n, d in q("name,driver_version") if n]      # an old nvidia-smi without compute_cap


def decide() -> Decision:
    try:
        return choose(detect())
    except Exception as e:                                                              # noqa: BLE001
        return Decision("cpu", [], f"Could not ask the NVIDIA driver ({type(e).__name__}); using the CPU build.", False)


if __name__ == "__main__":
    d = decide()
    print(d.flavour if "--explain" not in sys.argv else f"{d.flavour}: {d.why}")
