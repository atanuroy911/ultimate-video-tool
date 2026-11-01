import numpy as np
import soundfile as sf

from vt.schema import Cuts
from vt.stages import audio as A


def make_wav(path, segments, sr=16000, noise=0.0005):
    """segments: list of (seconds, amplitude). Amplitude 0 = silence."""
    rng = np.random.default_rng(1)
    parts = []
    for sec, amp in segments:
        t = np.arange(int(sec * sr)) / sr
        parts.append(amp * np.sin(2 * np.pi * 220 * t) * (1 + 0.3 * np.sin(2 * np.pi * 3 * t)) + noise * rng.normal(size=len(t)))
    sf.write(str(path), np.concatenate(parts).astype(np.float32), sr)


def test_cuts_time_mapping():
    c = Cuts(source_duration=10, keep=[(0, 2), (4, 6), (8, 10)])
    assert c.output_duration == 6
    assert c.map_time(1.0) == 1.0
    assert c.map_time(5.0) == 3.0          # 2 s kept before + 1 s into the second range
    assert c.map_time(3.0) is None         # inside a removed region
    assert c.map_time_nearest(3.0) == 2.0  # snaps to the boundary
    assert c.map_time_nearest(9.0) == 5.0


def test_cuts_from_removed_merges_and_orders():
    c = A.cuts_from_removed(10, [(5, 6), (2, 3), (2.5, 4)])
    assert c.keep == [(0.0, 2.0), (4.0, 5.0), (6.0, 10.0)]
    assert A.removed_from_cuts(c) == [(2.0, 4.0), (5.0, 6.0)]


def test_silence_detection_and_cut(tmp_path):
    wav = tmp_path / "a.wav"
    # 1.0 s lead silence, 1 s speech, 1.5 s pause, 1 s speech, 2 s trailing silence
    make_wav(wav, [(1.0, 0), (1.0, 0.3), (1.5, 0), (1.0, 0.3), (2.0, 0)])
    sil, dur, thr = A.find_silences(wav, 0.35)
    assert abs(dur - 6.5) < 0.01
    assert len(sil) == 3
    cuts = A.silence_cuts(dur, sil, "normal")
    # leading silence trimmed to LEAD_KEEP, trailing to TAIL_KEEP, inner pause shortened to 2*pad
    assert cuts.output_duration < dur - 2.5
    assert cuts.output_duration > 2.0 + A.LEAD_KEEP  # both speech segments survive
    first_keep_start = cuts.keep[0][0]
    assert 0.7 < first_keep_start < 1.0  # about 1.0 - LEAD_KEEP


def test_apply_cuts_duration_and_no_clicks(tmp_path):
    src = tmp_path / "m.wav"
    sr = 48000
    t = np.arange(sr * 4) / sr
    sf.write(str(src), np.stack([0.4 * np.sin(2 * np.pi * 200 * t)] * 2, axis=1).astype(np.float32), sr)
    cuts = Cuts(source_duration=4, keep=[(0, 1), (2, 3)])
    out = tmp_path / "o.wav"
    dur = A.apply_cuts(src, cuts, out)
    y, osr = sf.read(str(out))
    assert osr == sr and abs(dur - 2.0) < 0.001 and abs(len(y) / sr - 2.0) < 0.001
    # the join (at 1.0 s) is faded so there is no full-scale discontinuity
    j = y[sr - 50: sr + 50, 0]
    assert np.max(np.abs(np.diff(j))) < 0.2
