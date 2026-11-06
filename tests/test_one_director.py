"""One video has one director: no other model mixes into its direction, and the person can read every prompt and answer."""
import time

import pytest


@pytest.fixture(autouse=True)
def _no_computer_left_connected():
    """The broker is one per process: a stand-in computer must not stay connected for the next test."""
    yield
    from vt import directors

    for d in directors.broker.devices():
        directors.broker.disconnect(d.device_id)
    for run in list(directors.broker._runs.values()):             # a task still waiting would be sent to the next test's computer
        run.result = {"ok": False, "reason": "the test ended"}
        run.event.set()
    directors.broker._runs.clear()


def _no_plan(p):
    (p.dir / "scenes.json").unlink(missing_ok=True)


def _example(schema):
    """The smallest answer that satisfies a JSON Schema: what a stand-in assistant says when it only has to be valid."""
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    for key in ("anyOf", "oneOf"):
        if key in schema:
            return _example(schema[key][0])
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), kind[0])
    if kind == "object" or "properties" in schema:
        props = schema.get("properties", {})
        return {k: _example(props.get(k, {})) for k in schema.get("required", [])}
    if kind == "array":
        return []
    if kind == "string":
        return "x" * int(schema.get("minLength", 1))
    if kind == "integer":
        return int(schema.get("minimum", 0))
    if kind == "number":
        return float(schema.get("minimum", 0))
    if kind == "boolean":
        return True
    return None


class Laptop:
    """A stand-in for the helper on a person's computer (client/desktop/helper.js): the server hands it tasks and it answers them the same way."""

    def __init__(self, directors, device="laptop", assistant="claude", plan=None, answer=None, silent=False, name="Laptop"):
        self.broker, self.device, self.assistant, self.plan, self.silent = directors.broker, device, assistant, plan, silent
        self.sent = []
        self.answer = answer or (lambda system, prompt, schema, images: _example(schema))
        self.channel = self.send                                   # one object for the whole connection: the broker tells connections apart by identity
        self.broker.connect(device, name, version="2.1", logged_in=True, send=self.channel, assistant=assistant)

    def send(self, message):
        import base64
        import json

        self.sent.append(message)
        if self.silent or message["type"] == "cancel":
            return
        if message["type"] == "ask":
            data = self.answer(message["system"], message["prompt"], message["schema"], [base64.b64decode(i) for i in message["images"]])
            if isinstance(data, Exception):
                self.broker.finish(message["request"], ok=False, error=str(data), detail={"text": "", "error_kind": getattr(data, "kind", "other")}, device_id=self.device)
            else:
                self.broker.finish(message["request"], ok=True, detail={"text": json.dumps(data), "error_kind": "", "models": ["claude-sonnet-5-5"]}, device_id=self.device)
        elif message["type"] == "direct":
            if self.plan:
                self.plan(message)
            self.broker.finish(message["request"], ok=True, device_id=self.device)


def _watch_the_other_minds(monkeypatch):
    """Anything that reaches the local AI or the server's Claude for a video a computer directs is recorded here."""
    from vt import llm
    from vt.ai import providers as AIP

    used = []

    def asked(name):
        def inner(*a, **k):
            used.append(name)
            raise AIP.AIUnavailable(name + " was asked")
        return inner

    monkeypatch.setattr(AIP.OllamaProvider, "complete", asked("the local AI"))
    monkeypatch.setattr(AIP.ClaudeCLIProvider, "complete", asked("Claude on the server"))
    monkeypatch.setattr(llm, "chat_json", asked("llm.chat_json"))
    return used


def _choose(ref, director):
    meta = ref.meta()
    meta.options.director = director
    ref.save_meta(meta)


def test_claude_on_the_laptop_directs_alone(ref, monkeypatch):
    from vt import directors
    from vt.ai import providers as AIP
    from vt.director import heartbeat
    from vt.pipeline import Pipeline
    from vt.planner import llm_plan
    from vt.script import service

    _no_plan(ref)
    used = _watch_the_other_minds(monkeypatch)
    monkeypatch.setattr(llm_plan, "plan_llm", lambda *a, **k: used.append("local picture planner"))
    monkeypatch.setattr(service, "direct", lambda *a, **k: used.append("server script"))
    monkeypatch.setattr(heartbeat, "add_heartbeats", lambda *a, **k: used.append("heartbeats"))
    _choose(ref, "claude@laptop")
    laptop = Laptop(directors, plan=lambda m: ref.save_scenes(ref.scenes().model_copy(update={"planner": "claude"})))
    pl = Pipeline(ref)
    assert pl.director() == "claude@laptop"
    provider = pl._director_provider(pl.director())
    assert isinstance(provider, AIP.ClientProvider) and provider.available() and not hasattr(AIP, "NoProvider")
    with AIP.use_provider(provider):
        assert AIP.ai_enabled(), "understanding the video and directing the voice go to the same director"
        schema = {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}
        assert AIP.complete_json("What is this about?", schema, cache=False) == {"topic": "x"}
    ask = laptop.sent[0]
    assert ask["type"] == "ask" and ask["assistant"] == "claude" and ask["model"] == "sonnet" and ask["prompt"] == "What is this about?" and ask["schema"] == schema
    pl.stage_plan(force=True)
    assert used == [] and ref.scenes().planner == "claude"
    assert [m["type"] for m in laptop.sent] == ["ask", "direct"] and laptop.sent[1]["model"] == "sonnet"
    assert ref.meta().director["who"] == "claude@laptop"


