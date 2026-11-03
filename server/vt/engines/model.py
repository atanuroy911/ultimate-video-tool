from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

Mode = Literal["local", "remote", "off"]
Kind = Literal["llm", "image", "voice", "asr", "custom"]


@dataclass
class Endpoint:
    """Where an engine is, as the person set it. `key` never leaves the settings file except as a request header."""
    mode: Mode = "off"
    url: str = ""
    key: str = ""
    gpu: Optional[int] = None
    data_dir: str = ""
    workers: list = field(default_factory=list)       # more servers of the same engine (a second ComfyUI on another GPU): urls

    def public(self) -> dict:
        return {"mode": self.mode, "url": self.url, "has_key": bool(self.key), "gpu": self.gpu, "data_dir": self.data_dir, "workers": list(self.workers)}

    def all_urls(self) -> list[str]:
        return [u for u in [self.url, *self.workers] if u]


@dataclass
class Health:
    ok: bool
    why_not: str = ""
    version: str = ""
    seconds: float = 0.0
    gpu: str = ""
    models: list[dict] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    note: str = ""

    def public(self) -> dict:
        return {"ok": self.ok, "why_not": self.why_not, "version": self.version, "seconds": round(self.seconds, 2), "gpu": self.gpu,
                "models": self.models[:60], "capabilities": self.capabilities, "note": self.note}


@dataclass(frozen=True)
class EngineSpec:
    id: str
    kind: Kind
    label: str
    about: str                                            # one plain sentence for the Engines page
    capabilities: tuple[str, ...]
    default_url: str = ""                                 # offered when the person chooses "connect"; empty = nothing assumed
    needs_key: bool = False
    check: Optional[Callable[[Endpoint], Health]] = None
    local_install: str = ""                               # what "set it up here" does, in a sentence ("" = not available yet)
