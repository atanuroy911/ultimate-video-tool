"""Every MCP tool asks Claude Code to keep a large result in the conversation (see RESULT_SIZE in vt/mcp/server.py). Without it the planning task is saved to a
file the planning session cannot read, and Claude never plans (found 2026-11-20 with the real program)."""
import asyncio

from vt.mcp import server as mcp_server


def test_every_tool_asks_for_the_largest_result_size():
    listed = asyncio.run(mcp_server.server.list_tools())
    tools = listed.tools if hasattr(listed, "tools") else listed
    assert len(tools) > 30
    missing = [t.name for t in tools if (getattr(t, "meta", None) or {}).get("anthropic/maxResultSizeChars") != 500000]
    assert not missing, missing
    assert any(t.name == "get_script_task" for t in tools)