def test_every_ai_step_of_a_video_a_computer_directs_goes_to_that_computer(ref, monkeypatch, tmp_path):
    from PIL import Image

    from vt import directors
    from vt.ai import publish, talk
    from vt.mcp import server as M
    from vt.pipeline import Pipeline, directing
    from vt.render import hyperframes

    used = _watch_the_other_minds(monkeypatch)
    shot = tmp_path / "f.png"
    Image.new("RGB", (90, 160)).save(shot)
    monkeypatch.setattr(hyperframes, "snapshot", lambda comp, out, times, gpu=True: [shot for _ in times])
    monkeypatch.setattr(hyperframes, "frame_facts", lambda comp, times: {})
    _no_plan(ref)
    _choose(ref, "claude@laptop")

    def the_director_works(message):
        M.project_status(ref.id)                                   # a tool it calls during its planning session
        ref.save_scenes(ref.scenes().model_copy(update={"planner": "claude"}))

    laptop = Laptop(directors, plan=the_director_works)
    pl = Pipeline(ref)
    with directing(ref):                                           # what Pipeline.run and every later job on the video do
        pl.stage_context(force=True)                               # understanding the video
        pl.stage_plan(force=True)                                  # planning
        pl.stage_compose(force=True)                               # the last look at every scene
        publish.build_kit(ref, cover=False)                        # the title
    kinds = [m["type"] for m in laptop.sent]
    assert kinds.count("direct") == 1 and kinds.count("ask") >= 3, kinds
    assert any(m["type"] == "ask" and m["images"] for m in laptop.sent), "the last look sent the frames"
    assert any("title" in m["prompt"].lower() or "hashtag" in m["prompt"].lower() for m in laptop.sent if m["type"] == "ask"), "the title was asked of it too"
    assert used == [], f"another mind was asked: {used}"
    rows = talk.load(ref.dir)
    assert {r["who"] for r in rows} == {"claude-pc"}, "one director on the record: " + str(sorted({r["who"] for r in rows}))
    assert {r["model"] for r in rows if r["kind"] == "ask"} == {"sonnet"}
    assert any(r["kind"] == "tool" for r in rows), "the tool it called is on the record under the same name"
    assert {"context", "compose"} <= {r["stage"] for r in rows if r["kind"] == "ask"}


def test_a_computer_that_cannot_answer_says_why_in_plain_words(monkeypatch):
    from vt import directors
    from vt.ai import providers as AIP

    def says(**r):
        monkeypatch.setattr(directors.broker, "ask", lambda *a, **k: {"ok": False, **r})
        with pytest.raises(AIP.AIUnavailable) as e:
            AIP.ClientProvider("claude@pc").complete("", "q", {}, [], 100, 30, 0.2)
        return str(e.value)

    assert "usage limit was reached" in says(error_kind="limit", error="x")
    assert "not signed in" in says(error_kind="login", error="x")
    assert "did not answer within 30 s" in says(timeout=True, reason="slow")
    assert says(error_kind="other", error="Claude Code gave no JSON answer (exit 1)") == "Claude Code gave no JSON answer (exit 1)"
    monkeypatch.setattr(directors.broker, "ask", lambda *a, **k: {"ok": False, "error_kind": "limit"})
    with pytest.raises(AIP.AIUnavailable) as e:
        AIP.ClientProvider("codex@pc").complete("", "q", {}, [], 100, 30, 0.2)
    assert str(e.value).startswith("Codex's usage limit")
    gone = AIP.ClientProvider("claude@nobody")
    assert not gone.available() and "not connected" in gone.why_not()
    with AIP.use_provider(gone):
        with pytest.raises(AIP.AIUnavailable, match="not connected"):
            AIP.ensure_ai()


