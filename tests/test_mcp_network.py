"""An AI assistant on another computer uses the server's tools at /mcp (docs/plans/PLAN-CLIENT-SERVER.MD CS6): no key from the server's own network, never from a web page."""
import asyncio
import socket
import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient

from vt.server import serve
from vt.server.app import app

KEY = "k" * 43


@pytest.fixture()
def server(monkeypatch, tmp_path):
    from vt import paths

    monkeypatch.setattr(paths, "DATA", tmp_path)
    saved = {**serve.STATE, "services": dict(serve.STATE["services"])}
    serve.configure(key=KEY, name="GPU box", exposed=True)
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(400):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(10)
    services = saved.pop("services")
    serve.configure(**{k: saved[k] for k in ("key", "name", "exposed")}, services=services)


async def _tools(url: str, token: str = "") -> list[str]:
    from mcp import ClientSession
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    async with create_mcp_http_client(headers={"Authorization": f"Bearer {token}"} if token else {}) as http:
        async with streamable_http_client(url, http_client=http) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                return [t.name for t in (await session.list_tools()).tools]


def test_an_assistant_on_the_same_network_reaches_the_tools_with_no_key_and_a_web_page_does_not(server):
    import httpx

    assert httpx.post(server + "/mcp", json={}).status_code != 401                     # no key, from the server's own network: let in
    assert httpx.post(server + "/mcp", json={}, headers={"Origin": "https://evil.example"}).status_code == 401      # a web page: refused
    made = httpx.post(server + "/api/server/assistant", json={"name": "Claude Code on Roy's laptop"}).json()
    cfg = made["mcp_json"]["mcpServers"]["video-tool"]
    assert cfg == {"type": "http", "url": server + "/mcp"} and "token" not in made
    tools = asyncio.run(_tools(cfg["url"]))
    assert "list_projects" in tools and "submit_scenes" in tools


def test_a_studio_only_on_this_computer_offers_no_network_tools():
    c = TestClient(app, client=("127.0.0.1", 50000))
    assert not serve.STATE["exposed"]
    assert c.post("/api/server/assistant", json={}).status_code == 409
    assert c.post("/mcp", json={}).status_code == 404                                  # not offered at all
