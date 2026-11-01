"""The reel look: read a script like a director, group sentences into slots from the content, draw a picture for each, write valid scenes."""
from types import SimpleNamespace as NS

from vt.reel.reading import _check, read_script, rules_hook, rules_kind, rules_reading
from vt.reel.slots import build_slots
from vt.reel.style import FIGURE, STYLES, prompt_for

STEPS = ["Never put your money in one place.", "Here is the secret.", "Step one.", "Keep three months of bills in a savings account.", "Step two.",
         "Put the next slice in an index fund that grows over time.", "Step three.", "Hold a little in something you can sell in a day.", "Now one bad day touches a third."]


def beats(texts, per=0.5):
    out, t = [], 0.0
    for i, text in enumerate(texts, 1):
        n = len(text.split())
        out.append(NS(id=f"b{i}", text=text, start=t, end=t + n * per / 2, word_ids=[f"w{i}_{k}" for k in range(n)]))
        t += n * per / 2
    return out


def test_kind_follows_the_words():
    assert rules_kind(STEPS) == "steps"
    assert rules_kind(["Day 1.", "He walked out.", "Day 2.", "She said no."]) == "story"
    assert rules_kind(["Water boils at a hundred degrees.", "That is why steam rises."]) == "explanation"


def test_hook_types():
    assert rules_hook("How do rich people turn one house into five?").type == "question"
    assert rules_hook("Never put your name on the account.").type == "prohibition"
    assert rules_hook("Hello everyone, welcome back.").strength < 0.2


def test_chapter_jumps_become_cards_and_start_slots():
    b = beats(STEPS)
    reading = rules_reading(b)
    assert [j.label for j in reading.jumps] == ["STEP ONE", "STEP TWO", "STEP THREE"]
    slots = build_slots(b, reading)
    assert [s.card for s in slots if s.card] == ["STEP ONE", "STEP TWO", "STEP THREE"]
    covered = [x.id for s in slots for x in s.beats]
    assert covered == [x.id for x in b], "every sentence is in exactly one slot, in order"
    assert all(s.beats[0].id in {j.beat for j in reading.jumps} for s in slots if s.card)


def test_a_story_moves_faster_than_steps():
    text = ["The man walked into the old bank on the corner and asked for a very large loan today."] * 6
    b = beats(text)
    story = rules_reading(b)
    story.kind = "story"
    steps = rules_reading(b)
    steps.kind = "steps"
    assert len(build_slots(b, story)) >= len(build_slots(b, steps))


def test_the_check_rejects_a_picture_that_invents_a_number():
    b = beats(["He pays 20 percent down."])
    ok = {"notes": [{"beat": "b1", "draw": "a man hands over 20 dollars", "emphasis": "20", "turn": False}]}
    bad = {"notes": [{"beat": "b1", "draw": "a man hands over 5000 dollars", "emphasis": "20", "turn": False}]}
    assert _check(ok, b) == []
    assert any("5000" in e for e in _check(bad, b))
    assert any("no note" in e for e in _check({"notes": []}, b))


def test_without_an_ai_the_rules_still_read_every_sentence():
    b = beats(STEPS)
    r = read_script(b, use_ai=False)
    assert r.source == "rules" and [n.beat for n in r.notes] == [x.id for x in b]
    assert all(n.draw for n in r.notes)


def test_prompts_carry_the_style_the_figure_and_no_words():
    p = prompt_for("a man holds a check", "cartoon", FIGURE["cartoon"])
    assert STYLES["cartoon"]["text"] in p and FIGURE["cartoon"] in p and "no text" in p
    assert prompt_for("x", "photo").count("recurring") == 0


def test_a_reel_plan_without_pictures_is_valid_and_has_cards(ref):
    from vt.reel.plan import build_reel_plan
    from vt.schema import validate_scenes

    sf = build_reel_plan(ref, generate=False, use_ai=False)
    assert validate_scenes(sf, ref.transcript(), ref.beats(), None) == []
    assert all(s.transition_in == "cut" for s in sf.scenes)
    assert all(s.backdrop is None and s.elements for s in sf.scenes), "no server: each slot is a key-word card, never an empty screen"
    report = (ref.dir / "reel_report.json").read_text(encoding="utf-8")
    assert "pictures were switched off" in report


def test_a_chapter_card_keeps_the_picture_so_every_step_has_one_design(ref):
    """Owner, 2026-10-28: if step one is full screen the other steps must be too. A label sits on the picture; it never replaces it."""
    from vt.reel.plan import _scene
    from vt.reel.slots import build_slots
    from vt.reel.reading import read_script

    b = beats(STEPS)
    reading = read_script(b, use_ai=False)
    slots = build_slots(b, reading)
    scenes = [_scene(None, s, i, f"m{i}", reading, {}, "9:16") for i, s in enumerate(slots)]
    assert any(s.card for s in slots)
    assert all(sc.backdrop is not None for sc in scenes)
    assert any(sc.elements for sc, s in zip(scenes, slots) if s.card)


def test_the_cuts_motion_level_keeps_plain_cuts():
    from vt.compose.motion import apply

    data = {"scenes": [{"id": f"s{i}", "elements": [{"type": "title", "text": "x"}]} for i in range(8)]}
    out = apply(data, "cuts")
    assert not any("tx" in s or "moves" in s for s in out["scenes"])
    assert any("fx" in e for s in out["scenes"] for e in s["elements"])