def test_the_model_claude_runs_is_a_setting_and_travels_with_every_task(ref, monkeypatch):
    from vt import directors
    from vt.ai import providers as AIP

    assert directors.settings()["director_model"] == "sonnet" and directors.listing()["director_model"] == "sonnet"
    laptop = Laptop(directors)
    AIP.ClientProvider("claude@laptop").complete("s", "q", {"type": "object"}, [], 100, 30, 0.2)
    directors.broker.request("laptop", ref.id, "Direct it", 1.0)
    assert [m["model"] for m in laptop.sent if m["type"] in ("ask", "direct")] == ["sonnet", "sonnet"]
    assert directors.save_settings(model="opus")["director_model"] == "opus"
    AIP.ClientProvider("claude@laptop").complete("s", "q", {"type": "object"}, [], 100, 30, 0.2)
    directors.broker.request("laptop", ref.id, "Direct it", 1.0)
    assert [m["model"] for m in laptop.sent if m["type"] in ("ask", "direct")][2:] == ["opus", "opus"]
    assert AIP.ClientProvider("claude@laptop").model() == "opus"
    assert directors.save_settings(model="opus; calc")["director_model"] == "sonnet", "only letters, digits, dots and dashes are kept"
    assert directors.model_name("claude-sonnet-5-5") == "claude-sonnet-5-5" and directors.model_name("") == "sonnet"


def test_a_task_the_server_gives_up_on_is_cancelled_on_that_computer(ref, monkeypatch):
    from vt import directors

    monkeypatch.setattr(directors, "ASK_EXTRA_WAIT", 0)
    laptop = Laptop(directors, silent=True)
    r = directors.broker.ask("laptop", "claude", system="", prompt="q", schema={}, images=[], model="sonnet", timeout=0.05)
    assert r["ok"] is False and r["timeout"] is True
    d = directors.broker.request("laptop", ref.id, "Direct it", 0.05)
    assert d["ok"] is False and d["timeout"] is True
    sent = [m for m in laptop.sent if m["type"] in ("ask", "direct")]
    assert [m["request"] for m in laptop.sent if m["type"] == "cancel"] == [m["request"] for m in sent], "each abandoned task is cancelled by its request id"


def test_the_tools_a_director_calls_are_recorded_under_the_name_of_that_director(ref):
    from vt import directors

    assert directors.broker.who_directing(ref.id) == ""
    seen = []
    laptop = Laptop(directors, assistant="codex", device="desk", plan=lambda m: seen.append(directors.broker.who_directing(ref.id)))
    directors.broker.request("desk", ref.id, "Direct it", 1.0, assistant="codex")
    assert seen == ["codex-pc"] and directors.broker.who_directing(ref.id) == "" and laptop.sent[0]["assistant"] == "codex"


def test_a_job_on_a_video_asks_that_videos_director_and_is_written_on_its_record(ref):
    import threading

    from vt import directors
    from vt.ai import providers as AIP, talk
    from vt.server.jobs import JobManager

    _choose(ref, "claude@laptop")
    Laptop(directors)
    jobs, seen, done = JobManager(lambda m: None), {}, threading.Event()

    def work(cb):
        seen["provider"] = AIP.current_provider()
        seen["answer"] = AIP.complete_json("Which?", {"type": "object", "properties": {"pick": {"type": "string"}}, "required": ["pick"]}, cache=False)
        done.set()

    jobs.submit("qa", ref.id, "Check the frames", work)
    assert done.wait(10)
    assert isinstance(seen["provider"], AIP.ClientProvider) and seen["answer"] == {"pick": "x"}
    assert [r["who"] for r in talk.load(ref.dir)] == ["claude-pc"], "the manual check is on the video's record, under its director"
    other = threading.Event()
    jobs.submit("thumbs", ref.id, "Thumbnails", lambda cb: (seen.update(thumbs=bool(AIP._override)), other.set()))
    assert other.wait(10) and seen["thumbs"] is False, "a job that asks no AI is left alone"


def test_a_question_travels_the_socket_and_its_answer_comes_back_from_the_right_device():
    import base64
    import threading

    from fastapi.testclient import TestClient

    from vt import directors
    from vt.server.app import app

    result = {}
    with TestClient(app, client=("127.0.0.1", 50000)) as client, client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"type": "director", "director": "claude", "device_name": "Laptop", "version": "2.1", "logged_in": True})
        for _ in range(100):
            if directors.broker.ready("local-app"):
                break
            time.sleep(0.05)
        assert directors.broker.ready("local-app")
        asker = threading.Thread(target=lambda: result.update(directors.broker.ask("local-app", "claude", system="Be brief.", prompt="Which?", schema={"type": "object"}, images=[b"png"], model="sonnet", timeout=10)))
        asker.start()
        message = ws.receive_json()
        while message["type"] != "ask":                              # other events (the director list changed) may come first
            message = ws.receive_json()
        assert message["images"] == [base64.b64encode(b"png").decode()] and message["model"] == "sonnet" and message["system"] == "Be brief."
        assert directors.broker.finish(message["request"], ok=True, device_id="somebody-else") is False, "another device cannot answer for it"
        ws.send_json({"type": "ask_done", "request": message["request"], "ok": True, "text": "{\"pick\": 1}", "models": ["claude-sonnet-5-5"], "error_kind": ""})
        asker.join(10)
        directors.broker.disconnect("local-app")
    assert result["ok"] is True and result["text"] == '{"pick": 1}' and result["models"] == ["claude-sonnet-5-5"]


