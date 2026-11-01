from vt.schema import Cuts
from vt.stages import words as W


def raw(*items):
    return {"words": [{"text": t, "start": s, "end": e, "conf": c} for t, s, e, c in items]}


def test_ids_come_from_raw_index_and_times_map_through_cuts():
    r = raw(("এক", 0.0, 0.4, 0.9), ("ফিলার", 1.0, 1.3, 0.9), ("দুই", 3.0, 3.4, 0.9))
    cuts = Cuts(source_duration=4, keep=[(0, 0.6), (2.5, 4)])  # the middle word lies in a removed range
    tr = W.build_transcript(r, cuts)
    assert [w.id for w in tr.words] == ["w1", "w3"]
    assert tr.words[0].start == 0.0
    assert abs(tr.words[1].start - (0.6 + 0.5)) < 1e-6  # 0.6 s kept + 0.5 s into the second range


def test_glossary_edits_and_language_tags():
    r = raw(("yield।", 0.0, 0.5, 0.9), ("থাকবে", 0.6, 1.0, 0.3))
    cuts = Cuts(source_duration=2, keep=[(0, 2)])
    tr = W.build_transcript(r, cuts, {"yield": "ইয়েল্ড"}, edits={"w2": {"text": "থাকবে,"}})
    assert tr.words[0].text == "ইয়েল্ড।"           # punctuation preserved
    assert tr.words[0].lang == "bn"
    assert tr.words[1].text == "থাকবে," and tr.words[1].flag is None  # edited words are no longer flagged
    tr2 = W.build_transcript(r, cuts)
    assert tr2.words[0].lang == "en" and tr2.words[1].flag == "review"


def test_find_fillers_and_repeats():
    r = raw(("উম", 0, 0.2, 1), ("আজকে", 0.3, 0.6, 1), ("মানে", 0.7, 0.9, 1), ("মানে", 0.95, 1.2, 1), ("um", 1.3, 1.4, 1), ("ভালো", 1.5, 1.9, 1))
    assert W.find_fillers(r["words"]) == {0, 2, 4}


def test_beats_split_on_punctuation_and_pause_and_merge_singletons():
    r = raw(("এক", 0, .3, 1), ("দুই।", .4, .7, 1), ("তিন", .8, 1.1, 1), ("চার", 2.0, 2.3, 1), ("পাঁচ", 2.4, 2.7, 1))
    tr = W.build_transcript(r, Cuts(source_duration=3, keep=[(0, 3)]))
    beats = W.build_beats(tr)
    # "তিন" is a one-word fragment (a long pause follows it), so it joins the previous beat instead of flickering as its own scene
    assert [b.text for b in beats.beats] == ["এক দুই। তিন", "চার পাঁচ"]
    assert beats.beats[0].start == 0.0 and beats.beats[1].end == 2.7
    flat = [w for b in beats.beats for w in b.word_ids]
    assert flat == [w.id for w in tr.words]  # every word in exactly one beat, in order


def test_unpunctuated_speech_is_split_at_the_biggest_pause_not_at_a_word_count():
    """The Bangla model emits no punctuation: a 14-word run must break at the natural pause, not after word 12."""
    ws, t = [], 0.0
    for i in range(14):
        gap = 0.42 if i == 6 else 0.05                      # a clear (but < 0.5 s) pause after the 7th word
        ws.append({"text": f"শব্দ{i}", "start": t, "end": t + 0.3, "conf": 1})
        t += 0.3 + gap
    tr = W.build_transcript({"words": ws}, Cuts(source_duration=t + 1, keep=[(0, t + 1)]))
    beats = W.build_beats(tr, max_words=12)
    assert [len(b.word_ids) for b in beats.beats] == [7, 7]
