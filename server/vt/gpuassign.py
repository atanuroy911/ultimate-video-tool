"""Which graphics cards Video Tool may use, and which card each of its own jobs uses (Server page, `vt gpu`, MCP `gpu_assignment`).

The person decides two things:
    allowed  the cards Video Tool may use at all. A card that is not in the list is never touched: not for a job, not as a fallback, not by a library that was forgotten.
    jobs     of the allowed cards, which one does each job (this module owns the choice; the code that does the job asks `resolve`).
Jobs Video Tool runs itself, so it can choose their card per job and with no restart:
    render   video rendering (the browser that draws the frames, and the hardware encoder)
    speech   speech recognition (Whisper)
    ai       Video Tool's own copy of the local AI (Ollama): the card it is started on, and restarted on when this changes
    pictures Video Tool's own copy of the picture engine (ComfyUI): the same
Programs that are separate (an Ollama or ComfyUI that was already installed and running) are only reported: where they run is set where they are installed, and Video Tool
never starts, stops or moves them. It says so when one sits on a card that is not allowed, and offers its own copy instead.

Stored in the server's settings under "gpu":
    {"primary": "auto" | "<uuid>", "render": "primary" | "<uuid>", "speech": "primary" | "<uuid>", "allowed": ["<uuid>", ...]}
"auto" = the card that is freest right now (most free memory, then the lowest load) among the allowed cards. A card that is gone or not allowed falls back to auto and says
so; a choice never makes a job fail. No "allowed" key means the person was never asked. With one card there is nothing to ask. With two or more, until the person answers
Video Tool uses ONE card: the freest of those no other program is working on right now, or, when every card has someone on it, the freest card. It never uses all of them by
default. An empty list is an answer: no card, the processor does the work.
A server set up before the question existed may already have a card the person picked (the primary card, or one for a job). Until they answer, those cards are the ones
Video Tool uses, so an update never moves its work to a card they did not pick.

The launcher's own fence (a CUDA_VISIBLE_DEVICES it was started with) always stays: allowed cards are chosen among the cards the launcher lets the server see. That variable is
read once, when this module is first imported, because the server later sets the variable itself from the allowed list.
"""
from __future__ import annotations

import os
import re
import threading
import time
from typing import Any, Optional

from . import paths
from .util import read_json, write_json

JOBS = ("render", "speech", "ai", "pictures")
OWN_ENGINE_JOBS = {"ollama": "ai", "comfy": "pictures"}         # the job that decides the card of each engine Video Tool runs itself
_lock = threading.Lock()
os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")      # CUDA's numbering = nvidia-smi's numbering, so an index means the same card everywhere
_PIN = os.environ.get("CUDA_VISIBLE_DEVICES")                  # what the launcher fenced this server to (None: nothing). Read once, see the module text.
_APPLIED: Optional[list[str]] = None                           # the cards this process fenced itself to with apply() (uuids), None until then


_asking = threading.local()
_memo: dict[str, tuple[float, Any]] = {}
MEMO_SECONDS = 2.0


def _remembered(key: str, make):
    """What nvidia-smi says is asked for again and again within one request (every job, every check); ask it once per couple of seconds. An empty answer is never kept: a
    failed question is asked again at once."""
    at, value = _memo.get(key, (0.0, None))
    if value is None or time.monotonic() - at > MEMO_SECONDS:
        value = make()
        if value:
            _memo[key] = (time.monotonic(), value)
    return value


def _cards() -> list[dict[str, Any]]:
    """Every NVIDIA card, in nvidia-smi order: index, name, uuid, free memory (GB), load (%)."""
    return [dict(c) for c in _remembered("cards", _read_cards)]


def _read_cards() -> list[dict[str, Any]]:
    from .sysstats import _num, _smi

    out = []
    for r in _smi(["--query-gpu=index,name,uuid,memory.free,memory.total,utilization.gpu"]):
        if len(r) >= 6 and r[0].isdigit():
            out.append({"index": int(r[0]), "name": r[1], "uuid": r[2], "free_gb": round((_num(r[3]) or 0) / 1024, 1),
                        "total_gb": round((_num(r[4]) or 0) / 1024, 1), "load": _num(r[5]) or 0.0})
    return out


def _programs() -> dict[str, list[dict[str, Any]]]:
    """What is working on each card now (by card uuid): label, gigabytes, and whether it is Video Tool's own. Empty where the driver cannot say."""
    from . import sysstats

    if getattr(_asking, "on", False):                                   # asked from inside the question itself: no answer, never a loop
        return {}
    _asking.on = True
    try:
        return _remembered("programs", lambda: {g["uuid"]: g["programs"] for g in sysstats._gpus()})
    except Exception:                                                   # noqa: BLE001
        return {}
    finally:
        _asking.on = False


