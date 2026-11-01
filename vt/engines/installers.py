"""Put an engine on THIS computer (docs/plans/PLAN-ENGINES-AND-SETUP.MD section 3.3).

Every installer has the same shape: `plan()` says what would be downloaded (nothing is touched), `install(progress)` does it (idempotent: a file already complete is
skipped, a half-downloaded file is resumed), `verify()` says whether it is in place, `start()` starts it. Big files go to `models_dir`. Nothing here needs admin rights.

Status: the plans, the manifest handling, the resume and checksum logic and the commands are covered by tests with the network and the shell replaced; a complete install on
a clean computer has NOT been run yet (docs/TEST-PLAN.md section 7, T-6).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .. import paths
from ..util import CREATE_NO_WINDOW, noop_progress

Progress = Callable[[str, float, str], None]
COMFY_REPO = "https://github.com/comfyanonymous/ComfyUI"
# the pictures set is what a video needs; clips are optional and large
BUNDLES = {
    "pictures": ["diffusion_models/z_image_turbo_bf16.safetensors", "text_encoders/qwen_3_4b.safetensors", "vae/ae.safetensors"],
    "clips": ["diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", "loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
              "loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors", "text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "vae/wan_2.1_vae.safetensors"],
}


@dataclass
class Item:
    name: str
    size_gb: float
    what: str
    done: bool = False


@dataclass
class Plan:
    engine: str
    items: list[Item] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)          # things that stop the install (no git, no space), in plain words

    @property
    def total_gb(self) -> float:
        return round(sum(i.size_gb for i in self.items if not i.done), 1)

    def public(self) -> dict:
        return {"engine": self.engine, "items": [asdict(i) for i in self.items], "notes": self.notes, "problems": self.problems, "total_gb": self.total_gb, "ready": not self.problems}


def models_dir(override: str = "") -> Path:
    from ..util import read_json

    chosen = override or (read_json(paths.SETTINGS, {}) or {}).get("models_dir") or ""
    return Path(chosen) if chosen else paths.DATA / "models"


# ----------------------------------------------------------------------------- downloading, resumable and checked
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path, *, size: int, digest: str = "", progress: Callable[[float], None] = lambda f: None, opener: Optional[Callable] = None) -> Path:
    """Download `url` to `dest`: skipped when complete and matching, resumed from `dest.part` when interrupted, checked against `digest` at the end."""
    import httpx

    if dest.exists() and dest.stat().st_size == size and (not digest or sha256(dest) == digest):
        progress(1.0)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with (opener or httpx.stream)("GET", url, headers=headers, follow_redirects=True, timeout=60) as r:
        if r.status_code == 416:                                       # the part file is already everything
            have = size
        elif r.status_code not in (200, 206):
            raise RuntimeError(f"download failed: HTTP {r.status_code} for {url.split('?')[0].rsplit('/', 1)[-1]}")
        else:
            if r.status_code == 200:
                have = 0                                               # the server ignored the range: start again
            with part.open("ab" if have else "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
                    have += len(chunk)
                    progress(min(1.0, have / max(1, size)))
    if digest and sha256(part) != digest:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"{dest.name} did not match its checksum; it was deleted so the next try starts clean")
    part.replace(dest)
    return dest


class Installer:
    engine = ""

    def plan(self) -> Plan: raise NotImplementedError
    def install(self, progress: Progress = noop_progress) -> None: raise NotImplementedError
    def verify(self) -> bool: raise NotImplementedError
    def start(self) -> Optional[str]: return None


# ----------------------------------------------------------------------------- Ollama
class OllamaInstaller(Installer):
    engine = "ollama"

    def __init__(self, model: str = "") -> None:
        from .. import llm

        self.model = model or llm.model_name()

    def plan(self) -> Plan:
        from .. import llm

        have_bin = bool(llm.binary())
        p = Plan("ollama", [Item("Ollama program", 1.5 if os.name == "nt" else 0.2, "the engine that runs language models", have_bin), Item(f"Model {self.model}", 3.3, "a small model that reads and plans your videos", False)])
        if have_bin and llm.reachable(llm.settings()["ollama_url"]) and llm.has_model(self.model, llm.settings()["ollama_url"]):
            p.items[1].done = True
        return p

    def install(self, progress: Progress = noop_progress) -> None:
        from .. import llm

        llm.ensure_ready(lambda s, f, m="": progress("ollama", f, m), allow_download=True)

    def verify(self) -> bool:
        from .. import llm

        return bool(llm.binary()) and llm.reachable(llm.settings()["ollama_url"])


# ----------------------------------------------------------------------------- ComfyUI
def torch_index(compute: float) -> str:
    """The PyTorch wheel index for a card. Volta (the V100, 7.0) needs cu126 (the lesson of 2026-10-26); Blackwell (12+) needs cu128; no card = cpu."""
    if compute <= 0:
        return "https://download.pytorch.org/whl/cpu"
    if compute >= 12.0:
        return "https://download.pytorch.org/whl/cu128"
    return "https://download.pytorch.org/whl/cu126"


class ComfyInstaller(Installer):
    engine = "comfy"

    def __init__(self, root: Optional[Path] = None, bundles: tuple[str, ...] = ("pictures",), models: str = "", port: int = 8188) -> None:
        self.root = Path(root) if root else paths.DATA / "engines" / "comfyui"
        self.bundles = bundles
        self.models = models_dir(models) / "comfyui"
        self.port = port

    def manifest(self) -> list[dict]:
        m = json.loads((paths.ASSETS / "comfy" / "model-manifest.json").read_text(encoding="utf-8"))["models"]
        want = {p for b in self.bundles for p in BUNDLES.get(b, [])}
        return [x for x in m if x["path"] in want]

    def python(self) -> Path:
        return self.root / "venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")

    def plan(self) -> Plan:
        items = []
        for x in self.manifest():
            f = self.models / x["path"]
            items.append(Item(x["path"].rsplit("/", 1)[-1], round(x["size"] / 1e9, 1), x["path"].split("/")[0].replace("_", " "), f.exists() and f.stat().st_size == x["size"]))
        p = Plan("comfy", [Item("ComfyUI program and its Python", 5.0, "the picture server, with the right PyTorch for your card", (self.root / "main.py").exists() and self.python().exists())] + items)
        if not shutil.which("git"):
            p.problems.append("Git is not installed. Install Git (git-scm.com) and try again.")
        free = shutil.disk_usage(self.models.parent if self.models.parent.exists() else Path.home()).free / 1e9
        if free < p.total_gb + 5:
            p.problems.append(f"About {p.total_gb:.0f} GB are needed but only {free:.0f} GB are free where the models go. Choose another folder.")
        p.notes.append(f"Models go to {self.models}")
        return p

    def install(self, progress: Progress = noop_progress, compute: Optional[float] = None) -> None:
        from .hardware import gpus

        plan = self.plan()
        if plan.problems:
            raise RuntimeError(" ".join(plan.problems))
        cc = compute if compute is not None else max((g["compute"] for g in gpus()), default=0.0)
        self.root.parent.mkdir(parents=True, exist_ok=True)
        if not (self.root / "main.py").exists():
            progress("comfy", 0.01, "Downloading ComfyUI")
            self._run(["git", "clone", "--depth", "1", COMFY_REPO, str(self.root)])
        if not self.python().exists():
            progress("comfy", 0.04, "Making its Python environment")
            self._run([sys.executable, "-m", "venv", str(self.root / "venv")])
        progress("comfy", 0.06, "Installing PyTorch for your graphics card" if cc else "Installing PyTorch (no graphics card found)")
        self._run([str(self.python()), "-m", "pip", "install", "--upgrade", "pip"])
        self._run([str(self.python()), "-m", "pip", "install", "torch", "torchvision", "torchaudio", "--index-url", torch_index(cc)])
        progress("comfy", 0.14, "Installing ComfyUI's requirements")
        self._run([str(self.python()), "-m", "pip", "install", "-r", str(self.root / "requirements.txt")])
        self._link_models()
        todo = [x for x in self.manifest()]
        for i, x in enumerate(todo):
            base = 0.18 + 0.8 * i / max(1, len(todo))
            span = 0.8 / max(1, len(todo))
            name = x["path"].rsplit("/", 1)[-1]
            fetch(x["url"], self.models / x["path"], size=x["size"], digest=x.get("sha256", ""), progress=lambda f, b=base, s=span, n=name: progress("comfy", b + s * f, f"Downloading {n} {int(f * 100)}%"))
        progress("comfy", 1.0, "ComfyUI is ready")

    def _link_models(self) -> None:
        """ComfyUI reads its models from `extra_model_paths.yaml`, so the big files stay in models_dir and the program folder stays small."""
        self.models.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "extra_model_paths.yaml").write_text(
            "video_tool:\n    base_path: " + str(self.models).replace("\\", "/") + "\n    checkpoints: checkpoints\n    diffusion_models: diffusion_models\n    text_encoders: text_encoders\n"
            "    vae: vae\n    loras: loras\n    latent_upscale_models: latent_upscale_models\n", encoding="utf-8")

    def _run(self, cmd: list[str]) -> None:
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise RuntimeError(f"`{' '.join(cmd[:3])}` failed: {(r.stderr or r.stdout)[-300:]}")

    def verify(self) -> bool:
        return (self.root / "main.py").exists() and self.python().exists() and all((self.models / x["path"]).exists() for x in self.manifest())

    def start(self) -> Optional[str]:
        subprocess.Popen([str(self.python()), "main.py", "--listen", "127.0.0.1", "--port", str(self.port)], cwd=self.root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=CREATE_NO_WINDOW)
        return f"http://127.0.0.1:{self.port}"


# ----------------------------------------------------------------------------- VoiceStudio
class VoiceStudioInstaller(Installer):
    """VoiceStudio is another project with its own installer; we do not copy it. With Docker we start its image; without, we explain."""
    engine = "voicestudio"

    def plan(self) -> Plan:
        p = Plan("voicestudio", [Item("VoiceStudio (Docker image)", 4.0, "a voice studio with many voices and cloning", False)])
        if not shutil.which("docker"):
            p.problems.append("Docker is not installed. Install Docker, or run VoiceStudio yourself and use Connect to my server.")
        p.notes.append("Optional. Pictures, clips and voices through ComfyUI already work without it.")
        return p

    def install(self, progress: Progress = noop_progress) -> None:
        raise RuntimeError("Start VoiceStudio with its own instructions (github.com/debpalash/VoiceStudio), then use Connect to my server.")

    def verify(self) -> bool:
        return False


INSTALLERS: dict[str, Callable[..., Installer]] = {"ollama": OllamaInstaller, "comfy": ComfyInstaller, "voicestudio": VoiceStudioInstaller}


def installer(engine_id: str, **kw: Any) -> Installer:
    try:
        return INSTALLERS[engine_id](**kw)
    except KeyError:
        raise KeyError(f"there is no installer for '{engine_id}'") from None
