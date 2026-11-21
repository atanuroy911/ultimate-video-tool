"""A director's task credential authorizes one project's tools, never server administration."""
import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
from mcp.shared.exceptions import MCPError


@pytest.fixture()
def scoped(projects_dir):
    from vt.mcp import scope

    token = scope.issue("first", ttl=30)
    yield scope, token
    scope.revoke(token)


def test_tokens_expire_and_revoke_immediately(scoped, monkeypatch):
    scope, token = scoped
    assert scope.project_for(token) == "first"
    scope.revoke(token)
    assert scope.project_for(token) is None
    fresh = scope.issue("first", ttl=1)
    monkeypatch.setattr(scope.time, "monotonic", lambda: float("inf"))
    assert scope.project_for(fresh) is None


def test_scoped_director_gets_a_short_brief_and_blocks_delegation(ref, monkeypatch):
    from vt.ai import talk
    from vt.mcp import scope, server
    from vt.modules.envelope import CallResult
    from vt.modules.executor import Executor
    from vt.script import service
    from vt.script.prompt import transcript_text
    from vt.planner.catalogue import component_catalogue

    service.set_script_kind(ref, "cartoon")
    full = service.script_task(ref)
    calls = []

    def execute(self, module_id, *args, **kwargs):
        calls.append(module_id)
        return CallResult(ok=True, status="ok", summary="Checked")

    monkeypatch.setattr(Executor, "call", execute)
    token = scope.issue(ref.id)

    async def run(_ctx):
        brief = server.get_script_task(ref.id)
        assert len(brief["task"]) < .7 * len(full["task"])
        assert brief["schema"] == full["schema"]
        assert transcript_text(ref.transcript(), ref.beats()) in brief["task"]
        for spec in component_catalogue():
            example = json.dumps(spec["example"], ensure_ascii=False, separators=(",", ":"))
            assert example in brief["task"], f"{spec['type']} fields remain discoverable"
        assert "cartoon" in brief["task"] and "submit_script" in brief["submit"]
        assert brief["has_current_script"] is False
        assert server.get_current_script(ref.id)["script"] is None
        with pytest.raises(MCPError, match="already waiting for your direction"):
            server.run_pipeline(ref.id)

        catalog = {row["id"]: row for row in server.module_catalog_tool()}
        advice = catalog["direct.plan_script"]["during_director_task"]
        assert advice == server.module_describe_tool("direct.plan_script")["during_director_task"]
        result = server.module_call_tool(ref.id, "direct.plan_script", {})
        assert not result["ok"] and result["status"] == "refused" and result["fix"] == advice
        assert not calls
        assert server.module_call_tool(ref.id, "craft.check", {})["ok"]
        assert calls == ["craft.check"]

    try:
        ctx = SimpleNamespace(request=SimpleNamespace(headers={scope.HEADER: token}))
        asyncio.run(scope.middleware(ctx, run))
    finally:
        scope.revoke(token)

    logged = [json.loads(row["prompt"]) for row in talk.load(ref.dir) if row["kind"] == "tool"]
    assert [row["arguments"]["module_id"] for row in logged if row["tool"] == "module_call"] == ["direct.plan_script", "craft.check"]
    assert server.module_call_tool(ref.id, "direct.plan_script", {})["ok"], "manual assistant use keeps its existing access"


def test_cross_project_tools_and_global_changes_are_refused_before_execution(scoped):
    scope, token = scoped
    from vt.mcp import server

    async def scenario():
        ctx = SimpleNamespace(request=SimpleNamespace(headers={scope.HEADER: token}))
        async def tool_call(_ctx):
            assert scope.current_project() == "first"
            scope.check_tool("get_transcript", {"project": "first"})
            for name, args in (("get_transcript", {"project": "second"}),
                               ("module_call_tool", {"project_id": "second"}),
                               ("gpu_assignment", {"allowed": "all"}), ("create_project", {}),
                               ("prepare_upload", {}), ("update_theme", {})):
                with pytest.raises(MCPError, match="project"):
                    scope.check_tool(name, args)
            with pytest.raises(MCPError, match="project"):
                scope.check_tool("future_tool", {"project": "first"})
            with pytest.raises(MCPError, match="project"):
                scope.check_tool("get_theme", {"name": "../private-theme"})
            with pytest.raises(MCPError, match="project"):
                server.get_transcript("second")
        await scope.middleware(ctx, tool_call)
        assert scope.current_project() is None
    asyncio.run(scenario())


