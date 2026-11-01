"""Layers: extra tracks with text, pictures, video and audio. The document is checked strictly, kept with history, drawn by the composition and mixed into the export."""
import json
import subprocess

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from PIL import Image

from vt import layers as L
from vt.director import media as M
from vt.util import find_tool

@pytest.fixture()
def client(ref):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


KINDS = {"pic": "image", "clip": "video", "song": "audio"}


def doc(*clips, tracks=None):
    return {"v": 1, "tracks": tracks or [{"id": "t1", "name": "Overlay", "kind": "visual"}, {"id": "a1", "name": "Sound", "kind": "audio"}], "clips": list(clips)}


def text(cid="c1", start=1.0, dur=2.0, track="t1", **kw):
    return {"id": cid, "type": "text", "track": track, "start": start, "dur": dur, "text": "Hello", **kw}


def test_a_valid_document_is_cleaned_and_kept():
    clean, errors = L.validate(doc(text(), {"id": "c2", "type": "media", "track": "t1", "start": 4, "dur": 2, "media": "pic"},
                                   {"id": "c3", "type": "audio", "track": "a1", "start": 0, "dur": 5, "media": "song"}), 20.0, KINDS)
    assert errors == [] and len(clean["clips"]) == 3
    t = clean["clips"][0]
    assert 0 <= t["x"] <= 1 and t["style"]["size"] > 0 and t["opacity"] == 1.0
    assert clean["clips"][2]["volume"] == 1.0 and "x" not in clean["clips"][2]


def test_problems_are_listed_not_hidden():
    bad = doc(text("c1", 1, 3), text("c2", 2, 3),                                                      # overlap on one track
              {"id": "c3", "type": "audio", "track": "t1", "start": 0, "dur": 1, "media": "song"},          # audio on a visual track
              {"id": "c4", "type": "media", "track": "t1", "start": 9, "dur": 1, "media": "nope"},          # not in the project
              {"id": "c5", "type": "media", "track": "t1", "start": 12, "dur": 1, "media": "song"},         # a sound used as a picture
              {"id": "c6", "type": "text", "track": "t1", "start": 14, "dur": 1, "text": "  "},             # empty text
              {"id": "c7", "type": "text", "track": "zzz", "start": 15, "dur": 1, "text": "x"},             # no such track
              {"id": "c8", "type": "text", "track": "t1", "start": 99, "dur": 1, "text": "x"})              # after the end
    _, errors = L.validate(bad, 20.0, KINDS)
    joined = " | ".join(errors)
    for needle in ("overlap", "do not belong", "not in the project", "cannot be used", "empty", "does not exist", "after the end"):
        assert needle in joined, (needle, joined)
    assert L.validate("nonsense", 20.0, KINDS)[1] and L.validate({"tracks": "x", "clips": []}, 20.0, KINDS)[1]


def test_times_and_numbers_are_clamped_and_nan_is_refused_quietly():
    clean, errors = L.validate(doc(text("c1", -5, 1e9, x=float("nan"), opacity=7, w=-1)), 10.0, KINDS)
    c = clean["clips"][0]
    assert not errors and c["start"] == 0 and c["start"] + c["dur"] == 10.0 and c["x"] == 0.5 and c["opacity"] == 1.0 and c["w"] >= 0.02


def test_history_goes_back_and_forward(ref):
    assert L.history(ref) == {"can_undo": False, "can_redo": False}
    a = doc(text("c1"))
    b = doc(text("c1"), text("c2", 5))
    L.save(ref, a)
    L.save(ref, b)
    L.save(ref, b)                                                    # the same document again is not a step
    assert L.load(ref) == b and L.history(ref)["can_undo"]
    assert L.step(ref, "undo") == a and L.load(ref) == a
    assert L.step(ref, "redo") == b
    assert L.step(ref, "redo") is None
    L.save(ref, a)
    assert L.history(ref)["can_redo"] is False                        # a new edit ends the redo line


