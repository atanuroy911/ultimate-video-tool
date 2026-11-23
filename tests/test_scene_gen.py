"""G1/G4 (docs/plans/PLAN-SCENE-TOOLS.MD): pictures for one scene. The picture engine is a stand-in here (it writes a small PNG into the media bin)."""
from __future__ import annotations

import pytest
from PIL import Image


@pytest.fixture()
def engine(monkeypatch, tmp_path):
    from vt import comfy

    made = []

    class Client:
        def __init__(self, url):
            self.url = url

        def object_info(self):
            return {}

        def close(self):
            pass

    class WF:
        label = "Stand-in picture model"

    def still(project, client, workflow, prompt, *, aspect, seed, caption, scene, checked, cancelled, progress):
        from vt.director.media import add_media

        if "fail" in prompt and seed % 2:
            raise comfy.ComfyError("the stand-in failed this one", kind="failed")
        f = tmp_path / f"still-{seed}.png"
        Image.new("RGB", (32, 48), (seed % 255, 80, 120)).save(f)
        item = add_media(project, f, caption=caption, tags=["generated", "still"], source="comfyui", licence="generated locally")
        made.append(seed)
        progress(1.0, "done")
        return item, {"seed": seed, "seconds_taken": 0.1}

    monkeypatch.setattr(comfy, "ComfyClient", Client)
    monkeypatch.setattr(comfy, "picture_workflow", lambda recipe="", object_info=None: WF())
    monkeypatch.setattr(comfy, "generate_still", still)
    return made


def test_a_run_of_pictures_for_a_scene_is_kept_and_a_picture_can_be_forgotten(ref, engine):
    from vt import scene_gen as G

    sid = ref.scenes().scenes[0].id
    assert G.scene_words(ref, sid)
    assert "illustration" in G.suggest_prompt(ref, sid)
    run = G.generate(ref, sid, "a lighthouse at dusk", count=3, seed=100)
    assert [i["seed"] for i in run["items"]] == [100, 101, 102] and all(i.get("media") for i in run["items"])
    h = G.history(ref, sid)
    assert h["runs"][0]["prompt"] == "a lighthouse at dusk" and h["runs"][0]["model"] == "Stand-in picture model"
    gone = run["items"][1]["media"]
    h = G.forget(ref, sid, gone)
    assert [i["media"] for i in h["runs"][0]["items"]] == [run["items"][0]["media"], run["items"][2]["media"]]
    assert any(m.id == gone for m in ref.meta().media), "forgetting a candidate keeps the picture in the media bin"


def test_a_failed_picture_is_named_and_the_rest_still_come(ref, engine):
    from vt import scene_gen as G

    sid = ref.scenes().scenes[0].id
    run = G.generate(ref, sid, "fail sometimes", count=4, seed=10)
    assert [bool(i.get("media")) for i in run["items"]] == [True, False, True, False]
    assert "stand-in failed" in run["items"][1]["error"]
    with pytest.raises(G.GenError, match="Write what"):
        G.generate(ref, sid, "  ", count=1)
    with pytest.raises(G.GenError, match="no scene"):
        G.generate(ref, "nope", "a cat", count=1)


def test_the_api_lists_makes_and_uses_pictures(ref, engine):
    import time

    from fastapi.testclient import TestClient

    from vt.server.app import app

    sid = ref.scenes().scenes[0].id
    with TestClient(app) as c:
        got = c.get(f"/api/projects/{ref.id}/scenes/{sid}/pictures").json()
        assert got["runs"] == [] and got["prompt"] and got["models"]
        job = c.post(f"/api/projects/{ref.id}/scenes/{sid}/pictures", json={"prompt": "a lighthouse at dusk", "count": 2, "seed": 7}).json()
        for _ in range(100):
            j = c.get(f"/api/jobs/{job['id']}").json()
            if j["status"] in ("done", "error"):
                break
            time.sleep(0.05)
        assert j["status"] == "done", j
        runs = c.get(f"/api/projects/{ref.id}/scenes/{sid}/pictures").json()["runs"]
        media = runs[0]["items"][0]["media"]
        used = c.post(f"/api/projects/{ref.id}/scenes/{sid}/pictures/use", json={"media": media})
        assert used.status_code == 200, used.text
        sc = next(s for s in ref.scenes().scenes if s.id == sid)
        assert media in sc.model_dump_json(), "the scene now shows the chosen picture"
        assert c.post(f"/api/projects/{ref.id}/scenes/{sid}/pictures/use", json={"media": "nope"}).status_code == 404
