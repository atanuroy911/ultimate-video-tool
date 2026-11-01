import numpy as np
import pytest

from vt import beatsync as B


def clicks(bpm: float, offset: float, seconds: float = 30.0) -> np.ndarray:
    x = np.random.default_rng(0).normal(0, 0.003, int(B.SR * seconds)).astype(np.float32)
    burst = (np.sin(np.arange(400) * 0.6) * np.exp(-np.arange(400) / 80)).astype(np.float32)
    for t in np.arange(offset, seconds - 0.1, 60 / bpm):
        i = int(t * B.SR)
        x[i:i + 400] += burst
    return x


@pytest.mark.parametrize("bpm,offset", [(96.0, 0.21), (128.0, 0.0), (75.0, 0.5)])
def test_tempo_and_phase_are_found(bpm, offset):
    got_bpm, got_off = B.estimate(clicks(bpm, offset))
    assert abs(got_bpm - bpm) < 0.5
    step = 60 / bpm
    assert min(abs(got_off - offset) % step, step - abs(got_off - offset) % step) < 0.03


def test_snapping_is_small_and_stays_in_the_scene():
    beats = B.beat_times(120, 0.0, 10)               # every 0.5 s
    assert B.snap(1.08, beats, 0, 5) == 1.0           # 80 ms early: lands on the beat
    assert B.snap(1.25, beats, 0, 5) == 1.25          # between beats: left alone
    assert B.snap(4.95, beats, 0, 4.9) == 4.95        # the beat would be outside the scene


def test_apply_moves_elements_and_cues_but_not_the_opening_picture():
    data = {"duration": 6.0, "scenes": [
        {"start": 0.0, "end": 3.0, "elements": [{"at": 0.0}, {"at": 1.07}], "sfx": [{"t": 2.04, "id": "pop"}]},
        {"start": 3.0, "end": 6.0, "elements": [{"at": 3.0}, {"at": 4.6}]}]}
    n = B.apply(data, 120, 0.0)
    s1, s2 = data["scenes"]
    assert s1["elements"][0]["at"] == 0.0 and s1["elements"][1]["at"] == 1.0 and s1["sfx"][0]["t"] == 2.0
    assert s2["elements"][1]["at"] == 4.5 and n == 3 and data["beat_sync"]["moved"] == 3
