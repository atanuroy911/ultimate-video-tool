"""Where Video Tool's engines run, said in plain words: an Ollama or ComfyUI that was already running on this computer, and Video Tool's own copies (PLAN-PERFECT K3).

An engine that was there before Video Tool is never started, stopped or moved by it. When it sits on a graphics card Video Tool may not use, this says so, and offers Video Tool's
own copy (which starts on the card its job has: "ai" for Ollama, "pictures" for ComfyUI). Each row carries a `code` as well as the English sentence, so the Studio can say it
in the person's language.
"""
from __future__ import annotations

from typing import Any, Optional

from .. import paths
from . import pids, placement, store

LABEL = {"ollama": "Ollama", "comfy": "ComfyUI"}


def _names(cards: list[dict]) -> str:
    return ", ".join(f"{c['name']} ({c['gb']} GB)" if c.get("gb") else c["name"] for c in cards)


def _row(engine: str, gpus: list[dict], ok: set[str]) -> dict[str, Any]:
    from .. import llm

    label, endpoint, ours = LABEL[engine], store.load(engine), pids.running(engine)
    if endpoint.mode == "off" or not endpoint.url:
        source = "off"
    elif not llm.is_local(endpoint.url):
        source = "elsewhere"
    else:
        source = "own" if endpoint.mode == "local" else "existing"
    on = []
    for g in gpus:
        for p in g.get("programs", []):
            if p.get("label") != label:
                continue
            mine = ours is not None and p.get("pid") == ours
            if (source == "own") == mine:                                # our own copy's cards for "own", the others' for "existing"
                on.append({"index": g["index"], "name": g["name"], "gb": p.get("gb"), "allowed": g["uuid"] in ok, "ours": mine})
    blocked = [c for c in on if not c["allowed"]]
    if source == "off":
        code, text = "off", f"{label} is not used."
    elif source == "elsewhere":
        code, text = "elsewhere", f"{label} runs on another computer, so which card it uses is set there."
    elif source == "own":
        code = "own_running" if on else "own_idle"
        text = (f"Video Tool's own {label} is running on {_names(on)}." if on else f"Video Tool's own {label} is not holding a card right now. It starts on the card chosen for it.")
    elif blocked:
        code = "existing_blocked"
        text = (f"{label} was already running on this computer before Video Tool. It is using {_names(blocked)}, a card Video Tool is not allowed to use. Video Tool did not start it and "
                f"does not change it, so it keeps asking it for work. To keep Video Tool's work off that card, use Video Tool's own copy.")
    elif on:
        code, text = "existing_on", f"{label} was already running on this computer, on {_names(on)}. Video Tool leaves it as it is."
    else:
        code = "existing_idle"
        text = f"{label} was already running on this computer. It is not holding a graphics card right now, so which one it uses depends on how it was installed. Video Tool leaves it as it is."
    return {"id": engine, "label": label, "source": source, "url": endpoint.url, "code": code, "message": text, "on": on,
            "offer_own": source == "existing" and bool(blocked), "own_installed": placement.own_installed(engine)}


def report(gpus: Optional[list[dict]] = None, allowed_uuids: Optional[set[str]] = None) -> list[dict[str, Any]]:
    """One row per engine Video Tool can run itself (Ollama, ComfyUI): where it runs, in words, and whether to offer Video Tool's own copy."""
    from .. import gpuassign, sysstats

    gpus = sysstats._gpus() if gpus is None else gpus
    ok = {c["uuid"] for c in gpuassign.allowed()} if allowed_uuids is None else allowed_uuids
    return [_row(e, gpus, ok) for e in LABEL]


def use_own(engine: str, say=print) -> dict[str, Any]:
    """The person chose Video Tool's own copy: point the pipeline at it and start it on its job's card. Raises ValueError (a sentence) when it cannot be done."""
    if engine not in LABEL:
        raise ValueError(f"'{engine}' is not an engine Video Tool can run itself.")
    if not placement.own_installed(engine):
        raise ValueError(f"Video Tool's own {LABEL[engine]} is not installed yet. Install it from the Engines page first.")
    p = placement.place({engine: "own"}, say=say)[engine]
    return {"engine": engine, "source": p.source, "url": p.url, "note": p.note}
