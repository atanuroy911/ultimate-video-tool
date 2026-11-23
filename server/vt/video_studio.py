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

BASES = ".baked"                   # each page as baked, to tell edits from no edits (.baked/index.html, .baked/scenes/s4.html...); a dot-folder, so
                                   # HyperFrames never takes a copy for a second root page
STAMP = ".baked.json"              # what it was baked from
CAPTIONS = "compositions/captions.html"
# Studio copies made before 2026-11-23 kept the baselines beside the pages and the captions at the top: read where they are, moved on the next bake
_LEGACY = {".baked.html": "index.html", ".baked-captions.html": "captions.html"}


def pages(d: Path) -> list[str]:
    """The pages of a Studio copy: the root, the captions and (S4) one per scene, as paths inside it."""
    out = [f for f in ("index.html", CAPTIONS, "captions.html") if (d / f).exists()]
    return out + sorted(f"scenes/{p.name}" for p in (d / "scenes").glob("*.html")) if (d / "scenes").is_dir() else out


def base_of(page: str, d: Optional[Path] = None) -> str:
    """Where the page's baked baseline is (in an older copy, where it was)."""
    if d is not None:
        old = next((k for k, v in _LEGACY.items() if v == page), None)
        if old and (d / old).exists() and not (d / BASES / page).exists():
            return old
        if page.startswith("scenes/") and (d / ".baked-scenes" / page[7:]).exists() and not (d / BASES / page).exists():
            return f".baked-scenes/{page[7:]}"
    return f"{BASES}/{page}"


def folder(project, tag: str) -> Path:
    return project.dir / f"studio-{tag}"


