"""The retention scorecard measured on videos whose answer is known."""
import subprocess

import numpy as np
import pytest

from vt import retention as R
from vt.util import find_tool

FF = find_tool("ffmpeg")


def make(path, graph, seconds, size="320x180", audio=False):
    cmd = [FF, "-y", "-v", "error", "-f", "lavfi", "-i", graph.format(size=size, d=seconds)]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(path)]
    subprocess.run(cmd, check=True)
    return path


def concat(parts, out):
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    subprocess.run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True)
    return out


PLAIN = "color=c=0xf1efe8:s={size}:r=30:d={d},noise=alls=3:allf=t"          # paper-like background with a little grain
BUSY = "testsrc2=s={size}:r=30:d={d}"                                       # something moving everywhere
CARD = "color=c=0xf1efe8:s={size}:r=30:d={d},drawbox=x=20:y=20:w=60:h=60:color=0x3b7bd8:t=fill,noise=alls=3:allf=t"      # one small picture on an empty frame


def test_a_frame_with_one_small_picture_is_mostly_plain_and_a_busy_one_is_not(tmp_path):
    f, _ = R._frames(make(tmp_path / "c.mp4", CARD, 1))
    assert 0.8 < R.plain_share(f[2], 0.22) < 0.98
    b, _ = R._frames(make(tmp_path / "b.mp4", BUSY, 1))
    assert R.plain_share(b[2], 0.22) < 0.3
    p, _ = R._frames(make(tmp_path / "p.mp4", PLAIN, 1))
    assert R.plain_share(p[2], 0.22) > 0.95


def test_an_empty_stretch_and_a_late_hook_are_found_where_they_are(tmp_path):
    v = concat([make(tmp_path / "a.mp4", PLAIN, 2.0), make(tmp_path / "b.mp4", BUSY, 3.0), make(tmp_path / "c.mp4", CARD, 6.0), make(tmp_path / "d.mp4", BUSY, 3.0)], tmp_path / "v.mp4")
    c = R.scorecard(v, "16:9")
    assert 1.5 <= c["hook_s"] <= 2.5                                                         # nothing is on screen for the first two seconds
    assert any(5.0 <= s <= 5.5 and 10.5 <= e <= 11.5 for s, e in c["empty_stretches"]), c["empty_stretches"]
    assert 5.0 < c["empty_longest_s"] < 7.0
    kinds = [m["kind"] for m in c["worst"]]
    assert "empty" in kinds and "hook" in kinds and c["risk"] > 35
    worst = c["worst"][0]
    assert worst["kind"] == "empty" and 4.5 <= worst["t0"] <= 5.5                           # the longest problem comes first, with its time


def test_a_lively_video_scores_well(tmp_path):
    c = R.scorecard(make(tmp_path / "busy.mp4", BUSY, 8.0), "9:16")
    assert c["hook_s"] <= 0.5 and c["empty_longest_s"] == 0 and c["gaps_over_target"] == 0 and c["risk"] <= 15, c
    assert R.verdict(c).startswith("Strong")


def test_the_gap_target_depends_on_the_shape(tmp_path):
    v = concat([make(tmp_path / "a.mp4", BUSY, 1.0), make(tmp_path / "b.mp4", CARD, 3.5), make(tmp_path / "c.mp4", BUSY, 1.0)], tmp_path / "v.mp4")
    assert R.scorecard(v, "9:16")["gaps_over_target"] >= 1                                   # 3.5 s without a change is too long for a tall video ...
    assert R.scorecard(v, "16:9")["gaps_over_target"] >= 1                                   # ... and for a wide one: the rule is 3 s in every shape


def test_dead_air_and_fast_captions_are_reported(tmp_path):
    import soundfile as sf

    x = np.concatenate([0.3 * np.sin(2 * np.pi * 300 * np.arange(16000 * 2) / 16000), np.zeros(16000 * 2), 0.3 * np.sin(2 * np.pi * 300 * np.arange(16000 * 2) / 16000)]).astype("float32")
    sf.write(str(tmp_path / "voice.wav"), x, 16000)
    assert R.dead_air(tmp_path / "voice.wav")[0][0] == pytest.approx(2.0, abs=0.2)
    caps = [{"start": 0, "end": 1.0, "words": [{"text": "a"}] * 8}, {"start": 2, "end": 4, "words": [{"text": "a"}] * 6}]
    assert [round(w) for _, _, w in R.reading_speed(caps)] == [8]                               # only the fast one


def test_the_api_scores_an_export_and_lists_the_summary(ref, tmp_path):
    from fastapi.testclient import TestClient

    from vt.server.app import app

    c = TestClient(app)
    assert c.post("/api/projects/reference/retention").status_code == 409                    # nothing exported yet
    ref.exports_dir.mkdir(parents=True, exist_ok=True)
    v = concat([make(tmp_path / "a.mp4", BUSY, 2.0), make(tmp_path / "b.mp4", CARD, 6.0), make(tmp_path / "c.mp4", BUSY, 2.0)], ref.exports_dir / "reference-16x9-20260101-000000.mp4")
    card = c.post("/api/projects/reference/retention").json()
    assert card["aspect"] == "16:9" and card["empty_longest_s"] > 4 and card["verdict"].startswith("Risky") and "empty" in [m["kind"] for m in card["worst"]]            # (the reference voice is silent: dead air is reported too)
    listed = c.get("/api/projects/reference/exports").json()[0]
    assert listed["retention"]["risk"] == card["risk"] and listed["retention"]["worst"] == card["worst"]
    assert c.post("/api/projects/reference/retention?name=nope.mp4").status_code == 409
