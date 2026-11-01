"""Import the 67 film styles of lemo-opuscar (github.com/lemomo-ai/lemo-opuscar, MIT, LemoLab) as Video Tool styles.

    python scripts/import_lemo_styles.py <path to a lemo-opuscar checkout>

Each lemo style is a whole film engine plus a style bible (STYLE.md). We keep the bible as data the director reads (design/styles/<slug>.json:
essence, materials, colour logic, type, motion, camera, sound, native moves, pitfalls, uses) and derive a theme our renderer can draw
(design/themes/style-<slug>/theme.json: palette from the bible's own colours, its typefaces where they are bundled, background, motion and
caption feel). Text contrast is forced to WCAG levels (ink 7:1, accents and muted text 4.5:1). Bangla fonts are always kept as the fallback.
Re-running replaces what it wrote and nothing else.
"""
from __future__ import annotations

import colorsys
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLES = ROOT / "design" / "styles"
THEMES = ROOT / "design" / "themes"

# typefaces the bibles name that are bundled (renderer/scripts/build-fonts.mjs); first match wins
FONT_FAMILY = {
    "ibm plex mono": "IBM Plex Mono", "fredoka": "Fredoka", "caveat": "Caveat", "barlow condensed": "Barlow Condensed", "lilita one": "Lilita One",
    "jost": "Jost", "inter tight": "Inter Tight", "dm mono": "DM Mono", "cormorant garamond": "Cormorant Garamond", "cormorant": "Cormorant Garamond",
    "architects daughter": "Architects Daughter", "titan one": "Titan One", "quicksand": "Quicksand", "playfair display": "Playfair Display",
    "outfit": "Outfit", "old standard": "Old Standard TT", "league spartan": "League Spartan", "league gothic": "League Gothic",
    "josefin sans": "Josefin Sans", "jetbrains mono": "JetBrains Mono", "im fell": "IM Fell English", "fraunces": "Fraunces",
    "dela gothic": "Dela Gothic One", "bricolage grotesque": "Bricolage Grotesque", "big shoulders": "Big Shoulders Display", "bagel fat one": "Bagel Fat One",
    "b612": "B612", "space grotesk": "Space Grotesk", "inter": "Inter", "baloo": "Baloo 2",
}
BN_HEAD, BN_BODY = "Anek Bangla", "Hind Siliguri"
# drawn or monochrome looks: colour emoji would break them, so their pictures are line icons (Theme.picture)
LINE_STYLES = {"blueprint", "chalkboard", "whiteboard", "engraving", "woodcut", "one-line", "urban-sketch", "ink-wash", "telestrator", "transit-map",
               "pictogram-motion", "ascii-crt", "newsreel", "silent-film", "swiss-motion", "shadow-puppet"}
FALLBACK_FONT = {"mono": "IBM Plex Mono", "serif": "Cormorant Garamond", "hand": "Caveat", "display": "Bricolage Grotesque", "sans": "Inter"}


def sections(md: str) -> dict[str, str]:
    out, cur = {}, "_intro"
    for line in md.splitlines():
        m = re.match(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$", line)
        if m:
            cur = m.group(1).strip().lower()
            out[cur] = ""
        else:
            out[cur] = out.get(cur, "") + line + "\n"
    return {k: v.strip() for k, v in out.items()}


def pick(sec: dict[str, str], *names: str) -> str:
    for n in names:
        for k, v in sec.items():
            if k.startswith(n):
                return v
    return ""


def bullets(text: str, n: int = 12) -> list[str]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("- ", "* ")):
            out.append(re.sub(r"\*\*(.+?)\*\*", r"\1", line[2:]).strip())
        elif line.startswith("|") and not set(line) <= set("|-: "):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0].lower() not in ("move", "what", "beat"):
                out.append(" — ".join(c for c in cells if c))
    return out[:n]


# ----------------------------------------------------------------------------- colour
def rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def hexc(c) -> str:
    return "#" + "".join(f"{max(0, min(255, round(x * 255))):02X}" for x in c)


