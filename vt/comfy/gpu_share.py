"""One GPU, two jobs: video generation needs the memory an idle Ollama model is still holding.

Ollama keeps a model resident for OLLAMA_KEEP_ALIVE after its last answer. When it runs on the same machine as ComfyUI, those models sit on the GPU the
clip is about to use. Before a clip is queued the app asks that Ollama to unload (`keep_alive: 0`, Ollama's own documented way); it reloads by itself
on the next question, so nothing else changes. Anything that goes wrong here is ignored: a clip is never blocked by it.
"""
from __future__ import annotations

from urllib.parse import urlparse

import httpx


def same_machine(comfy_url: str, ollama_url: str) -> bool:
    return bool(urlparse(comfy_url).hostname) and urlparse(comfy_url).hostname == urlparse(ollama_url).hostname


def release_ollama_models(ollama_url: str) -> list[str]:
    """Unload every model Ollama has loaded; returns their names. Never raises."""
    unloaded = []
    try:
        with httpx.Client(base_url=ollama_url.rstrip("/"), timeout=10) as http:
            for model in http.get("/api/ps").json().get("models", []):
                name = model.get("name") or model.get("model")
                if name and http.post("/api/generate", json={"model": name, "keep_alive": 0}).status_code == 200:
                    unloaded.append(name)
    except Exception:
        pass
    return unloaded
