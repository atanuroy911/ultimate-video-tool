"""What is on the timeline stays there. A director's revision replaces only the scenes it changed; everything the person (or the
director's own last look) fixed in the other scenes is kept (vt/script/service.py carry_forward)."""
from vt import ai
from vt.script import chat
from vt.util import read_json


def _stick(p):
    from vt.script.rules_stick import rules_script
    from vt.script.service import apply_script, set_script_kind

    set_script_kind(p, "stick")
    s = rules_script(p.transcript(), p.beats(), p.scenes(), kind="stick", language=p.meta().language, aspect=p.meta().aspect)
    assert apply_script(p, s.model_dump(by_alias=True, exclude_none=True), planner="rules", compose=False)["ok"]
    return s


def _hand_edit(p, index: int = 0) -> str:
    """The person changes one scene on the timeline: a caption height only a person sets."""
    from vt import scene_ops

    sf = p.scenes()
    sid = sf.scenes[index].id
    p.save_scenes(scene_ops.patch_scene(sf, sid, {"caption": {**sf.scenes[index].caption.model_dump(), "y": 0.31}}))
    return sid


def _change_one_scene(script: dict, index: int) -> dict:
    """The director's answer: the same script with one scene's first action changed."""
    scene = script["scenes"][index]
    assert scene.get("actions"), "the reference stick script has an action in every scene"
    scene["actions"][0]["emotion"] = "angry" if scene["actions"][0].get("emotion") != "angry" else "happy"
    return script


def test_a_director_turn_keeps_the_hand_edits_of_the_scenes_it_did_not_change(ref, monkeypatch):
    from vt.project import Project

    p = Project("reference")
    cur = _stick(p)
    assert len(p.scenes().scenes) > 2
    edited = _hand_edit(p, 0)
    want = _change_one_scene(cur.model_dump(by_alias=True, exclude_none=True), -1)
    monkeypatch.setattr(ai, "complete_json", lambda *a, **k: want)
    monkeypatch.setattr("vt.pipeline.compose_all", lambda p: None)

    res = chat.talk(p, "make the last scene angrier", provider=ai.FakeProvider({}))

    assert res["ok"], res
    after = {s.id: s for s in p.scenes().scenes}
    assert after[edited].caption.y == 0.31                       # the person's edit is still there
    last = p.scenes().scenes[-1].id
    assert res["changed_scenes"] == [last]                       # and the reply marks only what the director changed
    assert edited not in res["changed_scenes"]


def test_the_scene_the_director_changed_is_replaced_and_the_reply_says_what_was_lost(ref, monkeypatch):
    from vt.project import Project

    p = Project("reference")
    cur = _stick(p)
    edited = _hand_edit(p, -1)
    want = _change_one_scene(cur.model_dump(by_alias=True, exclude_none=True), -1)
    monkeypatch.setattr(ai, "complete_json", lambda *a, **k: want)
    monkeypatch.setattr("vt.pipeline.compose_all", lambda p: None)

    res = chat.talk(p, "make the last scene angrier", provider=ai.FakeProvider({}))

    assert res["ok"], res
    assert p.scenes().scenes[-1].caption.y is None               # the director's new version of that scene is on screen
    assert res["replaced_edits"] == [edited]
    assert "your own edits" in res["reply"]
    assert read_json(p.dir / "scenes.prev.json")["scenes"][-1]["caption"]["y"] == 0.31       # undo brings them back


def test_the_director_is_told_what_was_edited_by_hand(ref, monkeypatch):
    from vt.project import Project

    p = Project("reference")
    cur = _stick(p)
    edited = _hand_edit(p, 0)
    seen = {}

    def fake(user, schema, **k):
        seen["user"] = user
        return cur.model_dump(by_alias=True, exclude_none=True)

    monkeypatch.setattr(ai, "complete_json", fake)
    monkeypatch.setattr("vt.pipeline.compose_all", lambda p: None)
    chat.talk(p, "anything", provider=ai.FakeProvider({}))
    assert "EDITED ON THE TIMELINE" in seen["user"] and f'"scene": "{edited}"' in seen["user"]


