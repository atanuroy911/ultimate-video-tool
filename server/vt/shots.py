"""Code-native shots (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD, step C1).

A shot is a folder an agent (Claude Code, Codex, the director) or a template writes:

    <project>/shots/<id>/index.html      the shot: HTML/CSS/SVG, motion on a paused GSAP timeline in window.__timelines[<root id>]
    <project>/shots/<id>/shot.json       title, duration, size, the knobs it offers, who made it
    <project>/shots/<id>/overrides.json  every change made in the visual editor; the visual editor never rewrites index.html
    <project>/shots/<id>/assets/         its pictures, clips and sounds

`build()` turns a shot into a page the renderer can draw: the overrides are written in as CSS (order-free, so they work whatever the shot's own
script does) plus a small script for text, a Content-Security-Policy keeps the page off the network, and the runtime (GSAP, fonts) is copied in.
The overrides are checked value by value, so nothing in them can break out of the CSS or the page.
"""
from __future__ import annotations

import json
import math
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from . import paths

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
KNOB = re.compile(r"^--[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
SAFE_CSS_VALUE = re.compile(r"^[A-Za-z0-9#%.,()\s'\"+/-]{1,200}$")        # no ; { } < > \ : nothing can close the rule or the tag
COLOUR = re.compile(r"^(#[0-9a-fA-F]{3,8}|(rgb|rgba|hsl|hsla)\([0-9.,%\s/-]{1,60}\)|[a-zA-Z]{3,30})$")
FONT = re.compile(r"^[A-Za-z0-9 ,'\"-]{1,120}$")
CSP = "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
MAX_TEXT = 2000

# What the visual editor may set on an element: name -> (CSS property, checker, unit)
STYLES: dict[str, tuple[str, Any, str]] = {
    "color": ("color", COLOUR, ""),
    "background": ("background", COLOUR, ""),
    "fontSize": ("font-size", "number", "px"),
    "fontWeight": ("font-weight", "weight", ""),
    "fontFamily": ("font-family", FONT, ""),
    "letterSpacing": ("letter-spacing", "number", "px"),
    "opacity": ("opacity", "unit", ""),
}


class ShotError(ValueError):
    """A shot or its overrides cannot be used; the message says what to fix."""


def _number(v: Any, what: str, lo: float = -100000, hi: float = 100000) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ShotError(f"{what} must be a number from {lo:g} to {hi:g}")
    return float(v)


def check_overrides(raw: Any) -> dict:
    """The overrides as the editor may write them, or ShotError. Unknown fields are refused rather than ignored, so a mistake is seen."""
    if raw in (None, ""):
        return {"knobs": {}, "elements": {}}
    if not isinstance(raw, dict) or set(raw) - {"knobs", "elements", "version"}:
        raise ShotError("overrides hold only 'knobs' and 'elements'")
    knobs: dict[str, str] = {}
    for k, v in (raw.get("knobs") or {}).items():
        if not KNOB.match(str(k)):
            raise ShotError(f"knob '{k}' must be a CSS variable name like --accent")
        if not isinstance(v, str) or not SAFE_CSS_VALUE.match(v):
            raise ShotError(f"knob {k}: '{v}' is not a plain CSS value")
        knobs[k] = v
    elements: dict[str, dict] = {}
    for eid, e in (raw.get("elements") or {}).items():
        if not ID.match(str(eid)):
            raise ShotError(f"element id '{eid}' must be letters, digits, - or _")
        if not isinstance(e, dict) or set(e) - {"text", "x", "y", "scale", "rotate", "hidden", "style"}:
            raise ShotError(f"element {eid}: only text, x, y, scale, rotate, hidden and style can be changed")
        out: dict[str, Any] = {}
        if "text" in e:
            if not isinstance(e["text"], str) or len(e["text"]) > MAX_TEXT:
                raise ShotError(f"element {eid}: text must be text of at most {MAX_TEXT} characters")
            out["text"] = e["text"]
        for key, lo, hi in (("x", -10000, 10000), ("y", -10000, 10000), ("scale", 0.01, 50), ("rotate", -3600, 3600)):
            if key in e:
                out[key] = _number(e[key], f"element {eid}: {key}", lo, hi)
        if "hidden" in e:
            if not isinstance(e["hidden"], bool):
                raise ShotError(f"element {eid}: hidden is true or false")
            out["hidden"] = e["hidden"]
        style = e.get("style") or {}
        if not isinstance(style, dict) or set(style) - set(STYLES):
            raise ShotError(f"element {eid}: style may set {', '.join(STYLES)}")
        good: dict[str, Any] = {}
        for name, v in style.items():
            _, check, _ = STYLES[name]
            if check == "number":
                good[name] = _number(v, f"element {eid}: {name}", -1000, 2000)
            elif check == "unit":
                good[name] = _number(v, f"element {eid}: {name}", 0, 1)
            elif check == "weight":
                w = _number(float(v) if isinstance(v, str) and v.isdigit() else v, f"element {eid}: fontWeight", 100, 900)
                good[name] = int(w)
            elif not isinstance(v, str) or not check.match(v):
                raise ShotError(f"element {eid}: {name} '{v}' is not allowed")
            else:
                good[name] = v
        if good:
            out["style"] = good
        elements[str(eid)] = out
    return {"knobs": knobs, "elements": elements}


def _fmt(n: float) -> str:
    return f"{n:.4f}".rstrip("0").rstrip(".") if n != int(n) else str(int(n))


def overrides_css(o: dict) -> str:
    """The checked overrides as one style sheet. `translate`/`scale`/`rotate` are separate CSS properties from `transform`, so they add to the
    shot's own animation instead of replacing it. !important beats the shot's own rules; the shot's script animates `transform`, never these."""
    rules = []
    if o["knobs"]:
        rules.append(":root{" + "".join(f"{k}:{v} !important;" for k, v in o["knobs"].items()) + "}")
    for eid, e in o["elements"].items():
        decl = []
        if e.get("hidden"):
            decl.append("display:none")
        if "x" in e or "y" in e:
            decl.append(f"translate:{_fmt(e.get('x', 0))}px {_fmt(e.get('y', 0))}px")
        if "scale" in e:
            decl.append(f"scale:{_fmt(e['scale'])}")
        if "rotate" in e:
            decl.append(f"rotate:{_fmt(e['rotate'])}deg")
        for name, v in (e.get("style") or {}).items():
            prop, _, unit = STYLES[name]
            decl.append(f"{prop}:{_fmt(v) + unit if isinstance(v, (int, float)) else v}")
        if decl:
            rules.append(f'[data-vt-id="{eid}"]{{' + "".join(d + " !important;" for d in decl) + "}")
    return "\n".join(rules)


def _text_script(o: dict) -> str:
    texts = {eid: e["text"] for eid, e in o["elements"].items() if "text" in e}
    if not texts:
        return ""
    payload = json.dumps(texts, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    return ("<script>(function(t){for(var k in t){var e=document.querySelector('[data-vt-id=\"'+k+'\"]');if(e)e.textContent=t[k];}})(" + payload + ");</script>")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as e:
        raise ShotError(f"{path.name} cannot be read: {e}") from e


def save_overrides(shot_dir: Path, raw: Any) -> dict:
    o = check_overrides(raw)
    tmp = shot_dir / "overrides.json.tmp"
    tmp.write_text(json.dumps({"version": 1, **o}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(shot_dir / "overrides.json")
    return o


def info(shot_dir: Path) -> dict:
    """shot.json with its defaults; the size and duration fall back to what index.html's root says."""
    return info_of(shot_dir.name, (shot_dir / "index.html").read_text(encoding="utf-8"), read_json(shot_dir / "shot.json", {}))


def info_of(shot_id: str, html: str, meta: Optional[dict] = None) -> dict:
    meta = meta or {}
    root = re.search(r"<[^>]*data-composition-id=\"([^\"]+)\"[^>]*>", html)
    if not root:
        raise ShotError("index.html needs one root element with data-composition-id, data-start, data-duration, data-width and data-height")
    attrs = dict(re.findall(r"data-([a-z-]+)=\"([^\"]*)\"", root.group(0)))
    try:
        duration = float(meta.get("duration") or attrs["duration"])
        width, height = int(meta.get("width") or attrs["width"]), int(meta.get("height") or attrs["height"])
    except (KeyError, ValueError) as e:
        raise ShotError("the root element needs data-duration, data-width and data-height") from e
    if not (0 < duration <= 600 and 16 <= width <= 4096 and 16 <= height <= 4096):
        raise ShotError("data-duration must be 0 to 600 seconds and data-width / data-height 16 to 4096 pixels")
    return {"id": shot_id, "title": meta.get("title") or shot_id, "duration": duration, "width": width, "height": height,
            "root": attrs.get("composition-id", "root"), "knobs": meta.get("knobs") or [], "made_by": meta.get("made_by") or "", "prompt": meta.get("prompt") or ""}


NETWORK = re.compile(r"""(?:src|href)\s*=\s*["']?\s*(?:https?:)?//|url\(\s*["']?\s*(?:https?:)?//|@import|\bfetch\s*\(|XMLHttpRequest|WebSocket\s*\(""", re.I)


def problems(shot_id: str, html: str, *, aspect_size: Optional[tuple[int, int]] = None) -> list[str]:
    """What a director must fix before a shot can be used, in words it can act on. Empty when the shot is good."""
    out: list[str] = []
    if not ID.match(shot_id or ""):
        out.append(f"shot id '{shot_id}' must be letters, digits, - or _")
    try:
        i = info_of(shot_id, html)
    except ShotError as e:
        return out + [f"shot {shot_id}: {e}"]
    if aspect_size and (i["width"], i["height"]) != aspect_size:
        out.append(f"shot {shot_id}: data-width/data-height are {i['width']}x{i['height']}; this video is {aspect_size[0]}x{aspect_size[1]}")
    if NETWORK.search(html):
        out.append(f"shot {shot_id}: it reaches for the network (a web address, @import, fetch or a socket). A shot runs offline: use runtime/gsap.min.js, the fonts in fonts/fonts.css, and inline SVG or CSS for pictures")
    if "__timelines" not in html:
        out.append(f"shot {shot_id}: register its paused GSAP timeline as window.__timelines['{i['root']}'] so the renderer can seek it")
    if re.search(r"\b(setTimeout|setInterval|requestAnimationFrame|Date\.now|new Date|Math\.random)\b", html):
        out.append(f"shot {shot_id}: motion must come from the paused timeline only (no setTimeout, setInterval, requestAnimationFrame, Date or Math.random), so every frame is the same each time it is drawn")
    if not ids_in(html):
        out.append(f"shot {shot_id}: give every text and every main shape a data-vt-id so the person can select and change it without code")
    return out


def ids_in(html: str) -> list[str]:
    """The element ids the visual editor can select."""
    return list(dict.fromkeys(re.findall(r"data-vt-id=\"([A-Za-z0-9_-]+)\"", html)))


def theme_vars(project) -> dict[str, str]:
    """The video's look as CSS variables every shot can use (--vt-bg, --vt-ink, --vt-accent, --vt-font-headline ...), so a theme change restyles the shots too."""
    try:
        t = project.theme(project.meta().theme)
    except Exception:                                   # noqa: BLE001  a shot still draws with its own colours
        return {}
    c = t.color
    fam = lambda names: ", ".join(f"'{n}'" for n in (names or [])) + ", sans-serif"
    out = {"--vt-bg": c.bg, "--vt-bg2": c.bg2 or c.bg, "--vt-ink": c.ink, "--vt-muted": c.muted, "--vt-accent": c.accent, "--vt-accent2": c.accent2,
           "--vt-card": c.card, "--vt-card-border": c.card_border, "--vt-font-headline": fam(t.font.headline), "--vt-font-body": fam(t.font.body)}
    return {k: v for k, v in out.items() if isinstance(v, str) and SAFE_CSS_VALUE.match(v)}


def build(shot_dir: Path, out_dir: Path, overrides: Optional[dict] = None, *, editor: bool = False, theme: Optional[dict] = None) -> Path:
    """A render-ready copy of the shot in out_dir: index.html with the CSP, the video's theme variables, the overrides and the runtime. Returns out_dir.
    editor=True: the page for the visual editor, without the saved edits (the editor sends them live) and with the bridge it talks to."""
    html = (shot_dir / "index.html").read_text(encoding="utf-8")
    if editor:
        overrides = {}
    info(shot_dir)                                                           # refuse a shot the renderer cannot time
    o = check_overrides(overrides if overrides is not None else read_json(shot_dir / "overrides.json", {}))
    themed = "".join(f"{k}:{v};" for k, v in (theme or {}).items() if KNOB.match(k) and SAFE_CSS_VALUE.match(v))
    head = (f'<meta http-equiv="Content-Security-Policy" content="{CSP}">\n' + (f'<style id="vt-theme">:root{{{themed}}}</style>\n' if themed else "")
            + f'<style id="vt-overrides">\n{overrides_css(o)}\n</style>\n')
    if re.search(r"</head>", html, re.I):
        html = re.sub(r"</head>", lambda m: head + m.group(0), html, count=1, flags=re.I)
    else:
        html = head + html
    text = _text_script(o)
    if text:
        # Text goes in before the shot's first script in the body, so a timeline built from the text (split words, measured widths) sees the new text.
        body = re.search(r"<body[^>]*>", html, re.I)
        start = body.end() if body else 0
        first = re.search(r"<script\b", html[start:], re.I)
        at = start + first.start() if first else (re.search(r"</body>", html, re.I) or re.search(r"$", html)).start()
        html = html[:at] + text + "\n" + html[at:]
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    if (shot_dir / "assets").is_dir():
        shutil.copytree(shot_dir / "assets", out_dir / "assets")
    rt = out_dir / "runtime"
    rt.mkdir()
    gsap = paths.RENDERER / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    if gsap.exists():
        shutil.copy(gsap, rt / "gsap.min.js")
    fonts = paths.FONTS
    if fonts.is_dir():
        shutil.copytree(fonts, out_dir / "fonts", dirs_exist_ok=True)
    if editor:
        html = self_contained(html, shot_dir)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    return out_dir


INLINE_MAX = 8_000_000            # a picture larger than this stays a file in the editor's page (it would make the page too big to send)


def _data_uri(p: Path) -> str:
    import base64
    import mimetypes

    kind = mimetypes.guess_type(p.name)[0] or ("font/woff2" if p.suffix == ".woff2" else "application/octet-stream")
    return f"data:{kind};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def _script(js: str) -> str:
    return "<script>" + re.sub(r"</script", r"<\/script", js, flags=re.I) + "</script>"


def self_contained(html: str, shot_dir: Path) -> str:
    """The visual editor's page asks the network for nothing: it runs in a sandboxed frame with no origin, which our local proxy would refuse.
    GSAP and the bridge go in as scripts, only the fonts the shot names go in as data, and its pictures too (up to INLINE_MAX each)."""
    gsap = paths.RENDERER / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    if gsap.exists():
        html = re.sub(r'<script\s+src="runtime/gsap\.min\.js"\s*>\s*</script>', lambda m: _script(gsap.read_text(encoding="utf-8")), html, flags=re.I)
    css_path = paths.FONTS / "fonts.css"
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        named = {n.strip().strip("'\"").lower() for decl in re.findall(r"font-family\s*:\s*([^;}\n]+)", html, re.I) for n in decl.split(",")}
        faces = []
        for block in re.findall(r"@font-face\s*\{[^}]*\}", css):
            fam = re.search(r"font-family:\s*'([^']+)'", block)
            src = re.search(r"url\(\./([^)]+)\)", block)
            if fam and src and fam.group(1).lower() in named and (paths.FONTS / src.group(1)).is_file():
                faces.append(block.replace(src.group(0), "url(" + _data_uri(paths.FONTS / src.group(1)) + ")"))
        html = re.sub(r'<link[^>]+href="fonts/fonts\.css"[^>]*>', lambda m: "<style>" + "\n".join(faces) + "</style>", html, flags=re.I)
    assets = shot_dir / "assets"

    def inline_asset(m):
        f = (assets / m.group(2)).resolve()
        if assets.is_dir() and assets.resolve() in f.parents and f.is_file() and f.stat().st_size <= INLINE_MAX:
            return m.group(1) + _data_uri(f)
        return m.group(0)
    html = re.sub(r"""((?:src|href)=["']|url\(["']?)assets/([A-Za-z0-9._/-]{1,200})""", inline_asset, html)
    bridge = _script((paths.RUNTIME / "vt-shot-bridge.js").read_text(encoding="utf-8"))
    end = re.search(r"</body>", html, re.I)
    return html[:end.start()] + bridge + "\n" + html[end.start():] if end else html + bridge


def render(shot_dir: Path, out: Path, *, fps: int = 30, gpu: bool = True, theme: Optional[dict] = None) -> Path:
    """The shot as a silent MP4, with its overrides."""
    from .render.hyperframes import render_silent

    work = out.parent / (out.stem + ".build")
    build(shot_dir, work, theme=theme)
    return render_silent(work, out, fps=fps, gpu=gpu)


def frames(shot_dir: Path, out_dir: Path, times: list[float], *, overrides: Optional[dict] = None, gpu: bool = False, theme: Optional[dict] = None) -> list[Path]:
    """PNG frames at these times (software drawing by default, so two runs give the same pixels)."""
    from .render.hyperframes import snapshot

    work = out_dir.parent / (out_dir.name + ".build")
    build(shot_dir, work, overrides, theme=theme)
    return snapshot(work, out_dir, times, gpu=gpu)


# --------------------------------------------------------------------------- shots in a project (C2)

def shot_dir(project, shot_id: str) -> Path:
    if not ID.match(shot_id or ""):
        raise ShotError(f"shot id '{shot_id}' must be letters, digits, - or _")
    return project.dir / "shots" / shot_id


def list_shots(project) -> list[dict]:
    root = project.dir / "shots"
    out = []
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        if d.is_dir() and ID.match(d.name) and (d / "index.html").exists():
            try:
                out.append(info(d))
            except ShotError as e:
                out.append({"id": d.name, "error": str(e)})
    return out


def fingerprint(shot_dir_: Path, fps: int = 30, theme: Optional[dict] = None) -> str:
    """Changes whenever anything that affects the picture changes: the code, the edits, shot.json, the assets, the frame rate, the video's theme."""
    import hashlib

    h = hashlib.sha1(f"v1|{fps}|{json.dumps(theme or {}, sort_keys=True)}".encode())
    for name in ("index.html", "overrides.json", "shot.json"):
        p = shot_dir_ / name
        h.update(name.encode() + b"\0" + (p.read_bytes() if p.exists() else b"") + b"\0")
    assets = shot_dir_ / "assets"
    for p in sorted(assets.rglob("*")) if assets.is_dir() else []:
        if p.is_file():
            st = p.stat()
            h.update(f"{p.relative_to(assets).as_posix()}|{st.st_size}|{st.st_mtime_ns}".encode())
    return h.hexdigest()[:16]


def cached_render(shot_dir_: Path, *, fps: int = 30, gpu: bool = True, theme: Optional[dict] = None) -> Path:
    """The shot's MP4, drawn again only when something in it changed. Older renders of the shot are removed."""
    out_dir = shot_dir_ / "render"
    out = out_dir / f"{fingerprint(shot_dir_, fps, theme)}.mp4"
    if out.exists() and out.stat().st_size > 0:
        return out
    render(shot_dir_, out, fps=fps, gpu=gpu, theme=theme)
    for old in out_dir.iterdir():
        if old != out and old.suffix in (".mp4", ".json", ".log") and not old.name.startswith(out.stem):
            old.unlink(missing_ok=True)
        elif old.is_dir() and old.name.endswith(".build"):
            shutil.rmtree(old, ignore_errors=True)
    return out


def place_on_scenes(project, sf, aspect: str, *, render_fn=None):
    """Each scene with a `shot` gets that shot, rendered, as a full-frame video behind it (no camera move, no scrim); returns (scenes, media items).
    A missing or broken shot fails here with the shot's name, never as a blank scene."""
    from .schema import Backdrop

    render_fn = render_fn or cached_render
    theme = theme_vars(project)
    media: dict[str, dict] = {}
    scenes = []
    for sc in sf.scenes:
        if sc.shot:
            key = f"shot:{sc.shot}"
            if key not in media:
                d = shot_dir(project, sc.shot)
                if not (d / "index.html").exists():
                    raise ShotError(f"scene {sc.id} uses shot '{sc.shot}', which has no index.html in shots/{sc.shot}/")
                i = info(d)
                mp4 = render_fn(d, theme=theme)
                media[key] = {"src": f"media/shot-{sc.shot}-{mp4.stem}.mp4", "kind": "video", "fx": 0.5, "fy": 0.5, "w": i["width"], "h": i["height"],
                              "role": "shot", "faces": [], "textBand": None, "shots": [], "trim": 0, "loop": False, "_abs": str(mp4)}
            sc = sc.model_copy(update={"backdrop": Backdrop(media=key, motion="none")})
        scenes.append(sc)
    return sf.model_copy(update={"scenes": scenes}), media
