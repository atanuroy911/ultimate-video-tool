"""An AI assistant on another computer uses the server's tools at /mcp with its own key (docs/plans/PLAN-CLIENT-SERVER.MD CS6)."""
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
    serve.configure(key=KEY, code="ab12-cd34-ef56", name="GPU box", exposed=True)
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
    serve.configure(**{k: saved[k] for k in ("key", "code", "name", "exposed")}, services=services)


async def _tools(url: str, token: str) -> list[str]:
    from mcp import ClientSession
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    async with create_mcp_http_client(headers={"Authorization": f"Bearer {token}"}) as http:
        async with streamable_http_client(url, http_client=http) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                return [t.name for t in (await session.list_tools()).tools]


def test_an_assistant_key_opens_the_tools_and_revoking_it_closes_them(server):
    import httpx

    assert httpx.post(server + "/mcp", json={}).status_code == 401                     # no key: not even from this computer
    made = httpx.post(server + "/api/server/assistant", json={"name": "Claude Code on Roy's laptop"}).json()
    cfg = made["mcp_json"]["mcpServers"]["video-tool"]
    assert cfg["type"] == "http" and cfg["url"] == server + "/mcp" and cfg["headers"]["Authorization"] == f"Bearer {made['token']}"
    tools = asyncio.run(_tools(cfg["url"], made["token"]))
    assert "list_projects" in tools and "submit_scenes" in tools
    devices = httpx.get(server + "/api/server/clients").json()
    assert [d["name"] for d in devices] == ["Claude Code on Roy's laptop"]
    httpx.delete(f"{server}/api/server/clients/{devices[0]['id']}")
    assert httpx.post(server + "/mcp", json={}, headers={"Authorization": f"Bearer {made['token']}"}).status_code == 401


def test_a_studio_only_on_this_computer_offers_no_network_tools():
    c = TestClient(app, client=("127.0.0.1", 50000))
    assert not serve.STATE["exposed"]
    assert c.post("/api/server/assistant", json={}).status_code == 409
    assert c.post("/mcp", json={}).status_code == 401
