"""Music "auto": the track an editor would reach for, from what the video is about.

The context reading (vt/context.py) gives the video's mood (story, finance, tech, kids, motivation, news ...). Each mood has
the music moods that suit it, in order; among the bundled tracks of the first mood that has any, the project id picks one, so
the choice is stable for a project and differs between projects. The choice is written into the project's options, so the
person sees which track it is and can change it.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from . import paths
from .util import read_json

FITS = {
    "story": ["playful", "lofi", "calm"], "kids": ["playful", "upbeat"], "food": ["playful", "lofi"],
    "finance": ["corporate", "lofi"], "business": ["corporate", "upbeat"], "tech": ["upbeat", "corporate"],
    "education": ["lofi", "calm", "corporate"], "health": ["calm", "lofi"], "nature": ["calm", "lofi"],
    "motivation": ["upbeat", "hiphop"], "sports": ["hiphop", "upbeat"], "news": ["tense", "corporate"],
    "other": ["lofi", "upbeat"],
}


def pick(mood: Optional[str], seed: str) -> Optional[str]:
    tracks = read_json(paths.MUSIC / "index.json", []) or []
    for want in FITS.get(mood or "other", FITS["other"]):
        cands = sorted(m["id"] for m in tracks if m.get("mood") == want)
        if cands:
            return cands[int(hashlib.sha1(seed.encode()).hexdigest(), 16) % len(cands)]
    return tracks[0]["id"] if tracks else None
