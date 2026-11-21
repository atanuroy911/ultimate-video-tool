"""The first-run setup (docs/plans/PLAN-ENGINES-AND-SETUP.MD section 3.2): seven steps, left and resumed at will. This module holds the person's choices; the screens are in the Studio."""
from __future__ import annotations

import socket
from typing import Any, Optional

from .. import paths
from ..util import read_json, write_json
from . import hardware, installers, registry, store
from .model import Endpoint

STEPS = ["welcome", "storage", "choose", "cards", "connect", "install", "try", "done"]
CHOICES = ("local", "remote", "off")
ASKED = ("ollama", "comfy")                     # the engines the wizard asks about; the Engine Server joins as a remote choice


def state() -> dict[str, Any]:
    s = (read_json(paths.SETTINGS, {}) or {}).get("setup") or {}
    from . import store

    settled = all(store.configured(e) for e in ASKED)                   # every engine was already chosen (the launcher's flags do this): nothing is left to ask, so no "Set up server" nag
    return {"step": s.get("step", "welcome") if s.get("step") in STEPS else "welcome", "done": bool(s.get("done")) or settled, "choices": s.get("choices", {}), "bundles": s.get("bundles", ["pictures"]),
            "models_dir": (read_json(paths.SETTINGS, {}) or {}).get("models_dir", ""),
            "install_dir": (read_json(paths.SETTINGS, {}) or {}).get("install_dir", ""),
            "picture_model": s.get("picture_model", ""), "language_model": s.get("language_model", ""),
            'gpu':pictures_card()}


def save(*, step: Optional[str] = None, choices: Optional[dict[str, str]] = None, bundles: Optional[list[str]] = None, models_dir: Optional[str] = None, install_dir: Optional[str] = None, gpu: Optional[int] = None, done: Optional[bool] = None,
         picture_model: Optional[str] = None, language_model: Optional[str] = None) -> dict[str, Any]:
    from . import fit

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
    if picture_model is not None:
        if picture_model and picture_model not in fit.BY_ID:
            raise ValueError("Choose one of the picture models offered.")
        cur["picture_model"] = picture_model
    if language_model is not None:
        if language_model and language_model not in dict(fit.LANGUAGE):
            raise ValueError("Choose one of the language models offered.")
        cur["language_model"] = language_model
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


