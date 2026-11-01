"""Colour stickers: Twemoji artwork (CC-BY 4.0) indexed by Unicode hex code, with a blocklist of offensive emoji."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from .. import paths
from ..util import read_json

# Never offered by the dictionary or the picker (rude gestures, sexual, drugs/tobacco, gore). Explicit use by hex is also refused.
BLOCKED = {
    "1f595", "1f4a9", "1f51e", "1f346", "1f351", "1f4a6", "1f6ac", "1f489", "1f480", "2620", "1f52b", "1f4a3", "1fa78",
    "1f918", "1f595-1f3fb", "1f48b", "1f445", "1f444", "1f9a0", "1fa66", "26b0", "26b1", "1f3b0", "1f37a", "1f37b", "1f943",
    "1f377", "1f378", "1f379", "1f37e", "1f37c-none",
}


@lru_cache(maxsize=1)
def index() -> dict:
    return read_json(paths.ICONS / "emoji_index.json", {}) or {}


def emoji_key(e: str) -> Optional[str]:
    """'💰', '1F4B0', '1f4b0' or '1f4b0-fe0f' -> '1f4b0' (the file/index key), or None if unknown or blocked."""
    e = (e or "").strip()
    if not e:
        return None
    if e.startswith("art-"):                              # clipart drawn or generated for ideas without an emoji (vt/art)
        from .. import art

        return e if art.known(e) else None
    if re.fullmatch(r"[0-9a-fA-F]{2,6}([-_ ][0-9a-fA-F]{2,6})*", e):
        key = "-".join(x.lower() for x in re.split(r"[-_ ]", e))
    else:
        key = "-".join(f"{ord(c):x}" for c in e)
    key = key.replace("-fe0f", "")
    if key in BLOCKED or key not in index():
        return None
    return key


def svg(key: str) -> Optional[str]:
    if key.startswith("art-"):
        from .. import art

        return art.svg(key)
    f = paths.ICONS / "emoji" / f"{key}.svg"
    return f.read_text(encoding="utf-8") if f.exists() else None


def label(key: str, lang: str = "en") -> str:
    if key.startswith("art-"):
        from .. import art

        return art.label(key)
    e = index().get(key) or {}
    return (e.get("bn") if lang == "bn" and e.get("bn") else e.get("en")) or key