def test_redoing_an_earlier_stage_keeps_the_plan_and_a_new_direction_replaces_it(ref):
    """A new pace or retakes put back re-run the stages before the plan. The plan an AI made (and what was fixed in it by hand) follows; only a run from the
    plan stage, or one that says force, directs the video again."""
    from vt.pipeline import Pipeline
    from vt.project import Project

    p = Project("reference")
    plan = p.scenes()
    first = plan.scenes[0].model_copy(update={"caption": plan.scenes[0].caption.model_copy(update={"y": 0.31})})
    p.save_scenes(plan.model_copy(update={"planner": "llm", "scenes": [first] + plan.scenes[1:]}))

    Pipeline(p).run(from_stage="words")
    assert p.scenes().planner == "llm" and p.scenes().scenes[0].caption.y == 0.31

    Pipeline(p).run(from_stage="plan")
    assert p.scenes().planner != "llm"


def _cuts(source: float, removed: list[tuple[float, float]]):
    from vt.stages import audio as A

    return A.cuts_from_removed(source, removed)


def test_clips_on_the_extra_tracks_follow_a_voice_cut_and_come_back_with_it(ref):
    """A text or a sound put on a moment of the recording stays on that moment when the voice is cut before it, and returns exactly when the cut is undone."""
    from vt import layers as L
    from vt.project import Project
    from vt.util import write_json

    p = Project("reference")
    doc = {"v": 1, "tracks": [{"id": "t1", "name": "Text", "kind": "visual", "hidden": False, "muted": False, "locked": False}],
           "clips": [{"id": "after", "track": "t1", "type": "text", "text": "later", "start": 10.0, "dur": 2.0},
                     {"id": "inside", "track": "t1", "type": "text", "text": "gone", "start": 2.5, "dur": 1.0},
                     {"id": "across", "track": "t1", "type": "text", "text": "shorter", "start": 4.5, "dur": 2.0,
                      "keyframes": [{"time": 4.5, "x": .2}, {"time": 6.4, "x": .8}]}]}
    write_json(p.dir / "layers.json", doc)
    whole, cut = _cuts(17.0, []), _cuts(17.0, [(2.0, 5.0)])

    clock = L.follow_cuts(p, whole, cut, {})
    now = {c["id"]: c for c in L.load(p)["clips"]}
    assert "inside" not in now                                         # its whole moment was cut out
    assert (now["after"]["start"], now["after"]["dur"]) == (7.0, 2.0)  # three seconds earlier, like the words it sits on
    assert (now["across"]["start"], now["across"]["dur"]) == (2.0, 1.5)
    assert [k["time"] for k in now["across"]["keyframes"]] == [2.0, 3.4]
    assert L.history(p) == {"can_undo": False, "can_redo": False}      # the voice edit's undo moves them back: no step of their own

    L.follow_cuts(p, cut, whole, clock)                                # the cut is undone
    back = {c["id"]: c for c in L.load(p)["clips"]}
    assert {k: (v["start"], v["dur"]) for k, v in back.items()} == {"after": (10.0, 2.0), "inside": (2.5, 1.0), "across": (4.5, 2.0)}
    assert [k["time"] for k in back["across"]["keyframes"]] == [4.5, 6.4]
    assert not (p.dir / L.PARKED).exists()


def test_hiding_a_word_keeps_its_picture_near_and_undo_puts_it_back(ref):
    """A picture timed to a word that is hidden from the captions moves to the nearest spoken word of its scene, not to the scene's start,
    and undoing the word change moves the picture back as well."""
    from fastapi.testclient import TestClient

    import vt.server.app as A
    from vt.project import Project

    p = Project("reference")
    before = p.scenes()
    scene = next(s for s in before.scenes if len(s.elements) > 1)
    k = len(scene.elements) - 1
    wid = scene.elements[k].at_word
    words = p.transcript().by_id()
    assert wid != scene.elements[0].at_word
    with TestClient(A.app) as c:
        assert c.put(f"/api/projects/reference/words/{wid}", json={"cut": True}).status_code == 200
        moved = next(s for s in p.scenes().scenes if s.id == scene.id).elements[k].at_word
        kept = [w for w in p.transcript().kept()]
        nearest = min((w for w in kept if w.id != wid), key=lambda w: abs(w.start - words[wid].start))
        assert moved != wid and abs(words[moved].start - words[wid].start) <= abs(nearest.start - words[wid].start) + 1.5
        assert moved != scene.elements[0].at_word                      # not thrown to the start of the scene

        assert c.post("/api/projects/reference/words/history/undo").status_code == 200
        assert p.scenes() == before
        assert c.post("/api/projects/reference/words/history/redo").status_code == 200
        assert next(s for s in p.scenes().scenes if s.id == scene.id).elements[k].at_word == moved