def fingerprint(comp_dir: Path) -> str:
    """What the video is, from its data. Captions on or off is not part of it: the baked captions are their own composition, left out when not wanted."""
    try:
        data = json.loads((comp_dir / "data.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    data.pop("captions_enabled", None)
    return hashlib.sha1(b"v4" + json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


HOST = re.compile(r'<div id="captions"[^>]*data-composition-src="(?:compositions/)?captions\.html"[^>]*></div>')


def without_captions(src: Path, dst: Path) -> Path:
    """The edited video with its captions composition left out (an export without captions)."""
    from .bake import _link_or_copy

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, copy_function=_link_or_copy, ignore=shutil.ignore_patterns(BASES, ".baked-scenes", *_LEGACY, STAMP, "captions.html"))
    page = dst / "index.html"
    page.write_text(HOST.sub("", page.read_text(encoding="utf-8")), encoding="utf-8")
    return dst


def info(project, tag: str, comp_dir: Optional[Path] = None) -> dict:
    """Whether this shape has Studio edits, and whether they still fit the current composition."""
    d = folder(project, tag)
    if not (d / "index.html").exists() or not (d / base_of("index.html", d)).exists():
        return {"baked": False, "edited": False, "current": False}
    edited = any((d / base_of(f, d)).exists() and (d / f).read_bytes() != (d / base_of(f, d)).read_bytes() for f in pages(d))
    try:
        stamp = json.loads((d / STAMP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stamp = {}
    current = comp_dir is not None and stamp.get("from") == fingerprint(comp_dir)
    return {"baked": True, "edited": edited, "current": current, "dir": str(d)}


def _swap_in(src: Path, dst: Path) -> None:
    """Move every file of `src` into `dst`, one by one with os.replace (a new directory entry: never a write through a hard-linked media file), so a
    Studio watching `dst` reloads the new page. Files `dst` has that `src` lacks go (dot-folders, the Studio's own history, stay)."""
    import os
    import time as _time

    keep = {p.relative_to(src) for p in src.rglob("*") if p.is_file()}
    for rel in sorted(keep, key=lambda r: (r.suffix == ".html" and not r.parts[0].startswith("."), r.as_posix() == "index.html", str(r))):  # pages last, the root last of all
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(20):
            try:
                os.replace(src / rel, target)
                break
            except PermissionError:                                              # Windows: the Studio is reading it at this instant
                if attempt == 19:
                    raise
                _time.sleep(0.05 * (attempt + 1))
    for p in sorted(dst.rglob("*"), reverse=True):
        rel = p.relative_to(dst)
        if rel.as_posix() in _LEGACY or rel.parts[0] == ".baked-scenes":    # an older copy's baselines: the new ones are in .baked/
            if p.is_file():
                p.unlink(missing_ok=True)
            else:
                shutil.rmtree(p, ignore_errors=True)
            continue
        if rel.parts[0].startswith(".") or p.name == STAMP:              # dot-folders (the baselines, HyperFrames' own history) stay
            continue
        if p.is_file() and rel not in keep:
            p.unlink(missing_ok=True)
    shutil.rmtree(src, ignore_errors=True)


_locks: dict = {}
_locks_guard = __import__("threading").Lock()


def _lock_for(d: Path):
    """One bake at a time per Studio folder: two at once would share the bake folder (a refresh asked while another runs waits for it)."""
    with _locks_guard:
        return _locks.setdefault(str(d).lower(), __import__("threading").Lock())


def prepare(project, tag: str, comp_dir: Path, *, fresh: bool = False) -> dict:
    """Bake the composition for the Studio, unless edits made on this same composition are already there (they are kept). When the video changed since
    the Studio edits, the edits are carried into the new bake where they still fit (a copy of the old ones stays in studio-<shape>.old). The new files
    are moved into the Studio folder one by one, so an open Studio shows the new video."""
    with _lock_for(folder(project, tag)):
        return _prepare(project, tag, comp_dir, fresh=fresh)


def _prepare(project, tag: str, comp_dir: Path, *, fresh: bool = False) -> dict:
    from .bake import _link_or_copy

    d = folder(project, tag)
    have = info(project, tag, comp_dir)
    if have["baked"] and have["current"] and not fresh:
        return {**have, "kept": True}
    earlier = {}
    if have["edited"] and not have["current"]:
        for f in pages(d):
            if (d / base_of(f, d)).exists():
                earlier[f] = ((d / base_of(f, d)).read_text(encoding="utf-8"), (d / f).read_text(encoding="utf-8"))
        old = project.dir / f"studio-{tag}.old"
        shutil.rmtree(old, ignore_errors=True)
        shutil.copytree(d, old, copy_function=_link_or_copy, ignore=shutil.ignore_patterns(".hyperframes", ".history"))
    new = project.dir / f".studio-{tag}-bake"
    got = bake(comp_dir, new)
    if got["lost_count"]:                                          # an export from this copy would not move like the video: never offer it
        shutil.rmtree(new, ignore_errors=True)
        raise ST.StudioError(f"This video has {got['lost_count']} animation step(s) the Studio cannot hold yet (for example stick figures, whose "
                             "limbs are drawn by code every frame). Edit it in Video Tool's own editor for now.")
    for f in pages(new):
        (new / base_of(f)).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(new / f, new / base_of(f))
    (new / STAMP).write_text(json.dumps({"from": fingerprint(comp_dir), "lost": got["lost"][:20], "lost_count": got["lost_count"]}, indent=1), encoding="utf-8")
    carried = missed = 0
    if not fresh and earlier:
        texts = {f: (new / f).read_text(encoding="utf-8") for f in pages(new)}
        for f, (base, mine) in earlier.items():                       # a change goes to the page it came from, else to the page that holds its code now
            texts, c, m = carry_many(base, mine, texts, prefer=f)       # (a scene's part moved from the root page into scenes/<id>.html in S4)
            carried, missed = carried + c, missed + m
        if "index.html" in texts:
            from . import shots as SH
            try:
                SH.info_of("video", texts["index.html"], {})
            except SH.ShotError:                                          # the carried root would not be a timed video: start from the new bake
                texts["index.html"] = (new / "index.html").read_text(encoding="utf-8")
        for f, text in texts.items():
            (new / f).write_text(text, encoding="utf-8")
    if d.exists():
        _swap_in(new, d)
    else:
        new.rename(d)
    return {**info(project, tag, comp_dir), "kept": False, "lost_count": got["lost_count"], "carried": carried, "missed": missed}


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
    note = None
    if not have["current"]:                                         # the video changed since: bake it again and carry the Studio edits into it
        try:
            got = prepare(project, tag, comp_dir)
        except Exception as e:                                       # noqa: BLE001
            return comp_dir, (f"The video changed after it was edited in the Studio, and the Studio edits could not be carried into the new version ({e}). "
                              "This export is the new version without them; the old edits are kept in the project folder.")
        if got.get("missed"):
            note = (f"The video changed after it was edited in the Studio. {got.get('carried', 0)} Studio change(s) were carried into the new version; "
                    f"{got['missed']} no longer had a place (the part changed or is gone) and are kept in studio-{tag}.old.")
        if not got.get("edited"):
            return comp_dir, note
    d = folder(project, tag)
    if not captions:
        return without_captions(d, project.dir / f".studio-{tag}-nocaptions"), note
    return d, note


# ---- O6: agents work on the same copy the person edits in the Studio ----

_ID_TAG = re.compile(r'<([a-zA-Z][\w-]*)\b([^>]*?)\sid="([^"]+)"([^>]*)>')
def _page(project, tag: str, file: str = "index.html") -> Path:
    have = pages(folder(project, tag))
    if file not in have:
        raise ST.StudioError(f"The Studio copy has {', '.join(have) or 'no pages'}; '{file}' is not one of them.")
    p = folder(project, tag) / file
    if not p.exists():
        raise ST.StudioError("This video has no Studio copy yet: open it in the Studio first (or call studio_parts, which makes one).")
    return p


def parts(project, tag: str, scene: Optional[str] = None, limit: int = 400) -> list[dict]:
    """Every part with an id in the Studio copy: its id, the scene it belongs to, its tag and the start of its text."""
    out = []
    for file in pages(folder(project, tag)):
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
    for file in pages(folder(project, tag)):
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
    if file != "index.html" and 'data-composition-id="' not in new:
        raise ST.StudioError("That change would remove the page's composition; keep its data-composition-id.")
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


def _history(project, tag: str, *args: str) -> dict:
    """HyperFrames' own history of the Studio copy (the Studio shows it and can undo it): `history <args> --json`, run in the copy's folder."""
    import json as _json
    import subprocess

    from .render.hyperframes import _env, hyperframes_cmd

    try:
        out = subprocess.run(hyperframes_cmd("history", *args, "--json"), cwd=str(folder(project, tag)), capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60, env=_env()).stdout
        return _json.loads(out[out.index("{"): out.rindex("}") + 1])
    except Exception as e:                                           # noqa: BLE001  the edit itself never depends on the history
        return {"ok": False, "error": {"message": str(e)[:160]}}


def recorded_edit(project, tag: str, find: str, replace: str, file: str = "index.html", who: str = "Claude Code", label: str = "") -> dict:
    """edit(), recorded as one entry of the Studio's history under `who` with `label`, so the person sees it there and can undo it."""
    label = (label or "Changed the video").strip()[:80]
    began = _history(project, tag, "begin", "--who", who, "--label", label)
    try:
        got = edit(project, tag, find, replace, file)
    finally:
        if began.get("entryId"):
            _history(project, tag, "end")
    return {**got, "history": label if began.get("entryId") else None}


def undo(project, tag: str, who: str = "Claude Code") -> dict:
    """Undo the newest change `who` made that is still in effect (from the Studio's history)."""
    _page(project, tag)
    got = _history(project, tag, "undo", "--who", who)
    if not got.get("ok"):
        raise ST.StudioError((got.get("error") or {}).get("message", "There was nothing to undo."))
    return {"ok": True, "undid": str(got.get("label") or (got.get("entry") or {}).get("label") or "").replace("Undid: ", ""), "edited": info(project, tag)["edited"]}


_TOKEN = re.compile(r"(?<=>)|(?<=\n)")


def carry(base: str, mine: str, new: str, context: int = 3) -> tuple[str, int, int]:
    """carry_many for one page."""
    got, c, m = carry_many(base, mine, {"page": new}, prefer="page", context=context)
    return got["page"], c, m


def carry_many(base: str, mine: str, news: dict, prefer: str = "", context: int = 3) -> tuple[dict, int, int]:
    """Apply the changes made from `base` to `mine` onto `new` (a fresh bake of a changed video). Each change is found in `new` by the code
    around it (a few tags or lines before and after, and what it replaced); it is applied only where that is found exactly once.
    Returns the new text, how many changes were carried and how many found no place."""
    from difflib import SequenceMatcher

    split = lambda t: [x for x in _TOKEN.split(t) if x]                     # noqa: E731
    a, b = split(base), split(mine)
    targets = {k: split(v) for k, v in news.items()}
    order = sorted(targets, key=lambda k: k != prefer)
    plans: dict = {k: [] for k in targets}
    missed = 0
    for op, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        before, removed, after = a[max(0, i1 - context): i1], a[i1:i2], a[i2: i2 + context]
        found = None
        for lead, tail in ((before, after), (before, []), ([], after)):        # the code around it, or only what comes before, or only after
            need = lead + removed + tail
            if not lead and not tail:
                continue
            for k in order:                                                   # its own page first, then the others
                n = targets[k]
                hits = [p for p in range(len(n) - len(need) + 1) if n[p: p + len(need)] == need]
                if len(hits) == 1:
                    found = (k, hits[0] + len(lead))
                    break
            if found:
                break
        if found is None:
            missed += 1
            continue
        k, start = found
        plans[k].append((start, start + len(removed), b[j1:j2]))
    out = {}
    for k, n in targets.items():
        for s0, s1, put in sorted(plans[k], key=lambda x: x[0], reverse=True):
            n[s0:s1] = put
        out[k] = "".join(n)
    return out, sum(len(p) for p in plans.values()), missed
