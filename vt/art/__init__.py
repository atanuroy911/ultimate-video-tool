"""Clipart for ideas with no emoji. Two sources, one namespace of sticker keys that start with "art-":
  * drawn by code (concepts.py): black hole, galaxy, atom, DNA, ... always available, offline;
  * generated on this computer by a small image model (generate.py), optional, cached in the data folder.
The rest of the app treats an "art-..." key exactly like an emoji key."""
from __future__ import annotations

import re
from typing import Optional

from . import concepts


def lookup(word: str) -> Optional[str]:
    """The art key for a spoken word ('galaxies' -> 'art-galaxy'), or None."""
    w = re.sub(r"[^\wঀ-৿ -]", "", (word or "").strip().lower()).strip()
    if not w:
        return None
    forms = [w, w.rstrip("s"), w[:-2] if w.endswith("es") else w, w[:-3] + "y" if w.endswith("ies") else w]
    for f in forms:
        for v in (f, f.replace(" ", "-")):
            if v in concepts.WORDS:
                return concepts.WORDS[v]
    from . import generate

    return generate.cached_key(w)


def known(key: str) -> bool:
    if key in concepts.KEYS:
        return True
    from . import generate

    return generate.exists(key)


def svg(key: str) -> Optional[str]:
    if key in concepts.KEYS:
        # several drawings share one page: their gradient/filter ids must not collide ("sp" in the galaxy is not "sp" in the nebula)
        return re.sub(r'(id="|url\(#)([A-Za-z0-9_-]+)', lambda m: f"{m.group(1)}{key}-{m.group(2)}", concepts.KEYS[key][1]())
    from . import generate

    return generate.svg(key)


def label(key: str) -> str:
    if key in concepts.KEYS:
        return concepts.KEYS[key][0]
    from . import generate

    return generate.label(key) or key
