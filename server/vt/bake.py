"""Bake a composition into plain HyperFrames source (docs/plans/PLAN-OPENMOTION.MD, O3).

Our runtime (vt.js and friends) builds every scene in the browser from data.json, so the page's source holds no scene elements and the HyperFrames Studio
has nothing to select. Baking lets the runtime build the page exactly as it does for a render, records every GSAP call it makes
(renderer/runtime/vt-bake.js), and writes the result as source: the built DOM, each animated element with a stable id and data-hf-id, and the timeline
as GSAP code addressing those ids. The baked page needs no vt.js. What cannot be written as plain code (a callback) is reported, never hidden.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from . import paths

RECORDER = paths.RENDERER / "runtime" / "vt-bake.js"
GSAP_TAG = '<script src="runtime/gsap.min.js"></script>'


class BakeError(Exception):
    pass


def _link_or_copy(src: str, dst: str) -> str:
    """Media can be gigabytes (a long talk's A-roll): a hard link costs no space and no time; another drive gets a copy. Only large files are linked:
    a small file (a page, a style sheet) is copied, so an editor that changes it in place never changes the original."""
    try:
        if os.path.getsize(src) > 1_000_000:
            os.link(src, dst)
            return dst
    except OSError:
        pass
    return shutil.copy2(src, dst)


def _with_recorder(comp_dir: Path, work: Path) -> Path:
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(comp_dir, work, copy_function=_link_or_copy, ignore=shutil.ignore_patterns("baked", ".bake-*", "*.mp4.part"))
    shutil.copy(RECORDER, work / "runtime" / "vt-bake.js")
    page = work / "index.html"
    html = page.read_text(encoding="utf-8")
    if GSAP_TAG not in html:
        raise BakeError("The composition page does not load GSAP the usual way; it cannot be baked.")
    html = html.replace(GSAP_TAG, GSAP_TAG + '\n<script src="runtime/vt-bake.js"></script>', 1)
    page.write_text(html, encoding="utf-8")
    return work


FONTS_LINK = '<link rel="stylesheet" href="fonts/fonts.css">'


def page_of(original: str, root_html: str, script: str, fonts_css: str = "") -> str:
    """The baked page: the original head (fonts, the runtime's style sheets), the built root, GSAP and the timeline code. No runtime scripts.
    Our @font-face rules go into the page itself: HyperFrames fetches its own copy of any font a page names without declaring it in the page
    (a linked style sheet does not count), and its Inter is wider than ours, so text would wrap and fit differently."""
    head = re.search(r"^.*?</head>", original, re.S | re.I)
    if not head:
        raise BakeError("The composition page has no head.")
    head_html = head.group(0)
    if fonts_css and FONTS_LINK in head_html:
        inline = re.sub(r"url\((['\"]?)\./", r"url(\1fonts/", fonts_css).replace("</style", "<\\/style")
        head_html = head_html.replace(FONTS_LINK, '<style id="vt-fonts">\n' + inline + "\n</style>", 1)
    safe = script.replace("</script", "<\\/script")
    return (head_html + "\n<body>\n" + root_html + "\n" + GSAP_TAG + "\n<script>\n" + safe + "\n</script>\n</body>\n</html>\n")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def captions_page(cap: dict) -> str:
    """The captions' own composition: their layer and the timeline of their words. The page mounts it inside its root, so it takes the page's styles."""
    safe = cap["script"].replace("</script", "<\\/script")
    return ("<!doctype html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n</head>\n<body>\n"
            f'<div id="captions-root" data-composition-id="captions" data-width="{cap["width"]}" data-height="{cap["height"]}" data-start="0" '
            f'data-duration="{cap["duration"]}" style="position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none">\n'
            f'{cap["html"]}\n<script>\n{safe}\n</script>\n</div>\n</body>\n</html>\n')


def bake(comp_dir: Path, out_dir: Path) -> dict:
    """Bake `comp_dir` (a composition folder: index.html, data.json, runtime/, fonts/, media/) into `out_dir`. Returns what was baked and what was lost."""
    from .render.hyperframes import probe

    comp_dir, out_dir = Path(comp_dir), Path(out_dir)
    work = _with_recorder(comp_dir, out_dir.parent / f".bake-{out_dir.name}")
    try:
        got = probe(work, "window.__vtBake ? window.__vtBake() : {error: 'the recorder did not load'}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if not isinstance(got, dict) or got.get("error"):
        raise BakeError(f"The page could not be baked: {(got or {}).get('error') if isinstance(got, dict) else got}")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(comp_dir, out_dir, copy_function=_link_or_copy, ignore=shutil.ignore_patterns("baked", ".bake-*", "index.html"))
    (out_dir / "index.html").write_text(page_of((comp_dir / "index.html").read_text(encoding="utf-8"), got["html"], got["script"],
                                                         (comp_dir / "fonts" / "fonts.css").read_text(encoding="utf-8") if (comp_dir / "fonts" / "fonts.css").exists() else ""), encoding="utf-8")
    cap = got.get("captions")
    if cap:
        (out_dir / "captions.html").write_text(captions_page(cap), encoding="utf-8")
    lost = got.get("lost") or []
    return {"dir": str(out_dir), "timelines": got.get("timelines", 0), "elements": got.get("elements", 0), "lost": lost[:50], "lost_count": len(lost)}
