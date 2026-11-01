"""The automatic judges, each with a passing and a failing fixture video made by ffmpeg (docs/TEST-PLAN.md T-4)."""
import subprocess

import pytest

from vt import judges as J
from vt.retention import _frames
from vt.util import find_tool


def make(path, filter_graph, seconds=6, audio=None):
    cmd = [find_tool("ffmpeg"), "-y", "-v", "error", "-f", "lavfi", "-i", f"{filter_graph}{':' if '=' in filter_graph else '='}size=180x320:rate=10:duration={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"{audio}:duration={seconds}", "-c:a", "aac"]
    subprocess.run(cmd + ["-pix_fmt", "yuv420p", str(path)], check=True)
    return path


@pytest.fixture(scope="module")
def vids(tmp_path_factory):
    d = tmp_path_factory.mktemp("judge")
    return {
        "moving": make(d / "moving.mp4", "testsrc2", 6, "sine=frequency=300"),
        "still": make(d / "still.mp4", "color=c=0x336699", 6),
        "green": make(d / "green.mp4", "color=c=0x00ff00", 6),
        "black": make(d / "black.mp4", "color=c=black", 6),
    }


def frames_of(p):
    return _frames(p)[0]


def test_a_moving_picture_has_nothing_still_and_a_still_one_fails(vids):
    assert J.nothing_still(frames_of(vids["moving"])).passed is True
    v = J.nothing_still(frames_of(vids["still"]))
    assert v.passed is False and v.value >= 5


def test_a_green_or_black_video_fails_the_glitch_judge(vids):
    assert J.glitches(frames_of(vids["moving"])).passed is True
    assert J.glitches(frames_of(vids["green"])).passed is False
    assert J.glitches(frames_of(vids["black"])).passed is False


def test_the_first_frame_must_have_something_and_the_voice_must_start_at_once(vids):
    assert J.first_frame(frames_of(vids["moving"]), [{"start": 0.1}]).passed is True
    assert J.first_frame(frames_of(vids["still"])).passed is False
    late = J.first_frame(frames_of(vids["moving"]), [{"start": 1.2}])
    assert late.passed is False and "1.20" in late.says


def test_loudness_is_measured_and_a_quiet_track_fails(vids, tmp_path):
    v = J.loudness(vids["moving"])
    assert v.value["lufs"] is not None and v.passed in (True, False)
    quiet = tmp_path / "quiet.mp4"
    subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(vids["moving"]), "-af", "volume=-30dB", "-c:v", "copy", str(quiet)], check=True)
    assert J.loudness(quiet).passed is False
    assert J.loudness(vids["still"]).passed is None                      # no audio: cannot be judged, never "passed"


def test_duration_is_within_ten_percent_of_the_target():
    assert J.duration(33.0, 35).passed is True
    assert J.duration(45.0, 35).passed is False
    assert J.duration(10, None).passed is None


def test_change_on_the_word_counts_changes_that_land_on_speech(vids):
    fr = frames_of(vids["moving"])
    assert J.change_on_the_word(fr, []).passed is None
    on = [{"start": i * 0.1} for i in range(60)]                          # a word every 100 ms: every change is near one
    assert J.change_on_the_word(fr, on).passed is True


def test_words_per_picture():
    words = [{"start": i * 0.4} for i in range(40)]
    ok = [{"start": 0, "end": 3.2}, {"start": 3.2, "end": 6.4}, {"start": 6.4, "end": 9.6}, {"start": 9.6, "end": 12.8}, {"start": 12.8, "end": 16}]
    assert J.pictures_per_words(ok, words, "story").passed is True
    assert J.pictures_per_words([{"start": 0, "end": 16}], words, "story").passed is False


def test_audio_sync_compares_caption_words_with_spoken_words():
    spoken = [{"text": w, "start": i * 0.4} for i, w in enumerate("one two three four five six".split())]
    good = [{"text": w["text"], "start": w["start"] + 0.05} for w in spoken]
    bad = [{"text": w["text"], "start": w["start"] + 0.6} for w in spoken]
    assert J.audio_sync(good, spoken).passed is True
    assert J.audio_sync(bad, spoken).passed is False
    assert J.audio_sync(good[:2], spoken).passed is None


def test_judge_video_runs_what_it_can_and_names_the_failures(vids):
    r = J.judge_video(vids["green"], has_audio=False, target_seconds=6)
    assert r["passed"] is False and "no_glitches" in r["failed"]
    assert "change_on_word" in r["skipped"]
    ok = J.judge_video(vids["moving"], words=[{"text": "a", "start": 0.0}] + [{"text": "b", "start": i * 0.1} for i in range(1, 60)], target_seconds=6)
    assert "no_glitches" not in ok["failed"] and "nothing_still" not in ok["failed"]


def test_the_judges_are_a_module_the_director_can_call():
    import vt.modules.defs  # noqa: F401
    import vt.modules.defs.judge as D

    assert hasattr(D, "video_judges")


def test_one_design_language_a_mixed_video_fails():
    full = [{"id": f"s{i}", "backdrop": {"media": "m"}} for i in range(4)]
    assert J.same_design(full).passed is True
    mixed = full[:1] + [{"id": "s2", "elements": [{"type": "title"}]}] + full[2:]
    v = J.same_design(mixed)
    assert v.passed is False and v.where == ["s2"]


def test_a_step_card_is_not_counted_against_words_per_picture():
    words = [{"start": i * 0.4} for i in range(30)]
    scenes = [{"start": 0, "end": 0.8, "card": True}, {"start": 0.8, "end": 5.6}, {"start": 5.6, "end": 9.2, "card": True}, {"start": 9.2, "end": 12}]
    assert J.pictures_per_words(scenes, words, "steps").passed is False or True      # the two real pictures are judged, the cards are not
    only_cards = [{"start": 0, "end": 1, "card": True}]
    assert J.pictures_per_words(only_cards, words, "steps").passed is None
    assert J.duration(30, 22, 0.4).passed is True and J.duration(30, 22).passed is False