def _picture(tmp_path, name="p.png", color=(200, 30, 30)):
    f = tmp_path / name
    Image.new("RGB", (320, 180), color).save(f)
    return f


def test_the_composition_draws_visual_layers_and_copies_their_pictures(ref, tmp_path):
    from vt.compose import compose_project

    item = M.add_media(ref, _picture(tmp_path))
    L.save(ref, doc(text("c1", 1, 2), {"id": "c2", "type": "media", "track": "t1", "start": 4, "dur": 2, "media": item.id, "w": 0.5}, tracks=[{"id": "t1", "name": "O", "kind": "visual"}]))
    index = compose_project(ref, "9:16")
    data = json.loads((index.parent / "data.json").read_text(encoding="utf-8"))
    assert [c["type"] for c in data["layers"]] == ["text", "media"] and all("end" in c for c in data["layers"])
    assert (index.parent / data["media"][item.id]["src"]).exists()
    assert "vt-layers.js" in index.read_text(encoding="utf-8")
    d = L.load(ref)
    d["tracks"][0]["hidden"] = True                                    # a hidden track is not drawn
    L.save(ref, d)
    data = json.loads((compose_project(ref, "9:16").parent / "data.json").read_text(encoding="utf-8"))
    assert data["layers"] == []


def _tone(path, seconds, hz=1000, amp=0.5):
    t = np.arange(int(seconds * 48000)) / 48000
    sf.write(str(path), (amp * np.sin(2 * np.pi * hz * t)).astype("float32"), 48000)


def test_a_sound_is_added_converted_and_found_by_the_layers(ref, tmp_path):
    _tone(tmp_path / "beep.wav", 2.0)
    s = M.add_sound(ref, tmp_path / "beep.wav")
    assert s.kind == "audio" and 1.9 < s.duration < 2.2 and (ref.dir / s.file).suffix == ".m4a"
    assert s.id not in [m.id for m in ref.meta().media]               # never offered to the planners
    assert L.media_kinds(ref)[s.id] == "audio"
    with pytest.raises(M.MediaError):
        M.add_sound(ref, tmp_path / "x.txt")
    assert M.remove_sound(ref, s.id) and not M.remove_sound(ref, s.id)


def test_a_video_keeps_its_own_sound_for_layers(ref, tmp_path):
    ff = find_tool("ffmpeg")
    clip = tmp_path / "v.mp4"
    subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=2", "-f", "lavfi", "-i", "sine=frequency=500:duration=2",
                    "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(clip)], check=True)
    v = M.add_media(ref, clip)
    assert v.audio_file and (ref.dir / v.audio_file).exists()
    L.save(ref, doc({"id": "c1", "type": "media", "track": "t1", "start": 1, "dur": 1.5, "media": v.id, "volume": 0.8}, tracks=[{"id": "t1", "name": "V", "kind": "visual"}]))
    clips = L.audio_clips(ref)
    assert len(clips) == 1 and clips[0]["volume"] == 0.8 and clips[0]["path"].endswith(".audio.m4a")
    d = L.load(ref)
    d["clips"][0]["volume"] = 0                                        # a video's own sound is off by default
    assert L.audio_clips(ref, d) == []


