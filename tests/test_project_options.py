"""Changing a video's options after it is made (the editor's Caption look, PATCH /api/projects/{id}) is validated: a known caption look is
saved and recomposed, an unknown one is refused with the field named and nothing is stored."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(ref):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_a_caption_look_is_saved_and_a_wrong_one_refused(client, ref):
    r = client.patch("/api/projects/reference", json={"options": {"caption_style": "word"}})
    assert r.status_code == 200 and ref.meta().options.caption_style == "word"
    bad = client.patch("/api/projects/reference", json={"options": {"caption_style": "sparkly"}})
    assert bad.status_code == 422 and "caption_style" in str(bad.json())
    assert ref.meta().options.caption_style == "word"
