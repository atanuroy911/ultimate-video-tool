"""Concurrent requests must not duplicate work or lose queued videos."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from vt.server.jobs import JobBusy, JobManager


def wait_for(job):
    end = time.monotonic() + 5
    while job.status in ("queued", "running") and time.monotonic() < end:
        time.sleep(0.005)
    assert job.status not in ("queued", "running"), job.public()


@pytest.mark.parametrize("policy", ["reuse", "refuse"])
def test_simultaneous_requests_start_one_job(monkeypatch, policy):
    import vt.server.jobs as J

    original = J.uuid.uuid4

    def slow_id():
        # Widen the interval between the busy check and registration. Both
        # requests used to pass the check before either registered its job.
        time.sleep(0.03)
        return original()

    monkeypatch.setattr(J.uuid, "uuid4", slow_id)
    manager = JobManager(lambda event: None)
    ready = threading.Barrier(12)
    release = threading.Event()
    executed = []

    def work(progress):
        executed.append(True)
        assert release.wait(5)

    def request(_):
        ready.wait(timeout=5)
        try:
            return manager.submit("pipeline", "video", "Make video", work, when_busy=policy)
        except JobBusy as error:
            return error.job

    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            jobs = list(pool.map(request, range(12)))
        assert len({job.id for job in jobs}) == 1
        assert len(manager.jobs) == 1
    finally:
        release.set()
    for job in list(manager.jobs.values()):
        wait_for(job)
    assert len(executed) == 1


def test_two_videos_export_and_thumbnails_keep_their_results():
    manager = JobManager(lambda event: None)
    release = threading.Event()
    started = threading.Event()
    order = []

    def first(progress):
        started.set()
        assert release.wait(5)
        order.append("video one")
        return "one.mp4"

    one = manager.submit("pipeline", "one", "First video", first)
    assert started.wait(5)
    two = manager.submit("pipeline", "two", "Second video", lambda cb: order.append("video two") or "two.mp4")
    thumbs = manager.submit("thumbs", "one", "Thumbnails", lambda cb: order.append("thumbnails") or ["one.png"])
    export = manager.submit("export", "one", "Export", lambda cb: order.append("export") or "export.mp4", when_busy="refuse")
    assert manager.active_for("one") is one
    assert manager.active_for("two") is two
    release.set()
    for job in (one, two, thumbs, export):
        wait_for(job)
        assert job.status == "done", job.error
    assert order == ["video one", "video two", "thumbnails", "export"]
    assert [job.result for job in (one, two, thumbs, export)] == ["one.mp4", "two.mp4", ["one.png"], "export.mp4"]
    assert manager.active_for("one") is None


def test_cancelled_queued_video_is_not_run_and_next_job_finishes():
    manager = JobManager(lambda event: None)
    release = threading.Event()
    first = manager.submit("pipeline", "one", "First", lambda cb: release.wait(5))
    called = []
    cancelled = manager.submit("pipeline", "two", "Second", lambda cb: called.append(True))
    last = manager.submit("export", "one", "Export", lambda cb: "ok")
    assert manager.cancel(cancelled.id)
    release.set()
    wait_for(first)
    wait_for(last)
    assert cancelled.status == "cancelled" and not called
    assert last.result == "ok"
