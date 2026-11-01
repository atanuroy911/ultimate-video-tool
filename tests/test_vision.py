import numpy as np
import pytest
from PIL import Image

from vt import ai
from vt.ai import vision


def solid(tmp_path, name, fill=(240, 240, 250), box=None, size=(540, 960)):
    a = np.zeros((size[1], size[0], 3), dtype="uint8") + np.array(fill, dtype="uint8")
    if box:
        x0, y0, x1, y1 = box
        a[y0:y1, x0:x1] = (20, 20, 60)
    p = tmp_path / name
    Image.fromarray(a).save(p)
    return p


def test_pixel_checks_find_empty_and_cut_off(tmp_path):
    assert "empty" in vision.pixel_check(solid(tmp_path, "e.png"), "9:16")
    ok = solid(tmp_path, "ok.png", box=(100, 200, 440, 500))
    assert vision.pixel_check(ok, "9:16") == []
    cut = solid(tmp_path, "c.png", box=(0, 100, 300, 600))
    assert "cut_off" in vision.pixel_check(cut, "9:16")


def test_check_frame_asks_one_question_per_problem(tmp_path):
    # four focused yes/no questions (cut_off, overlap, unreadable, empty): small vision models answer these far better than a checklist
    p = solid(tmp_path, "f.png", box=(100, 200, 440, 500))
    fake = ai.FakeProvider([{"answer": "no"}, {"answer": "yes", "where": "bubble over the title"}, {"answer": "no"}, {"answer": "no"}])
    r = vision.check_frame(p, "The sun is hot", provider=fake)
    assert r == {"ok": False, "problems": ["overlap"], "fix_hint": "overlap: bubble over the title"}
    assert len(fake.calls) == 4 and all(c["images"] for c in fake.calls) and "sliced by the image edge" in fake.calls[0]["prompt"]
    assert vision.check_frame(p, "x", provider=ai.FakeProvider([{"answer": "no"}] * 4))["ok"] is True


def test_judge_picture_picks_by_vlm(tmp_path, monkeypatch):
    monkeypatch.setattr(vision, "render_candidates", lambda c, w: solid(tmp_path, "sheet.png"))
    cands = [{"id": "1f441", "kind": "sticker"}, {"id": "231a", "kind": "sticker"}]
    assert vision.judge_picture("watch", "bring me the watch", cands, tmp_path, provider=ai.FakeProvider([{"choice": 1}])) == 1
    assert vision.judge_picture("watch", "x", cands[:1], tmp_path) == 0
    assert vision.judge_picture("watch", "x", cands, tmp_path, provider=ai.FakeProvider([ai.AIUnavailable("down")])) is None


def test_vision_provider_picks_installed_vision_model(monkeypatch):
    from vt import llm
    from vt.ai import providers as P

    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "auto", "ollama_url": "http://x", "ollama_model": "", "llm_auto_download": False})
    monkeypatch.setattr(llm, "installed_models", lambda url=None: ["gemma4:latest", "qwen2.5vl:3b", "qwen2.5vl:7b", "llama3:8b"])
    assert P.vision_provider().model() == "qwen2.5vl:7b"


@pytest.mark.slow
def test_qa_project_with_pixels_only(ref):
    from vt.render.hyperframes import BIN

    if not BIN.exists():
        pytest.skip("HyperFrames is not installed")
    from vt.planner import plan_rules

    ref.save_scenes(plan_rules(ref.transcript(), ref.beats()))
    res = vision.qa_project(ref, provider=ai.FakeProvider([ai.AIUnavailable("no vlm")] * 50))
    assert len(res["scenes"]) == len(ref.scenes().scenes) and all(s["source"] == "pixels" for s in res["scenes"])
    assert (ref.dir / "qa.json").exists()


def test_edge_content_tells_a_real_cut_from_a_false_alarm(tmp_path):
    # a vision model said "cut off at the top" on frames with nothing near any edge (2026-10-24); a sliced desk touches the edge
    from PIL import Image as I

    clean = I.new("RGB", (540, 960), (240, 240, 245))
    clean.paste((20, 20, 20), (150, 300, 390, 500))
    clean.save(tmp_path / "clean.png")
    cut = clean.copy()
    cut.paste((90, 60, 30), (0, 520, 80, 640))                 # a desk sliced by the left edge
    cut.save(tmp_path / "cut.png")
    assert vision.edge_content(tmp_path / "clean.png", "9:16") < 0.04 < vision.edge_content(tmp_path / "cut.png", "9:16")
