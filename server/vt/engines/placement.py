"""Where each engine comes from on the server computer: one that is already installed and running, our own copy, or none.

    existing  use a server that already answers (found on its usual ports, or the address given). Nothing of it is started, stopped or changed.
    own       our own copy: its own program folder and models under <data>, its own port (never the usual one), so it can sit next to an existing install.
    auto      existing when one answers, else our own copy when it is installed, else off.
    off       not used.

The choice is written to the engines block of settings.json, so the pipeline, the Engines page and the gateway all read the same addresses.
"""
from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

from .. import paths
from ..util import read_json, write_json
from . import hub, store
from .model import Endpoint

Choice = Literal["auto", "existing", "own", "off"]
CHOICES = ("auto", "existing", "own", "off")
ENGINES = ("ollama", "comfy")
# where an existing install usually listens; ComfyUI is often run once per graphics card on the next ports
USUAL = {"ollama": [11434], "comfy": list(range(8188, 8196))}
# our own copies start here and take the next free port, away from the usual ones
OWN_BASE = {"ollama": 11444, "comfy": 8288}
PORTS_FILE = "engine-ports.json"


@dataclass
class Placement:
    engine: str
    choice: str                                   # what was asked
    source: str                                   # what it came to: existing | own | off
    url: str = ""
    workers: list[str] = field(default_factory=list)
    note: str = ""

    def urls(self) -> list[str]:
        return [u for u in [self.url, *self.workers] if u]


def find_existing(engine: str, skip: tuple[str, ...] = ()) -> list[str]:
    """Servers of this engine answering on this computer's usual ports, best first. Our own copy (its port) is skipped."""
    from concurrent.futures import ThreadPoolExecutor

    urls = [f"http://127.0.0.1:{port}" for port in USUAL[engine] if f"http://127.0.0.1:{port}" not in skip]
    if not urls:
        return []
    with ThreadPoolExecutor(max_workers=len(urls)) as pool:                            # an address that does not answer costs a second: ask all of them at once, keep the order
        answers = list(pool.map(lambda url: hub.reachable(engine, url, 1.0), urls))
    return [url for url, ok in zip(urls, answers) if ok]


def _free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def own_url(engine: str) -> str:
    """Our copy's address. Chosen once (the first free port from OWN_BASE) and remembered, so it stays the same across restarts."""
    f = paths.DATA / PORTS_FILE
    ports = read_json(f, {}) or {}
    port = ports.get(engine)
    if not port:
        port = OWN_BASE[engine]
        while not _free(port):
            port += 1
        ports[engine] = port
        f.parent.mkdir(parents=True, exist_ok=True)
        write_json(f, ports)
    return f"http://127.0.0.1:{port}"


def own_installed(engine: str) -> bool:
    from .. import llm
    from .installers import ComfyInstaller

    if engine == "ollama":
        return llm.binary() is not None
    if engine == "comfy":
        return (ComfyInstaller().root / "main.py").exists()
    return False


def decide(engine: str, choice: str = "auto", url: str = "") -> Placement:
    """Work out where the engine comes from. Starts nothing."""
    if choice not in CHOICES:
        raise ValueError(f"{engine}: choose one of {', '.join(CHOICES)}")
    if choice == "off":
        return Placement(engine, choice, "off", note="not used")
    if choice in ("auto", "existing"):
        if url:
            urls = [u.strip().rstrip("/") for u in url.split(",") if u.strip()]
            ok = hub.reachable(engine, urls[0], 2.0)
            return Placement(engine, choice, "existing", urls[0], urls[1:], "" if ok else f"{urls[0]} does not answer yet")
        own = own_url(engine) if engine in OWN_BASE else ""
        found = find_existing(engine, skip=(own,))
        if found:
            # several ComfyUIs (one per card): the first is the main server, the rest are workers
            return Placement(engine, choice, "existing", found[0], found[1:] if engine == "comfy" else [], f"using the {engine} already running here")
        if choice == "existing":
            return Placement(engine, choice, "off", note=f"no {engine} answers on its usual ports {USUAL[engine]}; give its address")
    if engine not in OWN_BASE:
        return Placement(engine, choice, "off", note=f"{engine} has no copy of its own here; install it separately and choose 'existing'")
    if choice == "auto" and not own_installed(engine):
        return Placement(engine, choice, "off", note=f"no {engine} here; `vt engine setup --engines {engine}` installs our own copy")
    return Placement(engine, choice, "own", own_url(engine), note="our own copy, on its own port and folder")


