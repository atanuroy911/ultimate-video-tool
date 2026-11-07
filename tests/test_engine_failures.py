"""F3: real provider/fallback code, fake HTTP only; no model, renderer or GPU."""
import httpx
import pytest

from vt.ai import AIUnavailable
from vt.ai import providers as P

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


@pytest.mark.parametrize("provider", ["local", "openai", "claude"])
@pytest.mark.parametrize("failure,phrase", [
    ("down", "not reachable"), ("timeout", "took too long"),
    (401, "saved key"), (403, "account access"), (404, "model"),
    (429, "usage limit"), (503, "temporarily unavailable"), ("bad_json", "unreadable answer"),
])
def test_provider_failures_explain_the_next_action_without_raw_requests(monkeypatch, provider, failure, phrase):
    from vt import llm

    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "auto", "ollama_url": "http://fake.test"})
    monkeypatch.setattr(llm, "make_room", lambda *a: False)
    request = httpx.Request("POST", "http://fake.test/chat?token=private-credential")

    def post(*args, **kwargs):
        if failure == "down":
            raise httpx.ConnectError("private-credential refused", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private-credential timeout", request=request)
        if failure == "bad_json":
            return httpx.Response(200, text="not JSON", request=request)
        return httpx.Response(failure, json={"error": "private-credential"}, request=request)

    monkeypatch.setattr(P.httpx, "post", post)
    model = {"local": lambda: P.OllamaProvider("fake-model"),
             "openai": lambda: P.OpenAIProvider("http://fake.test/v1", "private-credential", "fake-model"),
             "claude": lambda: P.AnthropicProvider("private-credential", "fake-model")}[provider]()
    with pytest.raises(AIUnavailable) as error:
        model.complete("rules", "source", SCHEMA, [], 100, .1, .2)
    message = str(error.value)
    assert phrase in message
    assert "private-credential" not in message and "HTTPStatusError" not in message
    assert any(word in message.lower() for word in ("check", "choose", "try again", "wait"))


def test_direct_local_chat_uses_the_same_timeout_message(monkeypatch):
    from vt import llm

    monkeypatch.setattr(llm, "settings", lambda: {"ollama_url": "http://fake.test"})
    monkeypatch.setattr(llm, "make_room", lambda *a: False)
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.ReadTimeout("private-credential")))
    with pytest.raises(llm.LLMUnavailable, match="took too long"):
        llm.chat_json([{"role": "user", "content": "source"}], SCHEMA, model="fake-model")


@pytest.mark.parametrize("problem", ["not reachable", "refused the connection", "could not find the selected model", "took too long to answer"])
def test_script_keeps_a_valid_rule_plan_when_ai_fails(ref, monkeypatch, problem):
    from vt import ai
    from vt.script import service
    from vt.schema import validate_scenes
    from vt.planner.catalogue import all_icon_names

    provider = P.FakeProvider([AIUnavailable(f"The local AI {problem}. Try again or choose another director.")])
    monkeypatch.setattr(ai, "provider_status", lambda: {"available": True})
    with ai.use_provider(provider):
        scenes, how = service.direct(ref, ref.scenes(), want_ai=True)
    assert how.startswith("rules") and problem in how
    assert scenes.scenes and not validate_scenes(scenes, ref.transcript(), ref.beats(), all_icon_names())


@pytest.mark.parametrize("failure", ["down", "timeout"])
def test_comfy_failure_has_a_recoverable_status_without_touching_any_service(monkeypatch, failure):
    from vt.comfy import ComfyClient

    client = ComfyClient("http://fake.test")
    def request(*a, **k):
        raise (httpx.ReadTimeout("timeout") if failure == "timeout" else httpx.ConnectError("down"))
    monkeypatch.setattr(client._http, "request", request)
    try:
        status = client.status()
        assert status["ok"] is False
        assert ("not answer in time" if failure == "timeout" else "not reachable") in status["error"]
    finally:
        client.close()


def test_missing_local_model_does_not_download_without_authorization(monkeypatch):
    from vt import llm

    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "auto", "ollama_url": "http://fake.test", "llm_auto_download": False})
    monkeypatch.setattr(llm, "reachable", lambda *a: True)
    monkeypatch.setattr(llm, "has_model", lambda *a: False)
    monkeypatch.setattr(llm, "pull", lambda *a, **k: pytest.fail("unexpected download"))
    with pytest.raises(llm.LLMUnavailable, match="model 'fake-model' is not downloaded"):
        llm.ensure_ready(allow_download=False, model="fake-model")


@pytest.mark.parametrize("failure", ["down", "missing_model"])
def test_failed_generated_clip_preserves_the_existing_media_and_plan(ref, failure):
    from types import SimpleNamespace
    from vt.comfy import ComfyError, generate_clip
    from vt.comfy.generate import PROVENANCE

    before = {file: (ref.dir / file).read_bytes() for file in ("project.json", "scenes.json")}
    def object_info():
        if failure == "down":
            raise ComfyError("ComfyUI is not reachable. Check the connection.", kind="unreachable")
        return {}
    workflow = SimpleNamespace(label="Clip model", problems=lambda info: ["Model fake-model is not installed"])
    with pytest.raises(ComfyError, match="not reachable|not installed"):
        generate_clip(ref, SimpleNamespace(object_info=object_info), workflow, ref.dir / "not-needed.png", "A spoken fact")
    assert {file: (ref.dir / file).read_bytes() for file in before} == before
    assert not (ref.dir / PROVENANCE).exists()


def test_slow_comfy_run_stops_its_own_request_and_can_retry(monkeypatch):
    from vt.comfy import ComfyClient, ComfyError
    from vt.comfy import client as C

    client = ComfyClient("http://fake.test")
    stopped = []
    monkeypatch.setattr(client, "history", lambda pid: None)
    monkeypatch.setattr(client, "interrupt", stopped.append)
    clock = iter([0, 2])
    monkeypatch.setattr(C, "time", type("Clock", (), {"time": staticmethod(lambda: next(clock))}))
    try:
        with pytest.raises(ComfyError, match="not finished") as error:
            client.wait("our-request", timeout=1)
        assert error.value.kind == "timeout" and stopped == ["our-request"]
        monkeypatch.setattr(C, "time", type("Clock", (), {"time": staticmethod(lambda: 3)}))
        entry = {"status": {"completed": True}, "outputs": {"4": {}}}
        monkeypatch.setattr(client, "history", lambda pid: entry)
        assert client.wait("new-request", timeout=1) == entry
    finally:
        client.close()


def test_pipeline_finishes_its_plan_and_records_rule_fallback_when_the_engine_fails(ref, monkeypatch):
    from vt.pipeline import Pipeline
    from vt.script import service
    from vt.util import read_json
    from vt.visuals import picker

    service.set_script_kind(ref, "stick")
    ref.scenes_path.unlink()  # start a fresh temporary plan; manual plans are intentionally protected
    provider = P.FakeProvider([AIUnavailable("The local AI took too long to answer. Try again or choose another director.")])
    monkeypatch.setattr(Pipeline, "director", lambda self: "local")
    monkeypatch.setattr(Pipeline, "_director_provider", lambda *a: provider)
    monkeypatch.setattr(picker, "pick_visuals", lambda *a, **k: {})
    Pipeline(ref).stage_plan(force=True)
    assert ref.scenes().scenes
    assert "plan" in ref.meta().stages
    assert ref.meta().director["who"] == "rules"
    assert "took too long" in read_json(ref.dir / "ai_notice.json")["message"]
