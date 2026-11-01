"""Sound-effect library: classification of raw files into roles, and role-based picking at mix time.

The raw collection (a user-supplied SFX folder) is indexed once by scripts/build_sfx_library.py into assets/sfx/library.json
plus a curated, normalised subset of short clips. At mix time the video asks for a *role* ("whoosh", "pop", "impact"...)
and gets a varied pick from that role, never the same clip twice in a row.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import paths

# role -> what it is for. "target" = preferred clip length in seconds (min, ideal-max, hard-max) used when curating.
ROLES: dict[str, dict] = {
    "pop":      {"doc": "small element appears (bubble, pluck, soft pop)", "target": (0.04, 0.45, 1.0), "gain_db": -15, "mono": True},
    "click":    {"doc": "UI tap/button/tick: list items, tags, small steps", "target": (0.02, 0.30, 0.8), "gain_db": -16, "mono": True},
    "chime":    {"doc": "positive accent: ding, bell, notification, coin, success", "target": (0.15, 1.6, 3.0), "gain_db": -15, "mono": True},
    "whoosh":   {"doc": "movement and scene transitions (swoosh, swish, fly-by)", "target": (0.25, 1.4, 2.5), "gain_db": -14, "mono": False},
    "impact":   {"doc": "emphasis hit: big number, key word, section start", "target": (0.3, 2.2, 4.0), "gain_db": -12, "mono": False},
    "subdrop":  {"doc": "low sub drop for zoom/punch-in moments", "target": (0.4, 2.0, 4.0), "gain_db": -13, "mono": False},
    "riser":    {"doc": "build-up before a reveal", "target": (1.0, 3.5, 6.0), "gain_db": -16, "mono": False},
    "glitch":   {"doc": "digital glitch / tech transition", "target": (0.1, 1.2, 2.5), "gain_db": -15, "mono": False},
    "camera":   {"doc": "camera shutter/click: photo or screenshot moments", "target": (0.05, 0.8, 1.5), "gain_db": -14, "mono": True},
    "typing":   {"doc": "typing / keyboard / text appearing", "target": (0.1, 1.5, 3.0), "gain_db": -16, "mono": True},
    "success":  {"doc": "win, correct, level-up, achievement", "target": (0.3, 2.0, 3.5), "gain_db": -14, "mono": True},
    "error":    {"doc": "wrong, fail, buzzer", "target": (0.1, 1.2, 2.5), "gain_db": -14, "mono": True},
    "money":    {"doc": "coins, cash register, payment", "target": (0.1, 1.5, 3.0), "gain_db": -14, "mono": True},
    "applause": {"doc": "applause, cheer, crowd", "target": (0.5, 3.0, 6.0), "gain_db": -16, "mono": False},
    "funny":    {"doc": "meme / comedic stingers (opt-in)", "target": (0.2, 2.5, 5.0), "gain_db": -13, "mono": True},
    "nature":   {"doc": "fire, water, wind, ambience (not used automatically)", "target": (0.5, 5.0, 12.0), "gain_db": -20, "mono": False},
    "vehicle":  {"doc": "train, subway, car (not used automatically)", "target": (0.5, 5.0, 12.0), "gain_db": -18, "mono": False},
    "tension":  {"doc": "horror / tension drones (not used automatically)", "target": (0.5, 5.0, 12.0), "gain_db": -18, "mono": False},
    "weapon":   {"doc": "guns and explosions. Catalogued but disabled: wrong for explainers", "target": (0.1, 2.0, 5.0), "gain_db": -12, "mono": False},
    "misc":     {"doc": "unclassified", "target": (0.1, 3.0, 8.0), "gain_db": -16, "mono": False},
}
AUTO_ROLES = {"pop", "click", "chime", "whoosh", "impact", "subdrop", "riser", "glitch", "camera", "typing", "success", "error", "money", "applause"}
DISABLED_ROLES = {"weapon"}

# folder (any path component, lower-case) -> role. First match wins, so most specific first.
FOLDER_RULES: list[tuple[str, str]] = [
    ("gun sfx", "weapon"), ("machineguns", "weapon"), ("pistols", "weapon"), ("rifles", "weapon"), ("rocket launchers", "weapon"),
    ("shotguns", "weapon"), ("smg", "weapon"), ("snipers", "weapon"),
    ("horror", "tension"),
    ("subway", "vehicle"), ("train", "vehicle"),
    ("fire", "nature"), ("water", "nature"),
    ("buttons", "click"), ("clicks", "click"),
    ("digital hud", "glitch"),
    ("bells", "chime"),
    ("camera", "camera"),
    ("glitch", "glitch"),
    ("subdrop", "subdrop"), ("sub drop", "subdrop"),
    ("risers", "riser"), ("riser", "riser"),
    ("whooshes", "whoosh"), ("whoosh", "whoosh"), ("swoosh", "whoosh"), ("swishes", "whoosh"),
    ("hits", "impact"), ("trailer impact", "impact"),
    ("dramatic horn", "impact"),
    ("memes", "funny"), ("faaaaaah", "funny"), ("famous sound", "funny"),
    ("slow motion", "whoosh"),
]

# filename keyword -> role. Checked before folder rules for the generic "mix" folders; first match wins.
NAME_RULES: list[tuple[str, str]] = [
    (r"glock|pistol|rifle|shotgun|machine ?gun|ak ?47|m16|sniper|rocket|grenade|gun ?shot|9mm|luger|ammo|bullet|explosion|bazooka|\bshot\b", "weapon"),
    (r"cash|coin|money|register|payment|apple pay|purchase|jackpot", "money"),
    (r"applause|clap|cheer|crowd", "applause"),
    (r"success|win(ner)?\b|level ?up|achievement|correct|complete|fanfare|tada|victory", "success"),
    (r"error|fail(ure)?\b|wrong|buzzer|incorrect|denied|nope", "error"),
    (r"typing|keyboard|type text|typewriter", "typing"),
    (r"camera|shutter|8mm|film", "camera"),
    (r"glitch|glich|static|digital|hud|cyber|robot", "glitch"),
    (r"riser|rising|build ?up|uplifter|reverse", "riser"),
    (r"sub ?drop|subdrop|808|bass ?drop|boom", "subdrop"),
    (r"impact|hit\b|slam|crash|thud|punch|stomp|anvil", "impact"),
    (r"whoosh|woosh|swoosh|swish|fly ?by|zing|swipe|airy|pass\b|slide", "whoosh"),
    (r"bell|chime|ding|notification|ping|gong|glock(enspiel)?|xylophone|harp", "chime"),
    (r"pop|bubble|plop|pluck|bamboo|boing|spring|blip|bloop", "pop"),
    (r"click|tap\b|tick|button|switch|select|toggle|snap|clack|key ?press|ui sound", "click"),
    (r"laugh|awkward|disappoint|fah+|vine|bruh|oof|sad violin|cricket|meme|wow|ohh", "funny"),
    (r"fire|flame|water|rain|wave|wind|ocean|river|bird|forest", "nature"),
    (r"train|subway|car\b|engine|plane|helicopter|bicycle", "vehicle"),
]


def classify(rel_path: str) -> tuple[str, str]:
    """(role, reason) from a path relative to the SFX root. Weapons are detected anywhere, then folder, then name."""
    low = rel_path.lower().replace("\\", "/")
    name = low.rsplit("/", 1)[-1]
    name_noext = re.sub(r"\.[a-z0-9]+$", "", name)
    # weapons always win (they hide inside generic folders like 'Transition Sound Effects')
    if re.search(NAME_RULES[0][0], name_noext) or any(f in low for f, r in FOLDER_RULES if r == "weapon"):
        return "weapon", "weapon keyword/folder"
    generic = any(g in low for g in ("/mix/", "/mix ", "transition sound effects", "/ui ", "ui-sounds", "230 mixed", "100 famous"))
    for pat, role in NAME_RULES[1:]:
        if re.search(pat, name_noext):
            return role, f"filename ~ {pat.split('|')[0]}"
    for key, role in FOLDER_RULES:
        if key in low and role != "weapon":
            return role, f"folder '{key}'"
    return ("misc", "no rule") if not generic else ("misc", "generic folder, no keyword")


# Files that must never be picked automatically: other people's franchises (copyright claims on uploaded videos) and
# crude/explicit material. They stay in the catalogue, flagged, so nothing is hidden from the user.
FLAG_RULES: list[tuple[str, str]] = [
    (r"(?<![a-z])(one[ _-]?piece|dragon[ _-]?ball|naruto|katon|espada|jojo|pokemon|mario|zelda|minecraft|among[ _-]?us|gta|san andreas|"
     r"discord|upin|ipin|illuminati|mlg|hitmarker|netflix|tudum|sonic|fnaf|roblox|fortnite|undertale|kobo|ara[ -]?ara|hiyak)(?![a-z])", "third-party franchise (copyright risk)"),
    (r"(?<![a-z])(kontol|oppai|fart|kentut|porn|sex|moan|nsfw|nigga|fuck|shit|bitch|dick|hell nah|ahegao)(?![a-z])", "explicit/crude"),
]


def flag(rel_path: str) -> Optional[str]:
    low = rel_path.lower().replace("\\", "/").rsplit("/", 1)[-1]
    for pat, why in FLAG_RULES:
        if re.search(pat, low):
            return why
    return None


@dataclass
class Clip:
    id: str
    role: str
    file: str                  # path relative to assets/sfx/lib
    duration: float
    peak_db: float
    centroid: float
    source: str
    tags: list[str] = field(default_factory=list)


class Library:
    """Role-based picker over the curated clips. Falls back to the built-in synthesised sounds when no library is built."""

    def __init__(self, root: Optional[Path] = None):
        self.root = root or (paths.ASSETS / "sfx")
        self.clips: dict[str, list[Clip]] = {}
        idx = self.root / "library.json"
        if idx.exists():
            for c in json.loads(idx.read_text(encoding="utf-8")).get("clips", []):
                self.clips.setdefault(c["role"], []).append(Clip(**{k: c[k] for k in Clip.__dataclass_fields__ if k in c}))

    @property
    def available(self) -> bool:
        return any(self.clips.get(r) for r in AUTO_ROLES)

    def roles(self) -> list[str]:
        return sorted(r for r, v in self.clips.items() if v)

    def pick(self, role: str, rng: random.Random, avoid: Optional[set[str]] = None, short: bool = False) -> Optional[Clip]:
        pool = self.clips.get(role) or []
        if not pool or role in DISABLED_ROLES:
            return None
        if short:
            lim = sorted(c.duration for c in pool)[max(0, len(pool) // 2 - 1)]
            pool = [c for c in pool if c.duration <= lim] or pool
        fresh = [c for c in pool if not avoid or c.id not in avoid] or pool
        return rng.choice(fresh)

    def path(self, clip: Clip) -> Path:
        return self.root / "lib" / clip.file
