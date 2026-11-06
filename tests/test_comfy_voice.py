"""Voices through ComfyUI: the workflow is checked against the server, the request is written into it, the sound comes back as a WAV, and the choice of model follows language and direction."""
import io
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

SUBMITTED: list[dict] = []
UPLOADS: list[str] = []
FREED: list[bytes] = []
NODES = {n: {"input": {"required": {}}} for n in ("LoadAudio", "SaveAudio", "CLIPLoader", "KSampler", "SaveImage", "BreezeTTS2LoadModel", "BreezeTTS2VoiceDesign", "BreezeTTS2VoiceClone", "BreezeTTS2VoiceDirection")}
NODES["BreezeTTS2LoadModel"]["input"]["required"] = {"model": [["bf16 (best quality)", "int8 hybrid (recommended)"]]}


def _wav(seconds=0.6):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x20\x00" * int(24000 * seconds))
    return buf.getvalue()


class FakeComfy(BaseHTTPRequestHandler):
    nodes = NODES

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/system_stats"):
            return self._json({"system": {"comfyui_version": "fake"}, "devices": [{"name": "cuda:0 Fake GPU : x"}]})
        if self.path.startswith("/object_info"):
            return self._json(self.nodes)
        if self.path.startswith("/history/"):
            return self._json({self.path.rsplit("/", 1)[1]: {"status": {"completed": True, "status_str": "success", "messages": []},
                                                              "outputs": {"4": {"audio": [{"filename": "voice_x.flac", "subfolder": "video_tool", "type": "output"}]}}}})
        if self.path.startswith("/queue"):
            return self._json({"queue_running": [], "queue_pending": []})
        if self.path.startswith("/view"):
            data = _wav()
            self.send_response(200)
            self.send_header("content-type", "audio/wav")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        self._json({}, 404)

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(n)
        if self.path == "/upload/image":
            UPLOADS.append(body.decode("latin-1")[:400])
            return self._json({"name": "vt_ref_uploaded.wav"})
        if self.path == "/free":
            FREED.append(body)
            return self._json({})
        if self.path == "/prompt":
            SUBMITTED.append(json.loads(body)["prompt"])
            return self._json({"prompt_id": f"p{len(SUBMITTED)}"})
        self._json({}, 404)


@pytest.fixture()
def comfy():
    SUBMITTED.clear()
    UPLOADS.clear()
    FREED.clear()
    FakeComfy.nodes = NODES
    server = HTTPServer(("127.0.0.1", 0), FakeComfy)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_the_choice_of_model_follows_language_and_direction():
    from vt.comfy import voicing

    both = {"breeze_design", "breeze_clone", "breeze_direction", "omnivoice_design", "omnivoice_clone"}
    assert voicing.pick("me:anna", "en", both, wants_direction=True) == "breeze_direction"
    assert voicing.pick("me:anna", "en", both) == "breeze_clone"
    assert voicing.pick("me:anna", "bn", both) == "omnivoice_clone", "Bangla is not a Breeze language"
    assert voicing.pick("design:a calm woman", "zh", both) == "breeze_design"
    assert voicing.pick("design:a calm woman", "bn", both) == "omnivoice_design"
    assert voicing.pick("me:anna", "bn", {"breeze_clone"}) is None, "nothing installed can speak it, and that is said, not guessed"
    assert voicing.pick("design:x", "en", {"omnivoice_design"}) == "omnivoice_design"
    assert voicing.dialect("breeze_clone") == "breeze" and voicing.dialect("omnivoice_design") == "omnivoice" and voicing.dialect(None) == "none"


def test_a_described_voice_is_mapped_onto_omnivoices_vocabulary():
    """The real server refused 'calmly' ('Valid English items: american accent, ... young adult'): a description becomes the items it understands."""
    from vt.comfy.voicing import omnivoice_instruct as o

    assert o("A deep, serious older man speaking slowly, like a documentary narrator.") == "male, elderly, low pitch"
    assert o("A calm, thoughtful woman with a clear voice and a gentle, reflective delivery.") == "female"
    assert o("A bright, energetic young narrator, quick and upbeat") == "female, young adult, high pitch"
    assert o("a british man, whispering") == "whisper, male, british accent" or o("a british man, whispering") == "male, whisper, british accent"
    assert o("calmly", design=False) == "" and o("whisper softly", design=False) == "whisper"


