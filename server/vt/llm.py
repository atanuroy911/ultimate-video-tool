"""The local language model that plans scenes when Claude is not connected.

It talks to an Ollama server. The address comes from Settings (default http://127.0.0.1:11434). If nothing answers there and the
address is this computer, the app finds or downloads a portable copy of Ollama into its own data folder, starts it, and pulls a
model sized to the graphics card. Nothing is installed system-wide and no account or key is involved.

Settings keys (settings.json): llm_mode "auto" | "off", ollama_url, ollama_model ("" = recommended), llm_auto_download (bool).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from . import paths
from .util import ProgressFn, noop_progress, read_json

DEFAULT_URL = "http://127.0.0.1:11434"
WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"
CREATE_NO_WINDOW = 0x08000000 if WIN else 0

_ASSET = ("https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip" if WIN else
          "https://github.com/ollama/ollama/releases/latest/download/ollama-darwin.tgz" if MAC else
          "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tar.zst")


class LLMUnavailable(RuntimeError):
    """The local model cannot be used right now (the caller falls back to the rule planner)."""


# --------------------------------------------------------------------------- settings
def settings() -> dict[str, Any]:
    s = read_json(paths.SETTINGS, {}) or {}
    return {
        "llm_mode": s.get("llm_mode", "auto"),
        "ollama_url": (s.get("ollama_url") or DEFAULT_URL).rstrip("/"),
        "ollama_model": s.get("ollama_model") or "",
        "llm_auto_download": bool(s.get("llm_auto_download", True)),
    }


def gpu_memory_mb() -> int:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True,
                             timeout=8, creationflags=CREATE_NO_WINDOW).stdout
        return max(int(x) for x in out.split() if x.isdigit())
    except Exception:
        return 0


def recommend_model() -> str:
    """The biggest model that fits this computer's card with its context (vt/engines/fit.py LANGUAGE), else a small one on the processor."""
    from .engines import fit

    return fit.language_model(server_vram_gb())["model"]


def server_vram_gb() -> float:
    """The card of the computer Ollama runs on. This computer's when Ollama is here; for one elsewhere Ollama does not say, so the ComfyUI on
    the same computer is asked (its /system_stats), else nothing is assumed (0: a small model)."""
    url = settings()["ollama_url"]
    if is_local(url):
        return gpu_memory_mb() / 1024
    host = urllib.parse.urlparse(url).hostname or ""
    comfy = str((read_json(paths.SETTINGS, {}) or {}).get("comfy_url") or "")
    if host and urllib.parse.urlparse(comfy).hostname == host:
        try:
            devs = httpx.get(comfy.rstrip("/") + "/system_stats", timeout=3).json().get("devices", [])
            return max((float(d.get("vram_total", 0)) / 1e9 for d in devs if d.get("type") == "cuda"), default=0.0)
        except Exception:                                               # noqa: BLE001
            return 0.0
    return 0.0


_PREFER = [r"^gemma[34]", r"^qwen3", r"^qwen2\.5:(32|14|7)b(-instruct)?$", r"^llama3\.[123]:(8|70)b", r"^llama3:(8b|latest)", r"^mistral", r"^phi[34]", r"^qwen2\.5:3b", r"^llama3\.2"]
_SKIP = re.compile(r"(vl|vision|llava|moondream|smolvlm|coder|embed|nomic|bge|minilm)", re.I)


def choose_installed(models: list[str]) -> Optional[str]:
    """The best general text model already on the server (so nothing needs downloading), by a fixed preference order."""
    usable = [m for m in models if not _SKIP.search(m)]
    for pat in _PREFER:
        for m in usable:
            if re.search(pat, m):
                return m
    return None


def model_name() -> str:
    s = settings()
    if s["ollama_model"]:
        return s["ollama_model"]
    have = installed_models(s["ollama_url"])
    return choose_installed(have) or recommend_model()


def is_local(url: str) -> bool:
    return (urllib.parse.urlparse(url).hostname or "") in ("127.0.0.1", "localhost", "::1", "0.0.0.0")


# --------------------------------------------------------------------------- server
def reachable(url: Optional[str] = None, timeout: float = 1.5) -> bool:
    try:
        return httpx.get((url or settings()["ollama_url"]) + "/api/version", timeout=timeout).status_code == 200
    except Exception:
        return False


def installed_models(url: Optional[str] = None) -> list[str]:
    try:
        r = httpx.get((url or settings()["ollama_url"]) + "/api/tags", timeout=5)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def has_model(name: str, url: Optional[str] = None) -> bool:
    have = installed_models(url)
    return name in have or (":" not in name and f"{name}:latest" in have)


def ollama_program_dir() -> Path:
    chosen=(read_json(paths.SETTINGS,{}) or {}).get('install_dir')
    return Path(chosen)/'ollama' if chosen else paths.DATA/'ollama'


