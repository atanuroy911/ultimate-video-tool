"""Make a ComfyUI the person chose ready for Video Tool: the picture set that fits its card, put in its own model folders, checked, remembered.

    plan(url)          what would be downloaded and where; touches nothing
    prepare(url)       download what is missing (resumable, checksummed), check the graph runs there, point Video Tool at it

The model folders come from the instance itself (/internal/folder_paths), so files land where that ComfyUI already looks, whatever its
extra_model_paths.yaml says. Nothing of the install is edited: no custom nodes, no settings, no restart. ComfyUI sees new files by itself.
Writing files needs this computer to be the one ComfyUI runs on; for one elsewhere, Video Tool's server must be installed there.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable, Optional

from .. import paths
from ..util import read_json, write_json
from . import discover, fit

Progress = Callable[[float, str], None]


def _installed(info: dict) -> set[str]:
    """Model file names the instance already lists, for the loaders the picture graph uses."""
    from ..comfy import ComfyClient

    have: set[str] = set()
    try:
        oi = ComfyClient(info["url"]).object_info()
    except Exception:                                                   # noqa: BLE001
        return have
    for cls, field in (("UNETLoader", "unet_name"), ("CLIPLoader", "clip_name"), ("VAELoader", "vae_name")):
        spec = (oi.get(cls) or {}).get("input", {}).get("required", {}).get(field)
        if spec and isinstance(spec[0], list):
            have.update(spec[0])
    return have


def _folder(info: dict, kind: str) -> Optional[Path]:
    """Where a file of this kind goes: the first folder ComfyUI reads it from that exists (or can be made) and can be written to."""
    names = {"diffusion_models": ["diffusion_models", "unet"], "text_encoders": ["text_encoders", "clip"], "vae": ["vae"]}[kind]
    for name in names:
        for p in info.get("model_folders", {}).get(name, []):
            path = Path(p)
            if path.exists() and os.access(path, os.W_OK):
                return path
    for name in names:
        for p in info.get("model_folders", {}).get(name, []):
            path = Path(p)
            if path.parent.exists() and os.access(path.parent, os.W_OK):
                return path
    return None


def plan(url: str, recipe: str = "") -> dict:
    url = url.rstrip("/")
    info = discover.probe_comfy(url)
    if info is None:
        raise RuntimeError(f"no ComfyUI answers at {url}")
    host = url.split("//", 1)[-1].rsplit(":", 1)[0].strip("[]")
    local = discover.is_local(host)
    choice = fit.BY_ID.get(recipe) if recipe else None
    fitted = info["fit"]
    if choice is None:
        if not fitted["recipe"]:
            raise RuntimeError(fitted["why"])
        choice = fit.BY_ID[fitted["recipe"]]
    have = _installed(info)
    files = []
    for f in choice.files():
        name = f.rsplit("/", 1)[-1]
        dest = _folder(info, f.split("/")[0]) if local else None
        files.append({"file": name, "kind": f.split("/")[0], "gb": round(fit.FILES[f]["size"] / fit.GB, 1), "have": name in have, "to": str(dest / name) if dest else ""})
    todo = [x for x in files if not x["have"]]
    problems = []
    if todo and not local:
        problems.append(f"{len(todo)} file(s) must be put on that computer. Install Video Tool's server there (it finds this ComfyUI by itself), or copy them into its models folder.")
    if local and any(not x["to"] for x in todo):
        problems.append("this ComfyUI's model folders cannot be written to by Video Tool (check their permissions)")
    if local and todo:
        first = Path(next(x["to"] for x in todo if x["to"])).parent if any(x["to"] for x in todo) else Path.home()
        free = shutil.disk_usage(first if first.exists() else first.parent).free / fit.GB
        need = sum(x["gb"] for x in todo)
        if free < need + 2:
            problems.append(f"{need:.0f} GB to download but only {free:.0f} GB free in {first}")
    return {"url": url, "instance": {k: info[k] for k in ("version", "gpu", "vram_gb", "ram_gb", "compute")}, "recipe": choice.id, "label": choice.label,
            "fit": fitted if fitted["recipe"] == choice.id else fit.check(choice, fit.card_from_stats({"system": {"ram_total": info["ram_gb"] * fit.GB},
                                                                                                   "devices": [{"type": "cuda", "name": info["gpu"], "vram_total": info["vram_gb"] * fit.GB}]})),
            "files": files, "download_gb": round(sum(x["gb"] for x in todo), 1), "local": local, "problems": problems}


def prepare(url: str, recipe: str = "", progress: Progress = lambda f, m: None, save: bool = True) -> dict:
    """Download what the chosen picture set is missing into this ComfyUI, check the graph against it, and make it the picture server."""
    from ..comfy import ComfyClient, picture_workflow
    from .installers import fetch

    p = plan(url, recipe)
    if p["problems"]:
        raise RuntimeError(" ".join(p["problems"]))
    r = fit.BY_ID[p["recipe"]]
    todo = [x for x in p["files"] if not x["have"]]
    for i, x in enumerate(todo):
        src = fit.FILES[f"{x['kind']}/{x['file']}"]
        fetch(src["url"], Path(x["to"]), size=src["size"], digest=src.get("sha256", ""),
              progress=lambda f, i=i, n=x["file"]: progress(0.02 + 0.9 * (i + f) / len(todo), f"Downloading {n} {int(f * 100)}%"))
    progress(0.94, "Checking the picture workflow on this ComfyUI")
    client = ComfyClient(p["url"])
    problems = picture_workflow(r.id).problems(client.object_info())
    if problems:
        raise RuntimeError("the picture workflow cannot run there yet: " + "; ".join(problems[:3]))
    if save:
        use(p["url"], r.id)
    progress(1.0, f"Ready: {r.label} on {p['instance']['gpu'] or p['url']}")
    return {**p, "ready": True}


def use(url: str, recipe: str) -> None:
    """Make this ComfyUI the picture server, with this picture set. The engine store and the flat setting the older code reads."""
    from . import hub, store
    from .model import Endpoint

    before = store.load("comfy")
    workers = [w for w in before.workers if w != url and hub.reachable("comfy", w, 2.0)]          # a worker that is gone (stopped, moved) is dropped
    store.save("comfy", Endpoint(mode="remote", url=url, key=before.key, gpu=before.gpu, workers=workers))
    s = read_json(paths.SETTINGS, {}) or {}
    s.update(comfy_url=url, picture_recipe=recipe)
    write_json(paths.SETTINGS, s)
