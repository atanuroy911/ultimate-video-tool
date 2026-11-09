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
    with _download_lock(dest):
        return _fetch(url, dest, size=size, digest=digest, progress=progress, opener=opener)


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class _download_lock:
    """One download of a file at a time: two (the Studio and the terminal, a double click) appending to one .part corrupt it, the checksum
    fails and the file is lost (seen on the owner's server, 2026-11-01). A lock left by a process that is gone is taken over."""

    def __init__(self, dest: Path):
        self.path = dest.with_suffix(dest.suffix + ".lock")

    def __enter__(self):
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    pid = int(self.path.read_text().strip() or 0)
                except (OSError, ValueError):
                    pid = 0
                if _alive(pid):
                    raise RuntimeError(f"{self.path.stem} is already being downloaded (process {pid}); wait for it to finish")
                self.path.unlink(missing_ok=True)
        raise RuntimeError(f"could not lock {self.path}")

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


def _fetch(url: str, dest: Path, *, size: int, digest: str, progress: Callable[[float], None], opener: Optional[Callable]) -> Path:
    import httpx

    if dest.exists() and dest.stat().st_size == size and (not digest or sha256(dest) == digest):
        progress(1.0)
        return dest
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

    def __init__(self, model: str = "", storage=None) -> None:
        from .. import llm

        self.model = model or llm.model_name()
        self.storage=storage

    def plan(self) -> Plan:
        from .. import llm

        root=Path(self.storage.get('install_dir') or paths.DATA/'engines')/'ollama' if self.storage else None
        have_bin = bool(llm.binary(root) if root else llm.binary())
        from .fit import LANGUAGE_DOWNLOAD_GB

        p = Plan("ollama", [Item("Ollama program", 1.5 if os.name == "nt" else 0.2, "the program that runs the writing AI", have_bin),
                            Item(f"Model {self.model}", LANGUAGE_DOWNLOAD_GB.get(self.model, 3.3), "the model that plans and writes your videos", False)])
        url=self.storage['url'] if self.storage else llm.settings()['ollama_url']
        if have_bin and llm.reachable(url) and llm.has_model(self.model, url):
            p.items[1].done = True
        return p

    def install(self, progress: Progress = noop_progress) -> None:
        from .. import llm

        callback=lambda s, f, m='':progress('ollama',f,m)
        if self.storage:llm.ensure_ready(callback,allow_download=True,storage=self.storage,model=self.model)
        else:llm.ensure_ready(callback,allow_download=True)

    def start(self):
        from .. import llm
        return self.storage['url'] if self.storage else llm.settings()['ollama_url']

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

    def __init__(self, root: Optional[Path] = None, bundles: tuple[str, ...] = ("pictures",), models: str = "", port: int = 8188, recipe: str = '', gpu=None) -> None:
        from ..util import read_json
        chosen=(read_json(paths.SETTINGS,{}) or {}).get('install_dir')
        self.root = Path(root) if root else (Path(chosen) if chosen else paths.DATA / 'engines') / 'comfyui'
        self.bundles = bundles
        self.models = models_dir(models) / "comfyui"
        self.port = port
        self.recipe=recipe
        from . import setup
        self.gpu=gpu if gpu is not None else setup.pictures_card()                                  # the card a new install is built for: the one chosen for the "pictures" job
        self.chosen_gpu=gpu                                                                         # a card named by the caller; otherwise it starts on the card of the "pictures" job

    def manifest(self) -> list[dict]:
        m = json.loads((paths.ASSETS / "comfy" / "model-manifest.json").read_text(encoding="utf-8"))["models"]
        want = {p for b in self.bundles for p in BUNDLES.get(b, [])}
        if self.recipe and 'pictures' in self.bundles:
            from .fit import BY_ID,FILES
            want.difference_update(BUNDLES['pictures']);want.update(BY_ID[self.recipe].files())
            merged={x['path']:x for x in m};merged.update({p:{'path':p,**info} for p,info in FILES.items()})
            return [merged[p] for p in sorted(want)]
        return [x for x in m if x["path"] in want]

    def addons(self) -> list[dict]:
        """ComfyUI add-ons the chosen picture set needs (none for the full-size sets)."""
        from .fit import BY_ID
        r = BY_ID.get(self.recipe) if self.recipe and "pictures" in self.bundles else None
        return r.addons() if r else []

    def python(self) -> Path:
        return self.root / "venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")

    def plan(self) -> Plan:
        items = []
        role = {"diffusion_models": "Picture model", "text_encoders": "Text reader", "vae": "Picture decoder", "loras": "Clip speed-up", "clip_vision": "Picture reader"}
        for x in self.manifest():
            f = self.models / x["path"]
            folder, file = x["path"].split("/")[0], x["path"].rsplit("/", 1)[-1]
            stem = file.rsplit(".", 1)[0]
            if "wan2" in stem or "umt5" in stem or folder == "loras":
                folder_role = {"diffusion_models": "Clip model", "text_encoders": "Clip text reader", "vae": "Clip decoder"}.get(folder, role.get(folder, "Model file"))
            else:
                folder_role = role.get(folder, "Model file")
            items.append(Item(f"{folder_role} · {stem}", round(x["size"] / 1e9, 1), file, f.exists() and f.stat().st_size == x["size"]))
        addons = [Item(f"Add-on · {a['name']}", 0.1, "lets ComfyUI read the small model files", (self.root / "custom_nodes" / a["name"] / "__init__.py").exists()) for a in self.addons()]
        p = Plan("comfy", [Item("ComfyUI program", 5.0, "the program that draws, set up for your graphics card", (self.root / "main.py").exists() and self.python().exists())] + addons + items)
        if not shutil.which("git"):
            p.problems.append("Git is not installed. Install Git (git-scm.com) and try again.")
        free = shutil.disk_usage(self.models.parent if self.models.parent.exists() else Path.home()).free / 1e9
        if free < p.total_gb + 5:
            p.problems.append(f"About {p.total_gb:.0f} GB are needed but only {free:.0f} GB are free where the models go. Choose another folder.")
        p.notes.append(f"Models go to {self.models}")
        if self.gpu is not None:
            from .hardware import gpus
            if not any(g['index']==self.gpu for g in gpus()):
                p.problems.append('The selected graphics card is no longer available on this server. Choose it again before installing.')
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
        for a in self.addons():                                            # e.g. ComfyUI-GGUF for the squeezed picture sets of small cards
            dest = self.root / "custom_nodes" / a["name"]
            if not (dest / "__init__.py").exists():
                progress("comfy", 0.16, f"Adding {a['name']}")
                self._run(["git", "clone", a["repo"], str(dest)])
                self._run(["git", "-C", str(dest), "checkout", "--quiet", a["commit"]])
            if (dest / "requirements.txt").exists():
                self._run([str(self.python()), "-m", "pip", "install", "-r", str(dest / "requirements.txt")])
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
        return (self.root / "main.py").exists() and self.python().exists() and all((self.models / x["path"]).exists() for x in self.manifest())             and all((self.root / "custom_nodes" / a["name"] / "__init__.py").exists() for a in self.addons())

    def start(self) -> Optional[str]:
        env={**os.environ,'HF_HOME':str(self.models/'huggingface'),'TORCH_HOME':str(self.models/'torch-cache')}
        from .. import gpuassign
        env.update(gpuassign.child_env(self.chosen_gpu) if self.chosen_gpu is not None else gpuassign.job_env("pictures"))    # only a card Video Tool may use
        proc=subprocess.Popen([str(self.python()), "main.py", "--listen", "127.0.0.1", "--port", str(self.port)], cwd=self.root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=CREATE_NO_WINDOW,env=env)
        if getattr(proc,'pid',None):
            from . import pids
            pids.remember('comfy',proc.pid,self.port)                              # so a change of card can restart exactly this program, and nothing else
        return f"http://127.0.0.1:{self.port}"


INSTALLERS: dict[str, Callable[..., Installer]] = {"ollama": OllamaInstaller, "comfy": ComfyInstaller}


def installer(engine_id: str, **kw: Any) -> Installer:
    try:
        return INSTALLERS[engine_id](**kw)
    except KeyError:
        raise KeyError(f"there is no installer for '{engine_id}'") from None