def binary(root: Optional[Path] = None) -> Optional[Path]:
    exe = "ollama.exe" if WIN else "ollama"
    root = root or ollama_program_dir()
    for c in (root / exe, root / "bin" / exe, root / "Contents" / "Resources" / "ollama"):
        if c.exists():
            return c
    p = shutil.which("ollama")
    if p:
        return Path(p)
    if WIN:
        c = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if c.exists():
            return c
    return None


def _find(root: Path, name: str) -> Optional[Path]:
    for p in root.rglob(name):
        if p.is_file():
            return p
    return None


def start_server(url: Optional[str] = None, wait: float = 40.0, *, program_dir=None, model_dir=None, gpu=None) -> bool:
    url = url or settings()["ollama_url"]
    if reachable(url):
        return True
    exe = binary(program_dir) if program_dir else binary()
    if not exe or not is_local(url):
        return False
    host = urllib.parse.urlparse(url)
    chosen=(read_json(paths.SETTINGS,{}) or {}).get('models_dir')
    env = {**os.environ, "OLLAMA_HOST": f"{host.hostname}:{host.port or 11434}", "OLLAMA_MODELS": str(model_dir or ((Path(chosen) if chosen else paths.DATA/'models') / 'ollama')),
           "OLLAMA_KEEP_ALIVE": "10m"}
    from . import gpuassign
    env.update(gpuassign.child_env(gpu) if gpu is not None else gpuassign.job_env("ai"))     # only a card Video Tool may use: the one chosen for this job, or a number given
    if (program_dir or model_dir) and not WIN:                                          # our own copy keeps its identity key and history in its own folder, not in the person's home folder
        home = paths.DATA / "engines" / "ollama-home"
        home.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(home)
    kw: dict[str, Any] = {"creationflags": 0x08000000 | 0x00000008} if WIN else {"start_new_session": True}   # detached: survives this process
    proc = subprocess.Popen([str(exe), "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, **kw)
    if getattr(proc, "pid", None):
        from .engines import pids

        pids.remember("ollama", proc.pid, host.port or 11434)                          # so a change of card can restart exactly this program, and nothing else
    t0 = time.time()
    while time.time() - t0 < wait:
        if reachable(url):
            return True
        time.sleep(0.5)
    return False


def _download(url: str, dest: Path, progress: Callable[[float], None]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        got = 0
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
                got += len(chunk)
                if total:
                    progress(got / total)


def install_local(progress: ProgressFn = noop_progress, *, program_dir=None) -> Path:
    """Download a portable Ollama into <data>/ollama (about 1.5 GB on Windows, 175 MB on macOS)."""
    exe = binary(program_dir) if program_dir else binary()
    if exe:
        return exe
    dest = program_dir or ollama_program_dir()
    with tempfile.TemporaryDirectory() as d:
        arc = Path(d) / Path(_ASSET).name
        progress("llm", 0.0, "Downloading the local AI engine")
        try:
            _download(_ASSET, arc, lambda f: progress("llm", f * 0.6, f"Downloading the local AI engine {int(f * 100)}%"))
        except Exception as e:
            raise LLMUnavailable(f"Could not download the local AI engine ({type(e).__name__}). Check the internet connection.") from e
        progress("llm", 0.62, "Unpacking")
        dest.mkdir(parents=True, exist_ok=True)
        tar = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe") if WIN else "tar"
        args = [tar, "-xf", str(arc), "-C", str(dest)]
        if arc.name.endswith(".zst"):
            args = [tar, "--zstd", "-xf", str(arc), "-C", str(dest)]
        r = subprocess.run(args, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        if r.returncode != 0:
            raise LLMUnavailable("Could not unpack the local AI engine: " + (r.stderr or "")[-200:])
    exe = (binary(program_dir) if program_dir else binary()) or _find(dest, "ollama.exe" if WIN else "ollama")
    if not exe:
        raise LLMUnavailable("The downloaded package did not contain Ollama.")
    if not WIN:
        exe.chmod(0o755)
    return exe


def pull(model: str, progress: ProgressFn = noop_progress, base: float = 0.0, span: float = 1.0, *, url=None) -> None:
    url = url or settings()["ollama_url"]
    last = 0.0
    try:
        with httpx.stream("POST", url + "/api/pull", json={"model": model, "stream": True}, timeout=None) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                j = json.loads(line)
                if j.get("error"):
                    raise LLMUnavailable(j["error"])
                if j.get("total"):
                    f = j.get("completed", 0) / j["total"]
                    if f - last >= 0.01 or f >= 1:
                        last = f
                        progress("llm", base + span * f, f"Downloading the local AI model {int(f * 100)}%")
    except httpx.HTTPError as e:
        raise LLMUnavailable(f"Could not download the model '{model}' ({type(e).__name__}).") from e


def status() -> dict[str, Any]:
    s = settings()
    up = reachable(s["ollama_url"])
    model = model_name()
    return {
        **s, "model": model, "recommended": recommend_model(), "reachable": up, "local": is_local(s["ollama_url"]),
        "engine_installed": bool(binary()), "model_ready": bool(up and has_model(model)), "gpu_mb": gpu_memory_mb(),
        "models": installed_models(s["ollama_url"]) if up else [],
    }


def ensure_ready(progress: ProgressFn = noop_progress, allow_download: Optional[bool] = None, *, storage=None, model=None) -> str:
    """Make a model answer questions: start/install the server, pull the model. Returns the model name or raises LLMUnavailable."""
    s = settings()
    if s["llm_mode"] == "off":
        raise LLMUnavailable("The local AI is turned off in Settings.")
    allow = s["llm_auto_download"] if allow_download is None else allow_download
    url = storage['url'] if storage else s["ollama_url"]
    model = model or model_name()
    program_dir=Path(storage.get('install_dir') or paths.DATA/'engines')/'ollama' if storage else None
    model_dir=Path(storage.get('models_dir') or paths.DATA/'models')/'ollama' if storage else None
    if not reachable(url):
        if not is_local(url):
            raise LLMUnavailable(f"The Ollama server at {url} does not answer.")
        if not (binary(program_dir) if program_dir else binary()):
            if not allow:
                raise LLMUnavailable("The local AI engine is not installed.")
            install_local(progress,program_dir=program_dir) if storage else install_local(progress)
        progress("llm", 0.64, "Starting the local AI engine")
        started=start_server(url,program_dir=program_dir,model_dir=model_dir,gpu=storage.get('gpu')) if storage else start_server(url)
        if not started:
            raise LLMUnavailable("The local AI engine did not start.")
    if not has_model(model, url):
        if not allow:
            raise LLMUnavailable(f"The model '{model}' is not downloaded.")
        pull(model, progress, 0.65, 0.35,url=url) if storage else pull(model, progress, 0.65, 0.35)
    return model


_ROOM = {"at": 0.0}
ROOM_GB = 6.0                                       # the language model and its context need about this much of the card


def make_room(url: Optional[str] = None) -> bool:
    """Before the local AI answers: when ComfyUI runs on the same computer and leaves less than ROOM_GB of the card free, ask it to unload
    (the next picture loads its model again, ~40 s from an SSD). At most once a minute. Returns True when it asked."""
    if time.time() - _ROOM["at"] < 60:
        return False
    _ROOM["at"] = time.time()
    host = urllib.parse.urlparse(url or settings()["ollama_url"]).hostname or ""
    comfy = str((read_json(paths.SETTINGS, {}) or {}).get("comfy_url") or "")
    chost = urllib.parse.urlparse(comfy).hostname or ""
    same = host == chost or (is_local(f"http://{host}") and is_local(f"http://{chost}"))
    if not comfy or not same:
        return False
    try:
        devs = [d for d in httpx.get(comfy.rstrip("/") + "/system_stats", timeout=3).json().get("devices", []) if d.get("type") == "cuda"]
        if devs and min(float(d.get("vram_free", 0)) for d in devs) / 1e9 < ROOM_GB:
            httpx.post(comfy.rstrip("/") + "/free", json={"unload_models": True, "free_memory": True}, timeout=10)
            return True
    except Exception:                                                   # noqa: BLE001
        pass
    return False


def release(url: Optional[str] = None) -> list[str]:
    """Unload the models this Ollama holds on its card, so a picture model on the same card gets the room (one-card computers). Best effort;
    returns what was unloaded. The next question loads the model again in a few seconds."""
    base = (url or settings()["ollama_url"]).rstrip("/")
    try:
        loaded = [m["name"] for m in httpx.get(base + "/api/ps", timeout=3).json().get("models", []) if m.get("size_vram")]
        for name in loaded:
            httpx.post(base + "/api/generate", json={"model": name, "keep_alive": 0}, timeout=30)
        return loaded
    except Exception:                                                   # noqa: BLE001
        return []


# --------------------------------------------------------------------------- chat
def chat_json(messages: list[dict], schema: dict, *, model: Optional[str] = None, temperature: float = 0.2, num_ctx: int = 8192,
              timeout: float = 600, max_tokens: int = 2048) -> dict:
    """One structured answer. `schema` is enforced by the server while it generates, so the reply is always valid JSON of that shape."""
    s = settings()
    body = {"model": model or model_name(), "messages": messages, "stream": False, "think": False, "format": schema, "keep_alive": "10m",
            "options": {"temperature": temperature, "num_ctx": num_ctx, "num_predict": max_tokens}}
    from .ai import talk

    began = time.time()
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    prompt = "\n\n".join(m["content"] for m in messages if m["role"] != "system")
    try:
        make_room(s["ollama_url"])                                     # one card: the pictures' models step aside while the AI reads
        r = httpx.post(s["ollama_url"] + "/api/chat", json=body, timeout=timeout)
        r.raise_for_status()
        answer = r.json()["message"]["content"]
        talk.record("ollama", body["model"], system=system, prompt=prompt, answer=answer, seconds=time.time() - began)
        return json.loads(answer)
    except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
        from .ai.failures import service_failure

        talk.record("ollama", body["model"], system=system, prompt=prompt, seconds=time.time() - began, error=f"{type(e).__name__}: {e}")
        raise LLMUnavailable(service_failure("The local AI", e, local=True)) from e
