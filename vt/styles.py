"""Film styles: 66 looks adapted from lemo-opuscar (design/styles/<slug>.json, MIT, LemoLab), each with a theme the renderer draws
(design/themes/style-<slug>) and a style bible the director follows (essence, materials, colour, type, motion, camera, sound, native moves,
pitfalls). Imported by scripts/import_lemo_styles.py.

    vt styles [--category ...]          the list (Studio: New video, Look; MCP module style.list)
    vt styles show <slug>               one style bible (module style.get)
    for_theme(name) / brief(slug)       what a planner adds to its instructions when a project uses a style theme
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional

from . import paths


def _dir():
    return paths.ROOT / "design" / "styles"


@lru_cache(maxsize=1)
def index() -> list[dict[str, Any]]:
    f = _dir() / "index.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def listing(category: str = "", use: str = "") -> list[dict[str, Any]]:
    out = index()
    if category:
        out = [s for s in out if s["category"].lower() == category.lower()]
    if use:
        u = use.lower()
        out = [s for s in out if any(u in x.lower() for x in s.get("uses", [])) or u in s["summary"].lower()]
    return out


def get(slug: str) -> Optional[dict[str, Any]]:
    slug = slug.removeprefix("style-")
    f = _dir() / f"{slug}.json"
    if not f.exists() or "/" in slug or "\\" in slug:
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def for_theme(theme: str) -> Optional[dict[str, Any]]:
    return get(theme) if (theme or "").startswith("style-") else None


def brief(slug: str, keep: int = 4) -> str:
    """The style bible as instructions for a director: what the look is, how it moves, its native moves and the traps."""
    s = get(slug)
    if not s:
        return ""
    lines = [f"STYLE: {s['name']} ({s['category']}). {s['summary']}"]
    for key, title in (("essence", "What it is"), ("motion", "How it moves"), ("camera", "Camera"), ("native_moves", "Native moves (use one at the peak)"),
                       ("type", "Type and captions"), ("pitfalls", "Avoid")):
        if s.get(key):
            lines.append(title + ":")
            lines += [f"- {x[:260]}" for x in s[key][:keep]]
    lines.append("Keep the look on every scene; the style's demo film is an example of the grammar, never something to copy.")
    return "\n".join(lines)