def _others(card: dict, programs: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """The programs that are not Video Tool's own on this card."""
    return [p for p in programs.get(card["uuid"], []) if not p.get("ours")]


def _permitted(cards: list[dict]) -> list[dict]:
    """The cards the launcher lets this server see: the ones its CUDA_VISIBLE_DEVICES names, or every card when it set none."""
    if _PIN is None or not _PIN.strip():
        return cards
    want = {x.strip() for x in _PIN.split(",") if x.strip()}
    return [c for c in cards if str(c["index"]) in want or c["uuid"] in want]


def saved_allowed() -> Optional[list[str]]:
    """The uuids of the cards the person chose, or None when they were never asked."""
    raw = (read_json(paths.SETTINGS, {}) or {}).get("gpu") or {}
    got = raw.get("allowed")
    return [str(x) for x in got] if isinstance(got, list) else None


def _answered(seen: list[dict], saved: Optional[list[str]]) -> bool:
    """The question 'which cards may Video Tool use?' has an answer that still means something: an empty list (no card), or a list with at least one card that is here."""
    return saved is not None and (not saved or any(c["uuid"] in saved for c in seen))


def _freest(cards: list[dict]) -> Optional[dict]:
    return max(cards, key=lambda x: (x["free_gb"], -x["load"]), default=None)


def _picked(seen: list[dict]) -> list[dict]:
    """The cards the person picked for the primary card or a job before they were ever asked which cards may be used."""
    chosen = [v for v in config().values() if v not in ("auto", "primary")]
    return [c for c in seen if any(_match(v, [c]) for v in chosen)]


def allowed(cards: Optional[list[dict]] = None, programs: Optional[dict[str, list[dict[str, Any]]]] = None) -> list[dict[str, Any]]:
    """The cards Video Tool may use, in nvidia-smi order: the person's list within the cards the launcher lets it see. Before the person has answered and with two or more
    cards: one card, the freest of those nobody else is working on (or the freest card if none is free), never all of them. A caller that has just read the cards and what
    works on them (the System panel does) passes both, so nothing is asked twice and nothing can ask the caller back."""
    cards = _cards() if cards is None else cards
    seen = _permitted(cards)
    saved = saved_allowed()
    if _answered(seen, saved):
        return [c for c in seen if c["uuid"] in (saved or [])]
    if len(seen) < 2:
        return list(seen)
    picked = _picked(seen)
    if picked:
        return picked
    programs = _programs() if programs is None else programs
    idle = [c for c in seen if not _others(c, programs)]
    best = _freest(idle or seen)
    return [best] if best else []


def blocked() -> bool:
    """There are NVIDIA cards here and Video Tool may use none of them: the processor does the work, and nothing of ours may draw, encode or compute on a card."""
    cards = _cards()
    return bool(cards) and not allowed(cards)


def apply() -> list[str]:
    """Fence this process to the cards Video Tool may use: CUDA_VISIBLE_DEVICES becomes their uuids, in the order nvidia-smi lists them (how CUDA numbers them with
    CUDA_DEVICE_ORDER=PCI_BUS_ID). Programs it starts inherit the fence at once, and a library nobody remembered cannot reach any other card. Call it at the start of the server,
    before a GPU library does its first work: one that already holds a card keeps it until the next start (see restart_needed). No allowed card gives "-1", which hides every card.
    When nvidia-smi does not answer, the person's saved list is used as it is; with no answer saved and no way to look, nothing is changed. Returns the uuids."""
    global _APPLIED
    cards = _cards()
    if cards:
        uuids = [c["uuid"] for c in allowed(cards)]
    else:
        saved = saved_allowed()
        if saved is None:
            return []
        uuids = list(saved)
    os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(uuids) if uuids else "-1"
    _APPLIED = uuids
    return uuids


def uuid_for(index: Any) -> Optional[str]:
    """The uuid of card number `index` (nvidia-smi's number) when Video Tool may use it, else None. For starting a program of ours on a card chosen by number."""
    try:
        want = str(int(index))
    except (TypeError, ValueError):
        return None
    return next((c["uuid"] for c in allowed() if str(c["index"]) == want), None)


def child_env(index: Any) -> dict[str, str]:
    """The environment that starts a program of ours on card number `index`: only that card visible. When Video Tool may not use that card it is {}, and the program keeps the
    fence it inherits (the allowed cards, or none), so a chosen number can never reach a card that was not allowed."""
    uuid = uuid_for(index)
    return {"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": uuid} if uuid else {}


def job_env(job: str) -> dict[str, str]:
    """The environment that starts one of our own engines for this job: only the job's card visible. {} when there is nothing to pin (no NVIDIA card here). When there are cards
    and none is allowed it hides them all ("-1"): the engine then runs on the processor, slowly, and says nothing about a card it may not use."""
    card, _ = resolve(job)
    if card is not None:
        return {"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": card["uuid"]}
    return {"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": "-1"} if blocked() else {}


def affected_jobs(patch: dict[str, Any]) -> set[str]:
    """The jobs whose card a save could change: all of them when the allowed list or the primary card changes, else the ones named."""
    if "allowed" in patch or "primary" in patch:
        return set(JOBS)
    return {k for k in patch if k in JOBS}


def _engine_cards(jobs: set[str]) -> dict[str, Optional[str]]:
    """engine -> the card (uuid) its job resolves to now, for our own engines whose job is in `jobs`."""
    return {e: (resolve(j)[0] or {}).get("uuid") for e, j in OWN_ENGINE_JOBS.items() if j in jobs}


def change(patch: dict[str, Any], background: bool = True) -> list[str]:
    """The one way every front end (the Server page, `vt gpu`, the MCP tool) changes the choices: save them, and move our own engines (Ollama, ComfyUI) that now belong on another
    card by restarting them there (only a copy we started; one that was already running is never touched). Raises ValueError, a sentence, like `save`.
    Returns the engines being restarted: in the background by default (the Server page must not wait for a model to load), or finished when `background` is false."""
    import threading

    from .engines import pids, placement

    jobs = affected_jobs(patch)
    before = _engine_cards(jobs)
    save(patch)
    after = _engine_cards(jobs)
    moving = [e for e in after if before.get(e) != after[e] and pids.running(e, fresh=True) is not None]
    if moving and background:
        threading.Thread(target=placement.restart_own, args=(moving, lambda *a: None), daemon=True, name="restart-own-engines").start()
    elif moving:
        placement.restart_own(moving, lambda *a: None)
    return moving


def restart_needed() -> bool:
    """The person has changed which cards Video Tool may use since this process fenced itself (apply), so programs it already started may still hold a card they should not.
    False while nobody has answered: the default is not an answer to compare."""
    if _APPLIED is None or needs_choice():
        return False
    return [c["uuid"] for c in allowed()] != _APPLIED


def needs_choice(cards: Optional[list[dict]] = None) -> bool:
    """Two or more cards and nobody has said which Video Tool may use: the setup asks."""
    seen = _permitted(_cards() if cards is None else cards)
    return len(seen) >= 2 and not _answered(seen, saved_allowed())


def config() -> dict[str, str]:
    raw = (read_json(paths.SETTINGS, {}) or {}).get("gpu") or {}
    cfg = {"primary": str(raw.get("primary") or "auto")}
    for j in JOBS:
        cfg[j] = str(raw.get(j) or "primary")
    return cfg


def _match(choice: str, cards: list[dict]) -> Optional[dict]:
    c = choice.strip().lower()
    return next((x for x in cards if c in (x["uuid"].lower(), str(x["index"]), x["name"].lower())), None)


def _auto(cards: list[dict]) -> Optional[dict]:
    return _freest(cards)


def resolve(job: str, cards: Optional[list[dict]] = None) -> tuple[Optional[dict], str]:
    """(card, why) for a job. card is None when Video Tool may use no card (then the processor does the work). Never raises."""
    ok = allowed(cards)
    if not ok:
        return None, "no NVIDIA card is available to Video Tool"
    cfg = config()
    choice = cfg.get(job, "primary")
    source = job
    if choice == "primary":
        choice, source = cfg["primary"], "primary"
    if choice == "auto":
        c = _auto(ok)
        return c, f"automatic: the freest card right now ({c['free_gb']} GB free)" if c else "automatic"
    c = _match(choice, ok)
    if c:
        return c, f"chosen as {source}"
    c = _auto(ok)
    return c, f"the card chosen as {source} is not available; using the freest card instead"


def _seen(cards: list[dict]) -> list[dict]:
    """The cards this process can reach, in the order CUDA numbers them: what CUDA_VISIBLE_DEVICES says right now (the launcher's, or the one the server set from the allowed
    list), or every card. This can be more than the allowed cards (before the server has applied the list), so a card's number is counted here, not among the allowed ones."""
    live = os.environ.get("CUDA_VISIBLE_DEVICES")
    if live is None or not live.strip():
        return list(cards)
    out: list[dict] = []
    for token in (x.strip() for x in live.split(",")):
        card = next((c for c in cards if token in (str(c["index"]), c["uuid"])), None)
        if card is not None and card not in out:
            out.append(card)
    return out


def cuda_index(job: str) -> int:
    """The index of the job's card among the cards this process can see (what CTranslate2 and PyTorch call device 0, 1, ...). 0 when unknown."""
    card, _ = resolve(job)
    if card is None:
        return 0
    return next((i for i, c in enumerate(_seen(_cards())) if c["uuid"] == card["uuid"]), 0)


def _choose(v: Any, pool: list[dict]) -> list[dict]:
    """A list of cards from what the person gave: uuids, indexes or names (a list, or one text separated by commas or spaces), or 'all'."""
    items = [x for x in re.split(r"[,\s]+", v) if x] if isinstance(v, str) else [str(x).strip() for x in (v or []) if str(x).strip()]
    if [x.lower() for x in items] == ["all"]:
        return list(pool)
    out: list[dict] = []
    for x in items:
        card = _match(x, pool)
        if card is None:
            raise ValueError(f"'{x}' is not a card Video Tool can use. Cards here: " + ", ".join(f"{c['index']} {c['name']}" for c in pool))
        if card not in out:
            out.append(card)
    return out


def save(patch: dict[str, Any]) -> dict[str, str]:
    """Change the choices. 'allowed': a list of cards (uuid, index or name), or 'all', or [] for none. 'primary': 'auto' or a card. A job: 'primary' or a card.
    A card must be one of the allowed ones, and when the allowed list changes, a choice that pointed at a card that is no longer allowed goes back to the default."""
    cards = _cards()
    cur: dict[str, Any] = dict(config())
    chosen: Optional[list[dict]] = None
    for k in patch:
        if k != "allowed" and k != "primary" and k not in JOBS:
            raise ValueError(f"'{k}' is not something that can be assigned (allowed, primary, {', '.join(JOBS)})")
    if "allowed" in patch:
        chosen = sorted(_choose(patch["allowed"], _permitted(cards)), key=lambda c: c["index"])           # kept in the driver's order, whatever order they were named in
    pool = chosen if chosen is not None else allowed(cards)
    for k, v in patch.items():
        if k == "allowed":
            continue
        v = str(v).strip()
        if v in ("auto", "primary") or not v:
            if k == "primary" and v == "primary":
                raise ValueError("The primary card is 'auto' or a card, not 'primary'.")
            cur[k] = v or ("auto" if k == "primary" else "primary")
            continue
        card = _match(v, pool)
        if card is None:
            raise ValueError(f"'{v}' is not a card Video Tool can use. Choose one of: " + ", ".join(f"{c['index']} {c['name']}" for c in pool))
        cur[k] = card["uuid"]
    if chosen is not None:
        keep = {c["uuid"] for c in chosen}
        for k in ("primary", *JOBS):                                    # a choice that pointed at a card that may not be used any more goes back to the default
            if cur[k] not in ("auto", "primary") and cur[k] not in keep and not _match(cur[k], chosen):
                cur[k] = "auto" if k == "primary" else "primary"
    with _lock:
        s = read_json(paths.SETTINGS, {}) or {}
        was = (s.get("gpu") or {}).get("allowed")
        s["gpu"] = {**cur, **({"allowed": [c["uuid"] for c in chosen]} if chosen is not None else ({"allowed": was} if isinstance(was, list) else {}))}
        write_json(paths.SETTINGS, s)
    return config()


def _engines(gpus: list[dict], ok: set[str]) -> list[dict[str, Any]]:
    try:
        from .engines import where

        return where.report(gpus, ok)
    except Exception:                                                   # noqa: BLE001
        return []


def describe() -> dict[str, Any]:
    """What the Server page and `vt gpu` show: the cards (each with whether Video Tool may use it and what is working on it now), the saved choices, the card each job uses
    now and why, whether the person still has to be asked, and where the separate programs run."""
    from . import sysstats

    cards = _cards()
    ok = allowed(cards)
    jobs = {}
    for j in JOBS:
        c, why = resolve(j, cards)
        jobs[j] = {"gpu": c["uuid"] if c else None, "name": c["name"] if c else None, "index": c["index"] if c else None, "why": why}
    elsewhere = {}
    programs: dict[str, list[dict[str, Any]]] = {}
    gpus = sysstats._gpus()
    for g in gpus:
        programs[g["uuid"]] = g["programs"]
        for p in g["programs"]:
            if p["label"] in ("Ollama", "ComfyUI"):
                elsewhere.setdefault(p["label"], []).append({"gpu": g["name"], "index": g["index"], "gb": p["gb"]})
    return {"cards": [{**c, "allowed": c in ok, "using": [{"label": p["label"], "gb": p.get("gb"), "ours": bool(p.get("ours"))} for p in programs.get(c["uuid"], [])]} for c in cards],
            "saved": config(), "allowed_saved": saved_allowed(), "needs_choice": needs_choice(cards), "restart_needed": restart_needed(), "jobs": jobs, "separate_programs": elsewhere,
            "pinned_by_launcher": _PIN, "engines": _engines(gpus, {c["uuid"] for c in ok})}
