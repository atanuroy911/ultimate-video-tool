"""The local AI on a small graphics card (docs/plans/PLAN-LOCAL-AI-6GB.MD): our own Ollama starts with flash attention and an 8-bit context cache, an older
copy of ours is restarted with them when it is idle, and the model chosen for a card is one measured to stay whole on it at the context we ask for."""
import pytest

from vt import llm
from vt.engines import pids


@pytest.fixture()
def starting(monkeypatch, tmp_path):
    from vt import paths

    monkeypatch.setattr(paths, "DATA", tmp_path)
    started, up = [], {"yes": False}
    monkeypatch.setattr(llm, "reachable", lambda url: up["yes"])
    monkeypatch.setattr(llm, "binary", lambda *a: "ollama")
    monkeypatch.setattr(llm, "is_local", lambda url: True)

    class Proc:
        pid = 4242

    def popen(cmd, **kw):
        started.append(kw["env"])
        up["yes"] = True
        return Proc()
    monkeypatch.setattr(llm.subprocess, "Popen", popen)
    for k in llm.OLLAMA_TUNING:
        monkeypatch.delenv(k, raising=False)
    return started, up


def test_our_ollama_starts_with_the_small_card_settings_and_remembers_them(starting):
    started, _ = starting
    assert llm.start_server("http://127.0.0.1:11444", wait=2)
    env = started[-1]
    assert env["OLLAMA_FLASH_ATTENTION"] == "1" and env["OLLAMA_KV_CACHE_TYPE"] == "q8_0"
    assert env["OLLAMA_NUM_PARALLEL"] == "1" and env["OLLAMA_MAX_LOADED_MODELS"] == "1"
    assert pids.recorded("ollama")["tuning"] == llm.TUNING


def test_the_persons_own_ollama_settings_win(starting, monkeypatch):
    started, _ = starting
    monkeypatch.setenv("OLLAMA_KV_CACHE_TYPE", "f16")
    assert llm.start_server("http://127.0.0.1:11444", wait=2)
    assert started[-1]["OLLAMA_KV_CACHE_TYPE"] == "f16"
    assert started[-1]["OLLAMA_FLASH_ATTENTION"] == "1"


class _PS:
    def __init__(self, models):
        self.models = models

    def json(self):
        return {"models": self.models}


@pytest.mark.parametrize("case,recorded_tuning,ours,loaded,stopped", [
    ("an old copy of ours, idle", "", True, [], True),
    ("an old copy of ours, holding a model", "", True, [{"name": "gemma3:4b"}], False),
    ("our copy, already tuned", llm.TUNING, True, [], False),
    ("an Ollama the person runs themselves", "", False, [], False),
])
def test_an_old_copy_of_ours_is_restarted_only_when_idle(monkeypatch, tmp_path, case, recorded_tuning, ours, loaded, stopped):
    from vt import paths

    monkeypatch.setattr(paths, "DATA", tmp_path)
    extra = {"tuning": recorded_tuning} if recorded_tuning else {}
    pids.remember("ollama", 1234, 11434, **extra)
    monkeypatch.setattr(llm, "is_local", lambda url: True)
    monkeypatch.setattr(pids, "running", lambda engine, fresh=False: 1234 if ours else None)
    monkeypatch.setattr(llm.httpx, "get", lambda *a, **k: _PS(loaded))
    calls = []
    monkeypatch.setattr(pids, "stop", lambda engine, wait=15.0: calls.append(engine) or True)
    llm._retune_if_ours("http://127.0.0.1:11434")
    assert bool(calls) is stopped, case


@pytest.mark.parametrize("size,vram,noted", [(4e9, 4e9, False), (4e9, 3.1e9, True), (0, 0, False)])
def test_a_model_partly_off_the_card_is_said_in_the_ai_conversations(monkeypatch, size, vram, noted):
    from vt.ai import talk

    monkeypatch.setattr(llm.httpx, "get", lambda *a, **k: _PS([{"name": "gemma3:4b", "size": size, "size_vram": vram}]))
    said = []
    monkeypatch.setattr(talk, "record", lambda *a, **k: said.append(k))
    share = llm.note_if_spilled("http://127.0.0.1:11434", "gemma3:4b")
    assert bool(said) is noted
    if noted:
        assert "processor" in said[0]["answer"] and "78%" in said[0]["answer"] and share < 1


def test_getting_the_local_ai_ready_retunes_an_old_copy_first(monkeypatch):
    seen = []
    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "auto", "llm_auto_download": False, "ollama_url": "http://127.0.0.1:11434", "ollama_model": "gemma3:4b"})
    monkeypatch.setattr(llm, "reachable", lambda url=None: True)
    monkeypatch.setattr(llm, "_retune_if_ours", lambda url: seen.append(url))
    monkeypatch.setattr(llm, "has_model", lambda m, url=None: True)
    assert llm.ensure_ready(model="gemma3:4b") == "gemma3:4b"
    assert seen == ["http://127.0.0.1:11434"]