def test_claude_on_the_server_really_directs_an_explainer_or_says_it_did_not(ref, monkeypatch):
    from vt import directors
    from vt.pipeline import Pipeline
    from vt.script import service

    _no_plan(ref)
    asked = {}

    def direct(p, sf, say=None, want_ai=False):
        asked["want_ai"] = want_ai
        return sf, "rules (Claude is not logged in)"

    monkeypatch.setattr(service, "direct", direct)
    monkeypatch.setattr(directors, "listing", lambda: {"directors": [{"id": "claude-server", "kind": "claude-server", "label": "Claude", "available": True}]})
    monkeypatch.setattr(directors, "candidates", lambda choice: ["claude-server"])
    recorded = {}
    monkeypatch.setattr(directors, "record", lambda p, who, **k: recorded.update(who=who))
    Pipeline(ref).stage_plan(force=True)
    assert asked["want_ai"] is True and recorded["who"] == "rules", "a plan the rules wrote is never credited to Claude"


def test_every_prompt_and_answer_is_kept_for_the_video(tmp_path):
    from vt.ai import providers as AIP, talk

    with talk.for_project(tmp_path), AIP.use_provider(AIP.FakeProvider([{"a": 1}])):
        talk.set_stage("plan")
        AIP.complete_json("what should scene one show?", {"type": "object"}, system="you direct", cache=False)
    rows = talk.load(tmp_path)
    assert len(rows) == 1 and rows[0]["stage"] == "plan" and rows[0]["system"] == "you direct"
    assert "scene one" in rows[0]["prompt"] and '"a"' in rows[0]["answer"] and rows[0]["who"] == "fake"
    talk.record("x", "", prompt="not in a project")                  # nothing to write to: it stays quiet
    (tmp_path / talk.FILE).write_text("broken line\n", encoding="utf-8")
    assert talk.load(tmp_path) == []


def test_a_stage_moves_while_it_waits_and_never_goes_backward(ref):
    from vt.pipeline import Pipeline

    seen = []
    pl = Pipeline(ref, progress=lambda s, f, m: seen.append((s, f)))
    pl._say("plan", 0.95, "5 of 16")
    pl._say("plan", 0.90, "next step")
    assert seen[-1] == ("plan", 0.95), "95 % never falls back to 90 %"
    pl._say("context", 0.0, "reading")
    assert seen[-1] == ("context", 0.0), "the next stage starts from zero"
    import threading

    stop = threading.Event()
    threading.Thread(target=pl._tick_progress, args=(stop,), daemon=True).start()
    time.sleep(2.3)
    stop.set()
    moving = [f for s, f in seen if s == "context"]
    assert 0 < moving[-1] < 0.95 and moving == sorted(moving)


def test_the_studio_can_read_the_conversations(ref):
    from fastapi.testclient import TestClient

    from vt.ai import talk
    from vt.server.app import app

    talk.record("ollama", "qwen3", system="you direct", prompt="what now?", answer="a sticker", seconds=2, folder=ref.dir)
    talk.record("claude", "", kind="tool", prompt={"tool": "get_script_task", "arguments": {"project": ref.id}}, answer={"beats": []}, folder=ref.dir)
    with TestClient(app) as c:
        rows = c.get(f"/api/projects/{ref.id}/ai-talk").json()["rows"]
        assert [r["who"] for r in rows] == ["ollama", "claude"] and "prompt" not in rows[0] and rows[1]["preview"] == "get_script_task"
        full = c.get(f"/api/projects/{ref.id}/ai-talk/0").json()
        assert full["system"] == "you direct" and full["prompt"] == "what now?" and full["answer"] == "a sticker"
        assert c.get(f"/api/projects/{ref.id}/ai-talk/99").status_code == 404


def test_the_local_ai_always_has_room_for_the_prompt_and_the_whole_answer():
    from vt.ai.providers import MAX_CONTEXT, MIN_CONTEXT, context_for

    assert context_for(1000, 500) == MIN_CONTEXT
    big = context_for(40000, 8000)
    assert big >= 40000 / 2.5 + 8000 and big <= MAX_CONTEXT
    assert context_for(10_000_000, 8000) == MAX_CONTEXT


