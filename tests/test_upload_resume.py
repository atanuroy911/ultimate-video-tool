"""A big recording reaches the server even when the connection drops on the way (vt/server/uploads.py, CS5)."""
import io

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient


@pytest.fixture()
def client(ref):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def _wav() -> bytes:
    buf = io.BytesIO()
    sf.write(buf, np.zeros(16000, dtype="float32"), 16000, format="WAV")
    return buf.getvalue()


def test_an_interrupted_upload_carries_on_where_it_stopped_and_makes_the_project(client, monkeypatch):
    from vt.server import app as srv

    monkeypatch.setattr(srv, "start_pipeline", lambda p, frm, force: None)
    data = _wav()
    up = client.post("/api/uploads", json={"name": "talk.wav", "size": len(data)}).json()
    assert up["offset"] == 0 and not up["done"]
    first, rest = data[:10000], data[10000:]
    assert client.put(f"/api/uploads/{up['id']}?offset=0", content=first).json()["offset"] == 10000
    # the answer to the next chunk got lost, so the browser sends the first one again: told where to carry on, nothing doubled
    again = client.put(f"/api/uploads/{up['id']}?offset=0", content=first)
    assert again.status_code == 409 and again.json()["detail"]["offset"] == 10000
    assert client.get(f"/api/uploads/{up['id']}").json()["offset"] == 10000
    assert client.post("/api/projects", data={"audio_upload": up["id"], "start": "false"}).status_code == 409   # not finished yet
    assert client.put(f"/api/uploads/{up['id']}?offset=10000", content=rest).json()["done"]

    assert client.post("/api/inspect", data={"file_upload": up["id"]}).json()["mode"] == "audio"   # a look first; the upload stays
    r = client.post("/api/projects", data={"audio_upload": up["id"], "start": "false"})
    assert r.status_code == 200 and r.json()["project"]["title"] == "talk"
    assert client.get(f"/api/uploads/{up['id']}").status_code == 404                              # used up


def test_uploads_refuse_what_does_not_fit(client):
    up = client.post("/api/uploads", json={"name": "x.exe", "size": 4}).json()
    assert client.put(f"/api/uploads/{up['id']}?offset=0", content=b"12345").status_code == 413
    assert client.get(f"/api/uploads/{up['id']}").json()["offset"] == 0
    client.put(f"/api/uploads/{up['id']}?offset=0", content=b"1234")
    assert client.post("/api/projects", data={"audio_upload": up["id"]}).status_code == 400   # not a recording type
    assert client.get("/api/uploads/..%2F..%2Fsettings").status_code == 404
    assert client.post("/api/projects", data={"title": "nothing"}).status_code == 400


def test_an_assistant_on_another_computer_sends_a_file_with_a_one_time_ticket(monkeypatch, tmp_path):
    from vt import paths
    from vt.server import serve, uploads
    from vt.server.app import app

    monkeypatch.setattr(paths, "DATA", tmp_path)
    saved = {**serve.STATE, "services": dict(serve.STATE["services"])}
    serve.configure(key="k" * 43, exposed=True)
    try:
        up = uploads.new_ticketed("talk.wav", 5)
        away = TestClient(app, client=("8.8.8.8", 50000))                                    # outside the server's network: on it, no ticket is needed
        assert away.put(f"/api/uploads/{up['id']}/file?ticket=wrong", content=b"hello").status_code == 401
        assert away.put(f"/api/uploads/{up['id']}?offset=0&ticket={up['ticket']}", content=b"hello").status_code == 401   # the ticket opens only /file
        assert away.put(f"/api/uploads/{up['id']}/file?ticket={up['ticket']}", content=b"hello").json()["done"]
        f = uploads.resolve(f"upload:{up['id']}")
        assert f.name == "talk.wav" and f.read_bytes() == b"hello"
    finally:
        services = saved.pop("services")
        serve.configure(**{k: saved[k] for k in ("key", "name", "exposed")}, services=services)
