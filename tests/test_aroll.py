"""A-roll: the speaker's picture is cut with the voice's cuts so picture time = voice time, kept apart from B-roll, and shown where nothing better illustrates the words."""
import subprocess

import numpy as np
import pytest
import soundfile as sf

from vt import aroll as AR
from vt.schema import Cuts
from vt.util import find_tool, write_json

FF = find_tool("ffmpeg")


def ramp_video(path, seconds=20, with_audio=True):
    """A grey picture whose brightness is 12 x time (0 at the start, about 240 at 20 s): the frame at any moment says which source second it came from."""
    cmd = [FF, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s=320x180:r=30:d={seconds},geq=lum='min(255,T*12)':cb=128:cr=128"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", str(path)]
    subprocess.run(cmd, check=True)
    return path


def luminance_at(video, t):
    r = subprocess.run([FF, "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=16:9,format=gray", "-f", "rawvideo", "-"], capture_output=True)
    return float(np.frombuffer(r.stdout, dtype=np.uint8).mean())


def video_project(ref, tmp_path, keep):
    """The reference project, but made from a video: its input is the ramp video and its cuts keep only `keep`."""
    for f in ref.dir.glob("input.*"):
        f.unlink()
    ramp_video(ref.dir / "input.mp4")
    cuts = Cuts(source_duration=20.0, keep=keep)
    write_json(ref.cuts_path, cuts.model_dump())
    return ref


def test_only_a_real_picture_counts_as_a_video(tmp_path):
    assert AR.video_info(ramp_video(tmp_path / "v.mp4"))["width"] == 320
    sf.write(str(tmp_path / "a.wav"), np.zeros(16000, dtype="float32"), 16000)
    assert AR.video_info(tmp_path / "a.wav") is None
    subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i", "sine=duration=1", str(tmp_path / "a.mp3")], check=True)
    assert AR.video_info(tmp_path / "a.mp3") is None
    subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=64x64:d=1:r=1", "-frames:v", "1", str(tmp_path / "cover.png")], check=True)
    subprocess.run([FF, "-y", "-v", "error", "-i", str(tmp_path / "a.mp3"), "-i", str(tmp_path / "cover.png"), "-map", "0", "-map", "1", "-c", "copy", "-disposition:v", "attached_pic",
                    str(tmp_path / "cover.mp3")], check=True)
    assert AR.video_info(tmp_path / "cover.mp3") is None                           # cover art inside an audio file is not a talking head


def test_the_filter_plays_the_kept_ranges_in_order_and_limits_the_size():
    f = AR.filter_script([(1.0, 3.0), (5.5, 9.0)], 1920, 3840, 2160)
    assert "trim=start=1.000:end=3.000" in f and "trim=start=5.500:end=9.000" in f and "concat=n=2:v=1:a=0" in f and "scale=" in f
    assert "scale=" not in AR.filter_script([(0, 1)], 1920, 1280, 720)


