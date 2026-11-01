"""Generated motion clips: the ComfyUI client, workflow patching and the whole job, against a fake ComfyUI server (no GPU needed)."""
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from vt.comfy import ComfyClient, ComfyError, generate_clip
from vt.comfy import workflows as W
from vt.util import find_tool

GRAPH = {
    "1": {"class_type": "LoadImage", "inputs": {"image": "placeholder.png"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "x", "clip": ["9", 0]}},
    "3": {"class_type": "Sampler", "inputs": {"noise_seed": 1, "width": 64, "height": 64, "length": 9, "model_name": "good.safetensors"}},
    "4": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "video_tool/x", "video": ["3", 0]}},
}
OBJECT_INFO = {
    "LoadImage": {"input": {"required": {"image": [["placeholder.png"], {}]}}},
    "CLIPTextEncode": {"input": {"required": {"text": ["STRING", {}], "clip": ["CLIP"]}}},
    "Sampler": {"input": {"required": {"noise_seed": ["INT"], "width": ["INT"], "height": ["INT"], "length": ["INT"], "model_name": [["good.safetensors"], {}]}}},
    "SaveVideo": {"input": {"required": {"filename_prefix": ["STRING"], "video": ["VIDEO"]}}},
}


def workflow_file(directory: Path, graph=None, model="good.safetensors") -> None:
    graph = json.loads(json.dumps(graph or GRAPH))
    graph["3"]["inputs"]["model_name"] = model
    (directory / "fake.json").write_text(json.dumps({
        "id": "fake", "label": "Fake 14B", "version": 3, "status": "verified",
        "frame_rule": {"fps": 16, "step": 4, "offset": 1}, "sizes": {"9:16": [64, 96], "16:9": [96, 64]},
        "manifest": {"image": [["1", "image"]], "prompt": [["2", "text"]], "width": [["3", "width"]], "height": [["3", "height"]], "frames": [["3", "length"]],
                     "seed": [["3", "noise_seed"]], "prefix": [["4", "filename_prefix"]]},
        "output": "4", "graph": graph}), encoding="utf-8")


@pytest.fixture()
def fake_comfy(tmp_path):
    """A tiny stand-in for ComfyUI: records what it was sent, finishes a run on the second look, serves a real MP4."""
    clip = tmp_path / "out.mp4"
    subprocess.run([find_tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=96x64:rate=16:duration=2", "-f", "lavfi", "-i", "sine=duration=2",
                    "-shortest", "-pix_fmt", "yuv420p", str(clip)], check=True)
    state = {"prompts": [], "uploads": [], "interrupts": 0, "deleted": [], "polls": 0, "mode": "ok", "running": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/system_stats":
                return self._send(200, {"system": {"comfyui_version": "0.22.0"}, "devices": [{"name": "cuda:0 Tesla V100", "type": "cuda", "vram_total": 17e9, "vram_free": 16e9}]})
            if path == "/queue":
                return self._send(200, {"queue_running": [[0, pid, {}] for pid in state["running"]], "queue_pending": []})
            if path == "/object_info":
                return self._send(200, OBJECT_INFO)
            if path.startswith("/history/"):
                pid = path.rsplit("/", 1)[1]
                state["polls"] += 1
                if state["mode"] == "never" or state["polls"] < 2:
                    return self._send(200, {})
                if state["mode"] == "kernel":
                    return self._send(200, {pid: {"status": {"status_str": "error", "messages": [["execution_error", {"node_id": "3", "node_type": "Sampler", "exception_type": "RuntimeError",
                                                                                                                         "exception_message": "CUDA error: no kernel image is available for execution on the device"}]]}, "outputs": {}}})
                return self._send(200, {pid: {"status": {"status_str": "success", "completed": True, "messages": []}, "outputs": {"4": {"videos": [{"filename": "clip_00001.mp4", "subfolder": "video_tool", "type": "output"}]}}}})
            if path == "/view":
                return self._send(200, clip.read_bytes(), "video/mp4")
            self._send(404, {})

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n)
            if self.path == "/upload/image":
                state["uploads"].append(len(raw))
                return self._send(200, {"name": "uploaded.png", "subfolder": "", "type": "input"})
            if self.path == "/prompt":
                body = json.loads(raw)
                if state["mode"] == "reject":
                    return self._send(400, {"error": {"message": "Prompt outputs failed validation"}, "node_errors": {"3": {"class_type": "Sampler", "errors": [{"message": "Value not in list", "details": "model_name: 'bad'", "extra_info": {"input_name": "model_name"}}]}}})
                state["prompts"].append(body["prompt"])
                state["running"] = ["pid-1"]
                return self._send(200, {"prompt_id": "pid-1"})
            if self.path == "/interrupt":
                state["interrupts"] += 1
                return self._send(200, {})
            if self.path == "/queue":
                state["deleted"].append(json.loads(raw))
                return self._send(200, {})
            self._send(404, {})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{server.server_address[1]}"
    yield state
    server.shutdown()


