"""A small client for Concat's headless engine (`concat --mcp headless`: MCP over stdio, 42 editing tools, GPU compositor, H.264/HEVC/AV1 export).

Concat (https://github.com/jub0t/Concat, AGPL-3.0) is an optional sidecar: nothing here is needed to make videos. Where the exe is looked for: `VT_CONCAT_EXE`, the `concat_exe` setting, or
`tools/concat/concat.exe` next to the app (unpack the Windows MSI there with `msiexec /a Concat.msi /qn TARGETDIR=...`; nothing is installed). `scripts/spike_concat.py` shows a full edit
(video + transparent PNG on a lane above + a title, exported with the audio kept) driven through this client.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional

from . import paths
from .util import CREATE_NO_WINDOW, read_json


def exe_path() -> Optional[str]:
    for c in (os.environ.get("VT_CONCAT_EXE"), (read_json(paths.SETTINGS, {}) or {}).get("concat_exe"), str(paths.ROOT / "tools" / "concat" / "concat.exe"), str(paths.ROOT / "tools" / "concat" / "concat")):
        if c and Path(c).exists():
            return c
    return None


def available() -> bool:
    return exe_path() is not None


class Concat:
    def __init__(self, exe: str):
        self.p = subprocess.Popen([exe, "--mcp", "headless"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", creationflags=CREATE_NO_WINDOW)
        self.n = 0
        self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "video-tool-spike", "version": "0"}})
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.p.stdin.flush()

    def rpc(self, method, params=None, timeout=300):
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}) + "\n")
        self.p.stdin.flush()
        box: list[str] = []
        t = threading.Thread(target=lambda: box.append(self.p.stdout.readline()), daemon=True)
        t.start()
        t.join(timeout)
        if not box or not box[0]:
            raise TimeoutError(method)
        return json.loads(box[0])

    def call(self, _tool, **args):
        name = _tool
        r = self.rpc("tools/call", {"name": name, "arguments": args})
        if "error" in r:
            raise RuntimeError(f"{name}: {r['error']}")
        res = r["result"]
        text = "".join(c.get("text", "") for c in res.get("content", []))
        if res.get("isError"):
            raise RuntimeError(f"{name}: {text[:300]}")
        try:
            return res.get("structuredContent") or json.loads(text)
        except ValueError:
            return {"text": text}

    def close(self):
        self.p.kill()