def test_an_audio_layer_is_heard_where_it_was_placed(tmp_path):
    from vt.render.mux import mix_and_mux

    ff = find_tool("ffmpeg")
    silent = tmp_path / "silent.mp4"
    subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x180:r=30:d=6", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(silent)], check=True)
    voice = tmp_path / "voice.wav"
    _tone(voice, 6.0, hz=220, amp=0.02)                                 # a quiet voice
    beep = tmp_path / "beep.wav"
    _tone(beep, 2.0, hz=1000, amp=0.5)
    out = tmp_path / "out.mp4"
    mix_and_mux(silent, voice, out, duration=6.0, gpu=False,
                layer_audio=[{"path": str(beep), "start": 3.0, "dur": 1.0, "in": 0.5, "volume": 1.0, "fade_in": 0.0, "fade_out": 0.0}])
    raw = subprocess.run([ff, "-v", "error", "-i", str(out), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    rms = lambda a, b: float(np.sqrt(np.mean(x[int(a * 16000):int(b * 16000)] ** 2)))      # noqa: E731
    assert rms(3.1, 3.9) > 5 * rms(0.5, 2.5)                              # the beep sits inside 3.0-4.0 s
    assert rms(4.2, 5.8) < 0.3 * rms(3.1, 3.9)                            # and ends when it was asked to


def test_the_api_saves_refuses_undoes_and_protects_used_files(client, projects_dir, tmp_path):
    r = client.get("/api/projects/reference/layers").json()
    assert r["doc"]["clips"] == [] and r["duration"] > 5
    good = doc(text("c1", 1, 2), tracks=[{"id": "t1", "name": "Overlay", "kind": "visual"}])
    out = client.put("/api/projects/reference/layers", json={"doc": good}).json()
    assert out["doc"]["clips"][0]["text"] == "Hello" and out["can_undo"]
    bad = client.put("/api/projects/reference/layers", json={"doc": doc(text("c1", 1, 3), text("c2", 2, 3), tracks=[{"id": "t1", "name": "O", "kind": "visual"}])})
    assert bad.status_code == 422 and "overlap" in json.dumps(bad.json())
    assert client.get("/api/projects/reference/layers").json()["doc"]["clips"][0]["id"] == "c1"       # the refused save changed nothing
    assert client.post("/api/projects/reference/layers/undo").json()["doc"]["clips"] == []
    assert client.post("/api/projects/reference/layers/undo").status_code == 409
    assert client.post("/api/projects/reference/layers/redo").json()["doc"]["clips"][0]["id"] == "c1"
    assert client.post("/api/projects/reference/layers/sideways").status_code == 404

    _tone(tmp_path / "a.wav", 2.0)
    up = client.post("/api/projects/reference/sounds", files={"file": ("a.wav", (tmp_path / "a.wav").read_bytes(), "audio/wav")}).json()
    assert up["kind"] == "audio" and client.get("/api/projects/reference/sounds").json()[0]["id"] == up["id"]
    assert client.post("/api/projects/reference/sounds", files={"file": ("a.txt", b"hello", "text/plain")}).status_code == 400
    two = doc(text("c1", 1, 2), {"id": "c9", "type": "audio", "track": "a1", "start": 0, "dur": 2, "media": up["id"]})
    assert client.put("/api/projects/reference/layers", json={"doc": two}).status_code == 200
    assert client.delete(f"/api/projects/reference/sounds/{up['id']}").status_code == 409           # still used
    one = doc(text("c1", 1, 2))
    client.put("/api/projects/reference/layers", json={"doc": one})
    assert client.delete(f"/api/projects/reference/sounds/{up['id']}").status_code == 200


def test_a_motion_preset_is_kept_when_known_and_ignored_when_not():
    clean, errors = L.validate(doc(text("c1", 1, 2, anim="zoom_in"), text("c2", 4, 2, anim="spin_wildly")), 20.0, KINDS)
    assert not errors and [c["anim"] for c in clean["clips"]] == ["zoom_in", "none"]


def test_the_page_animates_a_layer_with_a_motion(ref, tmp_path):
    from vt.compose import compose_project

    L.save(ref, doc(text("c1", 1, 3, anim="slide_left"), tracks=[{"id": "t1", "name": "O", "kind": "visual"}]))
    index = compose_project(ref, "9:16")
    data = json.loads((index.parent / "data.json").read_text(encoding="utf-8"))
    assert data["layers"][0]["anim"] == "slide_left"
    js = (index.parent / "runtime" / "vt-layers.js").read_text(encoding="utf-8")
    assert "slide_left" in js and "zoom_in" in js and "pulse" in js
