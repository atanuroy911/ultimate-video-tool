"""Filesystem locations.

VT_PROJECTS moves the projects folder. VT_DATA moves everything the user owns (projects, models, settings, custom themes, own music):
the installed desktop app sets it to a per-user folder so program files can be replaced on update without touching user data.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_CHECKOUT = ROOT.parent if (ROOT.parent / '.git').exists() else ROOT
DATA = Path(os.environ["VT_DATA"]).resolve() if os.environ.get("VT_DATA") else _CHECKOUT
_LEGACY_CHECKOUT_DATA = not os.environ.get('VT_DATA') and _CHECKOUT != ROOT
DESIGN = ROOT / "design"
BUILTIN_THEMES_DIR = DESIGN / "themes"
THEMES = DATA / "themes" if DATA != ROOT and not _LEGACY_CHECKOUT_DATA else BUILTIN_THEMES_DIR
FONTS = DESIGN / "fonts"
ICONS = DESIGN / "icons"
RENDERER = ROOT / "renderer"
RUNTIME = RENDERER / "runtime"
ASSETS = ROOT / "assets"
MUSIC = ASSETS / "music"
SFX = ASSETS / "sfx"
MODELS = DATA / "models"
PROJECTS = Path(os.environ.get("VT_PROJECTS", DATA / "projects"))
GLOBAL_GLOSSARY = DATA / "glossary.json"
SETTINGS = DATA / "settings.json"
USER_MUSIC = DATA / "user-music" if DATA != ROOT and not _LEGACY_CHECKOUT_DATA else ASSETS / "music" / "user"


def ensure_data() -> None:
    """Create the user-data folders; copy the built-in themes next to the user's own (refreshed on every start)."""
    import shutil

    for d in (PROJECTS, MODELS, USER_MUSIC):
        d.mkdir(parents=True, exist_ok=True)
    if THEMES != BUILTIN_THEMES_DIR and BUILTIN_THEMES_DIR.is_dir():       # the engine package has no themes: it has no Studio
        THEMES.mkdir(parents=True, exist_ok=True)
        for src in BUILTIN_THEMES_DIR.iterdir():
            if src.is_dir():
                shutil.copytree(src, THEMES / src.name, dirs_exist_ok=True)


def mcp_seen_path() -> Path:
    """Where the MCP server records its last tool call; lives in the projects folder (tests use a temp one)."""
    return PROJECTS / ".mcp_seen.json"


if DATA != ROOT:
    ensure_data()