@pytest.fixture()
def workflow(tmp_path, monkeypatch):
    folder = tmp_path / "wf"
    folder.mkdir()
    workflow_file(folder)
    monkeypatch.setattr(W, "WORKFLOW_DIR", folder)
    return W.load_workflow("fake")


def a_still(project, name="still.png"):
    from PIL import Image

    from vt.director.media import add_media

    src = project.dir / name
    Image.new("RGB", (64, 96), (200, 120, 40)).save(src)
    return add_media(project, src, caption="still")


# ---------------------------------------------------------------- workflow
def test_frames_follow_the_models_rule_and_only_manifest_fields_change(workflow):
    assert workflow.frames_for(3.0) == (49, 16.0)              # 4k+1 frames at 16 fps
    assert workflow.frames_for(0.2)[0] == 5
    graph, used = workflow.patched(image="a.png", prompt="a fox runs", aspect="16:9", seconds=3.0, seed=7, prefix="video_tool/p")
    assert graph["1"]["inputs"]["image"] == "a.png" and graph["2"]["inputs"]["text"] == "a fox runs"
    assert (graph["3"]["inputs"]["width"], graph["3"]["inputs"]["height"], graph["3"]["inputs"]["length"], graph["3"]["inputs"]["noise_seed"]) == (96, 64, 49, 7)
    assert graph["3"]["inputs"]["model_name"] == "good.safetensors" and graph["2"]["inputs"]["clip"] == ["9", 0]       # untouched
    assert graph["4"]["inputs"]["filename_prefix"].startswith("video_tool/p_") and workflow.graph["1"]["inputs"]["image"] == "placeholder.png"
    assert used == {"frames": 49, "fps": 16.0, "width": 96, "height": 64, "seed": 7}


def test_a_missing_model_or_node_is_named_before_anything_is_queued(tmp_path, monkeypatch):
    folder = tmp_path / "wf"
    folder.mkdir()
    workflow_file(folder, model="missing.safetensors")
    monkeypatch.setattr(W, "WORKFLOW_DIR", folder)
    wf = W.load_workflow("fake")
    assert any("missing.safetensors" in p for p in wf.problems(OBJECT_INFO))
    assert any("no node 'Sampler'" in p for p in wf.problems({k: v for k, v in OBJECT_INFO.items() if k != "Sampler"}))
    assert W.load_workflow("fake").problems(OBJECT_INFO) != []
    with pytest.raises(KeyError):
        W.load_workflow("../etc")


# ---------------------------------------------------------------- framing the still
def test_the_crop_keeps_the_subject_in_a_vertical_clip_of_a_landscape_still():
    from vt.comfy.generate import crop_box

    # 1392 x 752, the subject at the left edge: a 9:16 window is 423 wide and must contain x = 0.1
    left, top, right, bottom = crop_box(1392, 752, 320 / 512, fx=0.1, fy=0.5)
    assert (right - left, bottom - top) == (470, 752) and left == 0 and right > 0.1 * 1392 + 100
    centre = crop_box(1392, 752, 320 / 512)
    assert centre[0] == (1392 - 470) // 2
    assert crop_box(1392, 752, 320 / 512, fx=0.99)[2] == 1392                                  # clamped to the picture, never outside it
    wide = crop_box(500, 1000, 512 / 320, fx=0.5, fy=0.9)                                     # a tall still for a wide clip: keep the full width, slide to the subject
    assert (wide[2] - wide[0], wide[3] - wide[1]) == (500, 312) and wide[3] == 1000