def lum(c) -> float:
    f = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4     # noqa: E731
    r, g, b = (f(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def sat(c) -> float:
    return colorsys.rgb_to_hls(*c)[2]


def toward(c, target, need: float, against) -> tuple:
    """Move colour c toward target (black or white) until it reaches the contrast `need` against `against`."""
    for i in range(41):
        t = i / 40
        x = tuple(a + (b - a) * t for a, b in zip(c, target))
        if contrast(x, against) >= need:
            return x
    return target


def mix(a, b, t: float):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def poster_colours(img: Path, n: int = 8) -> list[tuple]:
    """The poster's main colours, most covered first (the poster is the style's real look)."""
    from PIL import Image

    im = Image.open(img).convert("RGB").resize((320, 180))
    q = im.quantize(colors=16, method=Image.Quantize.MAXCOVERAGE)
    pal = q.getpalette()[: 16 * 3]
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    cols = [(tuple(pal[i * 3 + k] / 255 for k in range(3)), c / total) for c, i in counts]
    main = [c for c, _ in cols[:n]]
    # the accent is the most vivid colour that covers a little of the poster (amber phosphor text, a red stamp), not a large dull area
    vivid = sorted((c for c, share in cols if share >= 0.003), key=lambda c: -(colorsys.rgb_to_hsv(*c)[1] * colorsys.rgb_to_hsv(*c)[2]))
    if vivid and colorsys.rgb_to_hsv(*vivid[0])[1] > 0.35:
        main.insert(1, vivid[0])
    return main


def palette(text: str, poster: Path | None = None) -> dict[str, str]:
    hexes = [rgb(h) for h in dict.fromkeys(re.findall(r"#[0-9A-Fa-f]{6}\b", text))]
    if len(hexes) < 3 and poster is not None and poster.exists():
        hexes = poster_colours(poster) + hexes                       # the bible names its colours in words: read them off the poster
    if not hexes:
        hexes = [rgb("#F4F1EA"), rgb("#1A1A1A"), rgb("#E4572E")]
    bg = hexes[0]
    dark = lum(bg) < 0.18
    far = max(hexes, key=lambda c: contrast(c, bg))
    ink = far if contrast(far, bg) >= 7 else toward(far, (1, 1, 1) if dark else (0, 0, 0), 7, bg)
    colourful = sorted([c for c in hexes if c not in (bg, ink)], key=lambda c: -(colorsys.rgb_to_hsv(*c)[1] * colorsys.rgb_to_hsv(*c)[2]))   # vivid, not just saturated
    accent = colourful[0] if colourful else ((0.95, 0.42, 0.12) if not dark else (1.0, 0.78, 0.23))
    if contrast(accent, bg) < 4.5:                               # accents colour words too (captions, highlights): text contrast, not just shapes
        accent = toward(accent, (1, 1, 1) if dark else (0, 0, 0), 4.5, bg)
    accent2 = colourful[1] if len(colourful) > 1 else mix(accent, ink, 0.35)
    if contrast(accent2, bg) < 4.5:
        accent2 = toward(accent2, (1, 1, 1) if dark else (0, 0, 0), 4.5, bg)
    card = mix(bg, ink, 0.07)
    hl_ink = (1, 1, 1) if contrast((1, 1, 1), accent) >= contrast((0, 0, 0), accent) else (0, 0, 0)
    pill = lambda fill, text: fill if contrast(fill, text) >= 4.5 else toward(fill, (0, 0, 0) if text == (1, 1, 1) else (1, 1, 1), 4.5, text)   # noqa: E731
    tag_ink = (1, 1, 1) if contrast((1, 1, 1), accent2) >= contrast((0, 0, 0), accent2) else (0, 0, 0)
    out = {"bg": bg, "bg2": mix(bg, ink, 0.12), "ink": ink, "muted": toward(mix(ink, bg, 0.45), ink, 4.5, bg), "accent": accent, "accent2": accent2,
           "card": card, "card_border": ink, "caption_bg": card if not dark else mix(bg, (0, 0, 0), 0.4), "caption_ink": ink,
           "highlight_bg": pill(accent, hl_ink), "highlight_ink": hl_ink,                      # labels and highlights: text on a fill, 4.5:1 or more
           "tag_bg": pill(accent2, tag_ink), "tag_ink": tag_ink}
    res = {k: hexc(v) for k, v in out.items()}
    res["arc"] = f"rgba({round(ink[0] * 255)},{round(ink[1] * 255)},{round(ink[2] * 255)},0.08)"
    return res


# ----------------------------------------------------------------------------- the rest of the look
def font(type_text: str, essence: str) -> str:
    low = type_text.lower()
    hits = sorted(((low.find(k), v) for k, v in FONT_FAMILY.items() if k in low), key=lambda x: x[0])
    if hits:
        return hits[0][1]
    blob = (type_text + " " + essence).lower()
    for key, words in (("mono", ("mono", "terminal", "typewriter", "crt", "code")), ("hand", ("hand-letter", "handwrit", "chalk", "crayon", "marker", "brush")),
                       ("serif", ("serif", "engrav", "victorian", "newsprint", "letterpress", "art deco")), ("display", ("poster", "bold", "condensed"))):
        if any(w in blob for w in words):
            return FALLBACK_FONT[key]
    return FALLBACK_FONT["sans"]


def background(essence: str, rest: str, dark: bool) -> dict:
    for b in (essence.lower(), rest.lower()):                    # what the style IS decides first; materials only break ties
        got = _bg_kind(b)
        if got:
            return got
    return {"kind": "flat", "grain": 0.1, "arcs": False, "pattern": 0.3, "animated": False}


def _bg_kind(b: str) -> dict | None:
    for kind, words in (("grid", ("blueprint", "graph paper", "grid paper", "drafting", "schematic", "circuit board", "lidar", "isometric grid")),
                        ("dots", ("halftone", "risograph", "dot screen", "ben-day", "pixel")),
                        ("stripes", ("stripe", "scanline", "crt")),
                        ("aurora", ("hologram", "neon", "glow", "aurora")),
                        ("paper", ("paper", "sheet", "parchment", "canvas", "watercolour", "watercolor", "woodcut", "ink", "crayon", "chalk", "card")),
                        ("gradient", ("gradient", "sky", "light"))):
        if any(w in b for w in words):
            return {"kind": kind, "grain": 0.25 if kind == "paper" else 0.12, "arcs": False, "pattern": 0.35, "animated": kind in ("aurora", "gradient")}
    return None


def motion(text: str) -> str:
    b = text.lower()
    if any(w in b for w in ("squash", "rubber", "springy", "elastic", "bouncy")):
        return "bouncy"
    if any(w in b for w in ("slow", "gentle", "calm", "drift", "long take", "meditative", "ink spread", "bloom")):
        return "smooth"
    return "snappy"


def build(style_dir: Path) -> tuple[dict, dict] | None:
    meta_f, md_f = style_dir / "style.json", style_dir / "STYLE.md"
    if not meta_f.exists() or not md_f.exists():
        return None
    meta = json.loads(meta_f.read_text(encoding="utf-8"))
    md = md_f.read_text(encoding="utf-8")
    sec = sections(md)
    first = re.search(r"^>\s*(.+)$", md, re.M)
    essence, colour, typ = pick(sec, "essence"), pick(sec, "colour", "color"), pick(sec, "type")
    mat, mot = pick(sec, "material"), pick(sec, "motion")
    slug = meta["slug"]
    bible = {
        "slug": slug, "name": meta.get("en", slug), "category": meta.get("category_en", ""), "uses": meta.get("uses", []),
        "summary": first.group(1).strip() if first else meta.get("line", ""), "demo_film": meta.get("film", ""), "demo_line": meta.get("line", ""),
        "essence": bullets(essence), "materials": bullets(mat), "colour": bullets(colour), "type": bullets(typ), "motion": bullets(mot),
        "camera": bullets(pick(sec, "camera", "editing")), "sound": bullets(pick(sec, "sound")), "native_moves": bullets(pick(sec, "native")),
        "pitfalls": bullets(pick(sec, "pitfalls")), "variation": bullets(pick(sec, "variation")),
        "source": f"lemo-opuscar styles/{slug}/STYLE.md (MIT, LemoLab), github.com/lemomo-ai/lemo-opuscar",
    }
    pal = palette(colour + "\n" + mat, style_dir / "poster.jpg")
    dark = lum(rgb(pal["bg"])) < 0.18
    fam = font(typ, essence)
    blob = " ".join([essence, mat, colour])
    serif = fam in ("Cormorant Garamond", "Playfair Display", "Old Standard TT", "IM Fell English", "Fraunces")
    theme = {
        "name": f"style-{slug}", "label": meta.get("en", slug),
        "color": pal,
        "font": {"headline": [fam, BN_HEAD], "body": [fam if not serif else "Inter", BN_BODY], "numeral": [fam, BN_HEAD], "caption": ["Inter", BN_BODY],
                 "headline_weight": 700 if serif or fam in ("Caveat", "Architects Daughter") else 800},
        "shape": {"radius": 4 if any(w in blob.lower() for w in ("swiss", "brutal", "technical", "blueprint", "newsprint", "engrav")) else 18,
                  "stroke": 3, "shadow": {"x": 6, "y": 6, "color": pal["ink"], "blur": 0} if any(w in blob.lower() for w in ("memphis", "toy", "sticker", "pop"))
                  else {"x": 0, "y": 8, "color": "rgba(0,0,0,0.18)", "blur": 24}, "card_tilt": 0},
        "background": background(essence, mat + " " + colour, dark),
        "motion": {"preset": motion(mot + " " + essence)},
        "caption": {"style": "pop" if dark else "box", "reveal": "line", "weight": 800, "size": 60, "words_per_line": 3,
                    "safe_bottom": {"portrait": 380, "landscape": 64}},
        "style": f"lemo:{slug}",
        "picture": "line" if slug in LINE_STYLES else "emoji",
    }
    return bible, theme


def main() -> int:
    src = Path(sys.argv[1]) / "styles"
    STYLES.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    from vt.schema import Theme

    index = []
    for d in sorted(p for p in src.iterdir() if p.is_dir() and not p.name.startswith("_")):
        got = build(d)
        if not got:
            continue
        bible, theme = got
        Theme.model_validate(theme)
        (STYLES / f"{bible['slug']}.json").write_text(json.dumps(bible, indent=1, ensure_ascii=False), encoding="utf-8")
        tdir = THEMES / theme["name"]
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "theme.json").write_text(json.dumps(theme, indent=2, ensure_ascii=False), encoding="utf-8")
        index.append({"slug": bible["slug"], "name": bible["name"], "category": bible["category"], "uses": bible["uses"], "summary": bible["summary"],
                      "theme": theme["name"]})
    (STYLES / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    (STYLES / "CREDITS.md").write_text("The style bibles in this folder are adapted from lemo-opuscar (https://github.com/lemomo-ai/lemo-opuscar), "
                                       "MIT License, Copyright (c) 2026 LemoLab. The themes in design/themes/style-* are derived from them.\n", encoding="utf-8")
    print(f"{len(index)} styles imported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
