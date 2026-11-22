"""Edit a shot in the HyperFrames Studio (docs/plans/PLAN-OPENMOTION.MD, O2).

The Studio is HyperFrames' own editor (`hyperframes preview`): select, move, resize, retype, animate, layers, a timeline. It edits a folder of HTML
in place. We give it a working copy of one shot (`<shot>/studio/`) with the video's theme and the person's earlier visual edits shown, start it on a
free port bound to 127.0.0.1, and copy its edits back into the shot's own `index.html` when the person saves or closes. Only one shot is open at a time.
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional

from . import paths
from . import shots as SH

WORK = "studio"                                  # the folder name is also the Studio's project name: http://127.0.0.1:<port>/#project/studio
BEGIN, END = "<!--vt:studio-begin-->", "<!--vt:studio-end-->"
_ADDED = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)
START_SECONDS = 45.0

_lock = threading.Lock()
_open: dict[str, Any] = {}                       # the one open Studio: {"key", "work", "saver", "proc", "port", "url", "log", "started"}


class StudioError(Exception):
    pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def added_block(shot_dir: Path, theme: Optional[dict]) -> str:
    """What the working copy shows on top of the shot's own code: the video's theme and the earlier visual edits (moved, hidden, restyled).
    It sits between two markers and is taken out again when the edits come back, so the shot's code never keeps it."""
    themed = "".join(f"{k}:{v};" for k, v in (theme or {}).items() if SH.KNOB.match(k) and SH.SAFE_CSS_VALUE.match(v))
    o = SH.check_overrides(SH.read_json(shot_dir / "overrides.json", {}))
    css = SH.overrides_css(o)
    parts = [f'<style id="vt-theme">:root{{{themed}}}</style>' if themed else "", f'<style id="vt-overrides">\n{css}\n</style>' if css else ""]
    inner = "\n".join(p for p in parts if p)
    return f"{BEGIN}\n{inner}\n{END}\n" if inner else ""


def strip_added(html: str) -> str:
    return _ADDED.sub("", html)


def prepare(shot_dir: Path, theme: Optional[dict] = None) -> Path:
    """The working copy the Studio edits: the shot's code (with the theme and earlier edits shown), its assets, the animation library and fonts."""
    html = (shot_dir / "index.html").read_text(encoding="utf-8")
    SH.info(shot_dir)                                                    # refuse a shot the renderer cannot time
    block = added_block(shot_dir, theme)
    if block:
        head = re.search(r"</head>", html, re.I)
        html = html[:head.start()] + block + html[head.start():] if head else block + html
    work = shot_dir / WORK
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    if (shot_dir / "assets").is_dir():
        shutil.copytree(shot_dir / "assets", work / "assets")
    (work / "runtime").mkdir()
    gsap = paths.RENDERER / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    if gsap.exists():
        shutil.copy(gsap, work / "runtime" / "gsap.min.js")
    if paths.FONTS.is_dir():
        shutil.copytree(paths.FONTS, work / "fonts", dirs_exist_ok=True)
    (work / "index.html").write_text(html, encoding="utf-8")
    return work


def take_back(shot_dir: Path, work: Path, synced: Optional[str] = None) -> dict:
    """Copy the Studio's edits into the shot: its index.html (without what we added) and any picture or clip it added to assets.
    The new code must still be a timed composition, or nothing is copied and the reason is given.
    `synced` is the shot's code as the Studio last had it. When given: a Studio copy that still matches it changes nothing (so a change someone else
    made to the shot meanwhile is never overwritten), and when both changed, the shot is kept and the Studio's version is set aside next to it."""
    page = work / "index.html"
    if not page.exists():
        return {"saved": False, "reason": "The Studio's copy is gone."}
    html = strip_added(page.read_text(encoding="utf-8"))
    old = (shot_dir / "index.html").read_text(encoding="utf-8")
    if synced is not None and html == synced:
        return {"saved": True, "changed": False, "assets": []}
    if synced is not None and old != synced:
        (shot_dir / "studio-conflict.html").write_text(html, encoding="utf-8")
        return {"saved": False, "conflict": True, "reason": "The shot's code was changed elsewhere while the Studio had it open. The shot keeps that change; "
                "the Studio's version is kept as studio-conflict.html next to it. Open the Studio again to start from the current shot."}
    try:
        SH.info_of(shot_dir.name, html, SH.read_json(shot_dir / "shot.json", {}))
    except SH.ShotError as e:
        return {"saved": False, "reason": f"The edited shot cannot be timed: {e}"}
    added = []
    if (work / "assets").is_dir():
        for f in (work / "assets").rglob("*"):
            if f.is_file():
                dest = shot_dir / "assets" / f.relative_to(work / "assets")
                if not dest.exists() or dest.stat().st_size != f.stat().st_size or dest.read_bytes() != f.read_bytes():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest)
                    added.append(str(dest.relative_to(shot_dir)).replace("\\", "/"))
    changed = html != old
    if changed:
        tmp = shot_dir / "index.html.tmp"
        tmp.write_text(html, encoding="utf-8")
        tmp.replace(shot_dir / "index.html")
    return {"saved": True, "changed": changed, "assets": added}


