"""Concat's headless engine as an optional sidecar: found by setting or environment, and (when it is unpacked here) really driven over MCP. The real part is skipped when the exe is absent."""
import json
import os
import subprocess
import sys

import pytest

from vt import concat_client as CC


def test_the_exe_is_found_through_the_environment_and_absent_otherwise(tmp_path, monkeypatch):
    monkeypatch.delenv("VT_CONCAT_EXE", raising=False)
    monkeypatch.setattr("vt.paths.SETTINGS", tmp_path / "s.json")
    monkeypatch.setattr("vt.paths.ROOT", tmp_path)
    assert CC.exe_path() is None and not CC.available()
    fake = tmp_path / "concat.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv("VT_CONCAT_EXE", str(fake))
    assert CC.exe_path() == str(fake) and CC.available()


def test_the_client_speaks_mcp_with_a_stand_in_server(tmp_path):
    server = tmp_path / "fake_concat.py"
    server.write_text('''import json, sys
for line in sys.stdin:
    r = json.loads(line)
    if "id" not in r:
        continue
    if r["method"] == "tools/call":
        a = r["params"]["arguments"]
        if r["params"]["name"] == "boom":
            out = {"result": {"isError": True, "content": [{"type": "text", "text": "no such project"}]}}
        else:
            out = {"result": {"content": [{"type": "text", "text": json.dumps({"createdId": "m1", "echo": a})}]}}
    else:
        out = {"result": {"capabilities": {}}}
    print(json.dumps({"jsonrpc": "2.0", "id": r["id"], **out}), flush=True)
''', encoding="utf-8")

    class Stub(CC.Concat):
        def __init__(self):                                      # the same protocol, a different program
            self.p = subprocess.Popen([sys.executable, str(server)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
            self.n = 0
            self.rpc("initialize", {})
    c = Stub()
    try:
        r = c.call("project_create", location="x", name="spike")           # `name` is a tool argument, not the tool's name
        assert r["createdId"] == "m1" and r["echo"] == {"location": "x", "name": "spike"}
        with pytest.raises(RuntimeError, match="no such project"):
            c.call("boom")
    finally:
        c.close()


@pytest.mark.skipif(not CC.available(), reason="Concat is not unpacked in tools/concat (optional)")
def test_the_real_engine_lists_its_tools():
    c = CC.Concat(CC.exe_path())
    try:
        names = [t["name"] for t in c.rpc("tools/list")["result"]["tools"]]
        assert {"project_create", "media_import", "clip_add", "title_add", "export_start", "export_wait"} <= set(names)
    finally:
        c.close()