@pytest.mark.parametrize("module,inputs", [
    ("meta.wait", {"ticket": "someone-elses-ticket"}),
    ("meta.cancel", {"ticket": "someone-elses-ticket"}),
    ("voice.clone", {"audio": "another-video.wav", "consent": True}),
    ("project.create", {"source": "another-video.wav"}),
    ("publish.dispatch", {"confirmed": True}),
    ("future.unknown_capability", {}),
    ("meta.state", {"artifact_type": "../../settings"}),
    ("understand.faces", {"frame": "C:/outside/frame.png"}),
    ("asr.from_subtitles", {"file": "C:/outside/subtitles.vtt"}),
    ("sound.mix", {"video": "C:/outside/render.mp4"}),
    ("judge.scorecard", {"voice": "C:/outside/voice.wav"}),
])
def test_module_indirection_cannot_escape_task_scope(scoped, module, inputs):
    scope, token = scoped
    async def scenario():
        async def call(_ctx):
            with pytest.raises(MCPError, match="project"):
                scope.check_tool("module_call_tool", {"project_id": "first", "module_id": module, "inputs": inputs})
        await scope.middleware(SimpleNamespace(request=SimpleNamespace(headers={scope.HEADER: token})), call)
    asyncio.run(scenario())


def test_token_cannot_cross_request_or_survive_revocation(scoped):
    scope, token = scoped
    async def scenario():
        seen = []
        async def call(_ctx):
            seen.append(scope.current_project())
        await scope.middleware(SimpleNamespace(request=SimpleNamespace(headers={scope.HEADER: token})), call)
        await scope.middleware(SimpleNamespace(request=SimpleNamespace(headers={})), call)
        assert seen == ["first", None]
        scope.revoke(token)
        with pytest.raises(MCPError, match="expired"):
            await scope.middleware(SimpleNamespace(request=SimpleNamespace(headers={scope.HEADER: token})), call)
    asyncio.run(scenario())


def test_project_lists_and_background_jobs_stay_within_scope(ref, scoped, monkeypatch):
    scope, token = scoped
    from vt.mcp import server
    from vt.project import Project
    from vt.schema import ProjectMeta
    from vt.util import write_json

    second = Project("second")
    second.dir.mkdir()
    write_json(second.meta_path, ProjectMeta(id="second", title="Private other video", created_at="2026-11-06").model_dump())
    scope.revoke(token)
    token = scope.issue(ref.id)
    monkeypatch.setitem(server._BG, "other-job", {"project": "second", "error": "private other project failure"})
    monkeypatch.setitem(server._BG, "own-job", {"project": ref.id, "status": "done"})
    async def scenario():
        async def call(_ctx):
            assert [p["id"] for p in server.list_projects()] == [ref.id]
            assert server.job_status("own-job")["status"] == "done"
            with pytest.raises(MCPError, match="project"):
                server.job_status("other-job")
        await scope.middleware(SimpleNamespace(request=SimpleNamespace(headers={scope.HEADER: token})), call)
    try:
        asyncio.run(scenario())
    finally:
        scope.revoke(token)


def test_director_broker_sends_only_a_task_token_and_retires_it(monkeypatch):
    from vt import directors
    from vt.mcp import scope

    broker = directors.DirectorBroker(grace=0)
    sent, result = [], {}
    broker.connect("laptop", "Test laptop", logged_in=True, send=sent.append)
    thread = threading.Thread(target=lambda: result.update(broker.request("laptop", "first", "Direct it", 2)))
    thread.start()
    try:
        for _ in range(200):
            if sent:
                break
            threading.Event().wait(0.005)
        task = sent[0]
        assert scope.project_for(task["director_token"]) == "first"
        assert broker.finish(task["request"], ok=True)
        thread.join(3)
        assert result["ok"] is True
        assert scope.project_for(task["director_token"]) is None
    finally:
        broker.disconnect("laptop")
        thread.join(3)


