"""The visual heartbeat: long stills get a related visual at a spoken word; nothing unrelated, nothing on scenes that already move."""
import pytest

from vt.director import heartbeat as HB
from vt.planner import plan_rules
from vt.planner.catalogue import all_icon_names
from vt.schema import Backdrop, Scrim, Sticker, Transcript, Word, validate_scenes
from vt.stages.words import build_beats

SENTENCE = "Money grows when you save money every month because small savings become large wealth over many years of patience"


def one_scene(step=0.42, text=SENTENCE):
    toks = text.split()
    ws = [Word(id=f"w{i}", text=t, start=round(i * step, 2), end=round(i * step + step - 0.05, 2), conf=0.95, lang="en") for i, t in enumerate(toks, 1)]
    tr = Transcript(language="en", words=ws)
    beats = build_beats(tr, max_words=40, pause=5.0)                              # one long sentence: one beat, one scene
    sf = plan_rules(tr, beats, "paper", language="en")
    assert len(sf.scenes) == 1
    sc = sf.scenes[0]
    sc.elements = [Sticker(at_word="w1", emoji="1f4b0", label="Money")]            # one picture, then nothing for about 8 s
    return tr, beats, sf


def gaps(sf, tr, beats):
    sc = sf.scenes[0]
    t0, t1 = beats.beats[0].start, beats.beats[-1].end
    times = sorted([t0] + [{w.id: w for w in tr.words}[e.at_word].start for e in sc.elements] + [t1])
    return [y - x for x, y in zip(times, times[1:])]


def test_a_long_still_gets_related_visuals_at_spoken_words_and_no_gap_stays_long():
    tr, beats, sf = one_scene()
    assert max(gaps(sf, tr, beats)) > 7
    n = HB.add_heartbeats(sf, tr, beats, "16:9")
    sc = sf.scenes[0]
    assert n >= 2 and len(sc.elements) <= HB.MAX_ELEMENTS
    assert max(gaps(sf, tr, beats)) <= 3.0, gaps(sf, tr, beats)                    # the owner's rule: something on screen at least every 3 s
    words = {w.id: w.text.lower() for w in tr.words}
    for e in sc.elements[1:]:
        assert e.at_word in words                                                  # each one is tied to a word that is really spoken ...
        label = (getattr(e, "label", "") or getattr(e, "text", "")).lower()
        assert label and label.strip(" .") in words[e.at_word] or words[e.at_word] in label                # ... and shows that word, not something else
        assert words[e.at_word] not in {"the", "and", "when", "you", "because", "over", "many", "of"}          # never a function word
    assert not validate_scenes(sf, tr, beats, all_icon_names())
    assert HB.add_heartbeats(sf, tr, beats, "16:9") == 0                            # a second run changes nothing


def test_a_tall_video_gets_more_changes_than_a_wide_one():
    tr, beats, tall = one_scene()
    _, _, wide = one_scene()
    HB.add_heartbeats(tall, tr, beats, "9:16")
    HB.add_heartbeats(wide, tr, beats, "16:9")
    assert len(tall.scenes[0].elements) >= len(wide.scenes[0].elements)
    assert max(gaps(tall, tr, beats)) <= 3.0, gaps(tall, tr, beats)          # (a last stretch with no real word to show stays still on purpose)


def test_scenes_that_already_move_or_hold_a_picture_are_left_alone():
    tr, beats, sf = one_scene()
    sf.scenes[0].backdrop = Backdrop(media="aroll", motion="none", scrim=Scrim())      # the speaker's own picture
    assert HB.add_heartbeats(sf, tr, beats, "16:9") == 0 and len(sf.scenes[0].elements) == 1
    tr, beats, sf = one_scene()
    sf.scenes[0].stick = {"set": {}, "cast": [], "actions": []}                         # a stick-figure scene
    assert HB.add_heartbeats(sf, tr, beats, "16:9") == 0
    tr, beats, sf = one_scene()
    sf.scenes[0].elements.append(type("Chart", (), {"type": "bar_chart", "at_word": "w1"})())     # something that animates inside
    assert HB.add_heartbeats(sf, tr, beats, "16:9") == 0


def test_a_short_scene_is_not_touched():
    tr, beats, sf = one_scene(step=0.3, text="Money grows when you save")
    assert HB.add_heartbeats(sf, tr, beats, "9:16") == 0


def test_a_very_long_scene_is_helped_but_never_crowded():
    tr, beats, sf = one_scene(step=0.8)                                          # 15 s in one sentence
    before = max(gaps(sf, tr, beats))
    HB.add_heartbeats(sf, tr, beats, "9:16")
    assert len(sf.scenes[0].elements) <= HB.MAX_ELEMENTS and max(gaps(sf, tr, beats)) < before


def test_a_scene_that_stays_still_for_want_of_a_real_word_is_reported_and_the_speaker_takes_it():
    from vt import aroll as AR
    from vt.schema import MediaItem

    tr, beats, sf = one_scene(text="Money grows when you do the " + " ".join(["and"] * 12))          # nothing here is worth a picture
    assert HB.add_heartbeats(sf, tr, beats, "16:9") == 0
    assert HB.still_scenes(sf, tr, beats, "16:9") == ["s1"]
    item = MediaItem(id="aroll", file="media/aroll.mp4", kind="video", role="a_roll", width=1920, height=1080, duration=30.0, fx=0.5, fy=0.3, faces=[[0.45, 0.1, 0.1, 0.2]])
    from vt.project import Project  # noqa: F401

    class P:                                                                        # just enough of a project for the speaker step (no frames are read)
        dir = __import__("pathlib").Path(".")

        def meta(self):
            return type("M", (), {"media": [item]})()
    sf.scenes[0].backdrop = None
    import vt.aroll as A2
    old = A2.person_grid
    A2.person_grid = lambda *a, **k: []
    try:
        n = AR.apply_speaker(sf, P(), beats, "16:9", item, force={"s1"})
    finally:
        A2.person_grid = old
    assert n >= 1 and sf.scenes[0].backdrop is not None and sf.scenes[0].backdrop.media == "aroll"