def test_splitting_a_scene_keeps_its_picture_on_both_halves(ref):
    from vt import scene_ops
    from vt.project import Project
    from vt.schema import Backdrop

    p = Project("reference")
    sf, beats = p.scenes(), p.beats()
    k = next(i for i, s in enumerate(sf.scenes) if len(s.beats) > 1)
    with_picture = sf.scenes[k].model_copy(update={"backdrop": Backdrop(media="m1"), "tone": 3})
    sf = sf.model_copy(update={"scenes": sf.scenes[:k] + [with_picture] + sf.scenes[k + 1:]})
    out = scene_ops.split_scene(sf, beats, with_picture.id, with_picture.beats[1])
    first, second = out.scenes[k], out.scenes[k + 1]
    assert second.backdrop == first.backdrop == with_picture.backdrop and second.tone == 3
    assert second.transition_in == "cut"


def test_a_media_clip_cut_at_its_head_skips_the_same_stretch_of_its_file_and_gets_it_back(ref):
    """An overdub put under words 4.0-8.0 s: when 4.0-5.0 s of the voice is cut, the clip starts 1 s later into its file, so the sound still sits under the
    same words; undoing the cut brings the old in-point back."""
    from vt import layers as L
    from vt.project import Project
    from vt.util import write_json

    p = Project("reference")
    doc = {"v": 1, "tracks": [{"id": "a1", "name": "Sounds", "kind": "audio", "hidden": False, "muted": False, "locked": False}],
           "clips": [{"id": "dub", "track": "a1", "type": "audio", "media": "sfx1", "start": 4.0, "dur": 4.0, "in": 0.5}]}
    write_json(p.dir / "layers.json", doc)
    whole, cut = _cuts(17.0, []), _cuts(17.0, [(4.0, 5.0)])

    clock = L.follow_cuts(p, whole, cut, {})
    now = {c["id"]: c for c in L.load(p)["clips"]}["dub"]
    assert (now["start"], now["dur"], now["in"]) == (4.0, 3.0, 1.5)

    L.follow_cuts(p, cut, whole, clock)
    back = {c["id"]: c for c in L.load(p)["clips"]}["dub"]
    assert (back["start"], back["dur"], back["in"]) == (4.0, 4.0, 0.5)


def test_undoing_a_new_direction_brings_back_the_plan_with_its_script(ref, monkeypatch):
    """After "direct again", one undo puts the previous plan back on the timeline together with the script it came from: the next director turn
    revises what is on screen, not a newer script of a plan that is gone."""
    from vt.pipeline import Pipeline
    from vt.project import Project
    from vt.script import service
    from vt.util import read_json
    import vt.server.app as A

    p = Project("reference")
    _stick(p)
    p.save_scenes(p.scenes().model_copy(update={"planner": "llm"}))              # a plan an AI made, as after a real direction
    before_plan, before_script = p.scenes(), read_json(p.dir / "video_script.json")
    assert before_script

    monkeypatch.setattr(service, "uses_script", lambda p_, chosen: False)      # the new direction is a plain rule draft: no AI in this test
    Pipeline(p).run(from_stage="plan")
    assert p.scenes() != before_plan
    assert not (p.dir / "video_script.json").exists()                           # the old script does not survive a re-direction
    assert read_json(p.dir / service.UNDO_STATE)["script"] == before_script

    monkeypatch.setattr(A, "compose_all", lambda p_: None)
    out = A.undo_scenes("reference")
    assert out["plan"] == before_plan.model_dump(exclude_none=True)
    assert read_json(p.dir / "video_script.json") == before_script
    assert p.scenes() == before_plan
    again = A.undo_scenes("reference")                                           # a second undo is the redo: the new direction, without the old script
    assert again["plan"] != before_plan.model_dump(exclude_none=True)
    assert not (p.dir / "video_script.json").exists()


def test_edits_are_refused_while_the_pipeline_remakes_the_video(ref, monkeypatch):
    """An assistant's edit during a pipeline job would be overwritten a moment later: it is refused with the reason. An export is not such a job."""
    from fastapi import HTTPException
    import pytest

    import vt.server.app as A

    class Job:
        label, stage = "Making the video", "plan"

    A.editable("reference")
    monkeypatch.setattr(A.jobs, "active_for", lambda pid, kinds=("pipeline", "export"): Job() if "pipeline" in kinds else None)
    with pytest.raises(HTTPException) as e:
        A.editable("reference")
    assert e.value.status_code == 409 and "Making the video" in str(e.value.detail)
    monkeypatch.setattr(A.jobs, "active_for", lambda pid, kinds=("pipeline", "export"): Job() if kinds == ("pipeline", "export") else None)
    A.editable("reference")                                                     # only the pipeline counts, not an export


