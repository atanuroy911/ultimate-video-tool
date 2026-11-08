"""hook.frame0 measures what the viewer sees at the first frame, not only the word the first picture is tied to."""
from vt import craft


def _first_late(ref):
    sf = ref.scenes()
    words = [w for w in ref.transcript().kept()]
    sc = sf.scenes[0]
    sc.elements[0].at_word = next(w.id for w in words if w.start - words[0].start > 1.5)   # tied to a word 1.5 s in
    return sf, sc


def test_the_opening_picture_counts_from_the_first_frame(ref):
    sf, sc = _first_late(ref)
    ref.save_scenes(sf)
    assert not any(v["rule"] == "hook.frame0" for v in craft.check(ref)["violations"])      # the composer shows it from 0 s


def test_a_person_timed_late_opening_is_still_reported(ref):
    sf, sc = _first_late(ref)
    sc.backdrop = None
    sc.stick = None
    for e in sc.elements:
        e.start = 2.0
    ref.save_scenes(sf)
    assert any(v["rule"] == "hook.frame0" for v in craft.check(ref)["violations"])


def test_a_cartoon_figure_counts_as_shown_and_its_actions_as_change():
    from types import SimpleNamespace as N

    words = {f"w{i}": N(start=float(i)) for i in range(10)}
    beats = N(beats=[N(id="b1", word_ids=["w1", "w2", "w3"]), N(id="b2", word_ids=["w6", "w7"])])
    stick = {"cast": [{"id": "maya", "name": "Maya"}], "actions": [{"at_word": "w2", "who": "maya", "do": "walk_in"}, {"at_word": "w9", "who": "maya", "do": "point"}]}
    sf = N(scenes=[N(stick=stick, beats=["b1"]), N(stick=None, beats=["b2"])])
    spans, acts = craft._figures(sf, words, beats)
    assert spans == [(1.0, 3.0, {"maya"})] and acts == [2.0, 9.0]
