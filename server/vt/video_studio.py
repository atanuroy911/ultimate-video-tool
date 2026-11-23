"""The whole video in the HyperFrames Studio (docs/plans/PLAN-OPENMOTION.MD, O4).

"Edit in Studio" bakes the video's current composition (vt/bake.py) into `<project>/studio-<shape>/` and opens the Studio on that folder, so every scene
is a clip on its timeline and every part on the picture can be selected, moved, retyped and re-animated. The Studio saves into that folder itself.
The export draws from it when it holds edits and was baked from the composition the export is about to draw; when the video changed since (a new plan,
a re-timed cut), the edits no longer fit it: the export uses the new video and says so, and the next "Edit in Studio" bakes afresh.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Optional

from . import shot_studio as ST
from .bake import bake

BASELINE = ".baked.html"           # the page as baked, to tell edits from no edits
STAMP = ".baked.json"              # what it was baked from


def folder(project, tag: str) -> Path:
    return project.dir / f"studio-{tag}"


def fingerprint(comp_dir: Path) -> str:
    """What the video is, from its data. Captions on or off is not part of it: the baked captions are their own composition, left out when not wanted."""
    try:
        data = json.loads((comp_dir / "data.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    data.pop("captions_enabled", None)
    return hashlib.sha1(b"v2" + json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


HOST = re.compile(r'<div id="captions"[^>]*data-composition-src="captions\.html"[^>]*></div>')


def without_captions(src: Path, dst: Path) -> Path:
    """The edited video with its captions composition left out (an export without captions)."""
    from .bake import _link_or_copy

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, copy_function=_link_or_copy, ignore=shutil.ignore_patterns(BASELINE, STAMP, "captions.html"))
    page = dst / "index.html"
    page.write_text(HOST.sub("", page.read_text(encoding="utf-8")), encoding="utf-8")
    return dst


def info(project, tag: str, comp_dir: Optional[Path] = None) -> dict:
    """Whether this shape has Studio edits, and whether they still fit the current composition."""
    d = folder(project, tag)
    if not (d / "index.html").exists() or not (d / BASELINE).exists():
        return {"baked": False, "edited": False, "current": False}
    edited = (d / "index.html").read_bytes() != (d / BASELINE).read_bytes()
    try:
        stamp = json.loads((d / STAMP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stamp = {}
    current = comp_dir is not None and stamp.get("from") == fingerprint(comp_dir)
    return {"baked": True, "edited": edited, "current": current, "dir": str(d)}


def prepare(project, tag: str, comp_dir: Path, *, fresh: bool = False) -> dict:
    """Bake the composition into the Studio folder, unless edits made on this same composition are already there (they are kept)."""
    d = folder(project, tag)
    have = info(project, tag, comp_dir)
    if have["baked"] and have["current"] and not fresh:
        return {**have, "kept": True}
    if have["edited"] and not have["current"]:                     # older edits: kept beside, never thrown away silently
        old = project.dir / f"studio-{tag}.old"
        shutil.rmtree(old, ignore_errors=True)
        shutil.move(str(d), str(old))
    got = bake(comp_dir, d)
    if got["lost_count"]:                                          # an export from this copy would not move like the video: never offer it
        shutil.rmtree(d, ignore_errors=True)
        raise ST.StudioError(f"This video has {got['lost_count']} animation step(s) the Studio cannot hold yet (for example stick figures, whose "
                             "limbs are drawn by code every frame). Edit it in Video Tool's own editor for now.")
    shutil.copy(d / "index.html", d / BASELINE)
    (d / STAMP).write_text(json.dumps({"from": fingerprint(comp_dir), "lost": got["lost"][:20], "lost_count": got["lost_count"]}, indent=1), encoding="utf-8")
    return {**info(project, tag, comp_dir), "kept": False, "lost_count": got["lost_count"]}


def open_video(project, tag: str, comp_dir: Path, *, fresh: bool = False) -> dict:
    """Bake (or keep) and start the Studio on the whole video. The Studio writes into the folder itself, so saving only reports."""
    ready = prepare(project, tag, comp_dir, fresh=fresh)
    d = folder(project, tag)

    def saver() -> dict:
        now = info(project, tag, comp_dir)
        return {"saved": True, "changed": now["edited"], "assets": []}

    out = ST.start(f"{project.id}/video/{tag}", d, saver, project.dir)
    return {**out, **{k: ready[k] for k in ("kept", "edited") if k in ready}, "lost_count": ready.get("lost_count", 0)}


def for_render(project, tag: str, comp_dir: Path, captions: bool = True) -> tuple[Path, Optional[str]]:
    """The folder the export should draw, and a sentence for the person when their Studio edits are not used."""
    have = info(project, tag, comp_dir)
    if not have["edited"]:
        return comp_dir, None
    if have["current"]:
        if not captions:
            return without_captions(Path(have["dir"]), project.dir / f".studio-{tag}-nocaptions"), None
        return Path(have["dir"]), None
    return comp_dir, ("The video changed after it was edited in the Studio, so those Studio edits are not in this export. "
                      "Open the Studio again to edit the new version (the old edits are kept in the project folder).")


# ---- O6: agents work on the same copy the person edits in the Studio ----

_ID_TAG = re.compile(r'<([a-zA-Z][\w-]*)\b([^>]*?)\sid="([^"]+)"([^>]*)>')
FILES = ("index.html", "captions.html")


def _page(project, tag: str, file: str = "index.html") -> Path:
    if file not in FILES:
        raise ST.StudioError(f"The Studio copy has {' and '.join(FILES)}; '{file}' is not one of them.")
    p = folder(project, tag) / file
    if not p.exists():
        raise ST.StudioError("This video has no Studio copy yet: open it in the Studio first (or call studio_parts, which makes one).")
    return p


def parts(project, tag: str, scene: Optional[str] = None, limit: int = 400) -> list[dict]:
    """Every part with an id in the Studio copy: its id, the scene it belongs to, its tag and the start of its text."""
    out = []
    for file in FILES:
        p = folder(project, tag) / file
        if not p.exists():
            continue
        html = p.read_text(encoding="utf-8")
        body = html[html.find("<body"):] if "<body" in html else html
        for m in _ID_TAG.finditer(body):
            pid = m.group(3)
            sc = re.match(r"(s\d+[a-z0-9]*)-", pid)
            if scene and (not sc or sc.group(1) != scene):
                continue
            first = body[m.end(): m.end() + 400].split("</div>", 1)[0]            # its own first text (a part's children come before its end)
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", first)).strip()[:60]
            out.append({"id": pid, "file": file, "scene": sc.group(1) if sc else None, "tag": m.group(1), "text": text})
            if len(out) >= limit:
                return out
    return out


def part(project, tag: str, part_id: str) -> dict:
    """One part: its opening tag, the start of what is inside it, and every animation line on it (GSAP code addressing its id)."""
    for file in FILES:
        p = folder(project, tag) / file
        if not p.exists():
            continue
        html = p.read_text(encoding="utf-8")
        m = re.search(r'<[a-zA-Z][\w-]*\b[^>]*\sid="' + re.escape(part_id) + r'"[^>]*>', html)
        if not m:
            continue
        inside = html[m.end(): m.end() + 1500]
        lines = [ln.strip() for ln in html.splitlines() if f'"{part_id}"' in ln and ".map($)" in ln][:40]
        return {"id": part_id, "file": file, "tag": m.group(0), "inside": inside, "animation": lines}
    raise ST.StudioError(f"No part '{part_id}' in the Studio copy; studio_parts lists them.")


def edit(project, tag: str, find: str, replace: str, file: str = "index.html") -> dict:
    """Replace one exact piece of the Studio copy (it must appear exactly once). The page must stay a timed composition. The open Studio reloads it."""
    p = _page(project, tag, file)
    html = p.read_text(encoding="utf-8")
    n = html.count(find) if find else 0
    if n != 1:
        raise ST.StudioError(f"The text to replace appears {n} times; give a piece that appears exactly once (studio_part shows a part's exact code).")
    new = html.replace(find, replace, 1)
    if file == "index.html":
        from . import shots as SH
        try:
            SH.info_of("video", new, {})
        except SH.ShotError as e:
            raise ST.StudioError(f"That change would break the video's timing: {e}")
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(new, encoding="utf-8")
    tmp.replace(p)
    return {"ok": True, "file": file, "edited": info(project, tag)["edited"]}


def selection(project, tag: str) -> dict:
    """What the person has selected in the open Studio right now (id, label, text, time, place), or why there is nothing."""
    import json as _json
    import subprocess

    from .render.hyperframes import _env, hyperframes_cmd

    s = ST.status()
    if not s.get("open") or s.get("key") != f"{project.id}/video/{tag}":
        return {"selected": False, "reason": "The video is not open in the Studio."}
    try:
        out = subprocess.run(hyperframes_cmd("preview", "--selection", "--json", "--port", str(s["port"]), str(folder(project, tag))),
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, env=_env()).stdout
        got = _json.loads(out[out.index("{"): out.rindex("}") + 1])
    except Exception as e:                                           # noqa: BLE001
        return {"selected": False, "reason": f"The Studio did not answer: {str(e)[:120]}"}
    sel = got.get("selection")
    if not got.get("ok") or not sel:
        return {"selected": False, "reason": (got.get("error") or {}).get("message", "Nothing is selected in the Studio.")}
    t = sel.get("target") or {}
    box = sel.get("boundingBox") or {}
    return {"selected": True, "id": t.get("id"), "selector": t.get("selector"), "label": sel.get("label"), "text": (sel.get("textContent") or "")[:200],
            "file": sel.get("sourceFile"), "time": sel.get("currentTime"), "box": [round(box.get(k, 0)) for k in ("x", "y", "width", "height")]}