def own_dirs():
    """Where our own Ollama's program and models live (the setup wizard's folders, else under the data folder): the same two the installer uses."""
    from pathlib import Path

    s = read_json(paths.SETTINGS, {}) or {}
    return Path(s.get("install_dir") or paths.DATA / "engines") / "ollama", Path(s.get("models_dir") or paths.DATA / "models") / "ollama"


def start(p: Placement, say=print) -> Placement:
    """Start our own copy when that is the choice, on the card its job has (vt/gpuassign.py: "ai" for Ollama, "pictures" for ComfyUI). An existing server is never touched."""
    if p.source != "own" or hub.reachable(p.engine, p.url, 1.0):
        return p
    from .. import llm
    from .installers import ComfyInstaller

    port = int(p.url.rsplit(":", 1)[1])
    if p.engine == "ollama":
        program, models = own_dirs()
        if not llm.start_server(p.url, wait=40, program_dir=program, model_dir=models):
            p.note = "our Ollama did not start: is it installed? (`vt engine setup --engines ollama`)"
    elif p.engine == "comfy":
        inst = ComfyInstaller(port=port)
        if not (inst.root / "main.py").exists():
            p.note = "our ComfyUI is not installed: `vt engine setup --engines comfy`"
        else:
            inst.start()
            p.note = "our ComfyUI is starting (the first start takes a minute)"
    say(f"  {p.engine}: {p.note}")
    return p


def restart_own(engines: list[str], say=print) -> list[str]:
    """After a change of card: each of our own copies that is running, and is the program we started, is stopped and started again so it takes the card its job now has.
    An engine that was already running before Video Tool, or is not running, is left alone. Returns the engines restarted."""
    from . import pids

    done = []
    for e in engines:
        if e not in OWN_BASE or pids.running(e) is None:
            continue
        p = decide(e, "own")
        pids.stop(e)
        for _ in range(40):                                        # the port is free again
            if not hub.reachable(e, p.url, 0.5):
                break
            time.sleep(0.5)
        start(p, say)
        done.append(e)
    return done


def save(p: Placement, *, provisional: bool = False) -> None:
    """Point the pipeline at it: the engines block, plus the flat keys the older code still reads."""
    if p.source == "off":
        store.save(p.engine, Endpoint(mode="off", url=""), provisional=provisional)
        return
    data_dir = str(paths.DATA / "engines" / p.engine) if p.source == "own" else ""
    before = store.load(p.engine)                  # a key typed on the Engines page stays
    store.save(p.engine, Endpoint(mode="remote" if p.source == "existing" else "local", url=p.url, key=before.key, gpu=before.gpu, workers=p.workers, data_dir=data_dir), provisional=provisional)
    if p.engine in store.LEGACY:
        s = read_json(paths.SETTINGS, {}) or {}
        s[store.LEGACY[p.engine]] = p.url
        write_json(paths.SETTINGS, s)


def place(choices: dict[str, str], urls: Optional[dict[str, str]] = None, say=print, run: bool = True) -> dict[str, Placement]:
    """decide + start + save for each engine. Returns what each came to."""
    out = {}
    for e, c in choices.items():
        url = (urls or {}).get(e, "")
        p = decide(e, c, url)
        if run:
            start(p, say)
        # Startup discovery can pick a usable default. It does not finish setup
        # for an engine the person has never chosen, even when it finds nothing.
        provisional = c == "auto" and not url and not store.configured(e)
        save(p, provisional=provisional)
        out[e] = p
    return out