def test_elevenlabs_speaks_with_the_accounts_voices_and_says_why_it_refused(tmp_path, monkeypatch):
    import httpx

    from vt import paths, tts
    from vt.util import write_json

    tts._eleven_cache.clear()
    assert tts._elevenlabs_listing({"id": "elevenlabs", "voices": []})[1] is False
    with pytest.raises(tts.TTSError, match="API key"):
        tts._synth_elevenlabs("Hi.", "v1", 1.0, tmp_path / "o.wav")
    write_json(paths.SETTINGS, {"elevenlabs_key": "k"})
    sent = {}

    def fake_get(url, headers=None, timeout=0):
        assert headers["xi-api-key"] == "k"
        rows = {"voices": [{"voice_id": "v1", "name": "Ashwat", "labels": {"gender": "male", "accent": "indian"}}]} if url.endswith("/voices") else [
            {"model_id": "eleven_multilingual_v2", "can_do_text_to_speech": True, "languages": [{"language_id": "en"}]},
            {"model_id": "eleven_v3", "can_do_text_to_speech": True, "languages": [{"language_id": "en"}, {"language_id": "bn"}]}]
        return httpx.Response(200, json=rows, request=httpx.Request("GET", url))

    def fake_post(url, params=None, headers=None, json=None, timeout=0):
        sent.update(url=url, body=json)
        return httpx.Response(401, json={"detail": {"message": "invalid key"}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    e, ok, _ = tts._elevenlabs_listing({"id": "elevenlabs", "voices": []})
    assert ok and e["voices"] == [{"id": "v1", "label": "Ashwat (male, indian)", "lang": "multi"}]
    with pytest.raises(tts.TTSError, match="invalid key"):
        tts.synth_sentence("elevenlabs", "v1", "Bangla.", 1.5, tmp_path / "o.wav", language="bn")
    assert sent["url"].endswith("/text-to-speech/v1") and sent["body"]["model_id"] == "eleven_v3" and sent["body"]["language_code"] == "bn"
    assert sent["body"]["voice_settings"]["speed"] == 1.2, "ElevenLabs takes 0.7 to 1.2"


def test_auto_music_can_choose_a_track_from_the_library(tmp_path, monkeypatch):
    from vt import musicpick, paths
    from vt.util import write_json

    monkeypatch.setattr(paths, "USER_MUSIC", tmp_path)
    monkeypatch.setattr(paths, "MUSIC", tmp_path / "none")
    write_json(tmp_path / "bensound-a.mp3.credit.json", {"mood": "lofi", "attribution": "x"})
    assert musicpick.pick("story", "p1") == "user/bensound-a.mp3"


def test_the_director_sees_each_scene_and_what_it_decides_is_applied(ref, monkeypatch, tmp_path):
    from PIL import Image

    from vt import director_review as R
    from vt.ai import providers as AIP
    from vt.compose import FORMATS
    from vt.pipeline import compose_all
    from vt.render import hyperframes
    from vt.schema import Scene

    compose_all(ref)
    shot = tmp_path / "f.png"
    Image.new("RGB", (90, 160)).save(shot)
    monkeypatch.setattr(hyperframes, "snapshot", lambda comp, out, times, gpu=True: [shot for _ in times])
    first = ref.scenes().scenes[0]
    calls = []

    def director(system, prompt, schema, images):
        calls.append((prompt, len(images)))
        if len(calls) == 1:
            return {"people": ["Maya: a card covers her eyes"], "what_i_see": "the card covers her face", "looks_right": False, "changes": [{"element": 0, "set": {"x": 0.5, "y": 0.2, "scale": 0.8}}, {"element": 99, "set": {"x": 1}}]}
        return {"people": ["Maya: whole face visible"], "what_i_see": "clear", "looks_right": True, "changes": []}

    provider = AIP.FakeProvider(director)
    report = R.review(ref, provider=provider)
    moved = ref.scenes().scenes[0].elements[0]
    assert moved.x == 0.5 and moved.y == 0.2 and moved.scale == 0.8, "the director moved it"
    assert calls[0][1] == 1 and "element" in calls[0][0], "it saw the frame and the numbered elements"
    assert report["changed"] == 1 and "no element 99" in report["rounds"][0][0]["skipped"][0]
    assert report["rounds"][0][0]["saw"] == "the card covers her face"
    before = len(calls)
    assert R.review(ref, provider=provider)["changed"] == 1 and len(calls) == before, "the same plan is not looked at again"
    assert FORMATS and isinstance(first, Scene)
    same, skipped = R.apply_changes(first, [{"element": 0, "set": {"x": 7}}])
    assert same == first and skipped, "a value the plan cannot hold is refused and reported"


def test_claude_on_the_server_opens_the_frames_with_read(monkeypatch):
    from pathlib import Path

    from vt.ai.providers import ClaudeCLIProvider

    assert ClaudeCLIProvider.supports_images
    args, _ = ClaudeCLIProvider().command(Path("s.txt"), {"type": "object"}, "Read")
    assert args[args.index("--tools") + 1] == "Read"
    args, _ = ClaudeCLIProvider().command(Path("s.txt"), {"type": "object"})
    assert args[args.index("--tools") + 1] == ""


def test_a_cartoon_the_director_wrote_is_used_as_written():
    from types import SimpleNamespace

    from vt.schema import Beat, Beats, Scene, ScenesFile, Transcript, Word
    from vt.script.story_kit import apply_story_kit

    mine = {"type": "cartoon", "at_word": "w1", "set": "home", "framing": "scene", "cast": [{"who": "girl", "name": "Maya", "x": 0.3}]}
    default_actor = {"t0": 0, "t1": 1, "cast": [{"id": "n", "role": "teacher"}], "actions": [{"who": "n", "do": "wave", "start": 0, "end": 1}]}
    plan = ScenesFile(scenes=[Scene(id="s1", beats=["b1"], elements=[mine], stick=default_actor)])
    tr = Transcript(language="en", words=[Word(id="w1", text="Hi", start=0, end=1)])
    beats = Beats(beats=[Beat(id="b1", word_ids=["w1"], start=0, end=1, text="Hi")])
    out = apply_story_kit(plan, SimpleNamespace(kind="cartoon"), tr, beats, "classic").scenes[0]
    assert out.stick is None and len(out.elements) == 1
    assert out.elements[0].cast[0].who == "girl" and out.elements[0].set == "home" and out.elements[0].cast[0].name == "Maya"


def test_the_craft_check_runs_on_a_plan(ref):
    from vt import craft

    assert isinstance(craft.check(ref), dict)


def test_a_compound_number_is_one_number():
    from vt.planner.rules import _number_items
    from vt.schema import Word

    def nums(text):
        ws = [Word(id=f"w{i}", text=t, start=i, end=i + .5, lang="en") for i, t in enumerate(text.split())]
        return [(n["disp"], n["val"]) for n in _number_items(ws, "en")]

    assert nums("she counted two hundred and fifty dollars")[0][1] == 250
    assert nums("two hundred fifty five")[0][1] == 255
    assert nums("three thousand light years")[0][1] == 3000
    assert nums("two hundred, and fifty more")[0][1] == 200


def test_a_cast_member_may_be_placed_and_timed_and_captions_moved():
    from vt.schema import Cartoon, CastMember, SceneCaption

    m = CastMember(who="woman", x=.3, y=.7, arrive=0)
    assert m.arrive == 0 and m.y == .7
    assert Cartoon(cast=[m], at_word="w1").cast[0].arrive == 0
    assert SceneCaption(y=.5).y == .5


def test_edits_after_the_script_are_listed(ref):
    from vt.mcp.server import get_current_script
    from vt.script.service import SCRIPT_PLAN, edits_since_script
    from vt.util import write_json

    sf = ref.scenes()
    write_json(ref.dir / "video_script.json", {"kind": "explainer"})
    write_json(ref.dir / SCRIPT_PLAN, sf.model_dump(exclude_none=True))
    assert edits_since_script(ref) == []
    first = sf.scenes[0]
    ref.save_scenes(sf.model_copy(update={"scenes": [first.model_copy(update={"layout": "split" if first.layout != "split" else "hero"}), *sf.scenes[1:]]}))
    assert [(e["scene"], e["change"]) for e in edits_since_script(ref)] == [(first.id, "edited")]
    assert get_current_script(ref.id)["edits_since_this_script"][0]["scene"] == first.id


def test_measured_facts_reach_the_director():
    from vt.director_review import _scene_prompt
    from vt.schema import Scene

    text = _scene_prompt(Scene(id="s1", beats=["b1"]), "hello", ["element 1 (sticker) covers 80% of Maya's face."])
    assert "covers 80% of Maya's face" in text and "Measured on this exact frame" in text
    assert "Measured" not in _scene_prompt(Scene(id="s1", beats=["b1"]), "hello", [])


def test_a_scene_written_without_characters_gets_none():
    from types import SimpleNamespace

    from vt.schema import Beat, Beats, Scene, ScenesFile, Transcript, Word
    from vt.script.story_kit import apply_story_kit

    default_actor = {"t0": 0, "t1": 1, "cast": [{"id": "n", "role": "teacher"}], "actions": [{"who": "n", "do": "wave", "start": 0, "end": 1}]}
    plan = ScenesFile(scenes=[Scene(id="s1", beats=["b1"], elements=[{"type": "sticker", "at_word": "w1", "emoji": "1f4b0"}], stick=default_actor)])
    tr = Transcript(language="en", words=[Word(id="w1", text="Hi", start=0, end=1)])
    beats = Beats(beats=[Beat(id="b1", word_ids=["w1"], start=0, end=1, text="Hi")])
    script = SimpleNamespace(kind="cartoon", scenes=[SimpleNamespace(id="s1", actions=[])])
    out = apply_story_kit(plan, script, tr, beats, "classic").scenes[0]
    assert out.stick is None and [e.type for e in out.elements] == ["sticker"]


def test_one_refused_change_costs_only_its_own_scene(ref, monkeypatch):
    from pathlib import Path

    import vt.ai.providers as P
    import vt.director_review as R
    import vt.render.hyperframes as H

    sf = ref.scenes()
    ids = [s.id for s in sf.scenes][:2]
    first_time, second_time = 1.0, 2.0
    monkeypatch.setattr(R, "_frame_times", lambda comp, plan: [(ids[0], first_time), (ids[1], second_time)])
    monkeypatch.setattr(H, "snapshot", lambda *a, **k: [Path("a.png"), Path("b.png")])
    monkeypatch.setattr(H, "frame_facts", lambda *a, **k: {})
    monkeypatch.setattr(R, "_png", lambda f: b"x")
    answers = iter([
        {"people": [], "what_i_see": "", "looks_right": False, "changes": [{"element": 0, "set": {"opacity": .9}}]},
        {"people": [], "what_i_see": "", "looks_right": False, "changes": [{"element": 0, "set": {"at_word": "nope"}}]},
        {"people": [], "what_i_see": "", "looks_right": True, "changes": []},
        {"people": [], "what_i_see": "", "looks_right": True, "changes": []},
    ])
    monkeypatch.setattr(P, "complete_json", lambda *a, **k: next(answers))
    report = R.review(ref, compose=lambda p: None)
    assert report["changed"] == 1
    assert report["rounds"][0][1].get("refused")
    assert ref.scenes().scenes[0].elements[0].opacity == .9


def test_a_director_is_told_when_its_overlay_cannot_be_kept(ref):
    from vt.script import service
    from vt.script.prompt import overlay_catalogue_text

    words = list(ref.transcript().by_id())
    beats = ref.beats().beats
    script = {"kind": "cartoon", "scenes": [{"id": "s1", "beats": [b.id for b in beats],
                                             "overlays": [{"type": "cartoon", "at_word": words[0], "cast": [{"who": "girl", "pose": "idle"}]}]}]}
    res = service.apply_script(ref, script, strict=True)
    assert res["ok"] is False and any("pose" in e and "left out" in e for e in res["errors"])
    text = overlay_catalogue_text()
    assert "pose: stand" in text and "a mother or any other woman is woman" in text



def test_the_director_the_person_talks_to_in_the_plan_is_the_one_that_made_it():
    from vt import directors
    from vt.ai import providers as AIP
    from vt.direction import plan_doc as PD
    from vt.server import plan_routes

    answers = [{"ops": [{"op": "set_pace", "value": "calm"}]}, {"ops": [{"op": "not_an_operation"}]}, {"ops": [{"op": "not_an_operation"}]}]
    laptop = Laptop(directors, answer=lambda system, prompt, schema, images: answers.pop(0))
    plan = PD.PlanDoc()
    ops, why = plan_routes.ops_for(plan, "make it feel dreamier", AIP.ClientProvider("claude@laptop"))
    assert ops == [{"op": "set_pace", "value": "calm"}] and "director's suggestion" in why
    assert [m["type"] for m in laptop.sent] == ["ask"] and "make it feel dreamier" in laptop.sent[0]["prompt"]
    assert plan_routes.ops_for(plan, "something else entirely", AIP.ClientProvider("claude@laptop"))[0] == [], "an operation outside the vocabulary is refused"
    directors.broker.disconnect("laptop")
    before = len(laptop.sent)
    assert plan_routes.ops_for(plan, "and another thing", AIP.ClientProvider("claude@laptop"))[0] == [] and len(laptop.sent) == before, "a director that is not there asks nobody else"


def _ask_in_a_thread(directors, **extra):
    import threading

    result = {}
    thread = threading.Thread(target=lambda: result.update(directors.broker.ask("laptop", "claude", system="", prompt="q", schema={}, images=[], model="sonnet", timeout=extra.get("timeout", 20))))
    thread.start()
    return thread, result


def _wait_for(condition, what, seconds=5):
    end = time.time() + seconds
    while time.time() < end:
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("timed out waiting for " + what)


def test_a_short_drop_loses_nothing_the_task_goes_again_on_the_new_connection():
    from vt import directors

    first = Laptop(directors, silent=True)
    thread, result = _ask_in_a_thread(directors)
    _wait_for(lambda: first.sent, "the question to be sent")
    directors.broker.disconnect("laptop", first.channel)                          # the connection dies while it is being answered
    assert not directors.broker.ready("laptop") and thread.is_alive(), "the question waits"
    second = Laptop(directors, silent=True)                                    # the helper reconnects (a new socket)
    assert [m["request"] for m in second.sent] == [first.sent[0]["request"]], "the same task is sent again"
    directors.broker.finish(second.sent[0]["request"], ok=True, detail={"text": "{}"}, device_id="laptop")
    thread.join(5)
    assert result["ok"] is True and not thread.is_alive()
    third = Laptop(directors, silent=True)                                     # a later reconnect does not send finished work again
    assert third.sent == []


def test_a_new_connection_replacing_an_old_one_resends_what_may_have_been_lost_on_the_old_one():
    from vt import directors

    old = Laptop(directors, silent=True)
    thread, result = _ask_in_a_thread(directors)
    _wait_for(lambda: old.sent, "the question to be sent")
    new = Laptop(directors, silent=True)                                       # the new socket connects before the old one is seen to be dead
    assert [m["request"] for m in new.sent] == [old.sent[0]["request"]]
    directors.broker.finish(new.sent[0]["request"], ok=True, detail={"text": "{}"}, device_id="laptop")
    thread.join(5)
    assert result["ok"] is True


def test_a_long_drop_fails_the_task_with_a_reason_a_person_can_act_on_and_cancels_it_when_the_computer_returns(monkeypatch):
    from vt import directors

    monkeypatch.setattr(directors, "broker", directors.DirectorBroker(grace=0.2))
    first = Laptop(directors, silent=True)
    thread, result = _ask_in_a_thread(directors)
    _wait_for(lambda: first.sent, "the question to be sent")
    directors.broker.disconnect("laptop", first.channel)
    thread.join(5)
    assert not thread.is_alive() and result["ok"] is False
    assert "lost its connection" in result["reason"] and "did not come back within 0 seconds" in result["reason"] and "Open Video Tool there" in result["reason"]
    back = Laptop(directors, silent=True)
    assert [m["type"] for m in back.sent] == ["cancel"] and back.sent[0]["request"] == first.sent[0]["request"], "work the server gave up on is stopped over there"


def test_a_video_whose_director_does_not_come_back_is_handed_to_the_rules_with_a_notice(ref, monkeypatch):
    import threading

    from vt import directors
    from vt.director import heartbeat
    from vt.pipeline import Pipeline
    from vt.script import service
    from vt.planner import llm_plan
    from vt.util import read_json

    monkeypatch.setattr(directors, "broker", directors.DirectorBroker(grace=0.2))
    monkeypatch.setattr(llm_plan, "plan_llm", lambda *a, **k: None)
    monkeypatch.setattr(service, "direct", lambda *a, **k: None)
    monkeypatch.setattr(heartbeat, "add_heartbeats", lambda *a, **k: None)
    _no_plan(ref)
    _choose(ref, "claude@laptop")
    laptop = Laptop(directors, silent=True)
    done = threading.Event()
    worker = threading.Thread(target=lambda: (Pipeline(ref).stage_plan(force=True), done.set()))
    worker.start()
    _wait_for(lambda: laptop.sent, "the planning task to be sent")
    directors.broker.disconnect("laptop", laptop.channel)
    assert done.wait(10), "the video went on without it"
    director = ref.meta().director
    assert director["who"] == "rules" and "did not come back" in director["fallback_reason"], director
    assert "did not come back" in read_json(ref.dir / "ai_notice.json")["message"], "the person is told in plain words"
    assert ref.scenes() is not None and ref.scenes().planner != "claude", "no half-made plan is credited to Claude"


def test_a_director_the_person_picked_who_is_not_connected_is_named_in_the_notice(ref, monkeypatch):
    from vt import directors
    from vt.director import heartbeat
    from vt.pipeline import Pipeline
    from vt.planner import llm_plan
    from vt.script import service
    from vt.util import read_json

    monkeypatch.setattr(llm_plan, "plan_llm", lambda *a, **k: None)
    monkeypatch.setattr(service, "direct", lambda *a, **k: None)
    monkeypatch.setattr(heartbeat, "add_heartbeats", lambda *a, **k: None)
    Laptop(directors)
    directors.broker.disconnect("laptop")                                      # it was here, and it is not now
    _no_plan(ref)
    _choose(ref, "claude@laptop")
    Pipeline(ref).stage_plan(force=True)
    message = read_json(ref.dir / "ai_notice.json")["message"]
    assert message.startswith("Claude on Laptop was not available (Not connected.") and message.endswith("directed this video."), message
    assert ref.meta().director["requested"] == "claude@laptop" and ref.meta().director["who"] != "claude@laptop"


def test_a_computer_that_was_connected_is_remembered_as_not_connected_across_a_restart():
    from vt import directors

    Laptop(directors)
    here = next(d for d in directors.listing()["directors"] if d["id"] == "claude@laptop")
    assert here["available"] is True
    directors.broker.disconnect("laptop")
    gone = next(d for d in directors.listing()["directors"] if d["id"] == "claude@laptop")
    assert gone["available"] is False and gone["label"] == "Claude on Laptop" and gone["note"].startswith("Not connected.") and gone["last_seen"]
    restarted = directors.DirectorBroker()                                     # a new server process reads the same file
    assert restarted.devices() == [] and any(d["id"] == "claude@laptop" and not d["available"] for d in directors.listing()["directors"])


def test_every_connection_is_told_which_server_process_it_reached():
    from fastapi.testclient import TestClient

    from vt import directors
    from vt.server.app import app

    with TestClient(app, client=("127.0.0.1", 50000)) as client, client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
    assert hello["type"] == "hello" and hello["boot"] == directors.BOOT and len(directors.BOOT) == 12
