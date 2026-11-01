from vt import musicpick as M
from vt.util import read_json


def test_mood_picks_a_fitting_track_stably():
    moods = {m["id"]: m["mood"] for m in read_json(M.paths.MUSIC / "index.json")}
    assert moods[M.pick("finance", "a")] == "corporate"
    assert moods[M.pick("sports", "a")] == "hiphop"
    assert moods[M.pick("kids", "a")] == "playful"
    assert M.pick("motivation", "p1") == M.pick("motivation", "p1")                 # the same project keeps its track
    assert len({M.pick("motivation", f"p{i}") for i in range(20)}) > 1             # different projects get variety
    assert M.pick(None, "x") and M.pick("not-a-mood", "x")


def test_plan_stage_resolves_auto_and_never_passes_it_to_the_mixer(ref):
    from vt.pipeline import Pipeline
    from vt.project import Project
    from vt.render.mux import resolve_music

    p = Project("reference")
    m = p.meta()
    m.options.music = "auto"
    p.save_meta(m)
    Pipeline(p).stage_plan(True)
    chosen = p.meta().options.music
    assert chosen and chosen != "auto" and resolve_music(chosen) is not None
    assert resolve_music("auto") is None


def test_sound_stickers_speak_the_video_language():
    # the owner's Bangla sample showed "Person coughing" in English (2026-10-24)
    from vt.sounds import label_for

    assert label_for("cough", "Person coughing", "en") == "Person coughing"
    assert label_for("cough", "Person coughing", "bn") == "কাশি"
    assert label_for("gunfire", "Gunshots", "bn") == "" and label_for("cough", "Person coughing", "hi") == ""
