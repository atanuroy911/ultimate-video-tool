import re
import io

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(ref):
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_projects_and_catalogue(client):
    lst = client.get("/api/projects").json()
    assert lst[0]["id"] == "reference" and lst[0]["scene_count"] == 3 and lst[0]["duration"] > 10
    cat = client.get("/api/catalogue").json()
    assert len(cat["elements"]) == 40 and "shape" in {e["type"] for e in cat["elements"]} and "slide_up" in cat["transitions"]
    assert client.get("/api/projects/nope").status_code == 404
    assert client.get("/api/projects/..%2Fetc").status_code in (400, 404)


def test_scene_edit_flow_with_undo(client):
    plan = client.get("/api/projects/reference/scenes").json()
    assert plan["plan"]["scenes"][0]["id"] == "s1" and plan["timing"]["duration"] > 10
    t = plan["timing"]["scenes"]
    assert t[0]["start"] == 0.0 and t[-1]["end"] == plan["timing"]["duration"] and all(a["end"] == b["start"] for a, b in zip(t, t[1:]))

    r = client.patch("/api/projects/reference/scenes/s1", json={"layout": "hero", "transition_in": "fade"})
    assert r.status_code == 200 and r.json()["plan"]["scenes"][0]["layout"] == "hero"
    bad = client.patch("/api/projects/reference/scenes/s1", json={"layout": "nope"})
    assert bad.status_code == 422 and bad.json()["detail"]["errors"]
    assert client.patch("/api/projects/reference/scenes/s1", json={"beats": ["b2"]}).status_code == 422

    r = client.post("/api/projects/reference/scenes/s2/split", json={"at_beat": "b4"})
    assert r.status_code == 200 and len(r.json()["plan"]["scenes"]) == 4
    r = client.post("/api/projects/reference/scenes/undo")
    assert r.status_code == 200 and len(r.json()["plan"]["scenes"]) == 3   # back to before the split
    assert client.delete("/api/projects/reference/scenes/s2").status_code == 200


def test_word_edit_updates_transcript_and_captions(client):
    t = client.get("/api/projects/reference/transcript").json()
    w = next(x for x in t["transcript"]["words"] if x["text"] == "দিয়া")
    r = client.put(f"/api/projects/reference/words/{w['id']}", json={"text": "দিয়ে"})
    assert r.status_code == 200
    t2 = client.get("/api/projects/reference/transcript").json()
    assert next(x for x in t2["transcript"]["words"] if x["id"] == w["id"])["text"] == "দিয়ে"
    data = client.get("/media/reference/composition/9x16/data.json").json()
    assert any(x["text"] == "দিয়ে" for c in data["captions"] for x in c["words"])
    assert client.put(f"/api/projects/reference/words/{w['id']}", json={"text": "  "}).status_code == 422
    client.put(f"/api/projects/reference/words/{w['id']}", json={"restore": True})
    t3 = client.get("/api/projects/reference/transcript").json()
    assert next(x for x in t3["transcript"]["words"] if x["id"] == w["id"])["text"] == "দিয়া"


def test_cutting_a_word_repairs_scene_anchors(client):
    plan = client.get("/api/projects/reference/scenes").json()["plan"]
    anchor = plan["scenes"][1]["elements"][1]["at_word"]       # the value_card's word
    assert client.put(f"/api/projects/reference/words/{anchor}", json={"cut": True}).status_code == 200
    assert client.get("/api/projects/reference/scenes").status_code == 200   # plan still valid


def test_request_queue_and_mcp_status(client):
    r = client.post("/api/projects/reference/requests", json={"kind": "scene", "scene_id": "s2", "hint": "compare", "alternatives": 2})
    assert r.status_code == 200
    assert client.get("/api/projects/reference").json()["pending_requests"] == 1
    st = client.get("/api/mcp/status").json()
    assert st["pending"] >= 1 and "claude mcp add" in st["add_command"]
    assert client.post("/api/projects/reference/requests", json={"kind": "scene", "scene_id": "zz"}).status_code == 422
    assert client.delete(f"/api/projects/reference/requests/{r.json()['id']}").status_code == 200
    assert client.get("/api/projects/reference").json()["pending_requests"] == 0


