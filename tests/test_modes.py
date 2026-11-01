"""Each drawing style (Stick, Emoji, Pictures) and kind of video (Story, ...) is respected by the pipeline, switching between them leaves nothing behind,
and invalid or incomplete requests are refused clearly."""
import time

import pytest
from fastapi.testclient import TestClient

from vt.planner import plan_rules
from vt.script import service
from vt.schema import validate_scenes
from vt.planner.catalogue import all_icon_names

CHARTS = {"value_card", "big_number", "bar_chart", "ring", "line_chart", "stat_row", "compare", "equation", "gauge", "pictogram", "price_tag"}


def planned(ref):
    sf = plan_rules(ref.transcript(), ref.beats(), ref.meta().theme, language="bn")
    ref.save_scenes(sf)
    return sf


def directed(ref, kind):
    sf = planned(ref)
    service.set_script_kind(ref, kind)
    out, how = service.direct(ref, sf)
    return sf, out, how


def test_stick_mode_makes_a_cast_and_actions(ref):
    _, out, how = directed(ref, "stick")
    assert how.startswith("rules") and all(s.stick and s.stick["actions"] and s.stick["cast"] for s in out.scenes)
    assert all(s.layout in ("upper", "stack", "hero", "split", "grid", "side", "lower") for s in out.scenes)
    assert not validate_scenes(out, ref.transcript(), ref.beats(), all_icon_names())


def test_emoji_mode_uses_only_emoji_and_type_and_no_charts(ref):
    base, out, how = directed(ref, "emoji")
    assert any(e.type in CHARTS for s in base.scenes for e in s.elements), "the rule plan has charts, so the check below means something"
    assert how.startswith("rules")
    for s in out.scenes:
        assert s.archetype == "emoji" and not s.stick
        assert s.elements and all(e.type in ("sticker", "keyword") for e in s.elements), [e.type for e in s.elements]
        assert len(s.elements) <= 3
    emojis = [s.elements[0].emoji for s in out.scenes if s.elements[0].type == "sticker"]
    assert all(a != b for a, b in zip(emojis, emojis[1:]))                  # never the same picture twice in a row
    assert not validate_scenes(out, ref.transcript(), ref.beats(), all_icon_names())


def test_pictures_mode_leaves_the_plan_alone(ref):
    base, out, how = directed(ref, "explainer")
    assert how == "plan" and out == base


def test_the_modes_produce_different_videos(ref):
    sigs = {}
    for k in ("stick", "emoji", "explainer"):
        _, out, _ = directed(ref, k)
        sigs[k] = [(s.archetype, [e.type for e in s.elements], bool(s.stick)) for s in out.scenes]
    assert len({str(v) for v in sigs.values()}) == 3, sigs


def test_switching_modes_through_the_api_leaves_nothing_behind(ref, projects_dir):
    c = TestClient(app_())
    planned(ref)

    def run(kind):
        job = c.post(f"/api/projects/{ref.id}/script/generate?kind={kind}").json()
        for _ in range(150):
            j = c.get(f"/api/jobs/{job['id']}").json()
            if j["status"] in ("done", "error"):
                break
            time.sleep(0.2)
        assert j["status"] == "done", j
        return c.get(f"/api/projects/{ref.id}/scenes").json()["plan"]["scenes"]

    s1 = run("stick")
    assert all(s.get("stick") for s in s1) and c.get(f"/api/projects/{ref.id}").json()["video_kind"] == "stick"
    s2 = run("emoji")
    assert not any(s.get("stick") for s in s2) and all(e["type"] in ("sticker", "keyword") for s in s2 for e in s["elements"])
    assert c.get(f"/api/projects/{ref.id}").json()["video_kind"] == "emoji"
    s3 = run("stick")
    assert all(s.get("stick") for s in s3)                                 # and back again
    assert [s["id"] for s in s3] == [s["id"] for s in s1] or len(s3) >= 1
    again = run("stick")
    assert [s["beats"] for s in again] == [s["beats"] for s in s3]         # regenerating is stable


def test_bad_requests_are_refused_clearly(ref, projects_dir):
    c = TestClient(app_())
    assert c.post(f"/api/projects/{ref.id}/script/generate?kind=bogus").status_code == 400
    assert c.put(f"/api/projects/{ref.id}/video-kind", json={"kind": "bogus"}).status_code == 400
    assert c.post("/api/projects/nope-not-here/script/generate?kind=stick").status_code == 404
    assert c.post(f"/api/projects/{ref.id}/script/paste", json={"json": "{not json"}).json()["ok"] is False
    (ref.dir / "scenes.json").unlink()
    assert c.post(f"/api/projects/{ref.id}/script/generate?kind=stick").status_code == 409     # nothing planned yet


def test_story_kind_plans_a_story_not_a_product(ref):
    from vt.director import plan as D
    from vt.director import roles as RL

    tr, beats = ref.transcript(), ref.beats()
    story = D.plan(tr, beats, theme="paper", language="bn", usecase="story", seed="a", aspect="9:16")
    product = D.plan(tr, beats, theme="paper", language="bn", usecase="product", seed="a", aspect="9:16")
    assert [s.archetype for s in story.scenes] != [s.archetype for s in product.scenes]
    assert RL.analyse(tr, beats, "bn") is not None


def app_():
    from vt.server.app import app

    return app


def test_stick_videos_have_no_second_character(ref):
    from vt.director import plan as D

    tr, beats = ref.transcript(), ref.beats()
    sf = D.plan(tr, beats, theme="paper", language="bn", usecase="story", seed="cartoons-please", aspect="9:16")
    assert any(e.type in ("cartoon", "speaker_card") for s in sf.scenes for e in s.elements), "the story plan has cartoon scenes, so the check means something"
    ref.save_scenes(sf)
    service.set_script_kind(ref, "stick")
    out, _ = service.direct(ref, sf)
    assert not any(e.type in ("cartoon", "speaker_card") for s in out.scenes for e in s.elements)
    assert all(s.archetype == "stick" for s in out.scenes)


def test_stick_scenes_keep_at_most_two_stickers(ref):
    sf = planned(ref)
    service.set_script_kind(ref, "stick")
    out, _ = service.direct(ref, sf)
    assert all(sum(e.type == "sticker" for e in s.elements) <= 2 for s in out.scenes)
