import numpy as np
import pytest
from PIL import Image

from vt import ai
from vt.ai import publish


def test_rule_metadata_needs_no_ai(ref):
    m = publish.rule_metadata(ref)
    assert m["source"] == "rules" and m["title"] and m["description"] and len(m["hashtags"]) >= 1
    assert all(" " not in t and "#" not in t for t in m["hashtags"])


def test_ai_metadata_is_cleaned(ref):
    fake = ai.FakeProvider([{"title": "Why Yield Matters", "description": "Learn what yield means.", "hashtags": ["Yield", "#Money", "yield", "Save Up"], "hook": "Yield, explained"}])
    m = publish.metadata(ref, fake)
    assert m["source"] == "ai" and m["hashtags"] == ["yield", "money", "saveup"] and "hook" in m


def test_metadata_falls_back_when_ai_is_down(ref):
    m = publish.metadata(ref, ai.FakeProvider([ai.AIUnavailable("down")]))
    assert m["source"] == "rules"


def test_frame_score_prefers_content_over_empty(tmp_path):
    a = np.full((400, 300, 3), 240, "uint8")
    empty = tmp_path / "e.png"
    Image.fromarray(a).save(empty)
    a2 = a.copy()
    a2[120:280, 60:240] = (30, 30, 80)
    busy = tmp_path / "b.png"
    Image.fromarray(a2).save(busy)
    assert publish.frame_score(busy) > publish.frame_score(empty)
    assert publish.pick_frame([empty, busy], provider=ai.FakeProvider([ai.AIUnavailable("x")])) == 1


def test_hook_is_drawn_inside_the_picture(tmp_path):
    im = Image.fromarray(np.full((640, 360, 3), 200, "uint8"))
    out = publish.draw_hook(im, "Yield explained in one minute")
    a = np.asarray(out).astype(int)
    assert out.size == (360, 640) and (a[int(640 * 0.72):] < 100).any() and (a[:int(640 * 0.6)] == 200).all()


def test_publish_endpoints(ref, projects_dir):
    import time

    from fastapi.testclient import TestClient

    from vt.planner import plan_rules
    from vt.server.app import app

    ref.save_scenes(plan_rules(ref.transcript(), ref.beats()))
    c = TestClient(app)
    assert c.get(f"/api/projects/{ref.id}/publish").json()["kit"] is None
    job = c.post(f"/api/projects/{ref.id}/publish?cover=false").json()
    for _ in range(100):
        j = c.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.2)
    assert j["status"] == "done", j
    kit = c.get(f"/api/projects/{ref.id}/publish").json()["kit"]
    assert kit["title"] and kit["hashtags"]