def _card(hw: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """The card our own engines would be built for: the one chosen for pictures, else the newest."""
    cards = hw.get("gpus", [])
    return next((g for g in cards if g["index"] == config.get("gpu")), None) or max(cards, key=lambda g: g["compute"], default={})


# One line a person understands, under each model's name: what it is good at, and how long it takes where that was measured.
PLAIN = {
    "klein-4b": "Best pictures, about 9 seconds each on a 12 GB card.",
    "klein-4b-fp8": "Nearly the same pictures in half the memory.",
    "klein-4b-q4": "Good pictures made to fit 6 GB cards, about 17 seconds each.",
    "klein-4b-q3": "A little rougher, for when another program also uses the card.",
    "qwen21-turbo": "Finest detail of real things, but about 5 times slower.",
    "zimage-full": "Very good pictures, for 24 GB cards.",
    "zimage-fp8": "Very good pictures for 12 and 16 GB cards.",
    "zimage-fp8-small-text": "For computers with little memory to spare.",
    "zimage-nvfp4": "Made for the newest cards (RTX 50 series).",
    "gemma3:12b": "Best writing. Needs a 12 GB card to be quick.",
    "gemma3:4b": "Good writing, quick on most cards.",
    "gemma3:1b": "Basic writing, for small computers.",
    "gemma4:e4b": "Newer, but slower here, and it left a Bangla video nearly empty in our tests.",
    "gemma4:e2b": "The best fit for 6 to 8 GB cards: about twice as fast, and it picked the most sensible pictures in our tests.",
    "qwen3.5:4b": "Strong English, but slower on long plans and less reliable in our tests.",
}
LABELS = {"gemma3:12b": "Gemma 3 12B", "gemma3:4b": "Gemma 3 4B", "gemma3:1b": "Gemma 3 1B", "gemma4:e4b": "Gemma 4 E4B", "gemma4:e2b": "Gemma 4 E2B", "qwen3.5:4b": "Qwen 3.5 4B"}


def model_choices(hw: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Every model the wizard can install, each marked against this computer's card: fits and fast, fits but slow, or too big.
    The recommended one is what fit.py would pick by itself; the person may pick another that fits."""
    from . import fit

    card = _card(hw, config)
    vram = card.get("memory_gb", 0) * 2**30 / 1e9
    c = fit.Card(name=card.get("name", ""), compute=card.get("compute", 0), vram_gb=vram, ram_gb=hw.get("ram_gb", 0))
    best = fit.choose(c)
    checks = best.options or [fit.check(r, c) for r in fit.PICTURES]
    speed = {"resident": "fast", "sequential": "fast", "partial": "slow"}
    pictures = []
    rank = {"resident": 0, "sequential": 0, "partial": 1, "": 2}           # what runs well first, then what works slowly, then what does not fit
    for o in sorted(checks, key=lambda o: (rank.get(o["mode"] if vram > 0 else "", 2), -o["quality"])):
        r = fit.BY_ID[o["recipe"]]
        mode = o["mode"] if vram > 0 else ""
        if mode:
            why = ""
        elif vram <= 0:
            why = "Needs an NVIDIA graphics card."
        elif r.min_compute and c.compute < r.min_compute:
            why = "Needs a newer card (RTX 50 series)."
        else:
            why = f"Needs a bigger graphics card than {c.size} GB."
        if mode == "partial":
            why = f"Bigger than the {c.size} GB card: part of it waits in memory, so each picture takes several times longer."
        pictures.append({"id": r.id, "label": r.label, "note": PLAIN.get(r.id, r.note), "download_gb": r.download_gb(), "fits": bool(mode), "speed": speed.get(mode, ""),
                         "seconds": r.seconds, "recommended": r.id == best.recipe, "why": why})
    lang_best = fit.language_model(vram, hw.get("ram_gb", 0))["model"]
    language = []
    for name, need in fit.LANGUAGE:
        on_card = bool(vram) and need <= fit.usable(c)
        label = LABELS.get(name, name)
        language.append({"id": name, "label": label, "note": PLAIN.get(name, ""), "download_gb": fit.LANGUAGE_DOWNLOAD_GB.get(name, 0), "fits": True, "speed": "fast" if on_card else "slow",
                         "recommended": name == lang_best, "why": "" if on_card else ("Bigger than the graphics card: part of it runs on the processor, a few times slower." if vram else "Runs on the processor (no graphics card), a few times slower.")})
    return {"card": {"name": card.get("name", ""), "gb": c.size}, "pictures": pictures, "language": language,
            "clips": fit.clips_fit(vram, hw.get("ram_gb", 0)), "picture_default": best.recipe or "", "language_default": lang_best}


def chosen_picture_model(config: dict[str, Any], hw: Optional[dict[str, Any]] = None) -> str:
    """The person's picture model when it still fits the card, else the one fit.py picks."""
    m = model_choices(hw or hardware.detect(), config)
    want = config.get("picture_model") or ""
    best = next((p for p in m["pictures"] if p["id"] == m["picture_default"]), None)
    # a saved choice that only works slowly gives way when one that runs well fits (it was usually the old default, not a choice)
    return want if any(p["id"] == want and p["fits"] and (p["speed"] == "fast" or not best or best["speed"] != "fast") for p in m["pictures"]) else m["picture_default"]


def overview(same_computer: bool = False) -> dict[str, Any]:
    import socket
    from . import placement
    from concurrent.futures import ThreadPoolExecutor
    hw = hardware.detect()
    st = state()
    names = ('comfy', 'ollama')
    with ThreadPoolExecutor(max_workers=len(names)) as pool:                       # each engine's addresses cost a second when nothing answers: ask both at once
        existing = dict(zip(names, pool.map(placement.find_existing, names)))
    return {**st, 'same_computer': same_computer, 'models': model_choices(hw, st), 'recommended_gpu':_recommended_gpu(hw), 'server':{'name':_server_name(),'data_dir':str(paths.DATA),'os':__import__('platform').system()},
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
        try:
            inst.install(lambda stage, f, m="", b=base, s=span: progress(e, b + s * f, m))
        except Exception as err:                                      # noqa: BLE001 -- said in plain words; the job shows it with Try again
            raise RuntimeError(install_trouble(err, registry.spec(e).label if e in ("comfy", "ollama") else e)) from err
        url = inst.start()
        if url:
            store.save(e, Endpoint(mode="local", url=url))
            registry.forget(e)
            if e in store.LEGACY:
                settings=read_json(paths.SETTINGS,{}) or {}
                settings[store.LEGACY[e]]=url
                write_json(paths.SETTINGS,settings)
        if e == "comfy" and kw.get("recipe"):                         # pictures use the set installed for this card, not whatever else lies in the folder
            settings = read_json(paths.SETTINGS, {}) or {}
            settings["picture_recipe"] = kw["recipe"]
            write_json(paths.SETTINGS, settings)
        result[e] = {"installed": True, "url": url or registry.endpoint(e).url}
    return result


def install_trouble(err: BaseException, label: str) -> str:
    """What went wrong with an install, for a person: no internet, a full drive, or the program's own words."""
    import errno
    import socket

    text = f"{type(err).__name__}: {err}"
    chain = [err] + [c for c in (err.__cause__, err.__context__) if c]
    keep = " Press Try again: what already finished is kept."
    if any(isinstance(c, OSError) and c.errno == errno.ENOSPC for c in chain) or "No space left" in text or "not enough space" in text.lower():
        return f"The drive is full, so {label} could not finish. Free some space or choose another folder, then press Try again."
    if any(isinstance(c, socket.gaierror) for c in chain) or any(k in text for k in ("ConnectError", "ConnectTimeout", "ReadTimeout", "RemoteProtocolError",
                                                                                     "getaddrinfo", "Name or service not known", "No route to host",
                                                                                     "Connection reset", "Connection aborted", "timed out")):
        return f"The internet connection stopped while getting {label}. Check the connection." + keep
    return f"{label} could not be installed: {str(err)[:300]}" + keep


def install_options(engine,bundles,config=None):
    from pathlib import Path
    from . import placement
    config=state() if config is None else config
    root=Path(config.get('install_dir') or paths.DATA/'engines')
    if engine=='comfy':
        from urllib.parse import urlparse
        from . import fit
        return {'bundles':tuple(bundles),'root':root/'comfyui','models':config.get('models_dir',''),
                'gpu':config.get('gpu'),'recipe':chosen_picture_model(config),
                'port':urlparse(placement.own_url('comfy')).port}
    if engine=='ollama':
        return {'storage':{**config,'url':placement.own_url('ollama')},'model':config.get('language_model') or ''}
    return {}


def folders(path: str = "") -> dict[str, Any]:
    """The folders inside one folder on this server, for the folder picker (the person may sit at another computer, so a native dialog would show theirs).
    Only folder names are listed, never files. An empty path lists the drives (Windows) or / and the home folder."""
    import os
    import shutil
    import string
    from pathlib import Path

    def free(p: Path) -> float:
        try:
            return round(shutil.disk_usage(p).free / 1e9, 1)
        except OSError:
            return 0.0

    roots = [Path(f"{d}:\\") for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")] if os.name == "nt" else [Path("/"), Path.home()]
    root_list = [{"path": str(r), "name": str(r).rstrip("\\") or str(r), "free_gb": free(r)} for r in roots]
    if not path.strip():
        return {"path": "", "parent": "", "folders": [], "roots": root_list, "free_gb": 0.0, "writable": False}
    p = Path(path.strip()).expanduser()
    if not p.is_absolute():
        raise ValueError("Choose a full folder path, such as D:\\Video Tool.")
    while not p.exists() and p.parent != p:                                     # a folder not made yet: show the nearest one that exists
        p = p.parent
    out = []
    try:
        for e in sorted(os.scandir(p), key=lambda e: e.name.lower()):
            if len(out) >= 400:
                break
            try:
                if e.is_dir() and not e.name.startswith((".", "$")) and e.name not in ("System Volume Information", "Recovery", "PerfLogs"):
                    out.append({"name": e.name, "path": e.path})
            except OSError:
                continue
    except OSError:
        pass
    return {"path": str(p), "parent": "" if p.parent == p else str(p.parent), "folders": out, "roots": root_list, "free_gb": free(p), "writable": os.access(p, os.W_OK)}


def new_folder(parent: str, name: str) -> dict[str, Any]:
    """Make one folder inside an existing one, for the folder picker's New folder."""
    from pathlib import Path

    name = name.strip()
    if not name or any(ch in name for ch in '<>:"/\\|?*') or name in (".", ".."):
        raise ValueError('Use a folder name without / \\ : * ? " < > |.')
    p = Path(parent).expanduser()
    if not p.is_absolute() or not p.is_dir():
        raise ValueError("Open a folder first.")
    (p / name).mkdir(exist_ok=True)
    return folders(str(p / name))


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
    if engine_id == "comfy":
        return _try_picture()
    ready = [m for m in h.models if m.get("ready")]
    return {"ok": True, "says": f"Connected. {len(h.capabilities)} thing(s) it can do for you: {', '.join(h.capabilities) or 'none yet'}." + (f" {len(ready)} workflow(s) ready." if ready else "")}


TEST_PICTURE = "a red apple on a wooden kitchen table by a window, soft morning light, close-up"


def test_picture_path():
    return paths.DATA / "setup" / "test-picture.png"


def _try_picture() -> dict[str, Any]:
    """Draw one real picture with the set chosen for this card, so the person sees it work (and how long a picture takes)."""
    import time
    from ..comfy import ComfyClient, picture_workflow
    from ..comfy.client import output_files

    try:
        client = ComfyClient(registry.endpoint("comfy").url)
        oi = client.object_info()
        w = picture_workflow(object_info=oi)
        problems = w.problems(oi)
        if problems:
            return {"ok": False, "says": "It is running, but the picture model is not in place yet: " + problems[0]}
        graph, _ = w.patched(image="", prompt=TEST_PICTURE, aspect="9:16", seconds=0, seed=int(time.time()) % 100000, prefix="video_tool/setup-test")   # a new seed: ComfyUI would hand back the same picture without drawing
        started = time.time()
        entry = client.wait(client.submit(graph), None, lambda: False, 900)
        files = output_files(entry, w.output) or output_files(entry)
        if not files:
            return {"ok": False, "says": "It ran but made no picture."}
        dest = test_picture_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        client.download(files[0]["filename"], files[0]["subfolder"], files[0]["type"], dest)
        took = time.time() - started
        model = w.label.split(": ", 1)[-1]
        return {"ok": True, "says": f"Drew this test picture with {model} in {took:.0f} seconds." + (" The first picture is the slowest: the model was loading." if took > 25 else ""),
                "image": f"/api/setup/test-picture?t={int(time.time())}"}
    except Exception as e:                                                           # noqa: BLE001
        return {"ok": False, "says": f"It is running but could not draw: {str(e)[:160]}"}
