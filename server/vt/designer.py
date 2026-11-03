"""Design Studio engine: a theme = STYLE (shape, background, motion, captions, fonts) x PALETTE (colours).

Every combination is valid and readable: text colours are derived from the palette with a contrast check, so
"Surprise me" can never produce unreadable captions. Nothing here needs a model or the network.
"""
from __future__ import annotations

import colorsys
import random
from typing import Any, Optional

from .schema import Theme

# --------------------------------------------------------------------------- colour helpers


def _rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(c: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v * 255))):02x}" for v in c)


def luminance(h: str) -> float:
    def f(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (f(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable_on(bg: str, prefer: Optional[str] = None) -> str:
    """The preferred text colour if it has >= 4.5:1 on bg, otherwise black or white, whichever reads better."""
    if prefer and contrast(prefer, bg) >= 4.5:
        return prefer
    return "#111111" if contrast("#111111", bg) >= contrast("#ffffff", bg) else "#ffffff"


def fit_fill(fill: str, prefer_text: Optional[str] = None) -> str:
    """Nudge a fill colour (towards black or white) until some text colour reads on it at >= 4.5:1."""
    for step in range(0, 11):
        for target in ("#000000", "#ffffff"):
            c = mix(fill, target, step / 20)
            if contrast("#111111", c) >= 4.5 or contrast("#ffffff", c) >= 4.5:
                return c if step else fill
    return fill


def mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(x + (y - x) * t for x, y in zip(ra, rb)))  # type: ignore[arg-type]


def rgba(h: str, alpha: float) -> str:
    r, g, b = (round(v * 255) for v in _rgb(h))
    return f"rgba({r},{g},{b},{alpha})"


# --------------------------------------------------------------------------- palettes: bg, bg2, ink, accent, accent2, card
# `dark` palettes put light text on a dark background.
PALETTES: dict[str, dict[str, Any]] = {
    "marigold":  {"label": "Marigold",  "dark": False, "bg": "#f1efe8", "bg2": "#ffe9c2", "ink": "#1a1a1a", "accent": "#f26a1f", "accent2": "#ffc83a", "card": "#e3eee0"},
    "mint":      {"label": "Mint",      "dark": False, "bg": "#eaf6ef", "bg2": "#c9ecd9", "ink": "#12332a", "accent": "#12a36b", "accent2": "#ffd166", "card": "#ffffff"},
    "sky":       {"label": "Sky",       "dark": False, "bg": "#eaf2ff", "bg2": "#cfe0ff", "ink": "#10223f", "accent": "#2f6bff", "accent2": "#ffb703", "card": "#ffffff"},
    "rose":      {"label": "Rose",      "dark": False, "bg": "#fff0f3", "bg2": "#ffd6e0", "ink": "#3a1220", "accent": "#e63b6f", "accent2": "#ffd23f", "card": "#ffffff"},
    "lavender":  {"label": "Lavender",  "dark": False, "bg": "#f3efff", "bg2": "#dcd2ff", "ink": "#241a4a", "accent": "#7c4dff", "accent2": "#ffcf4a", "card": "#ffffff"},
    "sand":      {"label": "Sand",      "dark": False, "bg": "#f6efe3", "bg2": "#ead8b8", "ink": "#2b2116", "accent": "#b5651d", "accent2": "#2a9d8f", "card": "#fffaf0"},
    "lemon":     {"label": "Lemon",     "dark": False, "bg": "#fffbe6", "bg2": "#fff1a8", "ink": "#222200", "accent": "#e0a800", "accent2": "#ff5a36", "card": "#ffffff"},
    "coral":     {"label": "Coral",     "dark": False, "bg": "#fff3ee", "bg2": "#ffd9cc", "ink": "#33150d", "accent": "#ff5a3c", "accent2": "#16a6a0", "card": "#ffffff"},
    "mono":      {"label": "Ink & paper", "dark": False, "bg": "#f7f7f5", "bg2": "#e6e6e1", "ink": "#151515", "accent": "#151515", "accent2": "#ffd400", "card": "#ffffff"},
    "neon":      {"label": "Neon night", "dark": True, "bg": "#0b0d1a", "bg2": "#1a1240", "ink": "#f2f4ff", "accent": "#35e0ff", "accent2": "#ff4fd8", "card": "#161a33"},
    "ember":     {"label": "Ember",     "dark": True, "bg": "#16100d", "bg2": "#3a1a10", "ink": "#fff3ea", "accent": "#ff7a2f", "accent2": "#ffd166", "card": "#2a1d17"},
    "forest":    {"label": "Forest",    "dark": True, "bg": "#0e1a14", "bg2": "#12352a", "ink": "#eaf7ef", "accent": "#3ddc97", "accent2": "#f4d35e", "card": "#17291f"},
    "ocean":     {"label": "Deep ocean", "dark": True, "bg": "#08141f", "bg2": "#0b3350", "ink": "#e8f4ff", "accent": "#3aa0ff", "accent2": "#7ef0d4", "card": "#10293d"},
    "plum":      {"label": "Plum",      "dark": True, "bg": "#160f1f", "bg2": "#2e1a45", "ink": "#f6eeff", "accent": "#c77dff", "accent2": "#ff9f1c", "card": "#241633"},
    "graphite":  {"label": "Graphite",  "dark": True, "bg": "#141517", "bg2": "#25282d", "ink": "#f1f3f5", "accent": "#ffd43b", "accent2": "#74c0fc", "card": "#1f2226"},
    "sunset":    {"label": "Sunset",    "dark": True, "bg": "#1d1030", "bg2": "#6a1f4b", "ink": "#fff1f5", "accent": "#ff6b6b", "accent2": "#ffd93d", "card": "#2c1a45"},
    "bn-flag":   {"label": "Green & red", "dark": True, "bg": "#06402b", "bg2": "#0a5c3c", "ink": "#f3fff8", "accent": "#f42a41", "accent2": "#ffd166", "card": "#0b4f36"},
    "bubblegum": {"label": "Bubblegum", "dark": False, "bg": "#fff0fa", "bg2": "#d9f3ff", "ink": "#2a1740", "accent": "#ff4fa3", "accent2": "#4cc9f0", "card": "#ffffff"},
}

# --------------------------------------------------------------------------- styles
# shadow: (x, y, blur, "ink"|"accent"|"glow"); strokes of 0 mean borderless.
STYLES: dict[str, dict[str, Any]] = {
    "brutalist": {"label": "Bold outline", "about": "Thick borders, hard offset shadows, tilted cards. The reference look.",
                  "radius": 22, "stroke": 4, "shadow": (7, 7, 0, "ink"), "tilt": -3, "bg": "paper", "arcs": True, "grain": 0.4, "animated": False,
                  "motion": "snappy", "caption": "box", "reveal": "line", "fonts": ("Inter", "Anek Bangla"), "weight": 800},
    "soft": {"label": "Soft cards", "about": "Borderless rounded cards floating on a gradient mesh.",
             "radius": 34, "stroke": 0, "shadow": (0, 14, 36, "ink"), "tilt": 0, "bg": "mesh", "arcs": False, "grain": 0, "animated": False,
             "motion": "smooth", "caption": "pill", "reveal": "line", "fonts": ("Inter", "Hind Siliguri"), "weight": 700},
    "neon": {"label": "Neon glow", "about": "Glowing outlines on a slowly moving aurora.",
             "radius": 26, "stroke": 3, "shadow": (0, 0, 28, "glow"), "tilt": 0, "bg": "aurora", "arcs": False, "grain": 0, "animated": True,
             "motion": "snappy", "caption": "pill", "reveal": "words", "fonts": ("Space Grotesk", "Baloo Da 2"), "weight": 700},
    "editorial": {"label": "Editorial", "about": "Sharp corners, thin rules, quiet stripes. Looks like a magazine.",
                  "radius": 4, "stroke": 2, "shadow": (0, 0, 0, "ink"), "tilt": 0, "bg": "stripes", "arcs": False, "grain": 0, "animated": False, "pattern": 0.25,
                  "motion": "smooth", "caption": "underline", "reveal": "line", "fonts": ("Space Grotesk", "Hind Siliguri"), "weight": 700},
    "sticker": {"label": "Sticker pop", "about": "Chunky borders, big shadows, playful tilt on a dotted backdrop.",
                "radius": 40, "stroke": 6, "shadow": (10, 10, 0, "ink"), "tilt": 4, "bg": "dots", "arcs": False, "grain": 0, "animated": True,
                "motion": "bouncy", "caption": "box", "reveal": "words", "fonts": ("Baloo 2", "Baloo Da 2"), "weight": 800},
    "blueprint": {"label": "Blueprint", "about": "Thin lines on a drifting grid, precise and technical.",
                  "radius": 6, "stroke": 2, "shadow": (4, 4, 0, "ink"), "tilt": 0, "bg": "grid", "arcs": False, "grain": 0, "animated": True,
                  "motion": "snappy", "caption": "box", "reveal": "line", "fonts": ("Space Grotesk", "Anek Bangla"), "weight": 700},
    "calm": {"label": "Calm waves", "about": "Gentle rolling lines and soft shadows.",
             "radius": 36, "stroke": 0, "shadow": (0, 10, 30, "ink"), "tilt": 0, "bg": "waves", "arcs": False, "grain": 0, "animated": True, "pattern": 0.4,
             "motion": "smooth", "caption": "pill", "reveal": "line", "fonts": ("Inter", "Noto Sans Bengali"), "weight": 700},
    "retro": {"label": "Retro checks", "about": "Checkerboard, heavy borders, bouncy motion.",
              "radius": 10, "stroke": 5, "shadow": (8, 8, 0, "ink"), "tilt": -2, "bg": "checks", "arcs": False, "grain": 0, "animated": True, "pattern": 0.35,
              "motion": "bouncy", "caption": "box", "reveal": "words", "fonts": ("Baloo 2", "Baloo Da 2"), "weight": 800},
    "clean": {"label": "Clean", "about": "Almost no decoration. Lets the words and icons speak.",
              "radius": 18, "stroke": 1.5, "shadow": (0, 0, 0, "ink"), "tilt": 0, "bg": "flat", "arcs": False, "grain": 0, "animated": False,
              "motion": "smooth", "caption": "underline", "reveal": "line", "fonts": ("Inter", "Hind Siliguri"), "weight": 700},
    "halo": {"label": "Halo rings", "about": "Concentric rings breathing behind glowing cards.",
             "radius": 30, "stroke": 2, "shadow": (0, 0, 34, "glow"), "tilt": 0, "bg": "rings", "arcs": False, "grain": 0, "animated": True, "pattern": 0.5,
             "motion": "smooth", "caption": "pill", "reveal": "line", "fonts": ("Space Grotesk", "Baloo Da 2"), "weight": 700},
}


def colours(p: dict[str, Any], style: dict[str, Any]) -> dict[str, str]:
    dark = p["dark"]
    bg, ink = p["bg"], readable_on(p["bg"], p["ink"])
    accent, accent2, card = fit_fill(p["accent"]), fit_fill(p["accent2"]), p["card"]
    card_ink_ok = contrast(ink, card) >= 4.5
    cap_bg = card if dark else "#ffffff"
    if style["caption"] in ("underline",):
        cap_bg = bg
    return {
        "bg": bg, "bg2": p["bg2"], "ink": ink, "muted": mix(ink, bg, 0.45), "accent": accent, "accent2": accent2,
        "card": card, "card_border": ink if card_ink_ok else readable_on(card),
        "caption_bg": cap_bg, "caption_ink": readable_on(cap_bg, ink),
        "highlight_bg": accent, "highlight_ink": readable_on(accent, "#ffffff"),
        "tag_bg": accent2, "tag_ink": readable_on(accent2, "#111111"),
        "arc": rgba(ink, 0.12 if dark else 0.09),
    }


def build_theme(style: str, palette: str, name: Optional[str] = None, overrides: Optional[dict[str, Any]] = None) -> Theme:
    if style not in STYLES:
        raise ValueError(f"unknown style '{style}'")
    if palette not in PALETTES:
        raise ValueError(f"unknown palette '{palette}'")
    st, pl = STYLES[style], PALETTES[palette]
    c = colours(pl, st)
    sx, sy, blur, kind = st["shadow"]
    shadow_color = {"ink": c["ink"] if blur == 0 else rgba("#000000", 0.28 if not pl["dark"] else 0.55), "accent": c["accent"], "glow": c["accent"]}[kind]
    latin, bn = st["fonts"]
    data = {
        "name": name or f"{style}-{palette}",
        "label": f"{st['label']} · {pl['label']}",
        "color": c,
        "font": {"headline": [latin, bn], "body": [latin, "Hind Siliguri"], "numeral": [latin, bn], "caption": [latin, "Hind Siliguri"], "headline_weight": st["weight"]},
        "shape": {"radius": st["radius"], "stroke": st["stroke"], "shadow": {"x": sx, "y": sy, "blur": blur, "color": shadow_color}, "card_tilt": st["tilt"]},
        "background": {"kind": st["bg"], "grain": st["grain"], "arcs": st["arcs"], "pattern": st.get("pattern", 0.5), "animated": st["animated"]},
        "motion": {"preset": st["motion"]},
        "caption": {"style": st["caption"], "reveal": st["reveal"], "weight": 700, "size": 58, "words_per_line": 6, "safe_bottom": {"portrait": 300, "landscape": 64}},
        "currency": "৳", "sfx": "pop", "style": style, "palette": palette,
    }
    for k, v in (overrides or {}).items():
        if isinstance(v, dict) and isinstance(data.get(k), dict):
            data[k].update(v)
        else:
            data[k] = v
    return Theme.model_validate(data)


def surprise(seed: Optional[int] = None, dark: Optional[bool] = None) -> Theme:
    """A random but always readable combination. The same seed gives the same theme."""
    rnd = random.Random(seed)
    pals = [k for k, v in PALETTES.items() if dark is None or v["dark"] == dark]
    style, palette = rnd.choice(list(STYLES)), rnd.choice(pals)
    t = build_theme(style, palette, name=f"surprise-{rnd.randrange(10_000, 99_999)}")
    # small personal twists
    t.shape.radius = max(0, round(t.shape.radius * rnd.uniform(0.7, 1.3)))
    if rnd.random() < 0.5:
        t.background.animated = not t.background.animated
    return t


def hue_shift(theme: Theme, degrees: float) -> Theme:
    """Rotate every accent-ish colour (not text/background luminance), for quick variations of a saved theme."""
    out = theme.model_copy(deep=True)
    for f in ("accent", "accent2", "highlight_bg", "tag_bg"):
        h = getattr(out.color, f)
        if h and h.startswith("#") and len(h) == 7:
            hh, ll, ss = colorsys.rgb_to_hls(*_rgb(h))
            setattr(out.color, f, _hex(colorsys.hls_to_rgb((hh + degrees / 360) % 1, ll, ss)))
    out.color.highlight_ink = readable_on(out.color.highlight_bg, "#ffffff")
    out.color.tag_ink = readable_on(out.color.tag_bg or out.color.accent2, "#111111")
    return out


def catalogue() -> dict[str, Any]:
    return {
        "styles": [{"key": k, "label": v["label"], "about": v["about"], "background": v["bg"], "animated": v["animated"], "motion": v["motion"]} for k, v in STYLES.items()],
        "palettes": [{"key": k, "label": v["label"], "dark": v["dark"], "colors": [v["bg"], v["accent"], v["accent2"], v["ink"]]} for k, v in PALETTES.items()],
        "backgrounds": ["paper", "flat", "gradient", "grid", "dots", "stripes", "checks", "waves", "rings", "mesh", "aurora"],
    }


# --------------------------------------------------------------------------- automatic design from the video's content
MOOD_LOOKS: dict[str, tuple[list[str], list[str]]] = {
    "story":      (["sticker", "soft", "brutalist", "calm"], ["marigold", "coral", "sand", "lemon", "mint", "rose"]),
    "finance":    (["brutalist", "editorial", "clean", "blueprint"], ["sky", "mint", "graphite", "mono", "ocean", "marigold"]),
    "business":   (["clean", "editorial", "blueprint"], ["sky", "graphite", "mono", "plum", "ocean"]),
    "tech":       (["neon", "halo", "blueprint"], ["neon", "ocean", "plum", "graphite"]),
    "education":  (["soft", "clean", "blueprint", "sticker"], ["sky", "lavender", "mint", "lemon", "bubblegum"]),
    "health":     (["calm", "soft", "clean"], ["mint", "forest", "sky", "sand"]),
    "kids":       (["sticker", "retro", "soft"], ["bubblegum", "lemon", "coral", "rose"]),
    "motivation": (["brutalist", "halo", "neon", "sticker"], ["ember", "sunset", "marigold", "coral", "bn-flag"]),
    "news":       (["editorial", "clean", "blueprint"], ["mono", "graphite", "sky"]),
    "nature":     (["calm", "soft"], ["forest", "mint", "sand", "ocean"]),
    "food":       (["sticker", "soft", "retro"], ["coral", "lemon", "marigold", "rose"]),
    "sports":     (["neon", "brutalist", "retro"], ["ember", "sunset", "neon", "coral"]),
    "other":      (list(STYLES), list(PALETTES)),
}
MOOD_PROTOTYPES = {
    "story": "a story about a person, a family and what happened to them", "finance": "money, prices, savings, investing, banks and loans",
    "business": "business, customers, marketing, sales and companies", "tech": "technology, software, computers, apps and artificial intelligence",
    "education": "learning, school, lessons and how something works", "health": "health, medicine, exercise, food and sleep",
    "kids": "a children's story with animals and playful characters", "motivation": "motivation, success, discipline, habits and goals",
    "news": "news and facts about events in the world", "nature": "nature, animals, weather, plants and the environment",
    "food": "cooking, recipes and food", "sports": "sports, games, matches and competition",
}


def mood_from_text(text: str) -> str:
    """Best-matching category for the transcript, by meaning (the local embedding model; 'story' if it is not available)."""
    try:
        import numpy as np

        from .visuals.picker import _embedder

        emb = _embedder()
        if emb is None or not text.strip():
            return "story"
        keys = list(MOOD_PROTOTYPES)
        P = emb.encode([MOOD_PROTOTYPES[k] for k in keys], prefix="passage: ", max_len=48)
        q = emb.encode([text[:1500]], prefix="query: ", max_len=256)[0]
        return keys[int(np.argmax(P @ q))]
    except Exception:
        return "story"


def auto_theme(seed: str, mood: str = "story", name: Optional[str] = None, looks: Optional[dict] = None) -> Theme:
    """A theme chosen from the video's mood. The same video (seed) always gets the same look; different videos get different ones."""
    import hashlib

    styles, palettes = MOOD_LOOKS.get(mood, MOOD_LOOKS["other"])
    if looks and looks.get("styles") and looks.get("palettes"):         # a use-case profile narrows the choice (a product video is not 'retro checks')
        styles, palettes = [x for x in looks["styles"] if x in STYLES] or styles, [x for x in looks["palettes"] if x in PALETTES] or palettes
    h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    return build_theme(styles[h % len(styles)], palettes[(h // 97) % len(palettes)], name=name or f"auto-{h % 10**6:06d}")
