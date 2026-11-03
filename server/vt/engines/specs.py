"""The engines the app knows. Each `check` answers one question: is it there, what can it do, which models does it have."""
from __future__ import annotations

import httpx

from .model import Endpoint, EngineSpec, Health


def _get(ep: Endpoint, path: str, key: bool = False, timeout: float = 6.0):
    headers = {"Authorization": f"Bearer {ep.key}"} if (key and ep.key) else {}
    return httpx.get(ep.url.rstrip("/") + path, headers=headers, timeout=timeout, follow_redirects=True)


def check_ollama(ep: Endpoint) -> Health:
    r = _get(ep, "/api/tags")
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200 or "models" not in body:
        return Health(ok=False, why_not=str(body.get("error") or f"HTTP {r.status_code}")[:200])
    models = [{"id": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1)} for m in body["models"]]
    try:
        version = _get(ep, "/api/version").json().get("version", "")
    except Exception:                                                               # noqa: BLE001
        version = ""
    vision = any("vl" in m["id"] or "vision" in m["id"] for m in models)
    return Health(ok=True, version=version, models=models, capabilities=["llm.chat", "llm.vision"] if vision else ["llm.chat"])


def _gpu_name(raw: str) -> str:
    """'cuda:0 Tesla V100-PCIE-16GB : cudaMallocAsync' -> 'Tesla V100-PCIE-16GB'."""
    import re

    m = re.match(r"^(?:cuda:\d+\s+)?(.*?)(?:\s*:\s*\S+)?$", raw.strip())
    return (m.group(1) if m else raw).strip()


def check_comfy(ep: Endpoint) -> Health:
    """The main server, then each worker: capabilities are the union, and every workflow says which server can run it."""
    main = _check_comfy_one(ep)
    caps = set(main.capabilities)
    for url in ep.workers:
        try:
            w = _check_comfy_one(Endpoint(mode="remote", url=url))
        except Exception as e:                                                      # noqa: BLE001 - one worker that is down must not hide the others
            main.models.append({"id": url, "label": f"worker {url}", "ready": False, "why": f"{type(e).__name__}: {str(e)[:100]}"})
            continue
        if not w.ok:
            main.models.append({"id": url, "label": f"worker {url}", "ready": False, "why": w.why_not})
            continue
        caps |= set(w.capabilities)
        main.models += [{**m, "worker": url, "label": f"{m.get('label', m['id'])} (worker {w.gpu or url})"} for m in w.models]
    main.capabilities = sorted(caps)
    return main


def _check_comfy_one(ep: Endpoint) -> Health:
    r = _get(ep, "/system_stats")
    if r.status_code != 200:
        return Health(ok=False, why_not=f"HTTP {r.status_code}")
    d = r.json()
    dev = (d.get("devices") or [{}])[0]
    nodes = _get(ep, "/object_info", timeout=20).json()
    version = d.get("system", {}).get("comfyui_version", "")
    missing = [n for n in ("CLIPLoader", "KSampler", "SaveImage") if n not in nodes]
    if missing:
        return Health(ok=False, why_not="ComfyUI is running but lacks core nodes: " + ", ".join(missing), version=version)
    from ..comfy import list_workflows

    caps: list[str] = []
    models = []
    for w in list_workflows(None):
        bad = w.problems(nodes)
        models.append({"id": w.id, "label": w.label, "ready": not bad, "why": "; ".join(bad[:2])})
        if not bad:
            caps.append({"image": "image.generate", "audio": "voice.speak"}.get(w.kind, "video.generate"))
    return Health(ok=True, version=version, gpu=_gpu_name(dev.get("name", "")), models=models, capabilities=sorted(set(caps)))


def check_voicestudio(ep: Endpoint) -> Health:
    r = _get(ep, "/health")
    if r.status_code != 200:
        return Health(ok=False, why_not="VoiceStudio is still starting" if r.status_code == 503 else f"HTTP {r.status_code}")
    if not ep.key:
        return Health(ok=True, note="reachable; add the API key to use it", capabilities=[])
    t = _get(ep, "/engines/tts", key=True)
    if t.status_code in (401, 403):
        return Health(ok=False, why_not="the API key was refused")
    d = t.json()
    active = d.get("active", "")
    backends = d.get("backends", [])
    gpu = next((b.get("execution_evidence", {}).get("gpu_name") for b in backends if b.get("id") == active), "") or ""
    models = _get(ep, "/models", key=True).json().get("models", [])
    mine = [{"id": m["repo_id"], "role": m["role"], "size_gb": m.get("size_gb"), "installed": bool(m.get("installed")),
             "licence": (m.get("license_info") or {}).get("license_category", ""), "accepted": (m.get("license_acceptance") or {}).get("accepted")} for m in models]
    ready = [b["id"] for b in backends if b.get("available")]
    caps = ["voice.speak", "voice.list"]
    if any(b.get("supports_cloning") and b.get("available") for b in backends):
        caps.append("voice.clone")
    if any(b.get("supports_voice_design") and b.get("available") for b in backends):
        caps.append("voice.design")
    need = [m for m in mine if m["id"] == "k2-fsa/OmniVoice" and not m["accepted"]]
    note = "The default voice model has a non-commercial licence that has not been accepted yet; accept it in VoiceStudio's Model Catalogue, or use another voice engine."
    return Health(ok=True, gpu=gpu, models=mine, capabilities=caps, note=note if need else "engines ready: " + ", ".join(ready))


def check_vtengine(ep: Endpoint) -> Health:
    from . import vtengine

    return vtengine.check(ep)


SPECS: dict[str, EngineSpec] = {s.id: s for s in (
    EngineSpec("ollama", "llm", "Language AI (Ollama)", "Writes the script's plan and reads what a video is about. Any Ollama server works.",
               ("llm.chat",), default_url="http://127.0.0.1:11434", check=check_ollama, local_install="Download Ollama and a small model"),
    EngineSpec("comfy", "image", "Pictures and clips (ComfyUI)", "Draws a picture for each sentence and makes short silent clips.",
               ("image.generate", "video.generate"), default_url="http://127.0.0.1:8188", check=check_comfy, local_install=""),
    EngineSpec("voicestudio", "voice", "Voices (VoiceStudio)", "Speaks the script in any voice, clones a voice from a short recording, designs a voice from a description.",
               ("voice.speak", "voice.list", "voice.clone", "voice.design"), default_url="http://127.0.0.1:3900", needs_key=True, check=check_voicestudio, local_install=""),
    EngineSpec("vtengine", "custom", "Another Video Tool computer", "Uses the voices and speech recognition of another computer that runs Video Tool's engine server (vt serve-engine).",
               ("voice.speak", "asr.transcribe"), default_url="", needs_key=True, check=check_vtengine, local_install=""),
)}
