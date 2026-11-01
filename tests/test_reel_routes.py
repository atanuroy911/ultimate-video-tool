"""Change one picture of a reel: see it, draw it again, go back (docs/plans/PLAN-EDITOR-UI.MD U5). The picture server is replaced by a fake."""
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture()
def client(ref):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def png(color):
    b = io.BytesIO()
    Image.new("RGB", (90, 160), color).save(b, "PNG")
    return b.getvalue()


def add(client, color, name):
    r = client.post("/api/projects/reference/media", files={"file": (name + ".png", png(color), "image/png")}, data={"caption": name})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def wait(client, job_id):
    for _ in range(100):
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_a_picture_can_be_replaced_by_an_earlier_try_or_the_persons_own(client, ref):
    sid = client.get("/api/projects/reference/scenes").json()["plan"]["scenes"][0]["id"]
    a, b = add(client, "red", "first"), add(client, "blue", "second")
    p = client.post(f"/api/projects/reference/scenes/{sid}/picture/use", json={"media": a}).json()
    assert p["media"] == a and p["url"] and p["draw"]
    p = client.post(f"/api/projects/reference/scenes/{sid}/picture/use", json={"media": b}).json()
    assert p["media"] == b
    assert client.post(f"/api/projects/reference/scenes/{sid}/picture/use", json={"media": "nope"}).status_code == 404
    assert client.get("/api/projects/reference/scenes/zzz/picture").status_code == 404


def test_drawing_again_keeps_the_old_picture_in_the_tries(client, ref, monkeypatch):
    from vt.modules.executor import Executor

    sid = client.get("/api/projects/reference/scenes").json()["plan"]["scenes"][0]["id"]
    a = add(client, "red", "first")
    client.post(f"/api/projects/reference/scenes/{sid}/picture/use", json={"media": a})
    new = add(client, "green", "drawn")
    seen = {}

    class R:
        ok, output, fix, summary = True, {"media": {"id": new}}, "", ""

    def fake_call(self, module, values=None, **k):
        seen.update(module=module, values=values)
        return R()

    monkeypatch.setattr(Executor, "call", fake_call)
    job = client.post(f"/api/projects/reference/scenes/{sid}/redraw", json={"draw": "a man holds a check, seen from the side"}).json()
    assert wait(client, job["id"])["status"] == "done"
    assert seen["module"] == "fill.generated_still" and seen["values"]["draw"] == "a man holds a check, seen from the side" and seen["values"]["scene"] == sid
    p = client.get(f"/api/projects/reference/scenes/{sid}/picture").json()
    assert p["media"] == new
    assert {t["media"] for t in p["tries"]} == {a, new} and [t for t in p["tries"] if t["current"]][0]["media"] == new
    back = client.post(f"/api/projects/reference/scenes/{sid}/picture/use", json={"media": a}).json()
    assert back["media"] == a


def test_a_failed_redraw_says_why_and_keeps_the_picture(client, ref, monkeypatch):
    from vt.modules.executor import Executor

    sid = client.get("/api/projects/reference/scenes").json()["plan"]["scenes"][0]["id"]
    a = add(client, "red", "first")
    client.post(f"/api/projects/reference/scenes/{sid}/picture/use", json={"media": a})

    class R:
        ok, output, fix, summary = False, {}, "No connected engine can do 'image.generate'.", "no server"

    monkeypatch.setattr(Executor, "call", lambda self, *a, **k: R())
    job = wait(client, client.post(f"/api/projects/reference/scenes/{sid}/redraw", json={}).json()["id"])
    assert job["status"] == "error" and "image.generate" in job["error"]
    assert client.get(f"/api/projects/reference/scenes/{sid}/picture").json()["media"] == a
