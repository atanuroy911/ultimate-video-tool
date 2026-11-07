"""The first-run setup (docs/plans/PLAN-ENGINES-AND-SETUP.MD section 3.2): seven steps, left and resumed at will. This module holds the person's choices; the screens are in the Studio."""
from __future__ import annotations

from typing import Any, Optional

from .. import paths
from ..util import read_json, write_json
from . import hardware, installers, registry, store
from .model import Endpoint

STEPS = ["welcome", "storage", "choose", "cards", "connect", "install", "try", "done"]
CHOICES = ("local", "remote", "off")
ASKED = ("ollama", "comfy", "voicestudio")                     # the engines the wizard asks about; the Engine Server joins as a remote choice


def state() -> dict[str, Any]:
    s = (read_json(paths.SETTINGS, {}) or {}).get("setup") or {}
    return {"step": s.get("step", "welcome") if s.get("step") in STEPS else "welcome", "done": bool(s.get("done")), "choices": s.get("choices", {}), "bundles": s.get("bundles", ["pictures"]),
            "models_dir": (read_json(paths.SETTINGS, {}) or {}).get("models_dir", ""),
            "install_dir": (read_json(paths.SETTINGS, {}) or {}).get("install_dir", ""),
            'gpu':pictures_card()}


def save(*, step: Optional[str] = None, choices: Optional[dict[str, str]] = None, bundles: Optional[list[str]] = None, models_dir: Optional[str] = None, install_dir: Optional[str] = None, gpu: Optional[int] = None, done: Optional[bool] = None) -> dict[str, Any]:
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
        s["models_dir"] = storage_path(models_dir)
    if install_dir is not None:
        s['install_dir'] = storage_path(install_dir)
    if gpu is not None and (not isinstance(gpu,int) or not 0<=gpu<=16):
        raise ValueError('Choose a graphics card on the processing server.')            # a card for one install can still be named, but nothing is stored: the cards are chosen in vt/gpuassign.py
    s["setup"] = cur
    write_json(paths.SETTINGS, s)
    return state()


def storage_path(value):
    from pathlib import Path
    value=value.strip()
    if not value:return ''
    path=Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError('Choose an absolute folder path on the processing server, not on the client PC.')
    return str(path.resolve())


def pictures_card() -> Optional[int]:
    """The card our own picture engine is built for and started on: the one chosen for the "pictures" job (vt/gpuassign.py), None when there is none."""
    try:
        from .. import gpuassign

        card, _ = gpuassign.resolve("pictures")
        return card["index"] if card else None
    except Exception:
        return None


def _recommended_gpu(hw: dict[str, Any]) -> Optional[int]:
    """The newest card among those Video Tool may use (never one the person kept out of reach)."""
    try:
        from .. import gpuassign

        may = {c['index'] for c in gpuassign.allowed()}
        cards = [g for g in hw.get('gpus', []) if g.get('index') in may]
    except Exception:
        cards = hw.get('gpus', [])
    return max(cards, key=lambda g: g['compute'], default={}).get('index')


def _server_name() -> str:
    """The name this server goes by (its --name), the same everywhere; the computer's name only when it has none."""
    try:
        from ..server.serve import STATE

        return STATE.get("name") or socket.gethostname()
    except Exception:
        return socket.gethostname()


def overview() -> dict[str, Any]:
    import socket
    from . import placement
    from concurrent.futures import ThreadPoolExecutor
    hw = hardware.detect()
    st = state()
    names = ('comfy', 'ollama')
    with ThreadPoolExecutor(max_workers=len(names)) as pool:                       # each engine's addresses cost a second when nothing answers: ask both at once
        existing = dict(zip(names, pool.map(placement.find_existing, names)))
    return {**st, 'recommended_gpu':_recommended_gpu(hw), 'server':{'name':_server_name(),'data_dir':str(paths.DATA),'os':__import__('platform').system()},
            'existing':existing,
            "hardware": hw, "recommended": {k:v for k,v in hardware.recommend(hw).items() if k in ASKED}, "engines": [{"id": e.id, "label": e.label, "about": e.about, "local_install": e.local_install, "installable": e.id in installers.INSTALLERS,
                                                                                  "mode": registry.endpoint(e.id).mode} for e in registry.engines() if e.id in ASKED],
            "bundle_catalog": {k: [p.rsplit("/", 1)[-1] for p in v] for k, v in installers.BUNDLES.items()}, "steps": STEPS}


def plans(engines: list[str], bundles: list[str], config=None) -> list[dict[str, Any]]:
    out = []
    for e in engines:
        kw = install_options(e,bundles,config)
        out.append(installers.installer(e, **kw).plan().public())
    return out


def run_install(engines: list[str], bundles: list[str], progress, config=None) -> dict[str, Any]:
    """Install each chosen engine here, start it, and point the registry at it (mode local). Stops at the first failure and says which engine."""
    result: dict[str, Any] = {}
    for i, e in enumerate(engines):
        kw = install_options(e,bundles,config)
        inst = installers.installer(e, **kw)
        base, span = i / len(engines), 1 / len(engines)
        inst.install(lambda stage, f, m="", b=base, s=span: progress(e, b + s * f, m))
        url = inst.start()
        if url:
            store.save(e, Endpoint(mode="local", url=url))
            registry.forget(e)
            if e in store.LEGACY:
                settings=read_json(paths.SETTINGS,{}) or {}
                settings[store.LEGACY[e]]=url
                write_json(paths.SETTINGS,settings)
        result[e] = {"installed": True, "url": url or registry.endpoint(e).url}
    return result


def install_options(engine,bundles,config=None):
    from pathlib import Path
    from . import placement
    config=state() if config is None else config
    root=Path(config.get('install_dir') or paths.DATA/'engines')
    if engine=='comfy':
        from urllib.parse import urlparse
        from . import fit
        hw=hardware.detect();cards=hw.get('gpus',[])
        card=next((g for g in cards if g['index']==config.get('gpu')),None) or max(cards,key=lambda g:g['compute'],default={})
        choice=fit.choose(fit.Card(name=card.get('name',''),compute=card.get('compute',0),vram_gb=card.get('memory_gb',0)*2**30/1e9,ram_gb=hw['ram_gb']))
        return {'bundles':tuple(bundles),'root':root/'comfyui','models':config.get('models_dir',''),
                'gpu':config.get('gpu'),'recipe':choice.recipe or '',
                'port':urlparse(placement.own_url('comfy')).port}
    if engine=='ollama':
        return {'storage':{**config,'url':placement.own_url('ollama')}}
    return {}


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