def test_theme_crud_and_specimen(client, tmp_path, monkeypatch):
    names = [t["name"] for t in client.get("/api/themes").json()]
    assert {"paper", "dark-neon", "minimal"} <= set(names)
    r = client.post("/api/themes/paper/duplicate", json={"new_name": "mine"})
    assert r.status_code == 200 and r.json()["name"] == "mine"
    assert client.post("/api/themes/paper/duplicate", json={"new_name": "mine"}).status_code == 409
    mine = r.json()
    mine["color"]["accent"] = "#0a84ff"
    assert client.put("/api/themes/mine", json=mine).json()["color"]["accent"] == "#0a84ff"
    mine["color"].pop("accent")
    assert client.put("/api/themes/mine", json=mine).status_code == 422
    assert client.delete("/api/themes/paper").status_code == 409
    exp = client.get("/api/themes/mine/export")
    assert exp.status_code == 200 and exp.content[:2] == b"PK"
    imp = client.post("/api/themes/import", files={"file": ("mine.vttheme", io.BytesIO(exp.content))})
    assert imp.status_code == 200 and imp.json()["name"] == "mine-2"
    assert client.delete("/api/themes/mine-2").status_code == 200
    sp = client.get("/api/specimen?theme=mine&aspect=16:9").json()
    assert sp["data"]["format"]["aspect"] == "16:9" and sp["data"]["theme"]["color"]["accent"] == "#0a84ff"
    assert client.get(sp["url"]).status_code == 200


@pytest.mark.slow
def test_jobs_run_and_report(client):
    import time
    r = client.post("/api/projects/reference/thumbnails?aspect=9:16")
    assert r.status_code == 200
    jid = r.json()["id"]
    for _ in range(120):
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(1)
    assert j["status"] == "done", j.get("error")
    th = client.get("/api/projects/reference/thumbnails?aspect=9:16").json()
    assert {"s1", "s2", "s3"} <= set(th["scenes"]) and all(re.fullmatch(r"s\d+(p\d+)?", k) for k in th["scenes"])      # a scene paged into pictures (s1p2) has a thumbnail per page
    assert client.get(th["scenes"]["s2"]).status_code == 200


def test_upload_rejects_unknown_types(client):
    r = client.post("/api/projects", files={"audio": ("evil.exe", io.BytesIO(b"x"))}, data={"title": "t", "start": "false"})
    assert r.status_code == 400


def test_job_lifecycle_is_json_safe_and_visible_in_project(client):
    """A running job must not break project/job endpoints (regression: Event objects in the job were not serialisable)."""
    import threading
    import time
    from vt.server import app as srv

    gate = threading.Event()
    job = srv.jobs.submit("pipeline", "reference", "wait for gate", lambda cb: (cb("asr", 0.5, "halfway"), gate.wait(5), "ok")[2])
    for _ in range(50):
        if srv.jobs.jobs[job.id].status == "running":
            break
        time.sleep(0.05)
    p = client.get("/api/projects/reference").json()
    assert p["active_job"]["id"] == job.id and p["active_job"]["stage"] == "asr"
    assert client.get(f"/api/jobs/{job.id}").json()["msg"] == "halfway"
    assert client.post("/api/projects/reference/run", json={}).status_code == 409   # already busy
    gate.set()
    for _ in range(50):
        if srv.jobs.jobs[job.id].status == "done":
            break
        time.sleep(0.05)
    assert client.get(f"/api/jobs/{job.id}").json()["status"] == "done"


def test_job_cancel(client):
    import threading
    import time
    from vt.server import app as srv
    from vt.server.jobs import Cancelled

    started = threading.Event()

    def work(cb):
        started.set()
        for i in range(200):
            cb("render", i / 200)   # raises Cancelled once cancelled
            time.sleep(0.02)

    job = srv.jobs.submit("pipeline", "reference", "cancellable", work)
    assert started.wait(3)
    assert client.post(f"/api/jobs/{job.id}/cancel").json()["cancelled"] is True
    for _ in range(50):
        if srv.jobs.jobs[job.id].status == "cancelled":
            break
        time.sleep(0.05)
    assert srv.jobs.jobs[job.id].status == "cancelled"