def test_the_picture_is_cut_like_the_voice_so_each_moment_matches(ref, tmp_path):
    p = video_project(ref, tmp_path, keep=[(2.0, 6.0), (10.0, 14.0)])               # output 0-4 s = source 2-6 s, output 4-8 s = source 10-14 s
    item = AR.build(p)
    assert item.id == "aroll" and item.role == "a_roll" and 7.8 < item.duration < 8.3 and (p.dir / item.file).exists()
    video = p.dir / item.file
    for out_t, src_t in ((0.5, 2.5), (3.5, 5.5), (4.5, 10.5), (7.0, 13.0)):
        got = luminance_at(video, out_t)
        assert abs(got - 12 * src_t) < 14, (out_t, src_t, got)                      # within about one source second
    assert subprocess.run([find_tool("ffprobe"), "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip() == ""   # no sound in it
    assert AR.build(p) is not None and next(m for m in p.meta().media if m.id == "aroll")                      # again: cached
    assert [m.id for m in p.meta().planner_media()] == []                           # the planners never see it as B-roll
    # the cuts change: the picture is cut again
    write_json(p.cuts_path, Cuts(source_duration=20.0, keep=[(0.0, 3.0)]).model_dump())
    again = AR.build(p)
    assert again.duration < 3.4 and abs(luminance_at(p.dir / again.file, 2.5) - 12 * 2.5) < 14


def test_no_picture_means_no_aroll(ref):
    assert AR.build(ref) is None                                                     # the reference project is made from audio


def _plan(ref):
    from vt.planner import plan_rules

    sf = plan_rules(ref.transcript(), ref.beats(), ref.meta().theme, language="bn")
    return sf


def test_the_speaker_opens_the_video_and_replaces_weak_visuals_only(ref, tmp_path):
    from vt.schema import MediaItem

    sf = _plan(ref)
    types = [[getattr(e, "type", "") for e in s.elements] for s in sf.scenes]
    item = MediaItem(id="aroll", file="media/aroll.mp4", kind="video", role="a_roll", width=320, height=180, duration=18.0, fx=0.5, fy=0.4, faces=[[0.4, 0.2, 0.2, 0.3]])
    ref.update_meta(media=[item])
    n = AR.apply_speaker(sf, ref, ref.beats(), "9:16", item)
    assert n >= 1 and sf.scenes[0].backdrop.media == "aroll" and sf.scenes[0].archetype == "speaker"
    for s, t in zip(sf.scenes[1:], types[1:]):
        if s.backdrop and s.backdrop.media == "aroll":
            assert all(x in AR.WEAK for x in t)                                      # a chart, a card or steps are never replaced by the speaker
            assert len(s.elements) <= 1
    run, worst = 0, 0
    for s in sf.scenes:
        run = run + 1 if s.backdrop and s.backdrop.media == "aroll" else 0
        worst = max(worst, run)
    assert worst <= 2                                                                # the picture changes now and then
    punches = [bool(s.backdrop and s.backdrop.media == "aroll" and s.backdrop.motion == "kenburns") for s in sf.scenes]
    assert not any(a and b for a, b in zip(punches, punches[1:]))                    # never two punch-ins in a row


def test_the_composition_follows_the_cuts_through_the_scene_start(ref):
    from vt.compose import compose_project
    from vt.schema import MediaItem
    import json

    sf = _plan(ref)
    item = MediaItem(id="aroll", file="media/aroll.mp4", kind="video", role="a_roll", width=320, height=180, duration=18.0, fx=0.5, fy=0.4)
    (ref.dir / "media").mkdir(exist_ok=True)
    ramp_video(ref.dir / "media" / "aroll.mp4", 18, False)
    ref.update_meta(media=[item])
    AR.apply_speaker(sf, ref, ref.beats(), "9:16", item)
    sf.scenes[0].backdrop = sf.scenes[0].backdrop.model_copy(update={"offset": 99.0})        # a stale offset in the plan...
    ref.save_scenes(sf)
    data = json.loads((compose_project(ref, "9:16").parent / "data.json").read_text(encoding="utf-8"))
    bd = data["scenes"][0]["backdrop"]
    assert bd["offset"] == data["scenes"][0]["start"] and data["media"]["aroll"]["role"] == "a_roll" and data["media"]["aroll"]["loop"] is False      # ...is replaced by the scene's start


def test_the_api_puts_the_speaker_on_the_plan_and_takes_it_off_again(ref, tmp_path):
    from fastapi.testclient import TestClient

    from vt.schema import MediaItem
    from vt.server.app import app

    c = TestClient(app)
    assert c.post("/api/projects/reference/aroll/apply").status_code == 409                    # made from audio: no speaker's picture
    item = MediaItem(id="aroll", file="media/aroll.mp4", kind="video", role="a_roll", width=320, height=180, duration=18.0, fx=0.5, fy=0.3, faces=[[0.4, 0.1, 0.2, 0.3]])
    (ref.dir / "media").mkdir(exist_ok=True)
    ramp_video(ref.dir / "media" / "aroll.mp4", 18, False)
    ref.update_meta(media=[item])
    _plan(ref)
    ref.save_scenes(_plan(ref))
    r = c.post("/api/projects/reference/aroll/apply").json()
    assert r["scenes"] >= 1
    scenes = c.get("/api/projects/reference/scenes").json()["plan"]["scenes"]
    assert scenes[0]["backdrop"]["media"] == "aroll" and scenes[0]["layout"] == "lower"
    assert c.post("/api/projects/reference/aroll/apply?on=false").json()["scenes"] == 0
    assert not any(s.get("backdrop") for s in c.get("/api/projects/reference/scenes").json()["plan"]["scenes"])


def test_a_two_shot_is_framed_on_one_person_not_between_them():
    # the owner's podcast clip (2026-10-24): the vertical crop of the wide shot showed the empty shelf between host and guest
    import numpy as np

    from vt import people as PE
    from vt.aroll import head_focus

    g = np.zeros((PE.GH, PE.GW), dtype=bool)
    g[6:27, 4:13] = True              # guest on the left, a little bigger
    g[7:27, 36:44] = True             # host on the right
    rows = ["".join("1" if v else "0" for v in r) for r in g]
    fx, _ = head_focus(rows, 16 / 9, (0.5, 0.4))
    assert fx < 0.2                   # the crop goes to the left person (0 = far left), not the middle (0.5)
    fx2, _ = head_focus(rows, 16 / 9, (0.9, 0.4))
    assert fx2 < 0.2                  # the bigger one wins even when the usual position is on the right


def _clip(path, frames):
    import subprocess

    import numpy as np

    h, w = frames[0].shape
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", "1", "-i", "-",
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", str(path)], input=b"".join(np.asarray(f, dtype=np.uint8).tobytes() for f in frames))
    assert p.returncode == 0


def test_subtitles_burned_into_the_picture_are_found(tmp_path):
    # the owner's podcast clip (2026-10-24) has its own captions on key lines; a vertical crop cut them off next to ours
    import numpy as np

    from vt.aroll import text_band

    plain = np.full((360, 640), 40, dtype=np.uint8)
    captioned = plain.copy()
    for x in range(140, 500, 14):                                   # white lettering on one line, low in the frame
        captioned[300:322, x:x + 8] = 255
    _clip(tmp_path / "subs.mp4", [captioned if i % 4 == 0 else plain for i in range(16)])
    band = text_band(tmp_path / "subs.mp4", 16)
    assert band is not None and 0.75 < band < 0.85

    shirt = plain.copy()
    shirt[200:360, 150:490] = 240                                   # a white shirt: big, not a line of text
    _clip(tmp_path / "shirt.mp4", [shirt] * 16)
    assert text_band(tmp_path / "shirt.mp4", 16) is None
    _clip(tmp_path / "plain.mp4", [plain] * 16)
    assert text_band(tmp_path / "plain.mp4", 16) is None


def test_scene_framing_follows_the_face_and_ignores_a_lone_detection():
    from vt.aroll import face_focus_in_scene

    assert face_focus_in_scene([[0.4, 0.2, 0.2, 0.25]], 16 / 9) is None                       # one frame only: maybe a poster
    fx, fy = face_focus_in_scene([[0.4, 0.2, 0.2, 0.25], [0.42, 0.21, 0.2, 0.25], [0.41, 0.2, 0.2, 0.25]], 16 / 9)
    vw = (9 / 16) / (16 / 9)
    assert abs((fx * (1 - vw) + vw / 2) - 0.51) < 0.02 and isinstance(fx, float)            # the face centre lands in the middle of the vertical crop


def test_camera_cuts_are_found_and_each_shot_gets_a_target(tmp_path, monkeypatch):
    # the owner's podcast (2026-10-24): one framing per scene missed the face whenever the camera cut inside a scene
    import numpy as np

    from vt import aroll

    dark, light = np.full((360, 640), 30, dtype=np.uint8), np.full((360, 640), 200, dtype=np.uint8)
    _clip(tmp_path / "cuts.mp4", [dark] * 3 + [light] * 3 + [dark] * 2)            # 1 fps: shots 0-3 s, 3-6 s, 6-8 s
    monkeypatch.setattr("vt.director.media.detect_faces", lambda rgb, limit=1: [])
    calls = []
    monkeypatch.setattr(aroll, "head_centre", lambda rgb, prefer_x=0.5: calls.append(1) or (0.3 if rgb.mean() < 100 else 0.7, 0.3))
    shots = aroll.shot_track(tmp_path / "cuts.mp4", 8.0)
    assert [(s[0], s[1]) for s in shots] == [(0.0, 3.0), (3.0, 6.0), (6.0, 8.0)]
    assert [s[2] for s in shots] == [0.3, 0.7, 0.3] and len(calls) == 3