def test_update_scene_takes_the_scripts_camera_on_a_stick_scene(ref):
    """The director writes `camera` at the scene level in its script; the same shape works in update_scene on the timeline (seen refused on 2026-11-15,
    with a message about beats)."""
    import pytest

    from vt import scene_ops
    from vt.project import Project

    p = Project("reference")
    _stick(p)
    sf = p.scenes()
    sid = next(s.id for s in sf.scenes if s.stick)
    new = scene_ops.patch_scene(sf, sid, {"camera": {"shot": "medium", "move": "push_in"}})
    cam = next(s for s in new.scenes if s.id == sid).stick["camera"]
    assert (cam["shot"], cam["move"]) == ("medium", "push_in")
    with pytest.raises(scene_ops.OpError, match="beats and start move with split"):
        scene_ops.patch_scene(sf, sid, {"beats": ["b1"]})


def test_a_stick_patch_with_script_style_actions_is_timed_and_keeps_the_cast(ref):
    """Seen on 2026-11-15: update_scene with {"stick": {"actions": [...]}} as written in a script replaced the whole stick block with untimed actions,
    and composing every later frame of the video crashed (KeyError 'start')."""
    from vt import scene_ops
    from vt.project import Project
    from vt.schema import validate_scenes

    p = Project("reference")
    _stick(p)
    sf, tr, beats = p.scenes(), p.transcript(), p.beats()
    sc = next(s for s in sf.scenes if s.stick and s.stick.get("actions"))
    word = next(b for b in beats.beats if b.id in sc.beats).word_ids[0]
    who = sc.stick["actions"][0]["who"]
    new = scene_ops.patch_scene(sf, sc.id, {"stick": {"actions": [{"at_word": word, "who": who, "do": "wave"}]}}, tr, beats)
    block = next(s for s in new.scenes if s.id == sc.id).stick
    assert block.get("cast") == sc.stick.get("cast")                         # the rest of the block stays
    assert block["actions"][0]["start"] == round(tr.by_id()[word].start, 3) and block["actions"][0]["end"] > block["actions"][0]["start"]
    assert validate_scenes(new, tr, beats) == []

    untimed = sf.model_copy(update={"scenes": [s.model_copy(update={"stick": {**s.stick, "actions": [{"at_word": word, "who": who, "do": "wave"}]}}) if s.id == sc.id else s
                                               for s in sf.scenes]})
    assert any("no start and end time" in e for e in validate_scenes(untimed, tr, beats))


def test_a_script_for_a_chosen_type_is_held_to_that_type(ref):
    """An emoji video's script with a cast and actions is not accepted as one: the director is told to take them out (strict), not given a stick video."""
    from vt.script import service
    from vt.script.rules_stick import rules_script

    p = ref
    service.set_script_kind(p, "stick")
    s = rules_script(p.transcript(), p.beats(), p.scenes(), kind="stick", language=p.meta().language, aspect=p.meta().aspect).model_dump(by_alias=True, exclude_none=True)
    s.pop("kind", None)
    service.set_script_kind(p, "emoji")
    out = service.apply_script(p, s, planner="claude", compose=False, strict=True)
    assert not out["ok"] and any("emoji video" in e for e in out["errors"])


def test_a_screen_recording_says_why_its_graphics_were_not_planned(ref, monkeypatch):
    """2026-11-15: the notice said only "AIUnavailable" when the director's usage limit was reached; the person could not tell what to do."""
    from vt import screen_recording
    from vt.ai.providers import AIUnavailable
    from vt.pipeline import Pipeline
    from vt.util import read_json

    m = ref.meta()
    m.options.recording_edit = "screen"
    ref.save_meta(m)
    ref.scenes_path.unlink(missing_ok=True)

    def no_ai(project, plan):
        raise AIUnavailable("Claude's usage limit was reached. It works again when the limit resets.")

    from vt.planner import plan_rules

    plain = plan_rules(ref.transcript(), ref.beats(), ref.meta().theme, language=ref.meta().language)
    monkeypatch.setattr(screen_recording, "base_plan", lambda project: plain)          # the reference project has no picture to keep
    monkeypatch.setattr(screen_recording, "supporting_graphics", no_ai)
    Pipeline(ref).stage_plan()
    note = read_json(ref.dir / "ai_notice.json")["message"]
    assert "usage limit" in note and "original screen and captions were kept" in note
    assert ref.scenes() is not None