def test_a_command_that_goes_silent_is_stopped_not_waited_for():
    """2026-10-27: the GPU render sat in HyperFrames' final step for over twenty minutes. A silent process is now stopped so the caller can retry on the CPU."""
    import sys
    import time

    import pytest

    from vt.util import run

    started = time.time()
    with pytest.raises(RuntimeError, match="stalled"):
        run([sys.executable, "-c", "import time; print('start', flush=True); time.sleep(60)"], stall_seconds=3)
    assert time.time() - started < 30
    assert run([sys.executable, "-c", "print('fine')"], stall_seconds=3) == "fine"


def test_a_long_video_holds_each_picture_longer_than_a_short_reel():
    text = ["The keeper climbed the iron ladder slowly."] * 140
    short, long_ = beats(text[:8]), beats(text, per=0.5)
    r_short, r_long = rules_reading(short), rules_reading(long_)
    for r in (r_short, r_long):
        r.kind = "story"
    mean = lambda slots: sum(s.seconds for s in slots) / len(slots)
    assert long_[-1].end - long_[0].start > 180 > short[-1].end - short[0].start
    assert mean(build_slots(long_, r_long)) > mean(build_slots(short, r_short)) * 1.2


def test_the_reel_plan_does_not_erase_the_pictures_it_just_added(ref, monkeypatch):
    """2026-10-28: stage_plan saved the project settings it had read before the pictures were drawn, so every new picture vanished from the media bin."""
    from vt import pipeline
    from vt.pipeline import Pipeline
    from vt.schema import MediaItem

    m0 = ref.meta()
    m0.options.look, m0.options.motion = "reel", "auto"
    m0.options.plan_review = "never"                         # this test is about the media bin, not the plan review
    ref.save_meta(m0)
    ref.scenes_path.unlink(missing_ok=True)                    # an existing hand-made plan would be kept, and this test is about a fresh plan

    from vt.reel.plan import build_reel_plan as real

    def fake_build(project, progress=None, **kw):
        meta = project.meta()
        meta.media.append(MediaItem(id="stillx", file="media/stillx.jpg", caption="x"))
        project.save_meta(meta)
        return real(project, generate=False, use_ai=False)

    monkeypatch.setattr("vt.reel.plan.build_reel_plan", fake_build)
    Pipeline(ref).stage_plan(force=True)
    meta = ref.meta()
    assert any(m.id == "stillx" for m in meta.media) and meta.options.motion == "cuts"


def test_the_caption_look_follows_the_content_kind(tmp_path):
    """R3: steps and lists light the key word, an argument shows one word at a time, a story shows short lines."""
    import json
    from types import SimpleNamespace as P

    from vt.compose.composer import CAPTION_FOR_KIND, build_caption_chunks, reel_caption_preset
    from vt.schema import Word

    for kind, look in CAPTION_FOR_KIND.items():
        (tmp_path / "reel_report.json").write_text(json.dumps({"kind": kind}), encoding="utf-8")
        assert reel_caption_preset(P(dir=tmp_path)) == look
    assert reel_caption_preset(P(dir=tmp_path / "nothing")) == "pop"
    words = [Word(id=f"w{i}", text=t, start=i * 0.3, end=i * 0.3 + 0.25) for i, t in enumerate("keep three months of bills".split())]
    assert [len(c["words"]) for c in build_caption_chunks(words, 1, 20, set())] == [1] * 5, "the word preset shows one word at a time"


def test_an_end_card_is_added_only_when_asked_for():
    from vt.reel.plan import _scene
    from vt.reel.reading import read_script

    b = beats(STEPS)
    reading = read_script(b, use_ai=False)
    slots = build_slots(b, reading)
    last = slots[-1]
    plain = _scene(None, last, len(slots) - 1, "m", reading, {}, "9:16")
    asked = _scene(None, last, len(slots) - 1, "m", reading, {}, "9:16", end_card="Follow for more")
    assert not any(getattr(e, "text", "") == "Follow for more" for e in plain.elements)
    card = [e for e in asked.elements if getattr(e, "text", "") == "Follow for more"]
    assert card and card[0].at_word in last.beats[-1].word_ids and asked.backdrop is not None


def test_the_reel_stages_are_modules_the_director_can_call(ref):
    """R1: read the script, make slots and set the style as modules, in order, over the real project files."""
    from vt.modules.executor import Executor

    ex = Executor(ref.dir)
    read = ex.call("understand.read_script", {"use_ai": False})
    assert read.ok and read.output["source"] == "rules" and read.output["sentences"] >= 1
    assert (ref.dir / "reel_reading.json").exists()
    slots = ex.call("cut.reel_slots", {})
    assert slots.ok and slots.output["slots"] and slots.output["longest_seconds"] > 0
    style = ex.call("direct.set_style", {"style": "line-art"})
    assert style.ok and ref.meta().options.reel_style == "line-art"
    bad = ex.call("direct.set_style", {"style": "oil-painting"})
    assert not bad.ok and bad.status == "failed"
    dry = ex.call("fill.generated_still", {"draw": "a man hands over a check"}, force=True)
    assert dry.status in ("ok", "needs_input", "failed")                               # no picture server in the test: it must say so, never crash
