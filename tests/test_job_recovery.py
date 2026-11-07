"""Restart recovery uses saved state and never replays work without a request."""
import threading

from vt.server.jobs import Job, JobManager
from vt.util import read_json, write_json


def test_restart_reports_running_and_queued_work_without_replaying(tmp_path):
    store = tmp_path / "jobs"
    store.mkdir()
    running = Job("running", "pipeline", "video", "Make video", status="running", stage="plan", frac=0.4)
    queued = Job("queued", "export", "video", "Export")
    done = Job("done", "pipeline", "other", "Finished", status="done", frac=1)
    for job in (running, queued, done):
        write_json(store / f"{job.id}.json", job.public())
    manager = JobManager(lambda event: None, store=lambda: store)
    manager.recover()
    assert manager.jobs["running"].status == "error"
    assert manager.jobs["queued"].status == "error"
    assert manager.jobs["done"].status == "done"
    assert manager.jobs["running"].interrupted
    assert "server stopped" in manager.jobs["running"].error.lower()
    assert manager.jobs["running"].stage == "plan"
    assert manager.jobs["running"].finished_at
    assert manager.active_for("video") is None
    assert manager._q.empty(), "saved callables are never replayed"
    assert read_json(store / "running.json")["status"] == "error"


def test_progress_is_saved_before_it_is_sent_to_the_browser(tmp_path):
    store = tmp_path / "jobs"
    messages = []
    reached = threading.Event()
    release = threading.Event()

    def event(message):
        public = message["job"]
        saved = read_json(store / f"{public['id']}.json")
        assert saved == public
        messages.append(public)

    manager = JobManager(event, store=lambda: store)

    def work(progress):
        progress("asr", 0.4, "Listening")
        reached.set()
        assert release.wait(5)

    job = manager.submit("pipeline", "video", "Make video", work)
    try:
        assert reached.wait(5)
        saved = read_json(store / f"{job.id}.json")
        assert saved["stage"] == "asr" and saved["status"] == "running"
        assert messages[0]["status"] == "queued"
    finally:
        release.set()
    from test_job_queue import wait_for

    wait_for(job)


def test_recovery_repairs_processing_project_and_preserves_finished_stages(ref, tmp_path):
    store = tmp_path / "jobs"
    store.mkdir()
    ref.update_meta(status="processing")
    ref.mark_stage("preprocess", "finished-audio")
    before = ref.meta().stages["preprocess"]
    manager = JobManager(lambda event: None, store=lambda: store)
    manager.recover()
    assert ref.meta().status == "interrupted", "also covers an upgrade from the old memory-only queue"
    assert ref.meta().stages["preprocess"] == before
    recovered = [job for job in manager.snapshot() if job.project == ref.id]
    assert len(recovered) == 1 and recovered[0].interrupted
    manager.recover()
    assert len(manager.snapshot()) == 1, "startup recovery is idempotent"


def test_broken_job_record_does_not_hide_other_interrupted_work(tmp_path):
    store = tmp_path / "jobs"
    store.mkdir()
    (store / "broken.json").write_text("{", encoding="utf-8")
    job = Job("valid", "pipeline", None, "Make video", status="running")
    write_json(store / "valid.json", job.public())
    manager = JobManager(lambda event: None, store=lambda: store)
    manager.recover()
    assert manager.jobs["valid"].interrupted


def test_a_queued_pipeline_also_offers_continue_on_its_project(ref, tmp_path):
    store = tmp_path / "jobs"
    store.mkdir()
    ref.update_meta(status="draft")
    job = Job("queued", "pipeline", ref.id, "Make video")
    write_json(store / "queued.json", job.public())
    manager = JobManager(lambda event: None, store=lambda: store)
    manager.recover()
    assert ref.meta().status == "interrupted"
    assert manager.jobs["queued"].interrupted


def test_continue_requests_the_cached_pipeline_without_forcing_stages(ref, monkeypatch):
    from vt.pipeline import Pipeline
    from vt.server import app as A
    from test_job_queue import wait_for

    manager = JobManager(lambda event: None)
    monkeypatch.setattr(A, "jobs", manager)
    calls = []
    monkeypatch.setattr(Pipeline, "run", lambda self, start, end, force: calls.append((start, end, force)))
    ref.update_meta(status="interrupted")
    response = A.run_project(ref.id, A.RunBody())
    wait_for(manager.jobs[response["id"]])
    assert calls == [(None, None, False)]
    assert manager.jobs[response["id"]].status == "done"
