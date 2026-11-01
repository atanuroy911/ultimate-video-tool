"""VoiceStudio as an engine: the registry, the settings (keys stay private), the voices it offers and the spoken sentence, against a small fake server."""
import io
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

KEY = "test-key-123"
HITS: list[str] = []


def _wav(seconds: float = 0.5) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x10\x00" * int(24000 * seconds))
    return buf.getvalue()


class Fake(BaseHTTPRequestHandler):
    licence_ok = False
    licence_blocks_speech = False

    def log_message(self, *a):
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self) -> bool:
        return self.headers.get("authorization") == f"Bearer {KEY}"

    def do_GET(self):
        HITS.append("GET " + self.path)
        if self.path == "/health":
            return self._send(200, b"{}")
        if not self._auth():
            return self._send(401, json.dumps({"detail": "API key required"}).encode())
        if self.path == "/engines/tts":
            return self._send(200, json.dumps({"active": "omnivoice", "backends": [
                {"id": "omnivoice", "display_name": "VoiceStudio (OmniVoice)", "available": True, "supports_cloning": True, "supports_voice_design": True, "preset_voices": [],
                 "execution_evidence": {"gpu_name": "NVIDIA GeForce RTX 3060"}},
                {"id": "kittentts", "display_name": "KittenTTS (English)", "available": True, "supports_cloning": False, "supports_voice_design": False,
                 "preset_voices": ["expr-voice-2-f", "expr-voice-2-m"]}]}).encode())
        if self.path == "/models":
            return self._send(200, json.dumps({"models": [{"repo_id": "k2-fsa/OmniVoice", "role": "TTS", "size_gb": 2.4, "installed": False,
                                                           "license_info": {"license_category": "noncommercial"}, "license_acceptance": {"accepted": self.licence_ok}}]}).encode())
        if self.path == "/profiles":
            return self._send(200, json.dumps([{"id": "p1", "name": "Mina", "language": "bn"}]).encode())
        self._send(404, b"{}")

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(n)
        HITS.append("POST " + self.path + " " + body.decode("latin-1")[:300].replace("\r\n", " | "))
        if not self._auth():
            return self._send(401, json.dumps({"detail": "API key required"}).encode())
        if self.path == "/generate":
            if self.licence_blocks_speech:
                return self._send(403, json.dumps({"error": {"message": "Licence not accepted for k2-fsa/OmniVoice.", "code": "model_licence_required"}}).encode())
            return self._send(200, _wav(), "audio/wav")
        self._send(404, b"{}")


@pytest.fixture()
def fake():
    HITS.clear()
    Fake.licence_ok = False
    Fake.licence_blocks_speech = False
    server = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture()
def client(ref):
    from fastapi.testclient import TestClient
    from vt.engines import registry
    from vt.server.app import app

    registry.forget()
    with TestClient(app) as c:
        yield c
    registry.forget()


def test_engines_are_listed_and_the_key_is_never_returned(client, fake):
    names = [e["id"] for e in client.get("/api/engines", params={"health": "false"}).json()]
    assert names == ["ollama", "comfy", "voicestudio", "vtengine"]
    saved = client.put("/api/engines/voicestudio", json={"mode": "remote", "url": fake, "key": KEY}).json()
    assert saved["endpoint"]["mode"] == "remote" and saved["endpoint"]["has_key"] is True
    assert KEY not in json.dumps(saved) and KEY not in json.dumps(client.get("/api/settings").json())
    assert saved["health"]["ok"] and "voice.speak" in saved["health"]["capabilities"] and "voice.clone" in saved["health"]["capabilities"]
    assert saved["health"]["gpu"] == "NVIDIA GeForce RTX 3060"
    assert "non-commercial" in saved["health"]["note"], "the unaccepted model licence is said in words"


def test_a_wrong_key_or_address_is_reported_not_raised(client, fake):
    bad = client.post("/api/engines/voicestudio/test", json={"mode": "remote", "url": fake, "key": "nope"}).json()
    assert bad["ok"] is False and "key" in bad["why_not"]
    assert client.put("/api/engines/voicestudio", json={"mode": "remote", "url": "192.168.1.5:3900"}).status_code == 422
    down = client.post("/api/engines/voicestudio/test", json={"mode": "remote", "url": "http://127.0.0.1:9", "key": "x"})
    assert down.status_code == 502 and "Could not reach" in down.json()["detail"]


def test_the_old_settings_still_connect_ollama_and_comfy(client):
    from vt.engines import registry
    from vt.util import write_json
    from vt import paths

    write_json(paths.SETTINGS, {"ollama_url": "http://10.0.0.5:11434", "comfy_url": "http://10.0.0.6:8188"})
    assert registry.endpoint("ollama").mode == "remote" and registry.endpoint("ollama").url == "http://10.0.0.5:11434"
    assert registry.endpoint("comfy").url == "http://10.0.0.6:8188"
    client.put("/api/engines/ollama", json={"mode": "remote", "url": "http://10.0.0.7:11434"})
    assert registry.endpoint("ollama").url == "http://10.0.0.7:11434"


def test_the_voices_of_the_server_become_a_voice_list_and_a_sentence_is_spoken_and_cached(client, fake, tmp_path):
    from vt import tts

    client.put("/api/engines/voicestudio", json={"mode": "remote", "url": fake, "key": KEY})
    eng = next(e for e in tts.list_engines() if e["id"] == "voicestudio")
    ids = [v["id"] for v in eng["voices"]]
    assert "kittentts:expr-voice-2-f" in ids and "profile:p1" in ids and "auto" in ids
    out = tmp_path / "s.wav"
    tts.synth_sentence("voicestudio", "kittentts:expr-voice-2-f", "Hello there.", 1.0, out)
    assert out.exists() and out.stat().st_size > 1000
    posts = [h for h in HITS if h.startswith("POST /generate")]
    assert len(posts) == 1 and "kittentts" in posts[0] and "expr-voice-2-f" in posts[0]
    tts.synth_sentence("voicestudio", "kittentts:expr-voice-2-f", "Hello there.", 1.0, tmp_path / "s2.wav")
    assert len([h for h in HITS if h.startswith("POST /generate")]) == 1, "the same sentence in the same voice is not asked for twice"


def test_a_model_licence_block_is_a_plain_sentence(client, fake, tmp_path):
    from vt import tts

    client.put("/api/engines/voicestudio", json={"mode": "remote", "url": fake, "key": KEY})
    Fake.licence_blocks_speech = True
    with pytest.raises(tts.TTSError, match="Licence not accepted"):
        tts.synth_sentence("voicestudio", "auto", "Hello.", 1.0, tmp_path / "x.wav")


def test_an_unconnected_server_is_not_offered_and_says_why(client):
    from vt import tts

    eng = next(e for e in tts.list_engines() if e["id"] == "voicestudio")
    assert eng["voices"] == [] and not eng.get("available", True) or eng.get("why")


def test_a_comfy_device_name_becomes_a_gpu_name():
    from vt.engines.specs import _gpu_name

    assert _gpu_name("cuda:0 Tesla V100-PCIE-16GB : cudaMallocAsync") == "Tesla V100-PCIE-16GB"
    assert _gpu_name("NVIDIA GeForce RTX 3060") == "NVIDIA GeForce RTX 3060"
