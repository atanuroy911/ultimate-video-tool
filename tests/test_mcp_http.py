"""The remote (HTTP) MCP transport: token required, scripts round-trip over stdio."""
import asyncio
import json
import sys

import pytest

from vt.mcp import http as H


@pytest.fixture()
def token(tmp_path, monkeypatch):
    from vt import paths

    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    return H.ensure_token()


def test_token_created_and_revocable(token):
    assert len(token) >= 32 and H.ensure_token() == token
    new = H.revoke_token()
    assert new != token and H.get_token() == new


def test_http_denies_without_token_and_accepts_with_it(token):
    from starlette.testclient import TestClient

    from vt.mcp.server import server

    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    hdr = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with TestClient(H.make_app(server), base_url="http://127.0.0.1:8766") as c:
        assert c.post("/mcp", json=init, headers=hdr).status_code == 401
        assert c.post("/mcp", json=init, headers={**hdr, "Authorization": "Bearer nope"}).status_code == 401
        r = c.post("/mcp", json=init, headers={**hdr, "Authorization": f"Bearer {token}"})
        assert r.status_code == 200 and "video-tool" in r.text
        assert c.post(f"/mcp?token={token}", json=init, headers=hdr).status_code == 200
        H.revoke_token()
        assert c.post("/mcp", json=init, headers={**hdr, "Authorization": f"Bearer {token}"}).status_code == 401


def _text(result):
    sc = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if sc is not None:
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    for block in result.content:
        if getattr(block, "text", None):
            return json.loads(block.text)


def test_script_tools_over_stdio(ref, projects_dir):
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters

    from vt.script import examples as EX

    async def scenario():
        params = StdioServerParameters(command=sys.executable, args=["-m", "vt.mcp.server"], env={"VT_PROJECTS": str(projects_dir), "PYTHONIOENCODING": "utf-8"})
        async with Client(params) as c:
            tools = {t.name for t in (await c.list_tools()).tools}
            assert {"get_script_task", "submit_script", "preview_frames"} <= tools
            prompts = {p.name for p in (await c.list_prompts()).prompts}
            assert {"plan_this_video", "make_stick_figure_video", "improve_scene"} <= prompts
            task = _text(await c.call_tool("get_script_task", {"project": ref.id, "kind": "stick"}))
            assert "CRAFT RULES" in task["instructions"] and task["schema"]["properties"]["scenes"] and "EXAMPLE 1" in task["task"]
            bad = _text(await c.call_tool("submit_script", {"project": ref.id, "script": {"version": "1.0", "kind": "stick", "scenes": "not a list"}}))
            assert bad["ok"] is True and bad["repaired"] >= 1        # garbage is repaired (every beat gets a scene), never crashes
            tr, beats = ref.transcript(), ref.beats()
            from vt.script.rules_stick import rules_script
            from vt.planner import plan_rules

            sc = rules_script(tr, beats, plan_rules(tr, beats), kind="stick")
            ok = _text(await c.call_tool("submit_script", {"project": ref.id, "script": sc.model_dump(by_alias=True, exclude_none=True)}))
            assert ok["ok"] is True and ok["kind"] == "stick"

    asyncio.run(scenario())
    assert ref.scenes().scenes[0].stick
