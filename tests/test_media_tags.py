import numpy as np
from PIL import Image

from vt import ai
from vt.ai import media_tags
from vt.director import media as M


def _pic(tmp_path):
    a = np.zeros((300, 400, 3), "uint8") + 200
    a[100:200, 150:260] = (200, 30, 30)
    p = tmp_path / "shop.png"
    Image.fromarray(a).save(p)
    return p


def test_describe_fills_missing_caption_and_tags_only(ref, tmp_path):
    a = M.add_media(ref, _pic(tmp_path), caption="")
    b = M.add_media(ref, _pic(tmp_path), caption="my own caption", tags=["mine"])
    fake = ai.FakeProvider([{"caption": "a red box on grey", "tags": ["Box", " red "], "has_text": False, "subject_x": 0.5, "subject_y": 0.5}])
    res = media_tags.describe_project(ref, provider=fake)
    assert res["described"] == [a.id] and not res["error"]
    got = {m.id: m for m in ref.meta().media}
    assert got[a.id].caption == "a red box on grey" and got[a.id].tags == ["box", "red"]
    assert got[b.id].caption == "my own caption" and got[b.id].tags == ["mine"]
    assert fake.calls[0]["images"], "the picture was shown to the model"


def test_describe_stops_politely_without_a_vision_model(ref, tmp_path):
    M.add_media(ref, _pic(tmp_path))
    res = media_tags.describe_project(ref, provider=ai.FakeProvider([ai.AIUnavailable("no vlm")]))
    assert res["described"] == [] and "no vlm" in res["error"]
