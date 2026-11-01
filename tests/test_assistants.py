"""One click connects Claude Code, Codex or Claude Desktop to Video Tool, and leaves the rest of their settings alone (vt/assistants.py)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vt import assistants as A


@pytest.fixture()
def home(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(A, "_which", lambda name: None)                 # no CLIs: the settings files are edited directly
    return tmp_path


def test_claude_code_keeps_its_other_settings(home):
    (home / ".claude.json").write_text(json.dumps({"theme": "dark", "mcpServers": {"other": {"command": "x"}}}))
    assert A.connected("claude-code") is None and A.installed("claude-code")
    A.connect("claude-code")
    data = json.loads((home / ".claude.json").read_text())
    assert data["theme"] == "dark" and "other" in data["mcpServers"] and data["mcpServers"]["video-tool"]["args"] == ["-m", "vt.mcp.server"]
    assert A.connected("claude-code") == "here"
    A.connect("claude-code", {"url": "http://192.168.1.5:8767/mcp", "token": "t0k"})     # moving to a server elsewhere replaces the entry
    entry = json.loads((home / ".claude.json").read_text())["mcpServers"]["video-tool"]
    assert entry == {"type": "http", "url": "http://192.168.1.5:8767/mcp", "headers": {"Authorization": "Bearer t0k"}}
    A.disconnect("claude-code")
    assert "video-tool" not in json.loads((home / ".claude.json").read_text())["mcpServers"]


def test_codex_config_toml_gets_one_block_and_keeps_the_rest(home):
    import tomllib

    cfg = home / ".codex" / "config.toml"
    cfg.parent.mkdir()
    cfg.write_text('model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "x"\n')
    A.connect("codex")
    A.connect("codex")                                                   # twice: still one entry
    t = tomllib.loads(cfg.read_text())
    assert t["model"] == "gpt-5" and t["mcp_servers"]["other"]["command"] == "x"
    assert t["mcp_servers"]["video-tool"]["args"] == ["-m", "vt.mcp.server"] and cfg.read_text().count("[mcp_servers.video-tool]") == 1
    A.connect("codex", {"url": "http://gpu:8767/mcp", "token": 'a"b'})
    t = tomllib.loads(cfg.read_text())
    assert t["mcp_servers"]["video-tool"] == {"url": "http://gpu:8767/mcp", "http_headers": {"Authorization": 'Bearer a"b'}}
    assert A.connected("codex") == "http://gpu:8767/mcp"
    A.disconnect("codex")
    assert "video-tool" not in tomllib.loads(cfg.read_text())["mcp_servers"]


def test_claude_desktop_and_a_broken_file(home):
    f = A.claude_desktop_file()
    f.parent.mkdir(parents=True)
    f.write_text("{not json")
    with pytest.raises(RuntimeError):
        A.connect("claude-desktop")
    assert f.read_text() == "{not json"                                  # never overwritten
    f.write_text("{}")
    assert "Quit and reopen" in A.connect("claude-desktop")["note"] and A.connected("claude-desktop") == "here"


def test_the_settings_page_connects_only_on_the_server_computer(home):
    from vt.server.app import app

    here = TestClient(app, client=("127.0.0.1", 50000))
    (home / ".claude.json").write_text("{}")
    listed = {s["id"]: s for s in here.get("/api/assistants").json()["assistants"]}
    assert listed["claude-code"]["installed"] and not listed["claude-code"]["connected"]
    assert here.post("/api/assistants/claude-code/connect").json()["status"]["connected"]
    away = TestClient(app, client=("192.168.1.9", 50000))
    assert away.get("/api/assistants").json() == {"here": False, "assistants": []}
    assert away.post("/api/assistants/codex/connect").status_code == 403
