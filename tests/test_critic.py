"""The editor's critic, the enricher and the revise loop (vt/script/critic.py, planner.revise)."""
import pytest

from vt.schema import Beat, Beats, Transcript, Word
from vt.script import planner as PL
from vt.script.critic import MAX_STILL, enrich, review
from vt.script.models import VideoScript


def _talk(n_words=24, step=0.5):
    words = [Word(id=f"w{i}", text=("Why?" if i == 9 else "money" if i % 5 else "100"), start=i * step, end=i * step + 0.4, lang="en") for i in range(n_words)]
    half = n_words // 2
    beats = Beats(beats=[Beat(id="b1", word_ids=[w.id for w in words[:half]], start=0.0, end=words[half - 1].end, text="first half"),
                         Beat(id="b2", word_ids=[w.id for w in words[half:]], start=words[half].start, end=words[-1].end, text="second half")])
    return Transcript(language="en", words=words), beats


def _script(actions_s1, actions_s2=(), kind="stick"):
    return VideoScript.model_validate({
        "kind": kind, "cast": [{"id": "maya", "name": "Maya"}, {"id": "sam", "name": "Sam"}], "sets": [{"id": "room", "kind": "plain"}],
        "scenes": [{"id": "s1", "beats": ["b1"], "set": "room", "actions": [dict(a) for a in actions_s1]},
                   {"id": "s2", "beats": ["b2"], "set": "room", "actions": [dict(a) for a in actions_s2]}]})


def test_dull_script_gets_scene_by_scene_notes():
    tr, beats = _talk()
    s = _script([{"at_word": "w0", "who": "maya", "do": "explain"}, {"at_word": "w1", "who": "maya", "do": "explain"}])
    rv = review(s, tr, beats)
    text = " | ".join(f"{i['scene']}: {i['problem']}" for i in rv["issues"])
    assert "s1: nothing new" in text and "twice in a row" in text and "only talking" in text and "Sam" in text
    assert rv["metrics"]["longest_still_s"] > MAX_STILL and rv["score"] < 70


def test_enricher_fills_every_still_stretch_and_reacts_to_the_words():
    tr, beats = _talk()
    s = _script([{"at_word": "w0", "who": "maya", "do": "explain"}], [{"at_word": "w12", "who": "sam", "do": "wave"}])
    out, added = enrich(s, tr, beats)
    assert added >= 2 and review(out, tr, beats)["metrics"]["longest_still_s"] <= MAX_STILL
    s1 = out.scenes[0].actions
    assert all(a.who == "maya" for a in s1) and any(a.do == "think" and a.at_word == "w9" for a in s1)      # "Why?" -> think
    assert all(x.do != y.do for x, y in zip(s1, s1[1:]))                                                        # never the same thing twice running
    assert [a.at_word for a in s.scenes[0].actions] == ["w0"]                                                   # the input is not changed


def test_revise_keeps_a_revision_only_when_the_critic_likes_it_better(monkeypatch):
    tr, beats = _talk()
    dull = _script([{"at_word": "w0", "who": "maya", "do": "explain"}, {"at_word": "w1", "who": "maya", "do": "explain"}])
    better = _script([{"at_word": f"w{i}", "who": "maya", "do": v} for i, v in zip(range(0, 12, 2), ["walk_in", "point", "think", "clap", "react", "jump"])],
                     [{"at_word": f"w{i}", "who": "sam", "do": v} for i, v in zip(range(12, 24, 2), ["walk_in", "laugh", "shrug", "count", "wave", "bow"])])
    better_d = better.model_dump(by_alias=True, exclude_none=True)
    for sc in better_d["scenes"]:                                            # walk_in needs "from": keep it valid
        for a in sc["actions"]:
            if a["do"] == "walk_in":
                a["from"] = "left"
    asked = []
    monkeypatch.setattr(PL.ai, "complete_json", lambda user, *a, **k: asked.append(user) or better_d)
    out = PL.revise(dull, tr, beats, "sys", {}, "stick", set(), set(), None, lambda *a: None)
    assert "nothing new" in asked[0] and "s1" in asked[0]
    assert review(out, tr, beats)["score"] > review(dull, tr, beats)["score"]
    asked.clear()
    monkeypatch.setattr(PL.ai, "complete_json", lambda user, *a, **k: asked.append(user) or dull.model_dump(by_alias=True, exclude_none=True))
    out2 = PL.revise(better, tr, beats, "sys", {}, "stick", set(), set(), None, lambda *a: None)
    assert out2.model_dump() == better.model_dump() or len(asked) <= 1                                         # a worse answer is thrown away

    def boom(*a, **k):
        raise PL.ai.AIUnavailable("down")
    monkeypatch.setattr(PL.ai, "complete_json", boom)
    assert PL.revise(dull, tr, beats, "sys", {}, "stick", set(), set(), None, lambda *a: None).model_dump() == dull.model_dump()
