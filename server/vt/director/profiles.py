"""Use-case profiles: data (design/profiles/*.json), not code. A profile says how a kind of video is paced, which scene types it favours,
how it looks and sounds. Add a JSON file to add a use case; missing keys fall back to the 'general' profile."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from .. import paths
from ..util import read_json

PROFILES_DIR = paths.DESIGN / "profiles"
USER_PROFILES_DIR = paths.DATA / "profiles"
USECASES = ["auto", "general", "product", "story", "discussion", "education"]

DEFAULT: dict[str, Any] = {
    "id": "general", "label": "General", "about": "",
    "pace": {"scene_min": 3.0, "scene_target": 5.0, "scene_max": 10.0},
    "weights": {}, "first_role": "hook", "last_role": "recap",
    "looks": {"styles": [], "palettes": []},
    "motion": "snappy", "transitions": ["slide_up", "fade", "zoom", "slide_left", "wipe"], "sfx_level": "normal", "music_mood": "light", "cast_chance": 0.0,
}


@lru_cache(maxsize=1)
def _all() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for d in (PROFILES_DIR, USER_PROFILES_DIR):
        if d.exists():
            for f in sorted(d.glob("*.json")):
                j = read_json(f)
                if isinstance(j, dict) and j.get("id"):
                    out[j["id"]] = j
    return out


def reload() -> None:
    _all.cache_clear()


def get(usecase: str) -> dict:
    """The profile for a use case (merged over the defaults). Unknown names give 'general'."""
    p = _all().get(usecase) or _all().get("general") or {}
    out = {**DEFAULT, **p}
    out["pace"] = {**DEFAULT["pace"], **p.get("pace", {})}
    out["looks"] = {**DEFAULT["looks"], **p.get("looks", {})}
    return out


def listing() -> list[dict]:
    order = {k: i for i, k in enumerate(USECASES)}
    return sorted(({"id": k, "label": v.get("label", k), "about": v.get("about", "")} for k, v in _all().items()), key=lambda x: order.get(x["id"], 99))


def weight(profile: dict, archetype: str) -> float:
    return float(profile.get("weights", {}).get(archetype, 0.5))
