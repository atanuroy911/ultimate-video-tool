"""The judge and checklist endpoints (docs/TEST-PLAN.md T-3 and R13)."""
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from vt.util import find_tool


@pytest.fixture()
def client(ref):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_the_checklist_saves_answers_and_notes_for_known_questions_only(client):
    q = client.get("/api/projects/reference/checklist").json()
    assert len(q["questions"]) == 10 and q["answers"] == {}
    saved = client.put("/api/projects/reference/checklist", json={"answers": {"hook": "yes", "post": "no", "bogus": "yes"}, "notes": {"post": "the end is flat"}}).json()
    assert saved["answers"] == {"hook": "yes", "post": "no"} and saved["notes"] == {"post": "the end is flat"} and saved["at"]
    assert client.get("/api/projects/reference/checklist").json()["answers"]["post"] == "no"
    assert client.get("/api/projects/nope/checklist").status_code == 404


def test_a_video_has_to_exist_before_it_is_judged_and_a_bad_one_fails(client, ref):
    assert client.post("/api/projects/reference/judge").status_code == 409
    ref.exports_dir.mkdir(parents=True, exist_ok=True)
    green = ref.exports_dir / "bad.mp4"
    subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x00ff00:size=180x320:rate=10:duration=5", "-pix_fmt", "yuv420p", str(green)], check=True)
    r = client.post("/api/projects/reference/judge").json()
    assert r["passed"] is False and "no_glitches" in r["failed"] and r["file"] == "bad.mp4"
    listed = client.get("/api/projects/reference/exports").json()
    assert listed[0]["judges"]["passed"] is False and listed[0]["judges"]["says"]
    assert client.get("/api/projects/reference/judge").json()["result"]["failed"]
    shutil.rmtree(ref.exports_dir, ignore_errors=True)
