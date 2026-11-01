"""One AI path: every stage asks the same gate, whichever brain the person chose."""
import json

import pytest

from vt import llm, paths
from vt.ai import providers as P


def _settings(**kw):
    paths.SETTINGS.write_text(json.dumps(kw), encoding="utf-8")


def test_off_means_off_everywhere():
    _settings(ai_provider="off")
    assert not P.ai_enabled() and P.fingerprint() == "off"
    with pytest.raises(P.AIUnavailable):
        P.ensure_ai()


def test_claude_is_only_checked_never_installed(monkeypatch):
    _settings(ai_provider="claude_cli")
    monkeypatch.setattr(P.ClaudeCLIProvider, "available", lambda self: True)
    monkeypatch.setattr(llm, "ensure_ready", lambda *a, **k: pytest.fail("the local model must not be prepared when Claude is chosen"))
    assert P.ai_enabled() and P.fingerprint().startswith("claude")
    assert isinstance(P.ensure_ai(), P.ClaudeCLIProvider)
    monkeypatch.setattr(P.ClaudeCLIProvider, "available", lambda self: False)
    with pytest.raises(P.AIUnavailable):
        P.ensure_ai()


def test_local_model_is_prepared_and_respects_its_own_switch(monkeypatch):
    _settings(ai_provider="auto")
    calls = []
    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "auto", "ollama_url": "http://x", "ollama_model": "m", "llm_auto_download": False})
    monkeypatch.setattr(llm, "ensure_ready", lambda progress=None, **k: calls.append(1) or "m")
    assert isinstance(P.ensure_ai(), P.OllamaProvider) and calls == [1]
    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "off", "ollama_url": "http://x", "ollama_model": "m", "llm_auto_download": False})
    assert not P.ai_enabled()
    with pytest.raises(P.AIUnavailable):
        P.ensure_ai()
