"""A job keeps its own log: the steps it reports, the lines it logs, how it ended (vt/server/jobs.py, GET /api/jobs/{id}/log)."""
import logging
import time

from vt.server.jobs import JobManager


def _wait(job, secs=5.0):
    end = time.time() + secs
    while job.status in ("queued", "running") and time.time() < end:
        time.sleep(0.02)


def test_steps_and_log_lines_are_kept_and_readable_in_pieces():
    m = JobManager(lambda e: None)

    def work(progress):
        progress("listening", 0.2, "first words")
        logging.getLogger("vt.test").info("heard 12 words")
        progress("planning", 0.6, "")
        return "ok"

    job = m.submit("pipeline", "p1", "Making a video", work)
    _wait(job)
    assert job.status == "done" and job.started_at and job.finished_at
    texts = [ln["text"] for ln in job.log_after(0)["lines"]]
    assert any("listening" in t and "first words" in t for t in texts)
    assert any("heard 12 words" in t for t in texts)
    assert texts[-1] == "Finished"
    first = job.log_after(0)["lines"][0]["n"]
    assert all(ln["n"] > first for ln in job.log_after(first)["lines"])


def test_a_failed_job_logs_the_reason_and_the_trace():
    m = JobManager(lambda e: None)

    def boom(progress):
        raise RuntimeError("the card ran out of memory")

    job = m.submit("export", "p2", "Exporting", boom)
    _wait(job)
    levels = {ln["level"] for ln in job.log_after(0)["lines"]}
    assert job.status == "error" and {"error", "trace"} <= levels
