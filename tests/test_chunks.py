import numpy as np

from vt.stages.chunks import plan_chunks


def test_chunks_end_inside_pauses_and_respect_max_length():
    # speech 0-6, pause, 7-13, pause, 14-20, pause, 21-24; max 15 s -> [0..13], [14..24]
    sil = [(6.0, 7.0), (13.0, 14.0), (20.0, 21.0)]
    ch = plan_chunks(24.0, sil, max_len=15.0, pad=0.15)
    assert len(ch) == 2
    assert ch[0][0] == 0.0 and abs(ch[0][1] - 13.15) < 1e-6      # first chunk ends 0.15 s into the pause
    assert abs(ch[1][0] - 13.85) < 1e-6 and ch[1][1] == 24.0
    assert all(b - a <= 15.0 + 0.31 for a, b in ch)


def test_chunks_cover_all_speech():
    sil = [(1.0, 1.9), (3.6, 4.6), (6.2, 7.2), (9.2, 10.1), (13.6, 15.6), (18.0, 18.9), (21.5, 22.5), (24.4, 25.4), (27.3, 28.3), (31.9, 34.0), (34.7, 35.7), (37.4, 38.4), (40.0, 41.0), (43.0, 43.9), (47.3, 48.2)]
    ch = plan_chunks(48.2, sil)           # the 48 s test recording that lost words with 30 s windows
    assert len(ch) >= 3
    runs = []
    pos = 0.0
    for a, b in sil:
        runs.append((pos, a)); pos = b
    for s, e in runs:                      # every speech run lies fully inside some chunk
        assert any(cs <= s + 1e-6 and e <= ce + 1e-6 for cs, ce in ch), (s, e)
    assert all(b - a <= 15.0 + 0.31 for a, b in ch)


def test_long_unbroken_speech_is_split_at_the_quietest_frame():
    db = np.full(4000, -20.0)
    db[1234] = -60.0                      # quietest moment at 12.34 s, inside the allowed 9..15 s window
    ch = plan_chunks(40.0, [], db, max_len=15.0, pad=0.0)
    assert abs(ch[0][1] - 12.34) < 0.011
    assert all(b - a <= 15.01 for a, b in ch) and ch[-1][1] == 40.0


def test_tiny_fragments_are_ignored_and_empty_audio_gives_no_chunks():
    assert plan_chunks(5.0, [(0.0, 4.9)]) == []
    assert plan_chunks(0.0, []) == []