def test_background_thumbnail_job_does_not_make_the_project_busy(client):
    """Regression: a thumbnail job redirected the Review page to the Progress page after every edit."""
    import threading
    import time
    from vt.server import app as srv

    gate = threading.Event()
    job = srv.jobs.submit("thumbs", "reference", "thumbnails", lambda cb: gate.wait(5))
    for _ in range(50):
        if srv.jobs.jobs[job.id].status == "running":
            break
        time.sleep(0.05)
    assert client.get("/api/projects/reference").json()["active_job"] is None
    gate.set()


def test_upload_starts_processing_by_default(client, monkeypatch, tmp_path):
    """Regression: an omitted boolean form field is False in recent FastAPI, so uploads silently never started a job."""
    import numpy as np
    import soundfile as sf
    from vt.server import app as srv

    wav = tmp_path / "a.wav"
    sf.write(str(wav), np.zeros(8000, dtype="float32"), 16000)
    calls = []

    class FakeJob:
        def public(self):
            return {"id": "j1", "status": "queued"}

    monkeypatch.setattr(srv, "start_pipeline", lambda p, frm, force: calls.append(p.id) or FakeJob())

    def post(**data):
        with wav.open("rb") as f:
            return client.post("/api/projects", files={"audio": ("a.wav", f)}, data={"title": "t", **data})

    r = post()                                    # no 'start' field, exactly what the Studio sends
    assert r.status_code == 200 and r.json()["job"] == {"id": "j1", "status": "queued"} and len(calls) == 1
    assert post(start="true").json()["job"] is not None and len(calls) == 2
    r = post(start="false")
    assert r.json()["job"] is None and len(calls) == 2    # explicit opt-out still works


def test_failed_job_exposes_a_plain_message_never_a_traceback(client):
    import time
    from vt.server import app as srv

    def boom(cb):
        cb("asr", 0.3, "transcribing")
        raise RuntimeError("No speech was found in this recording.")

    job = srv.jobs.submit("pipeline", "reference", "will fail", boom)
    for _ in range(50):
        if srv.jobs.jobs[job.id].status == "error":
            break
        time.sleep(0.05)
    j = client.get(f"/api/jobs/{job.id}").json()
    assert j["status"] == "error" and j["error"] == "No speech was found in this recording."
    assert "Traceback" not in j["msg"] and "Traceback" not in j["error"]
    assert j["stage"] == "asr"                                  # the failing stage is kept so the UI can mark it


def test_visual_search_and_get_endpoints(client):
    r = client.get("/api/visuals/search", params={"q": "money", "kind": "sticker"})
    assert r.status_code == 200 and r.json() and r.json()[0]["svg"].startswith("<svg")
    assert all(x["kind"] == "sticker" for x in r.json())
    g = client.get("/api/visuals/get", params={"ids": "🪨,lucide:coins"}).json()
    assert g["🪨"]["id"] == "emoji:1faa8" and g["lucide:coins"]["inner"]
    assert client.get("/api/visuals/search", params={"q": " "}).json() == []