def test_a_missing_node_pack_is_named_before_anything_is_queued(comfy, tmp_path):
    from vt.comfy import ComfyClient, ComfyError, load_workflow
    from vt.comfy import voice as CV

    FakeComfy.nodes = {k: v for k, v in NODES.items() if not k.startswith("Breeze")}
    with pytest.raises(ComfyError, match="BreezeTTS2"):
        CV.speak(ComfyClient(comfy), load_workflow("breeze_design"), "Hello.", tmp_path / "o.wav")
    assert SUBMITTED == []


def test_a_designed_voice_is_written_into_the_graph_and_comes_back_as_wav_and_cached(comfy, tmp_path):
    import soundfile as sf

    from vt.comfy import ComfyClient, load_workflow
    from vt.comfy import voice as CV

    out = tmp_path / "o.wav"
    info = CV.speak(ComfyClient(comfy), load_workflow("breeze_design"), "(sigh) Hello there.", out, instruction="A calm woman.", seed=7, cache_dir=tmp_path / "cache")
    assert info["cached"] is False and out.exists() and sf.info(str(out)).samplerate == 24000
    g = SUBMITTED[0]
    assert g["3"]["inputs"]["text"] == "(sigh) Hello there." and g["3"]["inputs"]["instruction"] == "A calm woman." and g["3"]["inputs"]["seed"] == 7
    assert g["4"]["inputs"]["filename_prefix"].startswith("video_tool/voice_")
    again = CV.speak(ComfyClient(comfy), load_workflow("breeze_design"), "(sigh) Hello there.", tmp_path / "o2.wav", instruction="A calm woman.", seed=7, cache_dir=tmp_path / "cache")
    assert again["cached"] is True and len(SUBMITTED) == 1, "the same sentence in the same voice is not rendered twice"


class SplitModelComfy(FakeComfy):
    """The first run fails the way Breeze TTS 2 did once ComfyUI had parked half of it in system RAM."""

    def do_GET(self):
        if self.path.startswith("/history/p1"):
            return self._json({"p1": {"status": {"completed": False, "status_str": "error", "messages": [["execution_error", {
                "node_id": "3", "node_type": "BreezeTTS2VoiceDirection", "exception_type": "RuntimeError",
                "exception_message": "Input type (torch.FloatTensor) and weight type (torch.cuda.FloatTensor) should be the same"}]]}, "outputs": {}}})
        return super().do_GET()


def test_a_model_split_between_ram_and_the_gpu_is_reloaded_and_the_sentence_spoken(tmp_path):
    from vt.comfy import ComfyClient, load_workflow
    from vt.comfy import voice as CV

    SUBMITTED.clear()
    FREED.clear()
    server = HTTPServer(("127.0.0.1", 0), SplitModelComfy)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        ref = tmp_path / "ref.wav"
        ref.write_bytes(_wav())
        out = tmp_path / "o.wav"
        CV.speak(ComfyClient(f"http://127.0.0.1:{server.server_port}"), load_workflow("breeze_direction"), "We need to talk.", out,
                 instruction="Speak slowly.", ref_audio=ref, ref_text="This is me.")
    finally:
        server.shutdown()
    assert out.exists() and len(SUBMITTED) == 2 and len(FREED) == 1, "the models are unloaded once and the same sentence runs again"
    assert not CV.split_across_devices("CUDA out of memory"), "other failures are not retried"


def test_a_cloned_and_directed_voice_uploads_its_recording_and_transcript(comfy, tmp_path):
    from vt.comfy import ComfyClient, load_workflow
    from vt.comfy import voice as CV

    ref = tmp_path / "ref.wav"
    ref.write_bytes(_wav(1.0))
    CV.speak(ComfyClient(comfy), load_workflow("breeze_direction"), "We need to talk.", tmp_path / "o.wav", instruction="Speak slowly, seriously.", ref_audio=ref, ref_text="This is me.")
    g = SUBMITTED[0]
    assert g["2"]["inputs"]["audio"] == "vt_ref_uploaded.wav" and g["3"]["inputs"]["reference_text"] == "This is me."
    assert g["3"]["inputs"]["instruction"] == "Speak slowly, seriously." and UPLOADS
    from vt.comfy import ComfyError
    with pytest.raises(ComfyError, match="reference recording"):
        CV.speak(ComfyClient(comfy), load_workflow("breeze_clone"), "x", tmp_path / "p.wav")


