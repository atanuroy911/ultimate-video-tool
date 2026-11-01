"""Background removal: refusals and failure paths run offline; the real model (178 MB, downloaded once) is checked on a picture with a clear subject (slow)."""
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFilter

from vt import cutout as CO
from vt import paths


def subject_picture(path, size=(640, 480)):
    """A shaded orange ball with a face-like highlight on a busy grey checkerboard."""
    w, h = size
    bg = np.zeros((h, w, 3), dtype="uint8")
    yy, xx = np.mgrid[0:h, 0:w]
    bg[:] = (((xx // 40 + yy // 40) % 2) * 60 + 90)[..., None]
    im = Image.fromarray(bg)
    d = ImageDraw.Draw(im)
    d.ellipse((w // 2 - 130, h // 2 - 150, w // 2 + 130, h // 2 + 150), fill=(235, 120, 30), outline=(120, 50, 10), width=6)
    d.ellipse((w // 2 - 60, h // 2 - 90, w // 2 + 10, h // 2 - 30), fill=(250, 190, 120))
    d.ellipse((w // 2 - 50, h // 2 - 20, w // 2 + 50, h // 2 + 30), fill=(60, 30, 20))
    im = im.filter(ImageFilter.GaussianBlur(0.8))
    im.save(path)
    return path


@pytest.fixture()
def client(ref):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_the_download_is_checked_and_a_damaged_file_is_removed(tmp_path, monkeypatch):
    import httpx

    class Fake:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        status_code = 200
        def raise_for_status(self): pass
        def iter_bytes(self, n): yield b"x" * 5000
    monkeypatch.setattr(paths, "MODELS", tmp_path / "models")
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: Fake())
    with pytest.raises(CO.CutoutError, match="damaged"):
        CO.ensure_model()
    assert not list((tmp_path / "models" / "cutout").glob("*")) and not CO.ready()


def test_the_api_refuses_what_it_cannot_cut_and_cuts_in_a_job(client, ref, tmp_path, monkeypatch):
    from vt.director import media as M

    pic = M.add_media(ref, subject_picture(tmp_path / "ball.png"))
    assert client.post("/api/projects/reference/media/nope/cutout").status_code == 404
    monkeypatch.setattr(CO, "available", lambda: False)
    assert client.post(f"/api/projects/reference/media/{pic.id}/cutout").status_code == 422
    monkeypatch.setattr(CO, "available", lambda: True)
    # a stand-in model: the left half is "subject"
    monkeypatch.setattr(CO, "ensure_model", lambda progress=None: tmp_path / "fake.onnx")

    def fake_matte(im):
        a = np.zeros((im.height, im.width), dtype="float32")
        a[:, : im.width // 2] = 1.0
        return a
    monkeypatch.setattr(CO, "matte", fake_matte)
    job = client.post(f"/api/projects/reference/media/{pic.id}/cutout").json()
    for _ in range(200):
        j = client.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert j["status"] == "done", j
    ids = [m["id"] for m in client.get("/api/projects/reference/media").json()]
    assert pic.id in ids and j["result"]["id"] in ids                                      # the original stays
    new = next(m for m in client.get("/api/projects/reference/media").json() if m["id"] == j["result"]["id"])
    im = Image.open(ref.dir / new["file"])
    assert im.mode == "RGBA" and im.getpixel((10, 10))[3] > 200 and im.getpixel((im.width - 10, 10))[3] == 0
    # a picture with no subject is refused with a reason
    monkeypatch.setattr(CO, "matte", lambda im: np.zeros((im.height, im.width), dtype="float32"))
    job = client.post(f"/api/projects/reference/media/{pic.id}/cutout").json()
    for _ in range(200):
        j = client.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert j["status"] == "error" and "no clear subject" in j["error"]


@pytest.mark.slow
def test_the_real_model_keeps_the_subject_and_removes_the_background(tmp_path):
    src = subject_picture(tmp_path / "ball.png")
    out = tmp_path / "cut.png"
    info = CO.cut_out(src, out)
    im = np.asarray(Image.open(out).convert("RGBA"))
    h, w = im.shape[:2]
    centre, corner = im[h // 2 - 40:h // 2 + 40, w // 2 - 40:w // 2 + 40, 3].mean(), np.concatenate([im[:60, :60, 3].ravel(), im[-60:, -60:, 3].ravel()]).mean()
    assert centre > 200 and corner < 40, (centre, corner)
    assert 0.1 < info["kept"] < 0.5
