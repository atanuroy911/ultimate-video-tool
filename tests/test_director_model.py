"""Plan step B8: the person chooses which Claude directs (decision 3): Sonnet, faster, or Opus, slower and the most careful.

The choice is one setting. The Settings page and the `vt directors --model` command save it, the server sends it with every task for Claude on the person's computer, and the helper starts that model
(client/desktop/test-director-runner.js reads the model Claude reports in its own `init` line; docs/evidence/perfect/B8-claude-model.md has a real run for each choice)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from test_one_director import Laptop, _no_computer_left_connected  # noqa: F401  (the autouse fixture comes along)


@pytest.fixture()
def client():
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_the_default_is_sonnet_and_the_page_can_read_it(client):
    from vt import directors

    assert directors.settings()["director_model"] == "sonnet"
    assert client.get("/api/directors").json()["director_model"] == "sonnet"


@pytest.mark.parametrize("choice", ["sonnet", "opus"])
def test_the_settings_page_saves_the_choice(client, choice):
    from vt import directors

    r = client.put("/api/settings", json={"director_model": choice})
    assert r.status_code == 200 and r.json()["director_model"] == choice
    assert client.get("/api/settings").json()["director_model"] == choice
    assert directors.settings()["director_model"] == choice and client.get("/api/directors").json()["director_model"] == choice


def test_nothing_but_a_model_name_is_saved(client):
    for bad in ("--dangerously-skip-permissions", "opus; rm -rf /", "a b", ""):
        assert client.put("/api/settings", json={"director_model": bad}).json()["director_model"] == "sonnet", bad
    assert client.put("/api/settings", json={"director_model": "claude-opus-5-5"}).json()["director_model"] == "claude-opus-5-5", "a full model name is fine"


@pytest.mark.parametrize("choice", ["sonnet", "opus"])
def test_every_task_for_claude_carries_the_choice(client, choice):
    from vt import directors
    from vt.ai import providers as AIP

    client.put("/api/settings", json={"director_model": choice})
    laptop = Laptop(directors)
    AIP.ClientProvider("claude@laptop").complete("s", "q", {"type": "object"}, [], 100, 30, 0.2)
    directors.broker.request("laptop", "reference", "Direct it", 1.0)
    assert [m["model"] for m in laptop.sent if m["type"] in ("ask", "direct")] == [choice, choice]


def test_a_change_takes_effect_for_the_next_task_without_a_restart(client):
    from vt import directors

    laptop = Laptop(directors)
    directors.broker.request("laptop", "reference", "one", 1.0)
    client.put("/api/settings", json={"director_model": "opus"})
    directors.broker.request("laptop", "reference", "two", 1.0)
    assert [m["model"] for m in laptop.sent if m["type"] == "direct"] == ["sonnet", "opus"]


def test_the_command_line_chooses_it_too():
    from vt import directors
    from vt.cli import app

    runner = CliRunner()
    shown = runner.invoke(app, ["directors"])
    assert shown.exit_code == 0 and "Claude will direct" not in shown.output
    chosen = runner.invoke(app, ["directors", "--model", "opus"])
    assert chosen.exit_code == 0 and "Claude will direct with opus from the next video." in chosen.output
    assert directors.settings()["director_model"] == "opus"
    back = runner.invoke(app, ["directors", "--model", "sonnet"])
    assert "with sonnet" in back.output and directors.settings()["director_model"] == "sonnet"
    odd = runner.invoke(app, ["directors", "--model", "not a model!"])
    assert "with sonnet" in odd.output and directors.settings()["director_model"] == "sonnet", "free text becomes the default"
