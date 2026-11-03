"""The publishing kit for a finished video: a title, description and hashtags written from the transcript (AI, with a rule fallback),
and a cover image (the best frame, chosen by the vision model or by a pixel score, with a short hook title on it)."""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import AIUnavailable, complete_json, current_provider, vision_provider
from ..util import ProgressFn, noop_progress, now_iso, write_json

META_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "maxLength": 80},
        "description": {"type": "string", "maxLength": 600},
        "hashtags": {"type": "array", "items": {"type": "string", "maxLength": 30}, "minItems": 3, "maxItems": 10},
        "hook": {"type": "string", "maxLength": 40},
    },
    "required": ["title", "description", "hashtags", "hook"],
}

META_PROMPT = """Write the publishing text for a short social video (TikTok, Reels, Shorts, YouTube). The narrator says:

{text}

Write in the SAME language as the narration ({lang}). Give:
- title: at most 70 characters, specific, no clickbait lies, no emoji
- description: 2-3 short sentences saying what the viewer learns, no invented facts
- hashtags: 4-8 relevant hashtags without the # sign (single words, no spaces)
- hook: a 3-6 word line that could be printed on the cover image
Only use facts that appear in the narration."""


def _tag(s: str) -> str:
    return re.sub(r"[^\w]", "", s, flags=re.U).lower()


def rule_metadata(project) -> dict:
    """No AI: the project's title, the first sentences, and the most repeated key terms as hashtags."""
    from ..visuals import terms as T

    tr, beats = project.transcript(), project.beats()
    title = (project.meta().title or "Video").strip()
    sents = [b.text for b in beats.beats]
    topics = T.topic_counts(w.text for w in tr.words)
    tags = []
    for w in sorted({w.text for w in tr.words}, key=lambda x: -topics.get(x.lower(), 0)):
        t = _tag(w)
        if len(t) > 3 and T.is_key_term(w, topics) and t not in tags:
            tags.append(t)
        if len(tags) >= 6:
            break
    return {"title": title[:70], "description": " ".join(sents[:2])[:300], "hashtags": tags or [_tag(title) or "video"], "hook": title[:40], "source": "rules"}


def metadata(project, provider=None) -> dict:
    tr = project.transcript()
    text = " ".join(w.text for w in tr.kept())[:5000]
    try:
        r = complete_json(META_PROMPT.format(text=text, lang="Bangla" if project.meta().language == "bn" else "English"), META_SCHEMA, provider=provider,
                          max_tokens=500, timeout=240, temperature=0.4)
    except AIUnavailable:
        return rule_metadata(project)
    tags = []
    for t in r["hashtags"]:
        t = _tag(t)
        if t and t not in tags:
            tags.append(t)
    return {"title": r["title"].strip(), "description": r["description"].strip(), "hashtags": tags[:8], "hook": r["hook"].strip(), "source": "ai"}


