from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class Cancelled(BaseException):
    """Stop requested by the person, not an engine error to retry or replace."""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path | str, default: Any = None) -> Any:
    p = Path(path)
    for attempt in range(10):                                  # Windows refuses to open a file for the instant another request replaces it
        try:
            if not p.exists():
                return default
            return json.loads(p.read_text(encoding="utf-8"))
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.03 * (attempt + 1))
        except FileNotFoundError:                              # replaced between exists() and read
            return default


def write_json(path: Path | str, data: Any) -> None:
    """Atomic write so a crash never leaves a half-written file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.{threading.get_ident()}.tmp")       # unique per writer: two writers never share a temp file
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(10):                                                         # Windows refuses to replace a file another process is reading
        try:
            os.replace(tmp, p)
            return
        except PermissionError:
            time.sleep(0.03 * (attempt + 1))
    p.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
    tmp.unlink(missing_ok=True)


def file_hash(*paths: Path | str, extra: str = "") -> str:
    h = hashlib.sha1(extra.encode("utf-8"))
    for p in paths:
        p = Path(p)
        if p.exists():
            h.update(p.read_bytes())
        else:
            h.update(b"<missing>")
    return h.hexdigest()[:16]


def slugify(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-").lower()
    return s[:40].rstrip(".") or "video"  # Windows strips trailing dots when making a folder; the stored id must match that folder.


def tool_dirs() -> list[Path]:
    """Where the program's own copies of ffmpeg, node ... live, looked at before PATH: `VT_BIN` (a folder, or several separated like PATH), then `bin/` next to the app folder
    (the installed product: `<product>/app` and `<product>/bin`), then `bin/` inside it."""
    from . import paths

    out = [Path(x) for x in os.environ.get("VT_BIN", "").split(os.pathsep) if x]
    for base in (paths.ROOT.parent / "bin", paths.ROOT / "bin"):
        out += [base, base / "node", base / "node" / "bin"]     # Node is unpacked whole into bin/node (Windows: node.exe there; Linux/macOS: in its bin/)
    return [d for d in out if d.is_dir()]


def find_tool(name: str) -> str:
    """Locate an executable (ffmpeg, node, npx...): the program's own `bin/` folders first, then PATH; or raise a readable error."""
    names = [name] + ([name + ".exe", name + ".cmd"] if sys.platform == "win32" and not name.lower().endswith((".exe", ".cmd")) else [])
    for d in tool_dirs():
        for n in names:
            f = d / n
            if f.is_file():
                return str(f)
    p = shutil.which(name)
    if not p and sys.platform == "win32":
        p = shutil.which(name + ".cmd") or shutil.which(name + ".exe")
    if not p:
        raise RuntimeError(f"'{name}' was not found (looked in the program's bin folder and on PATH)")
    return p


def run(cmd: list[str], *, cwd: Optional[Path] = None, on_line: Optional[Callable[[str], None]] = None, check: bool = True,
        stall_seconds: Optional[float] = None) -> str:
    """Run a subprocess, streaming merged stdout/stderr lines to on_line. Returns the full output.

    `stall_seconds`: kill the process and raise if it prints nothing for that long. A render that hangs (seen on 2026-10-27: the GPU encoder
    stuck in HyperFrames' final "assemble" step for over twenty minutes) must become an error the caller can retry, not a job that never ends."""
    import threading
    import time

    proc = subprocess.Popen(
        cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    lines: list[str] = []
    assert proc.stdout is not None
    last = [time.monotonic()]
    stalled = threading.Event()
    done = threading.Event()

    def watch() -> None:
        while not done.wait(5.0):
            if time.monotonic() - last[0] > (stall_seconds or 0):
                stalled.set()
                proc.kill()
                return

    if stall_seconds:
        threading.Thread(target=watch, daemon=True).start()
    try:
        for raw in proc.stdout:
            last[0] = time.monotonic()
            line = raw.rstrip()
            lines.append(line)
            if on_line:
                on_line(line)  # may raise (e.g. job cancelled) -> the process is killed below
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    finally:
        done.set()
    code = proc.wait()
    out = "\n".join(lines)
    if stalled.is_set():
        raise RuntimeError(f"command stalled: no output for {int(stall_seconds or 0)} s, so it was stopped: {' '.join(map(str, cmd))[:160]}\n" + "\n".join(lines[-8:]))
    if check and code != 0:
        tail = "\n".join(lines[-25:])
        raise RuntimeError(f"command failed ({code}): {' '.join(map(str, cmd))[:200]}\n{tail}")
    return out


ProgressFn = Callable[[str, float, str], None]  # (stage, fraction 0..1, message)


def noop_progress(stage: str, frac: float, msg: str = "") -> None:
    return None


class TimeLeft:
    """Speed and time left of a download, in plain words: " · 12 MB/s · about 6 min left". Silent for the first seconds (no wild guesses)."""

    def __init__(self, total_bytes: float):
        import time

        self.total, self.start, self._now = max(1.0, float(total_bytes)), time.time(), time.time

    def words(self, done_bytes: float) -> str:
        took = self._now() - self.start
        if took < 4 or done_bytes <= 0:
            return ""
        rate = done_bytes / took
        left = max(0.0, (self.total - done_bytes) / rate)
        when = "less than a minute left" if left < 60 else f"about {round(left / 60)} min left" if left < 5400 else f"about {left / 3600:.1f} h left"
        return f" · {rate / 1e6:.0f} MB/s · {when}" if rate >= 1e6 else f" · {rate / 1e3:.0f} kB/s · {when}"
