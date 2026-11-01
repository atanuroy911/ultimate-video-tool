"""The first-run setup (docs/plans/PLAN-ENGINES-AND-SETUP.MD section 3.2): seven steps, left and resumed at will. This module holds the person's choices; the screens are in the Studio."""
from __future__ import annotations

from typing import Any, Optional

from .. import paths
from ..util import read_json, write_json
from . import hardware, installers, registry, store
from .model import Endpoint

STEPS = ["welcome", "storage", "choose", "connect", "install", "try", "done"]
CHOICES = ("local", "remote", "off")
ASKED = ("ollama", "comfy", "voicestudio")                     # the engines the wizard asks about; the Engine Server joins as a remote choice


def state() -> dict[str, Any]:
    s = (read_json(paths.SETTINGS, {}) or {}).get("setup") or {}
    return {"step": s.get("step", "welcome") if s.get("step") in STEPS else "welcome", "done": bool(s.get("done")), "choices": s.get("choices", {}), "bundles": s.get("bundles", ["pictures"]),
            "models_dir": (read_json(paths.SETTINGS, {}) or {}).get("models_dir", "")}


def save(*, step: Optional[str] = None, choices: Optional[dict[str, str]] = None, bundles: Optional[list[str]] = None, models_dir: Optional[str] = None, done: Optional[bool] = None) -> dict[str, Any]:
    if step is not None and step not in STEPS:
        raise ValueError(f"step must be one of {STEPS}")
    for k, v in (choices or {}).items():
        if k not in ASKED or v not in CHOICES:
            raise ValueError(f"choice for '{k}' must be one of {CHOICES}")
    s = read_json(paths.SETTINGS, {}) or {}
    cur = dict(s.get("setup") or {})
    if step is not None:
        cur["step"] = step
    if choices:
        cur["choices"] = {**cur.get("choices", {}), **choices}
    if bundles is not None:
        cur["bundles"] = [b for b in bundles if b in installers.BUNDLES]
    if done is not None:
        cur["done"] = done
    if models_dir is not None:
        s["models_dir"] = models_dir.strip()
    s["setup"] = cur
    write_json(paths.SETTINGS, s)
    return state()


def overview() -> dict[str, Any]:
    hw = hardware.detect()
    st = state()
    return {**st, "hardware": hw, "recommended": hardware.recommend(hw), "engines": [{"id": e.id, "label": e.label, "about": e.about, "local_install": e.local_install, "installable": e.id in installers.INSTALLERS,
                                                                                  "mode": registry.endpoint(e.id).mode} for e in registry.engines() if e.id in ASKED],
            "bundles": {k: [p.rsplit("/", 1)[-1] for p in v] for k, v in installers.BUNDLES.items()}, "steps": STEPS}


def plans(engines: list[str], bundles: list[str]) -> list[dict[str, Any]]:
    out = []
    for e in engines:
        kw = {"bundles": tuple(bundles)} if e == "comfy" else {}
        out.append(installers.installer(e, **kw).plan().public())
    return out


def run_install(engines: list[str], bundles: list[str], progress) -> dict[str, Any]:
    """Install each chosen engine here, start it, and point the registry at it (mode local). Stops at the first failure and says which engine."""
    result: dict[str, Any] = {}
    for i, e in enumerate(engines):
        kw = {"bundles": tuple(bundles)} if e == "comfy" else {}
        inst = installers.installer(e, **kw)
        base, span = i / len(engines), 1 / len(engines)
        inst.install(lambda stage, f, m="", b=base, s=span: progress(e, b + s * f, m))
        url = inst.start() if not inst.verify() or e == "comfy" else None
        if url:
            store.save(e, Endpoint(mode="local", url=url))
            registry.forget(e)
        result[e] = {"installed": True, "url": url or registry.endpoint(e).url}
    return result


def try_it(engine_id: str) -> dict[str, Any]:
    """Step 6: one real sample of a connected engine, in plain words. Never raises: a failure is the answer."""
    h = registry.health(engine_id, fresh=True)
    if not h.ok:
        return {"ok": False, "says": f"{registry.spec(engine_id).label} does not answer: {h.why_not or 'not connected'}"}
    if engine_id == "ollama":
        import httpx

        ep = registry.endpoint("ollama")
        try:
            model = next(m["id"] for m in h.models)
            r = httpx.post(ep.url + "/api/generate", json={"model": model, "prompt": "Reply with the single word OK.", "stream": False, "options": {"num_predict": 8}}, timeout=180).json()
            return {"ok": bool(str(r.get("response", "")).strip()), "says": f"{model} answered: {str(r.get('response', '')).strip()[:60]}"}
        except StopIteration:
            return {"ok": False, "says": "It is running but has no model yet. Install one in Engines."}
        except Exception as e:                                                       # noqa: BLE001
            return {"ok": False, "says": f"It is running but could not answer: {str(e)[:120]}"}
    ready = [m for m in h.models if m.get("ready")]
    return {"ok": True, "says": f"Connected. {len(h.capabilities)} thing(s) it can do for you: {', '.join(h.capabilities) or 'none yet'}." + (f" {len(ready)} workflow(s) ready." if ready else "")}
