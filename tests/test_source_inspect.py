"""The New flow asks what kind of recording it got: a talking head, a video, or audio only."""
import shutil
import subprocess
from pathlib import Path

import pytest

from vt.source_inspect import inspect_source
from vt.util import find_tool

ROOT = Path(__file__).resolve().parents[1]


def _tone(path: Path, video: bool) -> None:
    inputs = ["-f", "lavfi", "-i", "sine=frequency=440:duration=2"]
    if video:
        inputs += ["-f", "lavfi", "-i", "color=c=gray:s=320x240:d=2"]
    subprocess.run([find_tool("ffmpeg"), "-v", "error", "-y", *inputs, "-shortest", str(path)], check=True)


def test_audio_only_is_audio_mode(tmp_path):
    clip = tmp_path / "voice.mp3"
    _tone(clip, video=False)
    assert inspect_source(clip)["mode"] == "audio"


def test_a_video_without_a_face_is_video_mode(tmp_path):
    clip = tmp_path / "plain.mp4"
    _tone(clip, video=True)
    found = inspect_source(clip)
    assert found["mode"] == "video" and found["has_picture"] and found["width"] == 320


@pytest.mark.slow
def test_the_podcast_sample_is_a_talking_head():
    sample = ROOT / "P_snippet_AMS_2.mp4"
    if not sample.exists():
        pytest.skip("podcast sample not present")
    assert inspect_source(sample)["mode"] == "talking_head"


def test_inspect_endpoint(tmp_path):
    from fastapi.testclient import TestClient
    from vt.server.app import app

    clip = tmp_path / "plain.mp4"
    _tone(clip, video=True)
    with clip.open("rb") as handle:
        result = TestClient(app).post("/api/inspect", files={"file": ("plain.mp4", handle, "video/mp4")}).json()
    assert result["mode"] == "video"
    options = TestClient(app).get("/api/cast-options").json()
    assert "jane" in [t["id"] for t in options["toons"]] and any(a["name"] == "lion" for a in options["animals"])