# ---------------------------------------------------------------- client + job
def test_status_reports_gpu_and_queue(fake_comfy):
    status = ComfyClient(fake_comfy["url"]).status()
    assert status["ok"] and status["version"] == "0.22.0" and status["devices"][0]["name"].endswith("V100")
    down = ComfyClient("http://127.0.0.1:9").status()
    assert not down["ok"] and "ComfyUI at" in down["error"]            # refused or silent: either way a sentence, never a crash


def test_a_clip_comes_back_silent_verified_and_in_the_bin(fake_comfy, workflow, ref, monkeypatch):
    monkeypatch.setattr("vt.comfy.client.POLL_SECONDS", 0.05)
    item0 = a_still(ref)
    seen = []
    item, record = generate_clip(ref, ComfyClient(fake_comfy["url"]), workflow, ref.dir / item0.file, "a fox runs through snow", aspect="9:16", seconds=3.0, seed=11,
                                 progress=lambda f, m: seen.append((round(f, 2), m)))
    assert item.source == "comfyui" and item.role == "b_roll" and item.kind == "video" and "generated" in item.tags and not item.audio_file
    assert (ref.dir / item.file).exists() and item.duration >= 1.5
    streams = subprocess.run([find_tool("ffprobe"), "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(ref.dir / item.file)], capture_output=True, text=True).stdout
    assert "audio" not in streams and "video" in streams                                    # the fake's sound was dropped: silent B-roll
    sent = fake_comfy["prompts"][0]
    assert sent["1"]["inputs"]["image"] == "uploaded.png" and sent["3"]["inputs"]["noise_seed"] == 11 and sent["3"]["inputs"]["length"] == 49
    assert record["workflow"] == "fake" and record["workflow_version"] == 3 and record["seed"] == 11 and record["prompt_id"] == "pid-1" and seen[-1] == (1.0, "Done")
    log = json.loads((ref.dir / "comfy_clips.json").read_text(encoding="utf-8"))
    assert len(log["clips"]) == 1 and log["clips"][0]["media"] == item.id
    # the identical request is not rendered twice; a new seed is a new clip and the first one stays
    again, _ = generate_clip(ref, ComfyClient(fake_comfy["url"]), workflow, ref.dir / item0.file, "a fox runs through snow", aspect="9:16", seconds=3.0, seed=11)
    assert again.id == item.id and len(fake_comfy["prompts"]) == 1
    other, _ = generate_clip(ref, ComfyClient(fake_comfy["url"]), workflow, ref.dir / item0.file, "a fox runs through snow", aspect="9:16", seconds=3.0, seed=12)
    assert other.id != item.id and {m.id for m in ref.meta().media} >= {item.id, other.id}


def test_a_rejected_graph_is_explained_by_node_and_field(fake_comfy):
    fake_comfy["mode"] = "reject"
    with pytest.raises(ComfyError) as e:
        ComfyClient(fake_comfy["url"]).submit({"3": {"class_type": "Sampler", "inputs": {}}})
    assert e.value.kind == "rejected" and "node 3 (Sampler)" in str(e.value) and "model_name" in str(e.value)


def test_the_v100_kernel_failure_says_what_to_fix(fake_comfy, workflow, ref, monkeypatch):
    monkeypatch.setattr("vt.comfy.client.POLL_SECONDS", 0.05)
    fake_comfy["mode"] = "kernel"
    item0 = a_still(ref)
    with pytest.raises(ComfyError) as e:
        generate_clip(ref, ComfyClient(fake_comfy["url"]), workflow, ref.dir / item0.file, "a fox", seed=1)
    assert e.value.kind == "failed" and "Sampler (node 3)" in str(e.value) and "sm_70" in str(e.value)
    assert not any(m.source == "comfyui" for m in ref.meta().media)                             # nothing half-made is left in the bin


def test_cancel_stops_only_our_run_and_a_server_that_never_finishes_times_out(fake_comfy, workflow, ref, monkeypatch):
    monkeypatch.setattr("vt.comfy.client.POLL_SECONDS", 0.05)
    item0 = a_still(ref)
    fake_comfy["mode"] = "never"
    with pytest.raises(ComfyError) as e:
        generate_clip(ref, ComfyClient(fake_comfy["url"]), workflow, ref.dir / item0.file, "a fox", seed=2, cancelled=lambda: fake_comfy["polls"] >= 3)
    assert e.value.kind == "cancelled" and fake_comfy["interrupts"] == 1                       # ours was the running one: interrupted
    fake_comfy["running"] = ["someone-else"]
    ComfyClient(fake_comfy["url"]).interrupt("pid-1")
    assert fake_comfy["interrupts"] == 1 and fake_comfy["deleted"][-1] == {"delete": ["pid-1"]}   # not running: only dequeued, theirs untouched
    with pytest.raises(ComfyError) as t:
        generate_clip(ref, ComfyClient(fake_comfy["url"]), workflow, ref.dir / item0.file, "a fox", seed=3, timeout=0.3)
    assert t.value.kind == "timeout"


# ---------------------------------------------------------------- the API
def test_the_endpoints(fake_comfy, workflow, ref, monkeypatch):
    from fastapi.testclient import TestClient

    from vt.server import comfy_routes
    from vt.server.app import app

    monkeypatch.setattr("vt.comfy.client.POLL_SECONDS", 0.05)
    monkeypatch.setattr(comfy_routes, "comfy_url", lambda: fake_comfy["url"])
    client = TestClient(app)
    status = client.get("/api/comfy/status?check=true").json()
    assert status["ok"] and status["workflows"][0]["id"] == "fake" and status["workflows"][0]["ready"] is True
    item0 = a_still(ref)
    assert client.post(f"/api/projects/{ref.id}/comfy/generate", json={"media_id": "nope", "prompt": "a fox runs"}).status_code == 422
    assert client.post(f"/api/projects/{ref.id}/comfy/generate", json={"media_id": item0.id, "prompt": "a fox runs", "workflow": "ghost"}).status_code == 404
    job = client.post(f"/api/projects/{ref.id}/comfy/generate", json={"media_id": item0.id, "prompt": "a fox runs", "workflow": "fake", "seed": 5}).json()
    import time

    for _ in range(200):
        j = client.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "error", "cancelled"):
            break
        time.sleep(0.1)
    assert j["status"] == "done", j
    clips = client.get(f"/api/projects/{ref.id}/comfy/clips").json()["clips"]
    assert clips and clips[0]["media"] == j["result"]["media"] and clips[0]["seed"] == 5


# ---------------------------------------------------------------- sharing the GPU with Ollama
def test_idle_ollama_models_are_unloaded_only_on_the_same_machine():
    from vt.comfy.gpu_share import release_ollama_models, same_machine

    assert same_machine("http://192.168.1.5:8188", "http://192.168.1.5:11434") and not same_machine("http://192.168.1.5:8188", "http://localhost:11434")
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            data = json.dumps({"models": [{"name": "gemma4:latest"}, {"name": "qwen2.5vl:7b"}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"{}")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        assert release_ollama_models(f"http://127.0.0.1:{server.server_address[1]}") == ["gemma4:latest", "qwen2.5vl:7b"]
        assert calls == [{"model": "gemma4:latest", "keep_alive": 0}, {"model": "qwen2.5vl:7b", "keep_alive": 0}]
    finally:
        server.shutdown()
    assert release_ollama_models("http://127.0.0.1:9") == []                       # nothing there: no error, no clip blocked