def test_usecases_and_media_bin(client, tmp_path):
    from PIL import Image
    ucs = client.get("/api/usecases").json()
    assert [u["id"] for u in ucs][:2] == ["auto", "general"] and {"product", "story", "discussion", "education"} <= {u["id"] for u in ucs}
    assert client.patch("/api/projects/reference", json={"usecase": "product"}).json()["usecase"] == "product"
    assert client.patch("/api/projects/reference", json={"usecase": "nope"}).status_code == 400
    img = tmp_path / "shop.png"
    Image.new("RGB", (400, 300), (200, 120, 60)).save(img)
    with img.open("rb") as f:
        r = client.post("/api/projects/reference/media", files={"file": ("shop.png", f, "image/png")}, data={"caption": "our shop", "tags": "store, front"})
    assert r.status_code == 200 and r.json()["kind"] == "image" and r.json()["tags"] == ["store", "front"]
    mid = r.json()["id"]
    assert client.get(r.json()["url"]).status_code == 200                       # the file is served
    assert [m["id"] for m in client.get("/api/projects/reference/media").json()] == [mid]
    assert client.patch(f"/api/projects/reference/media/{mid}", json={"caption": "front door", "fx": 2}).json()["fx"] == 1.0
    bad = client.post("/api/projects/reference/media", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 400
    corrupt = client.post("/api/projects/reference/media", files={"file": ("broken.png", b"not a picture", "image/png")})
    assert corrupt.status_code == 422 and "could not" in corrupt.json()["detail"]
    assert client.delete(f"/api/projects/reference/media/{mid}").status_code == 200
    assert client.delete(f"/api/projects/reference/media/{mid}").status_code == 404
    assert client.get("/api/projects/reference/media").json() == []


def test_show_scene_as_another_type(client, tmp_path):
    from PIL import Image
    shows = client.get("/api/projects/reference/scenes/s2/shows")
    assert shows.status_code == 200 and shows.json() and all({"id", "label", "fit"} <= set(o) for o in shows.json())
    ids = [o["id"] for o in shows.json()]
    assert "hero_number" in ids or "stat_row" in ids                       # the reference scene says "৳১০০ ... তিন টাকা"
    assert client.get("/api/projects/reference/scenes/nope/shows").status_code == 404
    target = next(i for i in ("stat_row", "hero_number", "bar_compare") if i in ids)
    r = client.post("/api/projects/reference/scenes/s2/reshow", json={"archetype": target})
    assert r.status_code == 200
    sc = next(s for s in r.json()["plan"]["scenes"] if s["id"] == "s2")
    assert sc["archetype"] == target and sc["elements"]
    assert client.post("/api/projects/reference/scenes/undo").status_code == 200
    # a type the sentences cannot support is refused with a reason, and nothing changes
    bad = client.post("/api/projects/reference/scenes/s1/reshow", json={"archetype": "line_trend"})
    assert bad.status_code == 422 and "needs" in str(bad.json())
    assert client.post("/api/projects/reference/scenes/s1/reshow", json={"archetype": "nonsense"}).status_code == 422
    nomedia = client.post("/api/projects/reference/scenes/s1/reshow", json={"archetype": "media_hero"})
    assert nomedia.status_code == 422 and "media" in str(nomedia.json())
    # with a picture in the bin the picture types become available and validate
    img = tmp_path / "p.png"
    Image.new("RGB", (300, 200), (90, 160, 90)).save(img)
    with img.open("rb") as f:
        mid = client.post("/api/projects/reference/media", files={"file": ("p.png", f, "image/png")}).json()["id"]
    r = client.post("/api/projects/reference/scenes/s1/reshow", json={"archetype": "media_frame"})
    assert r.status_code == 422                                                   # no picture assigned to THIS scene yet
    r = client.post("/api/projects/reference/scenes/s1/reshow", json={"archetype": "media_frame", "media": mid})
    assert r.status_code == 200
    sc = next(s for s in r.json()["plan"]["scenes"] if s["id"] == "s1")
    assert sc["archetype"] == "media_frame" and sc["elements"][0]["media"] == mid
    r = client.post("/api/projects/reference/scenes/s1/reshow", json={"archetype": "media_hero"})
    assert r.status_code == 200 and r.json()["plan"]["scenes"][0]["backdrop"]["scrim"]["ratio"] >= 4.5      # the contrast engine ran on the real picture
    assert client.post("/api/projects/reference/scenes/s1/reshow", json={"archetype": "media_frame", "media": "ghost"}).status_code == 422
    assert client.delete(f"/api/projects/reference/media/{mid}").status_code == 200
    assert client.get("/api/projects/reference").json()["plan_notice"]["message"].startswith("The picture")      # a scene still used it: the user is told


def test_ai_kind_script_and_assistant_endpoints(ref, projects_dir, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from vt import paths
    from vt.server.app import app

    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    import vt.server.app as A

    monkeypatch.setattr(A, "SETTINGS_PATH", tmp_path / "settings.json", raising=False)
    c = TestClient(app)
    assert c.get("/api/ai/status").json()["available"] is False
    assert c.put(f"/api/projects/{ref.id}/video-kind", json={"kind": "stick"}).json()["kind"] == "stick"
    assert c.get(f"/api/projects/{ref.id}").json()["video_kind"] == "stick"
    assert c.put(f"/api/projects/{ref.id}/video-kind", json={"kind": "nope"}).status_code == 400
    task = c.get(f"/api/projects/{ref.id}/script/task").json()
    assert "Reply with ONLY the JSON" in task["message"] and task["schema"]["properties"]["scenes"]
    bad = c.post(f"/api/projects/{ref.id}/script/paste", json={"json": "not json"}).json()
    assert bad["ok"] is False
    con = c.get("/api/mcp/connect").json()
    assert len(con["token"]) >= 32 and "vt.mcp.server" in con["claude_code"] and con["claude_desktop"]["mcpServers"]["video-tool"]
    new = c.post("/api/mcp/token/revoke").json()["token"]
    assert new != con["token"]


def test_paste_script_applies_and_generate_job_runs(ref, projects_dir):
    import json
    import time

    from fastapi.testclient import TestClient

    from vt.planner import plan_rules
    from vt.script.rules_stick import rules_script
    from vt.server.app import app

    c = TestClient(app)
    tr, beats = ref.transcript(), ref.beats()
    sc = rules_script(tr, beats, plan_rules(tr, beats), kind="stick")
    txt = "Here you go:\n```json\n" + json.dumps(sc.model_dump(by_alias=True, exclude_none=True)) + "\n```"
    r = c.post(f"/api/projects/{ref.id}/script/paste", json={"json": txt}).json()
    assert r["ok"] is True and r["kind"] == "stick"
    assert c.get(f"/api/projects/{ref.id}/script").json()["script"]["kind"] == "stick"
    ref.save_scenes(plan_rules(tr, beats))                           # back to a plain plan, then let the job direct it again
    job = c.post(f"/api/projects/{ref.id}/script/generate?kind=stick").json()
    for _ in range(100):
        j = c.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.2)
    assert j["status"] == "done" and j["result"]["how"].startswith("rules"), j


def test_dashboard_fields_and_duplicate(ref, projects_dir):
    from fastapi.testclient import TestClient

    from vt.server.app import app

    c = TestClient(app)
    row = [p for p in c.get("/api/projects").json() if p["id"] == ref.id][0]
    assert row["updated_at"] and row["export_count"] == 0 and row["last_export"] is None and row["cover_url"] is None
    (ref.exports_dir).mkdir(exist_ok=True)
    (ref.exports_dir / "x.mp4").write_bytes(b"0")
    (ref.exports_dir / "cover.jpg").write_bytes(b"0")
    row = [p for p in c.get("/api/projects").json() if p["id"] == ref.id][0]
    assert row["export_count"] == 1 and row["last_export_url"].endswith("x.mp4") and row["cover_url"]
    dup = c.post(f"/api/projects/{ref.id}/duplicate").json()
    assert dup["id"] == f"{ref.id}-copy" and dup["title"].endswith("(copy)") and dup["scene_count"] == row["scene_count"]
    assert not (projects_dir / dup["id"] / "exports").exists()
    assert c.post(f"/api/projects/{ref.id}/duplicate").json()["id"] == f"{ref.id}-copy-2"


def test_unknown_api_paths_are_404_not_405_and_versions_agree():
    """Regression: a POST to an endpoint an older server did not have fell into the page's GET-only catch-all and answered 405.
    Also: the version the server reports must equal the one the page expects."""
    import re
    from pathlib import Path

    from fastapi.testclient import TestClient

    from vt.server.app import API_VERSION, app

    c = TestClient(app)
    for method in ("get", "post", "put", "patch", "delete"):
        r = getattr(c, method)("/api/projects/x/does-not-exist")
        assert r.status_code == 404 and "restart" in r.text.lower(), (method, r.status_code)
    assert c.get("/api/health").json()["api_version"] == API_VERSION
    ts = (Path(__file__).resolve().parents[1] / "studio" / "src" / "api.ts").read_text(encoding="utf-8")
    assert int(re.search(r"EXPECTED_API = (\d+)", ts).group(1)) == API_VERSION


def test_every_endpoint_the_studio_calls_exists_with_that_method():
    """Scan the page's source for api calls and check each (method, path) against the server's routes: a wrong verb or a missing route fails here, not in the browser."""
    import re
    from pathlib import Path

    from vt.server.app import app

    def flatten(items):
        """Routes of the app, including those of routers added with include_router (this FastAPI wraps them: original_router + prefix)."""
        for r in items:
            if hasattr(r, "methods"):
                yield r
            elif hasattr(r, "original_router"):
                prefix = getattr(getattr(r, "include_context", None), "prefix", "") or ""
                for sub in flatten(r.original_router.routes):
                    yield type("R", (), {"path": prefix + sub.path, "methods": sub.methods})

    routes = []
    for r in flatten(app.routes):
        if r.path.startswith("/api"):
            routes.append((r.path, set(r.methods)))
    pat = {m: re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", p) + "$") for p, m in [(p, tuple(sorted(ms))) for p, ms in routes]}
    src = Path(__file__).resolve().parents[1] / "studio" / "src"
    calls = set()
    for f in src.rglob("*.ts*"):
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\b(get|post|put|patch|del|api<[^>]*>\(\"(?:GET|POST|PUT|PATCH|DELETE)\")\s*(?:<[^>]*>)?\(\s*[`\"'](/api/[^`\"'?]*)", t):
            verb = {"del": "DELETE"}.get(m.group(1), m.group(1).upper())
            calls.add((verb, re.sub(r"\$\{[^}]+\}", "x", m.group(2))))
    assert len(calls) > 40, len(calls)
    bad = []
    for verb, path in sorted(calls):
        def fits(p: str) -> bool:                      # a ${variable} in the call matches any segment, a {param} in the route matches any text
            a, b = p.strip("/").split("/"), path.strip("/").split("/")
            return len(a) == len(b) and all(x == y or x.startswith("{") or y == "x" for x, y in zip(a, b))

        ok = any(verb in ms and fits(p) for p, ms in routes)
        if not ok:
            bad.append((verb, path))
    assert not bad, bad


def test_double_submits_do_not_start_the_work_twice(ref, projects_dir):
    """A second click / a reload while the same job runs: 'reuse' kinds return the running job, export refuses with 409."""
    import threading

    from vt.server.app import jobs

    gate = threading.Event()
    j1 = jobs.submit("qa", ref.id, "Check the frames", lambda cb: gate.wait(5), when_busy="reuse")
    j2 = jobs.submit("qa", ref.id, "Check the frames", lambda cb: None, when_busy="reuse")
    assert j2.id == j1.id
    other = jobs.submit("qa", "other-project", "Check the frames", lambda cb: None, when_busy="reuse")
    assert other.id != j1.id
    from vt.server.jobs import JobBusy

    e1 = jobs.submit("export", ref.id, "Export", lambda cb: gate.wait(5), when_busy="refuse")
    import pytest

    with pytest.raises(JobBusy):
        jobs.submit("export", ref.id, "Export", lambda cb: None, when_busy="refuse")
    gate.set()
    for _ in range(50):
        if jobs.jobs[e1.id].status == "done":
            break
        import time

        time.sleep(0.1)
    assert jobs.submit("export", ref.id, "Export", lambda cb: None, when_busy="refuse").id != e1.id        # free again once done


def test_reading_project_files_survives_concurrent_rewrites(ref):
    """Regression: parallel requests (a slider moved quickly) made `read_json` fail with PermissionError while another request replaced project.json (HTTP 500)."""
    import threading

    from vt.util import read_json, write_json

    f = ref.meta_path
    data = read_json(f)
    stop, errors = threading.Event(), []

    def writer():
        while not stop.is_set():
            write_json(f, data)

    def reader():
        for _ in range(300):
            try:
                assert read_json(f)["id"] == data["id"]
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))

    w = threading.Thread(target=writer)
    rs = [threading.Thread(target=reader) for _ in range(4)]
    w.start()
    [r.start() for r in rs]
    [r.join() for r in rs]
    stop.set()
    w.join()
    assert not errors, errors[:3]


def test_parallel_edits_do_not_collide_while_composing(ref, projects_dir):
    """Regression: a dropdown changed twice quickly sent two PATCHes at once; both composed the same files with the same temp name and one failed with HTTP 500
    (FileNotFoundError index.html.tmp). Edits to one project now compose one at a time, and temp files are unique per writer."""
    import threading

    from fastapi.testclient import TestClient

    from vt.server.app import app

    c = TestClient(app)
    sid = c.get(f"/api/projects/{ref.id}/scenes").json()["plan"]["scenes"][0]["id"]
    codes = []

    def edit(layout):
        for _ in range(4):
            codes.append(c.patch(f"/api/projects/{ref.id}/scenes/{sid}", json={"layout": layout}).status_code)

    ts = [threading.Thread(target=edit, args=(lay,)) for lay in ("stack", "hero", "split", "stack", "hero")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert set(codes) == {200}, codes
    from vt.compose.composer import _put

    f = ref.comp_dir / "9x16" / "x.bin"
    errs = []

    def w(i):
        try:
            for _ in range(30):
                _put(f, bytes([i]) * 5000)
        except Exception as e:  # noqa: BLE001
            errs.append(repr(e))

    ws = [threading.Thread(target=w, args=(i,)) for i in range(6)]
    [t.start() for t in ws]
    [t.join() for t in ws]
    assert not errs and len(f.read_bytes()) == 5000 and not list(f.parent.glob("x.bin.*.tmp"))


def test_media_files_are_served_whole_and_missing_ones_are_404(client):
    r = client.get("/media/reference/scenes.json")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    assert int(r.headers["content-length"]) == len(r.content)
    assert client.get("/media/reference/composition/9x16/nope.html").status_code == 404
    assert client.get("/media/..%2f..%2fsettings.json").status_code in (400, 404)


def test_a_planned_project_without_a_composition_gets_one_when_the_preview_asks(client, projects_dir):
    assert not (projects_dir / "reference" / "composition" / "9x16" / "index.html").exists()
    r = client.get("/media/reference/composition/9x16/index.html")
    assert r.status_code == 200 and "<html" in r.text.lower()
    assert client.get("/media/reference/composition/9x16/data.json").status_code == 200
    assert client.get("/media/nope-project/composition/9x16/index.html").status_code == 404


def test_audio_is_served_with_range_support(client, projects_dir):
    (projects_dir / "reference" / "audio.preview.m4a").write_bytes(bytes(range(256)) * 8)
    assert client.get("/media/reference/missing.m4a", headers={"Range": "bytes=0-9"}).status_code == 404
    r = client.get("/media/reference/audio.preview.m4a", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100
    assert client.get("/media/reference/audio.preview.m4a").headers.get("accept-ranges") == "bytes"


def test_a_pasted_sentence_corrects_the_words_and_keeps_their_times(client):
    from vt.project import Project

    p = Project("reference")
    beats = p.beats().beats
    b = beats[0]
    before = {w.id: w for w in p.transcript().words if w.id in set(b.word_ids)}
    first = next(iter(before.values()))
    text = " ".join(w.text for w in before.values()) + " বাড়তি"
    dry = client.put("/api/projects/reference/transcript", json={"text": text, "beat": b.id, "dry": True}).json()
    assert dry["applied"] is False and dry["changed"] == 1
    r = client.put("/api/projects/reference/transcript", json={"text": text, "beat": b.id}).json()
    assert r["applied"] is True
    after = {w.id: w for w in Project("reference").transcript().words}
    last = list(before)[-1]
    assert after[last].text.endswith("বাড়তি")
    assert after[first.id].start == first.start                                 # the real time of the word is untouched
    assert client.put("/api/projects/reference/transcript", json={"text": "  ", "beat": b.id}).status_code == 422
    assert client.put("/api/projects/reference/transcript", json={"text": "x", "beat": "b999"}).status_code == 404
    gone = client.put("/api/projects/reference/transcript", json={"text": " ".join(w.text for w in list(before.values())[:-1]), "beat": b.id}).json()
    assert Project("reference").transcript().words[-1].id != last or len(Project("reference").transcript().words) < len(after)


def test_a_text_change_can_be_undone_and_redone(client):
    from vt.project import Project

    b = Project("reference").beats().beats[0]
    n = len(Project("reference").transcript().words)
    assert client.post("/api/projects/reference/transcript/undo").status_code == 409
    client.put("/api/projects/reference/transcript", json={"text": "একদম নতুন লেখা", "beat": b.id})
    assert len(Project("reference").transcript().words) != n or "নতুন" in " ".join(w.text for w in Project("reference").transcript().words)
    assert client.post("/api/projects/reference/transcript/undo").json()["ok"]
    assert len(Project("reference").transcript().words) == n
    assert "নতুন" not in " ".join(w.text for w in Project("reference").transcript().words)
