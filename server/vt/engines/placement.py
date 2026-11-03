"""Where each engine comes from on the server computer: one that is already installed and running, our own copy, or none.

    existing  use a server that already answers (found on its usual ports, or the address given). Nothing of it is started, stopped or changed.
    own       our own copy: its own program folder and models under <data>, its own port (never the usual one), so it can sit next to an existing install.
    auto      existing when one answers, else our own copy when it is installed, else off.
    off       not used.

The choice is written to the engines block of settings.json, so the pipeline, the Engines page and the gateway all read the same addresses.
"""
from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Literal, Optional

from .. import paths
from ..util import read_json, write_json
from . import hub, store
from .model import Endpoint

Choice = Literal["auto", "existing", "own", "off"]
CHOICES = ("auto", "existing", "own", "off")
ENGINES = ("ollama", "comfy", "voicestudio")
# where an existing install usually listens; ComfyUI is often run once per graphics card on the next ports
USUAL = {"ollama": [11434], "comfy": list(range(8188, 8196)), "voicestudio": [3900]}
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
    found = []
    for port in USUAL[engine]:
        url = f"http://127.0.0.1:{port}"
        if url not in skip and hub.reachable(engine, url, 1.0):
            found.append(url)
    return found


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
    return False                                   # VoiceStudio is another project with its own installer: only an existing one is used


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


def start(p: Placement, say=print) -> Placement:
    """Start our own copy when that is the choice. An existing server is never touched."""
    if p.source != "own" or hub.reachable(p.engine, p.url, 1.0):
        return p
    from .. import llm
    from .installers import ComfyInstaller

    port = int(p.url.rsplit(":", 1)[1])
    if p.engine == "ollama":
        if not llm.start_server(p.url, wait=40):
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


def save(p: Placement) -> None:
    """Point the pipeline at it: the engines block, plus the flat keys the older code still reads."""
    if p.source == "off":
        store.save(p.engine, Endpoint(mode="off", url=""))
        return
    data_dir = str(paths.DATA / "engines" / p.engine) if p.source == "own" else ""
    before = store.load(p.engine)                  # a key typed on the Engines page (VoiceStudio) stays
    store.save(p.engine, Endpoint(mode="remote" if p.source == "existing" else "local", url=p.url, key=before.key, gpu=before.gpu, workers=p.workers, data_dir=data_dir))
    if p.engine in store.LEGACY:
        s = read_json(paths.SETTINGS, {}) or {}
        s[store.LEGACY[p.engine]] = p.url
        write_json(paths.SETTINGS, s)


def place(choices: dict[str, str], urls: Optional[dict[str, str]] = None, say=print, run: bool = True) -> dict[str, Placement]:
    """decide + start + save for each engine. Returns what each came to."""
    out = {}
    for e, c in choices.items():
        p = decide(e, c, (urls or {}).get(e, ""))
        if run:
            start(p, say)
        save(p)
        out[e] = p
    return out
