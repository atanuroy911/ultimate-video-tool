"""Claude through the logged-in Claude Code program: the command is exactly as designed (no tools, empty folder, schema, model), every failure is a readable AIUnavailable, answers are cached,
the daily cap stops a runaway, and nothing of the account is kept. The real call is marked slow."""
import json
import subprocess
from pathlib import Path

import pytest

from vt import paths
from vt.ai import providers as P

SCHEMA = {"type": "object", "properties": {"greeting": {"type": "string"}, "n": {"type": "integer"}}, "required": ["greeting", "n"]}


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA", tmp_path)
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    monkeypatch.setattr(P, "find_claude", lambda: "C:/fake/claude.exe")
    monkeypatch.setitem(P._login_cache, "v", {"found": True, "logged_in": True, "plan": "pro", "method": "claude.ai", "reason": ""})
    monkeypatch.setitem(P._login_cache, "t", 1e18)
    calls = []

    def fake_run(cmd, **kw):
        calls.append({"cmd": cmd, **kw})
        out = {"is_error": False, "result": '{"greeting":"hello","n":3}', "structured_output": {"greeting": "hello", "n": 3}, "total_cost_usd": 0.02}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(out), "")
    monkeypatch.setattr(P.subprocess, "run", fake_run)
    return calls


def test_the_command_has_no_tools_an_empty_folder_the_schema_and_the_model(cli):
    p = P.ClaudeCLIProvider("opus")
    out = p.complete("be brief", "say hello", SCHEMA, [], 1000, 60, 0.2)
    assert json.loads(out) == {"greeting": "hello", "n": 3}
    c = cli[0]
    cmd = c["cmd"]
    assert cmd[0] == "C:/fake/claude.exe" and "-p" in cmd and cmd[cmd.index("--tools") + 1] == "" and "--strict-mcp-config" in cmd and "--disable-slash-commands" in cmd
    assert cmd[cmd.index("--model") + 1] == "opus" and cmd[cmd.index("--output-format") + 1] == "json" and "--no-session-persistence" in cmd
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == SCHEMA
    assert c["input"] == "say hello"                                                   # the prompt goes in through stdin, never the command line
    assert Path(c["cwd"]).name.startswith("vt_claude_") and not Path(c["cwd"]).exists()          # an empty temp folder, removed afterwards
    assert "ANTHROPIC_API_KEY" not in c["env"]


def test_a_big_schema_goes_into_the_prompt_not_the_command_line(cli):
    big = {"type": "object", "properties": {f"k{i}": {"type": "string", "description": "x" * 40} for i in range(200)}}
    P.ClaudeCLIProvider().complete("", "go", big, [], 1000, 60, 0.2)
    c = cli[0]
    assert "--json-schema" not in c["cmd"] and "JSON Schema" in c["input"] and '"k199"' in c["input"]


