import time
import httpx

from fastapi.testclient import TestClient

from vt import paths
from vt.server.app import app
from vt.social import core


def test_mock_dispatch_publishes_and_records_log(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROJECTS", tmp_path / "projects")
    monkeypatch.setattr(core, "DB", tmp_path / "social.db")
    project = paths.PROJECTS / "demo"
    (project / "exports").mkdir(parents=True)
    (project / "project.json").write_text('{"id":"demo","title":"Demo","language":"en","aspect":"9:16","theme":"paper","pace":"normal","created_at":"2026-01-01T00:00:00Z"}', encoding="utf-8")
    (project / "exports" / "demo.mp4").write_bytes(b"mock video")
    client = TestClient(app)
    account = client.post("/api/social/accounts/connect/mock", json={"platform":"mock","name":"Test channel","credentials":{}})
    assert account.status_code == 200, account.text
    account_id = account.json()["id"]
    assert "credentials" not in client.get("/api/social/accounts").text
    group = client.post("/api/social/groups", json={"name":"Test group","account_ids":[account_id]})
    assert group.status_code == 200, group.text
    response = client.post("/api/projects/demo/social/dispatch", json={"group_id":group.json()["id"],"video_filename":"demo.mp4","title":"Demo clip","platform_overrides":{"mock":{"title":"Mock title"}}})
    assert response.status_code == 200, response.text
    for _ in range(30):
        task = client.get("/api/social/tasks").json()[0]
        if task["status"] == "published": break
        time.sleep(.1)
    assert task["status"] == "published"
    assert task["title"] == "Mock title"
    assert task["permalink"].startswith("https://example.com/mock/")
    assert [entry["status"] for entry in client.get("/api/social/logs").json()][:2] == ["published", "uploading"]


def test_dispatch_rejects_foreign_video(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROJECTS", tmp_path / "projects")
    monkeypatch.setattr(core, "DB", tmp_path / "social.db")
    project = paths.PROJECTS / "demo"
    (project / "exports").mkdir(parents=True)
    (project / "project.json").write_text('{"id":"demo","title":"Demo","language":"en","aspect":"9:16","theme":"paper","pace":"normal","created_at":"2026-01-01T00:00:00Z"}', encoding="utf-8")
    client = TestClient(app)
    account_id = client.post("/api/social/accounts/connect/mock", json={"platform":"mock","name":"Test","credentials":{}}).json()["id"]
    group_id = client.post("/api/social/groups", json={"name":"Test","account_ids":[account_id]}).json()["id"]
    response = client.post("/api/projects/demo/social/dispatch", json={"group_id":group_id,"video_filename":"../secret.mp4","title":"No"})
    assert response.status_code == 400


def test_one_failed_channel_does_not_block_other_channel(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROJECTS", tmp_path / "projects")
    monkeypatch.setattr(core, "DB", tmp_path / "social.db")
    project = paths.PROJECTS / "demo"
    (project / "exports").mkdir(parents=True)
    (project / "project.json").write_text('{"id":"demo","title":"Demo","language":"en","aspect":"9:16","theme":"paper","pace":"normal","created_at":"2026-01-01T00:00:00Z"}', encoding="utf-8")
    (project / "exports" / "demo.mp4").write_bytes(b"mock video")
    client = TestClient(app)
    bad = client.post("/api/social/accounts/connect/mock", json={"platform":"mock","name":"Bad","credentials":{}}).json()["id"]
    good = client.post("/api/social/accounts/connect/mock", json={"platform":"mock","name":"Good","credentials":{}}).json()["id"]
    group = client.post("/api/social/groups", json={"name":"Both","account_ids":[bad,good]}).json()["id"]
    original = core._upload
    def upload(task, credentials, progress):
        if task["account_name"] == "Bad": raise ValueError("Simulated platform rejection")
        return original(task, credentials, progress)
    monkeypatch.setattr(core, "_upload", upload)
    response = client.post("/api/projects/demo/social/dispatch", json={"group_id":group,"video_filename":"demo.mp4","title":"Demo clip"})
    assert response.status_code == 200
    for _ in range(30):
        tasks = client.get("/api/social/tasks").json()
        if len(tasks) == 2 and all(task["status"] in ("failed", "published") for task in tasks): break
        time.sleep(.1)
    assert {task["status"] for task in tasks} == {"failed", "published"}
    assert core.one("SELECT status FROM batch WHERE id=?", (response.json()["batch_id"],))["status"] == "partial_error"
    monkeypatch.setattr(core, "_upload", original)
    failed_id = next(task["id"] for task in tasks if task["status"] == "failed")
    assert client.post(f"/api/social/tasks/{failed_id}/retry").status_code == 200
    for _ in range(30):
        retried = core.one("SELECT status FROM task WHERE id=?", (failed_id,))
        if retried["status"] == "published": break
        time.sleep(.1)
    assert retried["status"] == "published"
    assert core.one("SELECT status FROM batch WHERE id=?", (response.json()["batch_id"],))["status"] == "completed"


def test_instagram_uploads_local_video_bytes(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"local video bytes")
    seen = []
    def respond(request):
        seen.append((request.method, str(request.url), request.read()))
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id":"container-1","uri":"https://rupload.facebook.com/ig-api-upload/container-1"})
        if request.url.host == "rupload.facebook.com":
            return httpx.Response(200, json={"success":True})
        if request.url.path.endswith("/container-1"):
            return httpx.Response(200, json={"status_code":"FINISHED"})
        if request.url.path.endswith("/media_publish"):
            return httpx.Response(200, json={"id":"post-1"})
        return httpx.Response(200, json={"permalink":"https://www.instagram.com/reel/example/"})
    client_cls = httpx.Client
    monkeypatch.setattr(core.httpx, "Client", lambda **kwargs: client_cls(transport=httpx.MockTransport(respond), **kwargs))
    remote, url = core._upload({"id":"test","account_id":"test","platform":"instagram","video_path":str(video),"description":"Test","title":"Test","tags":"[]"}, {"access_token":"token","ig_user_id":"123"}, lambda *_: None)
    assert remote == "post-1"
    assert url.endswith("/example/")
    assert any(method == "POST" and "rupload.facebook.com" in uri and body == b"local video bytes" for method, uri, body in seen)