# --------------------------------------------------------------------------- cover
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    cands = []
    if sys.platform == "win32":
        cands = [r"C:\Windows\Fonts\Nirmala.ttc", r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"]
    elif sys.platform == "darwin":
        cands = ["/System/Library/Fonts/Supplemental/Bangla MN.ttc", "/System/Library/Fonts/Helvetica.ttc"]
    else:
        cands = ["/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for c in cands:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except OSError:
                continue
    return ImageFont.load_default()


def frame_score(path: Path) -> float:
    """A pixel score for 'looks like a cover': content fills 10-45% of the picture, with contrast, not an empty frame."""
    im = np.asarray(Image.open(path).convert("RGB")).astype("int16")
    h, w = im.shape[:2]
    corners = np.concatenate([im[:12, :12].reshape(-1, 3), im[:12, -12:].reshape(-1, 3), im[-12:, :12].reshape(-1, 3), im[-12:, -12:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    fg = (np.abs(im - bg).sum(axis=2) > 40).mean()
    return float(1.0 - abs(fg - 0.27) / 0.27)


def pick_frame(frames: list[Path], provider=None) -> int:
    """Index of the best cover frame: the vision model when it answers, else the pixel score."""
    if len(frames) == 1:
        return 0
    scores = [frame_score(f) for f in frames]
    best = int(np.argmax(scores))
    try:
        prov = provider or vision_provider()
        if not (prov.available() and prov.supports_images):
            return best
        tiles = []
        for i, f in enumerate(frames[:6]):
            im = Image.open(f).convert("RGB")
            im.thumbnail((300, 400))
            ImageDraw.Draw(im).rectangle((0, 0, 34, 34), fill="black")
            ImageDraw.Draw(im).text((12, 8), str(i), fill="white")
            tiles.append(im)
        sheet = Image.new("RGB", (sum(t.width for t in tiles), max(t.height for t in tiles)), "white")
        x = 0
        for t in tiles:
            sheet.paste(t, (x, 0))
            x += t.width
        b = io.BytesIO()
        sheet.save(b, "PNG")
        n = len(tiles)
        r = complete_json(f"These {n} frames (numbered 0 to {n - 1}) are candidates for the cover image of a short video. Pick the one with the clearest, most interesting picture and readable text. Answer as JSON.",
                          {"type": "object", "properties": {"choice": {"type": "integer", "minimum": 0, "maximum": n - 1}}, "required": ["choice"]},
                          [b.getvalue()], provider=prov, max_tokens=60, timeout=180, temperature=0.0)
        return int(r["choice"])
    except AIUnavailable:
        return best


def draw_hook(im: Image.Image, text: str) -> Image.Image:
    """The hook line on the lower third, white on a dark band, sized to fit."""
    if not text.strip():
        return im
    im = im.convert("RGB")
    w, h = im.size
    size = max(28, int(w * 0.085))
    d = ImageDraw.Draw(im)
    while size > 22:
        f = _font(size)
        words, lines, cur = text.split(), [], ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if d.textlength(t, font=f) <= w * 0.86:
                cur = t
            else:
                lines.append(cur)
                cur = wd
        lines.append(cur)
        if len(lines) <= 3:
            break
        size = int(size * 0.88)
    lh = int(size * 1.25)
    band_h = lh * len(lines) + int(size * 0.7)
    top = int(h * 0.72)
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(over).rectangle((0, top, w, min(h, top + band_h)), fill=(0, 0, 0, 170))
    im = Image.alpha_composite(im.convert("RGBA"), over).convert("RGB")
    d = ImageDraw.Draw(im)
    y = top + int(size * 0.35)
    for ln in lines:
        d.text(((w - d.textlength(ln, font=f)) / 2, y), ln, font=f, fill="white")
        y += lh
    return im


_COVER_HTML = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="fonts/fonts.css"><style>
html,body{margin:0;background:#000}
#root{position:relative;width:__W__px;height:__H__px;overflow:hidden}
#root img{position:absolute;inset:0;width:100%;height:100%}
.band{position:absolute;left:0;right:0;top:70%;padding:__PAD__px __PAD2__px;background:rgba(0,0,0,.68);color:#fff;font:800 __FS__px/1.25 __FONT__;text-align:center}
</style></head><body>
<div id="root" data-composition-id="root" data-start="0" data-duration="1" data-width="__W__" data-height="__H__"><img src="bg.png"><div class="band">__TEXT__</div></div>
<script src="runtime/gsap.min.js"></script>
<script>window.__timelines=window.__timelines||{};window.__timelines["root"]=gsap.timeline({paused:true});</script>
</body></html>"""


def render_hook(bg: Path, hook: str, out: Path, aspect: str, theme, workdir: Path) -> Path:
    """The hook line on the lower third, drawn by the same browser that draws the video so Bangla conjuncts and the theme's fonts come out right."""
    import html
    import shutil

    from .. import paths
    from ..compose import FORMATS
    from ..compose.composer import _copy_fonts, _put
    from ..render.hyperframes import snapshot

    fmt = FORMATS[aspect]
    w, h = fmt["width"], fmt["height"]
    workdir.mkdir(parents=True, exist_ok=True)
    shutil.copy(bg, workdir / "bg.png")
    (workdir / "runtime").mkdir(exist_ok=True)
    shutil.copy(paths.RENDERER / "node_modules" / "gsap" / "dist" / "gsap.min.js", workdir / "runtime" / "gsap.min.js")
    _copy_fonts(workdir / "fonts", theme)
    fam = ", ".join(f"'{f}'" for f in theme.font.headline) + ", sans-serif"
    page = (_COVER_HTML.replace("__W__", str(w)).replace("__H__", str(h)).replace("__FONT__", fam).replace("__FS__", str(int(w * 0.085)))
            .replace("__PAD__", str(int(w * 0.03))).replace("__PAD2__", str(int(w * 0.06))).replace("__TEXT__", html.escape(hook)))
    _put(workdir / "index.html", page.encode("utf-8"))
    shot = snapshot(workdir, workdir / "out", [0.2])[0]
    Image.open(shot).convert("RGB").save(out, quality=92)
    return out


def make_cover(project, hook: str, progress: ProgressFn = noop_progress, provider=None) -> Path:
    from ..compose import FORMATS, scene_timing
    from ..pipeline import compose_all
    from ..render.hyperframes import snapshot

    meta = project.meta()
    sf, beats = project.scenes(), project.beats()
    if not sf:
        raise ValueError("no plan yet")
    from ..compose import compose_project

    compose_project(project, meta.aspect, captions=False)           # candidate frames without captions
    cuts = project.cuts()
    dur = cuts.output_duration if cuts else max((w.end for w in project.transcript().kept()), default=1.0) + 0.5
    timing = scene_timing(sf, beats, dur)
    times = [round(t["start"] + min(2.4, 0.7 * (t["end"] - t["start"])), 2) for t in timing][:8]
    progress("cover", 0.2, "Capturing candidate frames")
    frames = snapshot(project.comp_dir / FORMATS[meta.aspect]["tag"], project.dir / "cover_frames", times)
    progress("cover", 0.6, "Choosing the best frame")
    best = frames[pick_frame(frames, provider)]
    out_dir = project.dir / "exports"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "cover.jpg"
    try:
        from ..project import load_theme

        render_hook(best, hook, out, meta.aspect, load_theme(sf.theme or meta.theme), project.dir / "cover_comp")
    except Exception:                                   # no browser: Latin-only fallback drawn with Pillow
        draw_hook(Image.open(best), hook).save(out, quality=92)
    compose_all(project)                                 # the preview composition gets its captions back
    progress("cover", 1.0, "Cover ready")
    return out


def build_kit(project, progress: ProgressFn = noop_progress, provider=None, cover: bool = True) -> dict:
    progress("publish", 0.05, "Writing the title and description")
    kit = metadata(project, provider)
    if cover:
        try:
            make_cover(project, kit.get("hook", ""), lambda s, f, m: progress("publish", 0.2 + 0.75 * f, m), provider)
            kit["cover"] = "cover.jpg"
        except Exception as e:                      # the cover is a bonus: text is still useful
            kit["cover_error"] = f"{type(e).__name__}: {str(e)[:120]}"
    kit["at"] = now_iso()
    write_json(project.dir / "publish.json", kit)
    return kit