def test_an_api_key_in_the_environment_is_not_passed_on(cli, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    P.ClaudeCLIProvider().complete("", "go", SCHEMA, [], 1000, 60, 0.2)
    assert "ANTHROPIC_API_KEY" not in cli[0]["env"]


def test_each_failure_is_a_readable_unavailable(cli, monkeypatch):
    p = P.ClaudeCLIProvider()

    def run_with(out, code=0, exc=None):
        def f(cmd, **kw):
            if exc:
                raise exc
            return subprocess.CompletedProcess(cmd, code, out, "boom")
        monkeypatch.setattr(P.subprocess, "run", f)
    run_with("not json at all", 1)
    with pytest.raises(P.AIUnavailable, match="no JSON answer"):
        p.complete("", "x", SCHEMA, [], 100, 5, 0.2)
    run_with(json.dumps({"is_error": True, "result": "rate limited"}))
    with pytest.raises(P.AIUnavailable, match="rate limited"):
        p.complete("", "x", SCHEMA, [], 100, 5, 0.2)
    run_with("", exc=subprocess.TimeoutExpired("claude", 5))
    with pytest.raises(P.AIUnavailable, match="did not answer within"):
        p.complete("", "x", SCHEMA, [], 100, 5, 0.2)
    run_with("", exc=FileNotFoundError())
    with pytest.raises(P.AIUnavailable, match="could not be started"):
        p.complete("", "x", SCHEMA, [], 100, 5, 0.2)
    fence = chr(96) * 3
    run_with(json.dumps({"is_error": False, "result": fence + 'json\n{"greeting":"hi","n":1}\n' + fence}))        # no structured_output: the text answer is parsed by the caller
    assert P.parse_json(p.complete("", "x", SCHEMA, [], 100, 5, 0.2)) == {"greeting": "hi", "n": 1}


def test_logged_out_or_missing_says_exactly_what_to_do(cli, monkeypatch):
    monkeypatch.setitem(P._login_cache, "v", {"found": True, "logged_in": False, "plan": "", "method": "", "reason": "Claude Code is not logged in. Run `claude auth login` in a terminal once."})
    p = P.ClaudeCLIProvider()
    assert not p.available()
    with pytest.raises(P.AIUnavailable, match="claude auth login"):
        p.complete("", "x", SCHEMA, [], 100, 5, 0.2)
    monkeypatch.setitem(P._login_cache, "v", {"found": False, "logged_in": False, "plan": "", "method": "", "reason": "Claude Code is not installed. Install it ..."})
    with pytest.raises(P.AIUnavailable, match="not installed"):
        p.complete("", "x", SCHEMA, [], 100, 5, 0.2)


def test_usage_is_counted_the_cap_stops_a_runaway_and_complete_json_caches(cli, tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"claude_cli_daily_cap": 2}), encoding="utf-8")
    p = P.ClaudeCLIProvider()
    a = P.complete_json("question one", SCHEMA, provider=p)
    b = P.complete_json("question one", SCHEMA, provider=p)                                 # the same question is answered from the cache
    assert a == b == {"greeting": "hello", "n": 3} and len(cli) == 1
    P.complete_json("question two", SCHEMA, provider=p)
    u = P.usage_today()
    assert u["calls"] == 2 and abs(u["cost_usd"] - 0.04) < 1e-6
    with pytest.raises(P.AIUnavailable, match="daily limit of 2"):
        P.complete_json("question three", SCHEMA, provider=p)
    assert "@" not in (tmp_path / "claude_usage.json").read_text(encoding="utf-8")            # nothing of the account is kept


def test_the_provider_choices(cli, tmp_path, monkeypatch):
    sf = tmp_path / "settings.json"
    sf.write_text(json.dumps({"ai_provider": "claude_cli"}), encoding="utf-8")
    assert P.current_provider().name == "claude-cli"
    sf.write_text(json.dumps({"ai_provider": "best"}), encoding="utf-8")
    assert P.current_provider().name == "claude-cli"                                          # logged in: Claude
    monkeypatch.setitem(P._login_cache, "v", {"found": True, "logged_in": False, "plan": "", "method": "", "reason": "x"})
    assert P.current_provider().name == "ollama"                                              # not logged in: the local model
    sf.write_text(json.dumps({"ai_provider": "claude_cli"}), encoding="utf-8")
    assert P.vision_provider().name == "ollama"                                               # pictures always go to the local vision model


@pytest.mark.assistant
@pytest.mark.slow
def test_a_real_call_through_the_logged_in_claude_code(tmp_path, monkeypatch):
    """Uses the real program and the real login on this machine; skipped when Claude Code is missing or logged out."""
    import time

    monkeypatch.setattr(paths, "DATA", tmp_path)
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    P._login_cache.update(t=0.0, v=None)
    if not P.login_status(force=True)["logged_in"]:
        pytest.skip("Claude Code is not installed or not logged in")
    t0 = time.time()
    out = P.complete_json("Give a greeting word and the number 3.", SCHEMA, provider=P.ClaudeCLIProvider(), cache=False, timeout=180)
    assert isinstance(out["greeting"], str) and out["n"] == 3
    u = P.usage_today()
    print(f"real Claude call: {time.time() - t0:.1f} s, {u['calls']} call, about ${u['cost_usd']} of list price")
    assert u["calls"] == 1


def test_the_status_endpoint_reports_claude_without_any_account_detail(cli, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from vt.server import app as A

    monkeypatch.setattr(A, "SETTINGS_PATH", tmp_path / "settings.json")
    c = TestClient(A.app)
    st = c.get("/api/ai/status").json()["claude"]
    assert st == {"found": True, "logged_in": True, "plan": "pro", "reason": "", "model": "sonnet", "daily_cap": 200, "calls_today": 0, "cost_usd_today": 0.0}
    assert "@" not in json.dumps(c.get("/api/ai/status").json())
    c.put("/api/settings", json={"ai_provider": "best", "claude_cli_model": "opus", "claude_cli_daily_cap": 50})
    st = c.get("/api/ai/status").json()
    assert st["settings"]["ai_provider"] == "best" and st["claude"]["model"] == "opus" and st["claude"]["daily_cap"] == 50 and st["provider"] == "claude-cli"