def _stop_proc(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":                                                  # node starts children (the file watcher, the thumbnail browser): end the whole tree
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def status() -> dict:
    with _lock:
        if not _open or _open["proc"].poll() is not None:
            return {"open": False}
        return {"open": True, "key": _open["key"], "url": _open["url"], "port": _open["port"], "started": _open["started"]}


def start(key: str, work: Path, saver, log_dir: Path) -> dict:
    """Start the Studio on the folder `work` (closing another open one first, with its edits saved). `saver()` copies the edits to where they
    belong and says what it did; it runs on Save, on close and when another Studio is opened. Used for one shot (O2) and for a whole video (O4)."""
    from .render.hyperframes import _env, hyperframes_cmd

    with _lock:
        if _open and _open["key"] == key and _open["proc"].poll() is None:
            return {"open": True, "key": key, "url": _open["url"], "port": _open["port"], "started": _open["started"]}
        previous = _close_locked()
        port = _free_port()
        log_path = log_dir / "studio.log"
        log = log_path.open("w", encoding="utf-8")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        proc = subprocess.Popen(hyperframes_cmd("preview", "--no-open", "--foreground", "--port", str(port), str(work)), cwd=str(log_dir),
                                stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=_env(), creationflags=flags)
        t0 = time.time()
        while not _listening(port):
            if proc.poll() is not None or time.time() - t0 > START_SECONDS:
                _stop_proc(proc)
                log.close()
                tail = log_path.read_text(encoding="utf-8", errors="replace")[-600:]
                raise StudioError("The Studio did not start. " + tail.strip())
            time.sleep(0.3)
        url = f"http://127.0.0.1:{port}/#project/{work.name}"
        _open.update(key=key, work=work, saver=saver, proc=proc, port=port, url=url, log=log, started=time.time())
        out = {"open": True, "key": key, "url": url, "port": port, "started": _open["started"]}
        if previous:
            out["closed"] = previous
        return out


def open_shot(key: str, shot_dir: Path, theme: Optional[dict] = None) -> dict:
    """Start the Studio on this shot. `key` names the shot (`<project>/<shot>`)."""
    with _lock:
        if _open and _open["key"] == key and _open["proc"].poll() is None:
            return {"open": True, "key": key, "url": _open["url"], "port": _open["port"], "started": _open["started"]}
    work = prepare(shot_dir, theme)
    state = {"synced": (shot_dir / "index.html").read_text(encoding="utf-8")}

    def saver() -> dict:
        got = take_back(shot_dir, work, state["synced"])
        if got.get("changed"):
            state["synced"] = (shot_dir / "index.html").read_text(encoding="utf-8")
        return got

    return start(key, work, saver, shot_dir)


def save(key: str) -> dict:
    with _lock:
        if not _open or _open["key"] != key:
            raise StudioError("That is not open in the Studio.")
        return _open["saver"]()


def _close_locked() -> Optional[dict]:
    if not _open:
        return None
    try:
        got = _open["saver"]()
    except Exception as e:                                               # noqa: BLE001  the Studio still stops
        got = {"saved": False, "reason": f"The edits could not be saved: {e}"}
    _stop_proc(_open["proc"])
    try:
        _open["log"].close()
    except Exception:                                                    # noqa: BLE001
        pass
    got["key"] = _open["key"]
    _open.clear()
    return got


def close(key: Optional[str] = None) -> dict:
    """Save the edits and stop the Studio. With a key, only if that shot is the open one."""
    with _lock:
        if not _open or (key and _open["key"] != key):
            return {"open": False}
        return {"open": False, **(_close_locked() or {})}
