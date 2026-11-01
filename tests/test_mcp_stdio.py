"""The MCP server exactly as Claude Code runs it: a subprocess speaking the protocol over stdio."""
import asyncio
import json
import sys

import pytest

from vt import planning
from vt.planner import plan_rules


def _text(result):
    """Tool results arrive as structured content and/or text blocks; return the parsed JSON payload."""
    sc = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if sc is not None:
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    for block in result.content:
        if getattr(block, "text", None):
            return json.loads(block.text)
    raise AssertionError(f"no usable content in {result!r}")


def test_claude_plans_a_video_over_stdio(ref, projects_dir):
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters

    req = planning.create_request(ref, "full")
    good = plan_rules(ref.transcript(), ref.beats()).model_dump(exclude_none=True)["scenes"]

    async def scenario():
        params = StdioServerParameters(command=sys.executable, args=["-m", "vt.mcp.server"],
                                       env={"VT_PROJECTS": str(projects_dir), "PYTHONIOENCODING": "utf-8"})
        async with Client(params) as c:
            tools = {t.name for t in (await c.list_tools()).tools}
            assert {"list_pending_requests", "get_planning_task", "submit_scenes", "get_preview_frame", "render", "list_media", "add_media", "list_scene_types", "show_scene_as"} <= tools
            assert {"module_catalog", "module_describe", "module_call"} <= tools
            catalogue = _text(await c.call_tool("module_catalog", {}))
            assert any(item["id"] == "audio.find_retakes" for item in catalogue)
            description = _text(await c.call_tool("module_describe", {"module_id": "audio.find_retakes"}))
            assert "transcript.raw" in description["requires"]
            module_result = _text(await c.call_tool("module_call", {
                "project_id": ref.id, "module_id": "audio.find_retakes",
                "inputs": {}, "why": "Check the recording for repeated takes.",
            }))
            assert module_result["ok"] is True
            for module_id, inputs in (("project.inspect_source", {}),
                                      ("audio.prosody", {"windows": [[0.0, 1.0]]})):
                extra = _text(await c.call_tool("module_call", {
                    "project_id": ref.id, "module_id": module_id, "inputs": inputs,
                    "why": "Verify the shared module contract.",
                }))
                assert extra["ok"] is True, extra
            assert (ref.dir / "calls.jsonl").exists()

            pending = _text(await c.call_tool("list_pending_requests", {}))
            assert [p["id"] for p in pending] == [req.id]

            task = _text(await c.call_tool("get_planning_task", {"project": ref.id, "request_id": req.id}))
            assert "Cover EVERY beat" in task["instructions"] and task["beats"] and task["catalogue"]["elements"]

            bad = _text(await c.call_tool("submit_scenes", {"project": ref.id, "request_id": req.id,
                                                            "scenes": [{"id": "s1", "beats": ["b1"], "elements": [{"type": "title", "text": "x", "at_word": "w999"}]}]}))
            assert bad["ok"] is False and any("w999" in e for e in bad["errors"])

            ok = _text(await c.call_tool("submit_scenes", {"project": ref.id, "request_id": req.id, "scenes": good}))
            assert ok["ok"] is True and ok["applied"] is True

            scenes = _text(await c.call_tool("get_scenes", {"project": ref.id}))
            assert scenes["planner"] == "claude" and scenes["scenes"][0]["time"][0] == 0.0

            types = _text(await c.call_tool("list_scene_types", {"project": ref.id, "scene_id": "s2"}))
            assert types and all("id" in t for t in types)
            shown = _text(await c.call_tool("show_scene_as", {"project": ref.id, "scene_id": "s2", "scene_type": types[0]["id"]}))
            assert shown["ok"] is True and shown["scene"]["archetype"] == types[0]["id"]
            refused = _text(await c.call_tool("show_scene_as", {"project": ref.id, "scene_id": "s1", "scene_type": "line_trend"}))
            assert refused["ok"] is False and "needs" in refused["error"]
            assert _text(await c.call_tool("list_media", {"project": ref.id})) == []
            from PIL import Image
            Image.new("RGB", (80, 60), (10, 90, 160)).save(projects_dir / "mcp.png")
            added = _text(await c.call_tool("add_media", {"project": ref.id, "file_path": str(projects_dir / "mcp.png"), "caption": "blue"}))
            assert added["ok"] is True and [m["id"] for m in _text(await c.call_tool("list_media", {"project": ref.id}))] == [added["id"]]
            assert _text(await c.call_tool("add_media", {"project": ref.id, "file_path": str(projects_dir / "nope.png")}))["ok"] is False
            fixed = _text(await c.call_tool("fix_word", {"project": ref.id, "word_id": "w20", "text": "বদলানো"}))
            assert fixed["ok"] is True
            theme = _text(await c.call_tool("update_theme", {"name": "paper", "patch": {"color": {"accent": "#123456"}}}))
            assert theme["ok"] is False          # built-in themes are read-only over MCP too

    asyncio.run(asyncio.wait_for(scenario(), 120))
    assert planning.pending() == []
    assert ref.scenes().planner == "claude"
    assert (projects_dir.parent / "x").exists() is False  # nothing leaked outside the temp projects folder


def test_server_never_writes_to_stdout_outside_the_protocol(ref, projects_dir):
    """A stray print() would corrupt the JSON-RPC stream and silently break Claude Code's connection."""
    import subprocess

    p = subprocess.run([sys.executable, "-c", "import vt.mcp.server"], capture_output=True, text=True, timeout=60,
                       env={**__import__("os").environ, "VT_PROJECTS": str(projects_dir), "PYTHONIOENCODING": "utf-8"})
    assert p.returncode == 0 and p.stdout == "", p.stdout


def test_heartbeat_goes_to_the_projects_folder_not_the_repo(ref, projects_dir):
    """Regression: tests wrote .mcp_seen.json into the repo, so the app claimed 'Claude connected' with no Claude running."""
    from vt import paths
    from vt.mcp import server as srv

    srv.list_projects()                                    # any tool call records a heartbeat
    assert (projects_dir / ".mcp_seen.json").exists()
    assert not (paths.ROOT / ".mcp_seen.json").exists()


def test_codex_plan_is_attributed_and_prompt_is_available(ref, monkeypatch):
    from vt.mcp.server import direct_whole_video

    monkeypatch.setenv("VT_MCP_CLIENT", "codex")
    req = planning.create_request(ref, "full")
    scenes = plan_rules(ref.transcript(), ref.beats()).model_dump(exclude_none=True)["scenes"]
    result = planning.submit(ref, req.id, scenes)
    assert result["ok"] is True
    assert ref.scenes().planner == "assistant"
    assert "get_script_task" in direct_whole_video(ref.id)
