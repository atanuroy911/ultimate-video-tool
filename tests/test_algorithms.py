"""The research algorithms behind the editor's judgement: LexRank + MMR, prosodic arousal, L1-optimal camera path, pause-based sentences."""
import subprocess

import numpy as np
import pytest

from vt import camerapath, pausesplit, prosody, saliency
from vt.util import find_tool


# ---------------------------------------------------------------- LexRank / MMR
def test_lexrank_puts_the_central_sentence_first_and_the_aside_last():
    sentences = [
        "Saving money is simple when you start small.",
        "Put away ten percent of what you earn every month.",
        "Ten percent of your earnings, saved monthly, grows fast.",
        "Saving a small share every month is the whole trick.",
        "My cat knocked a glass off the table yesterday.",
    ]
    scores = saliency.lexrank(sentences)
    assert len(scores) == 5 and abs(sum(scores) / 5 - 1.0) < 1e-6
    assert scores.index(min(scores)) == 4            # the aside shares no words with the talk
    assert scores[1] > scores[4] and scores[3] > scores[4]


def test_lexrank_handles_bangla_and_degenerate_input():
    assert saliency.lexrank([]) == []
    assert saliency.lexrank(["একটা বাক্য"]) == [1.0]
    scores = saliency.lexrank(["নেকড়ে বকের কাছে গেল", "বক নেকড়ের গলা থেকে হাড় বের করল", "আজ আবহাওয়া খুব সুন্দর"])
    assert scores[2] < scores[0] and scores[2] < scores[1]


def test_mmr_prefers_different_items_over_near_duplicates():
    relevance = [1.0, 0.95, 0.6]
    similarity = [[1, 0.95, 0.1], [0.95, 1, 0.1], [0.1, 0.1, 1]]
    assert saliency.mmr_select(relevance, similarity, 2, lam=0.7) == [0, 2]
    assert saliency.mmr_select(relevance, similarity, 2, lam=1.0) == [0, 1]       # λ=1: plain relevance order


# ---------------------------------------------------------------- pauses → sentences
def test_pause_threshold_adapts_to_the_speaker():
    fast = [0.05] * 30 + [0.3] * 3
    slow = [0.3] * 30 + [0.8] * 3
    assert pausesplit.FLOOR <= pausesplit.pause_threshold(fast) < pausesplit.pause_threshold(slow) <= pausesplit.CEILING
    assert pausesplit.pause_threshold([]) == 0.45


def test_boundaries_from_pauses_without_punctuation():
    words, t = [], 0.0
    for k in range(24):
        words.append({"text": f"w{k}", "start": round(t, 2), "end": round(t + 0.25, 2)})
        t += 0.25 + (0.9 if k in (7, 15) else 0.06)
    ends = pausesplit.boundaries(words)
    assert ends == [7, 15, 23]


def test_tiny_fragments_join_their_neighbour():
    words = [{"text": "a", "start": 0, "end": 0.2}, {"text": "b.", "start": 0.25, "end": 0.4}, {"text": "c", "start": 0.5, "end": 0.7},
             {"text": "d", "start": 0.75, "end": 0.9}, {"text": "e", "start": 0.95, "end": 1.1}, {"text": "f.", "start": 1.15, "end": 1.3}]
    assert pausesplit.boundaries(words) == [5]


# ---------------------------------------------------------------- camera path
def test_l1_path_is_still_for_a_steady_face_and_pans_for_a_drift():
    jitter = 0.5 + 0.02 * np.sin(np.arange(40))
    still = camerapath.optimal_path(jitter, margin=0.08)
    assert np.ptp(still) < 0.005                                          # jitter inside the margin: a locked camera
    drift = np.concatenate([np.full(20, 0.3), np.linspace(0.3, 0.7, 20), np.full(20, 0.7)])
    path = camerapath.optimal_path(drift, margin=0.05)
    assert abs(path[0] - 0.3) <= 0.051 and abs(path[-1] - 0.7) <= 0.051  # the face stays inside the crop
    assert len(camerapath.knots(path)) <= 8                               # a handful of steady pieces, not 60 twitches


def test_l1_path_ignores_frames_without_a_face():
    centres = np.array([0.4, np.nan, np.nan, 0.42, 0.41, np.nan, 0.4, 0.39])
    path = camerapath.optimal_path(centres, margin=0.05)
    assert np.all(np.isfinite(path)) and np.ptp(path) < 0.03


# ---------------------------------------------------------------- arousal
def _tone(path, seconds, freq, gain):
    subprocess.run([find_tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}", "-af", f"volume={gain}",
                    "-ar", "16000", str(path)], check=True)


def test_pitch_tracker_finds_a_sine():
    x = np.sin(2 * np.pi * 180 * np.arange(16000) / 16000).astype(np.float32)
    _, f0, _ = prosody.frame_features(x)
    voiced = f0[np.isfinite(f0)]
    assert len(voiced) > 50 and abs(np.median(voiced) - 180) < 4


def test_arousal_is_higher_where_the_voice_is_higher_and_louder(tmp_path):
    calm, excited = tmp_path / "calm.wav", tmp_path / "excited.wav"
    _tone(calm, 3, 120, 0.3)
    _tone(excited, 3, 240, 1.0)
    both = tmp_path / "both.wav"
    subprocess.run([find_tool("ffmpeg"), "-v", "error", "-y", "-i", str(calm), "-i", str(excited), "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1", str(both)], check=True)
    scores = prosody.arousal_for(both, [(0.0, 3.0), (3.0, 6.0)])
    assert scores[1] > scores[0]


def test_arousal_without_audio_is_zero():
    assert prosody.arousal_for(pytest.importorskip("pathlib").Path("nowhere.wav"), [(0, 1), (1, 2)]) == [0.0, 0.0]