def test_the_voice_engine_speaks_a_sentence_end_to_end(comfy, tmp_path, ref, monkeypatch):
    from vt import tts, voices as V
    from vt.engines import store
    from vt.engines.model import Endpoint

    store.save("comfy", Endpoint(mode="remote", url=comfy))
    from vt.engines import registry
    registry.forget()
    monkeypatch.setattr(V, "voices_dir", lambda: tmp_path / "voices")
    from vt import paths
    monkeypatch.setattr(paths, "DATA", tmp_path)                          # the voice cache lives under DATA: a test must never write into the real one
    d = tmp_path / "voices" / "anna"
    d.mkdir(parents=True)
    (d / "ref.wav").write_bytes(_wav(6.0))
    (d / "voice.json").write_text(json.dumps({"name": "Anna", "consent": True, "ref_text": "This is Anna speaking."}), encoding="utf-8")
    eng = next(e for e in tts.list_engines() if e["id"] == "comfyvoice")
    ids = [v["id"] for v in eng["voices"]]
    assert "me:anna" in ids and any(i.startswith("design:") for i in ids)
    out = tts.synthesize("{slowly} It is good to hear you (sigh).", tmp_path / "x.wav", engine="comfyvoice", voice="me:anna", language="en")
    g = SUBMITTED[0]
    assert "BreezeTTS2VoiceDirection" == g["3"]["class_type"], "a direction asks for the model that can follow one"
    assert g["3"]["inputs"]["text"] == "It is good to hear you (sigh)." and g["3"]["inputs"]["instruction"] == "slowly"
    assert out["sentences"][0]["text"] == "It is good to hear you." and out["sentences"][0]["direction"]["dialect"] == "breeze"


def test_a_voice_is_made_on_the_worker_that_has_the_model(tmp_path, ref, monkeypatch):
    """One ComfyUI per GPU is still ComfyUI: the main server (no voice nodes) and a worker (the RTX 3060 with Breeze) are both listed, and the sentence goes to the worker."""
    from vt import paths, tts
    from vt.engines import registry, store
    from vt.engines.model import Endpoint

    class Bare(FakeComfy):
        nodes = {k: v for k, v in NODES.items() if not k.startswith("Breeze")}

    class WithBreeze(FakeComfy):
        nodes = NODES

    servers = [HTTPServer(("127.0.0.1", 0), h) for h in (Bare, WithBreeze)]
    for s in servers:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        SUBMITTED.clear()
        monkeypatch.setattr(paths, "DATA", tmp_path)
        store.save("comfy", Endpoint(mode="remote", url=f"http://127.0.0.1:{servers[0].server_port}", workers=[f"http://127.0.0.1:{servers[1].server_port}"]))
        registry.forget()
        assert tts._comfy_voice_servers() == {"breeze_design": f"http://127.0.0.1:{servers[1].server_port}", "breeze_clone": f"http://127.0.0.1:{servers[1].server_port}",
                                               "breeze_direction": f"http://127.0.0.1:{servers[1].server_port}"}
        tts.synthesize("Hello there.", tmp_path / "w.wav", engine="comfyvoice", voice="design:A calm woman.", language="en")
        assert SUBMITTED and SUBMITTED[0]["3"]["class_type"] == "BreezeTTS2VoiceDesign"
        health = registry.health("comfy", fresh=True)
        assert "voice.speak" in health.capabilities
    finally:
        for s in servers:
            s.shutdown()


def test_breeze_prefers_the_worker_when_both_servers_can_run_it(tmp_path, ref, monkeypatch):
    from vt import paths, tts
    from vt.engines import registry, store
    from vt.engines.model import Endpoint

    servers = [HTTPServer(("127.0.0.1", 0), FakeComfy) for _ in range(2)]
    for s in servers:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(paths, "DATA", tmp_path)
        main, worker = (f"http://127.0.0.1:{s.server_port}" for s in servers)
        store.save("comfy", Endpoint(mode="remote", url=main, workers=[worker]))
        registry.forget()
        got = tts._comfy_voice_servers()
        assert got["breeze_design"] == worker, "the older main card is kept for pictures and clips"
    finally:
        for s in servers:
            s.shutdown()


def test_the_director_casts_a_voice_from_the_kind_of_script():
    """R9: steps and lists get the bright host, a story the documentary narrator, an explanation the calm woman."""
    from vt.comfy import voicing as V

    assert "energetic" in V.cast("Step one. Keep three months of bills. Step two. Invest the next slice. Step three. Hold some cash.")
    assert "documentary" in V.cast("Day 1. He walked out. Day 2. She said no. Day 3. They met again.")
    assert "calm" in V.cast("Water boils at a hundred degrees. That is why steam rises.")
    assert V.AUTO_VOICE == "design:auto"
