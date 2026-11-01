"""Line-icon registry: Lucide (bare names or 'lucide:x') and Tabler ('tabler:x'). All share a 24x24, 2 px stroke grid."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from .. import paths
from ..util import read_json


@lru_cache(maxsize=1)
def _lucide() -> dict[str, str]:
    return read_json(paths.ICONS / "lucide.json", {}) or {}


@lru_cache(maxsize=1)
def _tabler() -> dict[str, str]:
    return read_json(paths.ICONS / "tabler.json", {}) or {}


def canonical(name: str) -> str:
    """'coins' -> 'lucide:coins'; 'tabler:coin' stays."""
    return name if ":" in name else f"lucide:{name}"


@lru_cache(maxsize=1)
def all_names() -> frozenset[str]:
    """Every accepted spelling: bare Lucide names plus prefixed ones for both sets."""
    out = set(_lucide()) | {f"lucide:{n}" for n in _lucide()} | {f"tabler:{n}" for n in _tabler()}
    return frozenset(out)


def inner(name: str) -> Optional[str]:
    src, _, n = canonical(name).partition(":")
    return (_lucide() if src == "lucide" else _tabler()).get(n)
