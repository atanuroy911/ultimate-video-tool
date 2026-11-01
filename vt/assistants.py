"""Connect AI assistants to Video Tool in one click: Claude Code (terminal, VS Code, desktop app), Codex and Claude Desktop.

    GET  /api/assistants                    which ones are on this computer and whether each is connected
    POST /api/assistants/{id}/connect       register Video Tool with it (`vt assistants connect claude-code`)
    POST /api/assistants/{id}/disconnect

An assistant on the server computer starts the tools itself (stdio: this Python, `-m vt.mcp.server`). One on another computer reaches the
server's `/mcp` with a key of its own (`remote={"url", "token"}`); the desktop app does the same registration on its own computer
(desktop/assistants.js). The CLI is used when it is installed (`claude mcp add --scope user`, `codex mcp add`), otherwise the config file is
edited directly, keeping everything else in it. Registration is per user, so it works in every folder.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from .util import CREATE_NO_WINDOW

NAME = "video-tool"
IDS = ("claude-code", "codex", "claude-desktop")
LABELS = {"claude-code": "Claude Code", "codex": "Codex", "claude-desktop": "Claude Desktop"}


def _stdio() -> dict[str, Any]:
    return {"command": str(Path(sys.executable)), "args": ["-m", "vt.mcp.server"], "env": {"PYTHONIOENCODING": "utf-8"}}


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW,
                          encoding="utf-8", errors="replace")


def _which(name: str) -> Optional[str]:
    for n in (name, name + ".cmd", name + ".exe"):
        p = shutil.which(n)
        if p:
            return p
    local = Path.home() / ".local" / "bin" / (name + (".exe" if os.name == "nt" else ""))
    return str(local) if local.exists() else None


# --------------------------------------------------------------------------- where each one keeps its settings
def claude_code_file() -> Path:
    d = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(d) / ".claude.json" if d else Path.home() / ".claude.json"


def codex_file() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"


def claude_desktop_file() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "Claude" / "claude_desktop_config.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _read_json(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8") or "{}")
    except ValueError as e:
        raise RuntimeError(f"{p} is not valid JSON, so it was left alone. Fix or remove it, then try again.") from e


def _write_json(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".vt-tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


_TOML_BLOCK = re.compile(r"(?ms)^\[mcp_servers\.(?:\"video-tool\"|video-tool)(?:\.[^\]]+)?\]\n.*?(?=^\[|\Z)")


def _toml_str(s: str) -> str:
    return json.dumps(s)                                         # a JSON string is a valid TOML basic string


def _codex_block(remote: Optional[dict]) -> str:
    if remote:
        return (f"[mcp_servers.{NAME}]\nurl = {_toml_str(remote['url'])}\n"
                f"http_headers = {{ Authorization = {_toml_str('Bearer ' + remote['token'])} }}\n")
    s = _stdio()
    args = ", ".join(_toml_str(a) for a in s["args"])
    return (f"[mcp_servers.{NAME}]\ncommand = {_toml_str(s['command'])}\nargs = [{args}]\n"
            f"env = {{ PYTHONIOENCODING = \"utf-8\", VT_MCP_CLIENT = \"codex\" }}\n")


# --------------------------------------------------------------------------- status
def installed(aid: str) -> bool:
    if aid == "claude-code":
        return bool(_which("claude")) or claude_code_file().exists()
    if aid == "codex":
        return bool(_which("codex")) or codex_file().parent.exists()
    return claude_desktop_file().parent.exists()


def connected(aid: str) -> Optional[str]:
    """None, "here" (stdio on this computer) or the server address it uses."""
    try:
        if aid == "claude-code":
            e = (_read_json(claude_code_file()).get("mcpServers") or {}).get(NAME)
        elif aid == "claude-desktop":
            e = (_read_json(claude_desktop_file()).get("mcpServers") or {}).get(NAME)
        else:
            p = codex_file()
            m = _TOML_BLOCK.search(p.read_text(encoding="utf-8")) if p.exists() else None
            if not m:
                return None
            u = re.search(r'^url = "([^"]+)"', m.group(0), re.M)
            return u.group(1) if u else "here"
    except RuntimeError:
        return None
    if not e:
        return None
    return e.get("url") or ("here" if e.get("command") else None)


def status() -> list[dict[str, Any]]:
    out = []
    for aid in IDS:
        c = connected(aid)
        out.append({"id": aid, "label": LABELS[aid], "installed": installed(aid), "connected": c is not None, "to": c,
                    "restart": aid != "claude-code"})
    return out


# --------------------------------------------------------------------------- connect / disconnect
def connect(aid: str, remote: Optional[dict] = None) -> dict[str, Any]:
    """Register Video Tool with one assistant, replacing an older entry. `remote` = {"url", "token"} for a server elsewhere."""
    if aid not in IDS:
        raise ValueError(f"unknown assistant {aid}")
    if aid == "claude-code":
        exe = _which("claude")
        if exe:
            _run([exe, "mcp", "remove", "--scope", "user", NAME])
            cmd = ([exe, "mcp", "add", "--scope", "user", "--transport", "http", NAME, remote["url"], "--header", f"Authorization: Bearer {remote['token']}"] if remote
                   else [exe, "mcp", "add", "--scope", "user", NAME, "-e", "PYTHONIOENCODING=utf-8", "--", _stdio()["command"], *_stdio()["args"]])   # -e takes many values: the name goes first
            r = _run(cmd)
            if r.returncode:
                raise RuntimeError((r.stderr or r.stdout or "Claude Code refused the connection").strip()[:300])
        else:                                                    # only the VS Code extension or the desktop app: the same user settings file
            data = _read_json(claude_code_file())
            data.setdefault("mcpServers", {})[NAME] = ({"type": "http", "url": remote["url"], "headers": {"Authorization": f"Bearer {remote['token']}"}} if remote
                                                       else {"type": "stdio", **_stdio()})
            _write_json(claude_code_file(), data)
        note = "Connected. Start a new Claude Code chat and ask it to make a video."
    elif aid == "codex":
        p = codex_file()
        text = p.read_text(encoding="utf-8") if p.exists() else ""
        text = _TOML_BLOCK.sub("", text).rstrip()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text((text + "\n\n" if text else "") + _codex_block(remote), encoding="utf-8")
        note = "Connected. Restart Codex to load the Video Tool tools."
    else:
        if remote:
            raise RuntimeError("Claude Desktop on another computer connects through the Video Tool app there (it carries the bridge).")
        data = _read_json(claude_desktop_file())
        data.setdefault("mcpServers", {})[NAME] = _stdio()
        _write_json(claude_desktop_file(), data)
        note = "Connected. Quit and reopen Claude Desktop to load it."
    return {"ok": True, "id": aid, "note": note, "status": next(s for s in status() if s["id"] == aid)}


def disconnect(aid: str) -> dict[str, Any]:
    if aid == "claude-code" and _which("claude"):
        _run([_which("claude"), "mcp", "remove", "--scope", "user", NAME])
    elif aid == "codex":
        p = codex_file()
        if p.exists():
            p.write_text(_TOML_BLOCK.sub("", p.read_text(encoding="utf-8")).rstrip() + "\n", encoding="utf-8")
    else:
        f = claude_code_file() if aid == "claude-code" else claude_desktop_file()
        data = _read_json(f)
        if (data.get("mcpServers") or {}).pop(NAME, None) is not None:
            _write_json(f, data)
    return {"ok": True, "id": aid, "note": f"{LABELS[aid]} no longer uses Video Tool."}
