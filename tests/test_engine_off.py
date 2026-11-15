"""Turning the local AI's engine off turns the local AI off (2026-11-15: with the engine off, the old ollama_url was still called and the Local AI was
still listed as a ready director)."""
from vt import llm, paths
from vt.util import write_json


def _real_settings(monkeypatch):
    """conftest replaces llm.settings with a stub that says "off"; this test is about the real one."""
    return next(old for obj, name, old in monkeypatch._setattr if obj is llm and name == "settings")


def test_engine_off_turns_the_local_ai_off(monkeypatch):
    settings = _real_settings(monkeypatch)
    write_json(paths.SETTINGS, {"ollama_url": "http://192.0.2.1:11434", "engines": {"ollama": {"mode": "off", "url": ""}}})
    assert settings()["llm_mode"] == "off"


def test_a_remote_or_unset_engine_keeps_the_local_ai(monkeypatch):
    settings = _real_settings(monkeypatch)
    write_json(paths.SETTINGS, {"ollama_url": "http://192.0.2.1:11434", "engines": {"ollama": {"mode": "remote", "url": "http://192.0.2.1:11434"}}})
    assert settings()["llm_mode"] == "auto"
    write_json(paths.SETTINGS, {})
    assert settings()["llm_mode"] == "auto"
    write_json(paths.SETTINGS, {"llm_mode": "off"})                  # the old switch still works
    assert settings()["llm_mode"] == "off"
