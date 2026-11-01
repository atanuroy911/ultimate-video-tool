"""The Engine Server and its client over real HTTP on loopback (docs/plans/PLAN-ENGINES-AND-SETUP.MD E6)."""
import socket
import threading
import time

import numpy as np
import pytest
import soundfile as sf
import uvicorn
from fastapi.testclient import TestClient

from vt import paths, tts
from vt.engines import registry, server, store, vtengine
from vt.engines.model import Endpoint


@pytest.fixture()
def remote(monkeypatch, tmp_path):
    key, code = server.new_secrets()
    app = server.create_app(key=key, pairing_code=code, name="Test box")
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", key, code
    srv.should_exit = True
    t.join(5)


def test_the_capability_document_is_public_but_everything_else_needs_the_key():
    key, code = server.new_secrets()
    c = TestClient(server.create_app(key=key, pairing_code=code, name="Box"))
    d = c.get("/.well-known/vt-engine").json()
    assert d["name"] == "Box" and "voice.speak" in d["capabilities"] and d["needs_pairing"] is True
    assert c.get("/v1/health").status_code == 401
    assert c.get("/v1/health", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/v1/health", headers={"Authorization": f"Bearer {key}"}).json()["ok"] is True
    assert c.post("/v1/voice/speak", json={"text": "hi"}).status_code == 401


def test_a_pairing_code_works_once(remote):
    url, key, code = remote
    assert vtengine.pair(url, code) == key
    with pytest.raises(vtengine.EngineServerError):
        vtengine.pair(url, code)
    with pytest.raises(vtengine.EngineServerError):
        vtengine.pair(url, "0000-0000-0000")


def test_another_computers_voice_is_used_like_a_local_one(remote, monkeypatch, tmp_path):
    url, key, code = remote
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    store.save("vtengine", Endpoint(mode="remote", url=url, key=vtengine.pair(url, code)))
    registry.forget("vtengine")
    h = registry.health("vtengine", fresh=True)
    assert h.ok and "voice.speak" in h.capabilities and h.version == "Test box"
    assert "vtengine" in [s.id for s in registry.engines()] and registry.resolve("voice.speak") in ("vtengine", "voicestudio")

    def fake(text, out, *, engine, voice, rate=1.0, language="", **k):
        sf.write(str(out), (np.sin(np.linspace(0, 440, 24000)) * 0.1).astype("float32"), 24000)
        return {"engine": engine}

    monkeypatch.setattr(tts, "synthesize", fake)
    monkeypatch.setattr(tts, "list_engines", lambda: [{"id": "kokoro", "label": "Kokoro (offline)", "voices": [{"id": "af_heart", "label": "Heart", "lang": "en"}]}])
    assert vtengine.voices(registry.endpoint("vtengine"))[0]["id"] == "kokoro:af_heart"
    out = tmp_path / "s.wav"
    tts._synth_vtengine("Hello there.", "kokoro:af_heart", 1.0, out)
    data, sr = sf.read(str(out))
    assert sr == tts.SR and len(data) > 1000


def test_a_wrong_key_is_named(remote, monkeypatch, tmp_path):
    url, key, code = remote
    h = vtengine.check(Endpoint(mode="remote", url=url, key="nope"))
    assert not h.ok and "key was refused" in h.why_not
    assert "pair it" in vtengine.check(Endpoint(mode="remote", url=url)).note