@pytest.mark.parametrize("failure", ["timeout", "send", "disconnect"])
def test_abandoned_director_tasks_lose_their_credential(failure):
    from vt import directors
    from vt.mcp import scope

    sent = []
    broker = directors.DirectorBroker(grace=0)
    def send(task):
        sent.append(task)
        if failure == "send":
            raise OSError("fake disconnect")
        if failure == "disconnect":
            broker.disconnect("laptop")
    broker.connect("laptop", "Test laptop", logged_in=True, send=send)
    try:
        result = broker.request("laptop", "first", "Direct it", 0.01)
        assert not result["ok"]
        assert scope.project_for(sent[0]["director_token"]) is None
    finally:
        broker.disconnect("laptop")


@pytest.mark.parametrize("path", ["/mcp/director", "/mcp/director/", "/mcp/director/anything",
                                  "/mcp//director", "/mcp%2fdirector", "/mcp/director/../"])
def test_scoped_endpoint_needs_its_token_even_on_the_home_network(scoped, path):
    scope, token = scoped
    from vt.server import serve

    request = {"path": path, "method": "POST", "client": ("192.168.1.2", 1234), "headers": []}
    assert not serve.allowed(request)
    request["headers"] = [(scope.HEADER.encode(), token.encode())]
    assert serve.allowed(request)
    scope.revoke(token)
    assert not serve.allowed(request)
    request["path"] = "/mcp"
    request["headers"] = []
    assert not serve.allowed(request), "another computer needs the key, even on the person's network"
    serve.STATE["trust_network"] = True
    try:
        assert serve.allowed(request), "...unless the person turned on trust for their network"
    finally:
        serve.STATE["trust_network"] = False


def test_dedicated_request_without_validated_scope_marker_is_refused(scoped):
    scope, token = scoped
    called = []
    async def call(_ctx):
        called.append(True)
    ctx = SimpleNamespace(request=SimpleNamespace(headers={scope.HEADER: token},
                                                  scope={"path": "/mcp/director"}))
    with pytest.raises(MCPError, match="project"):
        asyncio.run(scope.middleware(ctx, call))
    assert called == []


def test_real_mcp_protocol_keeps_scope_on_every_message(ref, monkeypatch):
    """Real SDK transport in process, with a synthetic director and no listening server."""
    from starlette.testclient import TestClient
    from mcp.server.transport_security import TransportSecuritySettings
    from vt.mcp import scope, server
    from vt.server import serve

    token = scope.issue(ref.id)
    inner = server.server.streamable_http_app(transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    monkeypatch.setitem(serve._mcp, "app", inner)
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
               "X-VT-Director-Token": token}
    try:
        with TestClient(serve.Guard(serve._MCPEndpoint())) as client:
            def post(message, extra=None):
                return client.post("/mcp/director", json=message, headers={**headers, **(extra or {})})
            response = post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                        "clientInfo": {"name": "fake-director", "version": "1"}}})
            assert response.status_code == 200
            headers["Mcp-Session-Id"] = response.headers["mcp-session-id"]
            assert post({"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
            own = post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": "get_transcript", "arguments": {"project": ref.id}}})
            assert own.status_code == 200 and "w1" in own.text
            other = post({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                          "params": {"name": "get_transcript", "arguments": {"project": "other"}}})
            assert "own project's tools" in other.text and "w1" not in other.text
            module = post({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                           "params": {"name": "module_call", "arguments": {"project_id": "other", "module_id": "craft.rules"}}})
            assert "own project's tools" in module.text
            listed = post({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                           "params": {"name": "list_projects", "arguments": {}}})
            payload = json.loads(next(line[6:] for line in listed.text.splitlines() if line.startswith("data: ")))
            assert ref.id in json.dumps(payload)
            scope.revoke(token)
            assert post({"jsonrpc": "2.0", "id": 6, "method": "tools/list"}).status_code == 401
    finally:
        scope.revoke(token)
