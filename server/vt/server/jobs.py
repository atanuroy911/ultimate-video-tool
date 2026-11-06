"""A tiny single-worker job queue (the GPU is the bottleneck, so jobs run one at a time)."""
from __future__ import annotations

import logging
import queue
import threading
import time
import traceback
import uuid
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..util import now_iso


log = logging.getLogger("vt.jobs")


class Cancelled(Exception):
    pass


DIRECTED = {"media", "plan", "qa", "autofix", "director", "polish", "context", "publish", "scene-direction", "redraw", "shorts"}      # the jobs that ask an AI about a video


class JobBusy(Exception):
    """The same kind of job is already running for this project and the caller asked not to start another."""

    def __init__(self, job: "Job"):
        super().__init__(f"{job.label} is already running")
        self.job = job


@dataclass
class Job:
    id: str
    kind: str
    project: Optional[str]
    label: str
    status: str = "queued"  # queued | running | done | error | cancelled
    stage: str = ""
    frac: float = 0.0
    msg: str = ""
    result: Any = None
    error: str = ""
    created_at: str = field(default_factory=now_iso)
    started_at: str = ""
    finished_at: str = ""
    lines: list = field(default_factory=list, repr=False)      # the job's own log: every step it reports and every log line it writes (newest 3000), shown on the Server page
    seq: int = 0
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def public(self) -> dict:
        """JSON-safe view (asdict would try to deep-copy the cancel Event, which cannot be pickled)."""
        return {k: getattr(self, k) for k in ("id", "kind", "project", "label", "status", "stage", "frac", "msg", "result", "error", "created_at", "started_at", "finished_at")}

    def add(self, level: str, text: str) -> None:
        self.seq += 1
        self.lines.append({"n": self.seq, "t": round(time.time(), 2), "level": level, "text": text[:2000]})
        if len(self.lines) > 3200:
            del self.lines[:200]

    def log_after(self, after: int = 0) -> dict:
        return {"lines": [ln for ln in list(self.lines) if ln["n"] > after], "status": self.status}


class _JobLog(logging.Handler):
    """Copies what the code logs while a job runs into that job's own log."""

    def __init__(self, manager: "JobManager"):
        super().__init__(level=logging.INFO)
        self.manager = manager

    def emit(self, record: logging.LogRecord) -> None:
        job = self.manager.current
        if job is not None and threading.current_thread() is self.manager._t and record.name != "vt.jobs":
            try:
                job.add(record.levelname.lower(), f"{record.name}: {record.getMessage()}")
            except Exception:                           # a log line must never break a job
                pass


class JobManager:
    def __init__(self, on_event: Callable[[dict], None]):
        self.current: Optional[Job] = None
        self.jobs: dict[str, Job] = {}
        self._q: "queue.Queue[tuple[Job, Callable[[Callable], Any]]]" = queue.Queue()
        self._on_event = on_event
        self._t = threading.Thread(target=self._worker, daemon=True, name="vt-jobs")
        vt_log = logging.getLogger("vt")
        if vt_log.level in (logging.NOTSET, logging.WARNING):
            vt_log.setLevel(logging.INFO)
        vt_log.addHandler(_JobLog(self))
        self._t.start()

    def submit(self, kind: str, project: Optional[str], label: str, fn: Callable[[Callable], Any], when_busy: str = "queue") -> Job:
        """fn receives a progress callback (stage, frac, msg) that also raises Cancelled when the job is cancelled.
        when_busy: if a job of the same kind is already queued or running for this project, "queue" (start another), "reuse" (return the running one: a double
        click or a page reload does not start the work twice) or "refuse" (raise JobBusy, which the API answers with 409)."""
        if when_busy != "queue":
            for j in self.jobs.values():
                if j.kind == kind and j.project == project and j.status in ("queued", "running"):
                    if when_busy == "reuse":
                        return j
                    raise JobBusy(j)
        job = Job(id=uuid.uuid4().hex[:10], kind=kind, project=project, label=label)
        self.jobs[job.id] = job
        self._q.put((job, fn))
        self._emit(job)
        return job

    def _directed(self, job: Job):
        """The AI steps of a job on a video go to that video's director and onto its record, the same as the pipeline's own stages."""
        if job.project and job.kind in DIRECTED:
            try:
                from ..pipeline import directing
                from ..project import Project

                p = Project(job.project)
                if p.exists():
                    return directing(p)
            except Exception:                                      # noqa: BLE001  a job still runs when its video cannot be looked up
                log.warning("job %s runs without its video's director", job.id, exc_info=True)
        return nullcontext()

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job or job.status not in ("queued", "running"):
            return False
        job.cancel.set()
        if job.status == "queued":
            job.status = "cancelled"
            self._emit(job)
        return True

    def active_for(self, project: str, kinds: tuple[str, ...] = ("pipeline", "export")) -> Optional[Job]:
        """The running/queued job that makes a project 'busy'. Background chores such as thumbnails do not count."""
        for j in self.jobs.values():
            if j.project == project and j.kind in kinds and j.status in ("queued", "running"):
                return j
        return None

    def _emit(self, job: Job) -> None:
        self._on_event({"type": "job", "job": job.public()})

    def _worker(self) -> None:
        while True:
            job, fn = self._q.get()
            if job.cancel.is_set():
                job.status = "cancelled"
                self._emit(job)
                continue
            job.status = "running"
            job.started_at = now_iso()
            self.current = job
            job.add("info", f"Started: {job.label}")
            self._emit(job)

            last = {"t": 0.0}

            def progress(stage: str, frac: float, msg: str = "") -> None:
                import time
                if job.cancel.is_set():
                    raise Cancelled()
                if stage != job.stage or (msg and msg != job.msg):
                    job.add("step", f"{stage} · {int(float(frac) * 100)}%" + (f" · {msg}" if msg else ""))
                frac = max(float(frac), job.frac) if stage == job.stage else float(frac)      # a stage never runs backward, whichever step inside it reports
                job.stage, job.frac, job.msg = stage, frac, str(msg)
                now = time.time()
                if now - last["t"] > 0.25 or frac in (0.0, 1.0):  # throttle websocket chatter
                    last["t"] = now
                    self._emit(job)

            try:
                with self._directed(job):
                    job.result = fn(progress)
                job.status, job.frac = "done", 1.0
                job.add("info", "Finished")
            except Cancelled:
                job.status = "cancelled"
                job.add("warning", "Cancelled")
            except Exception as e:  # noqa: BLE001
                job.status = "error"
                job.error = str(e)                      # plain message for the UI; the traceback goes to the server log only
                job.add("error", job.error)
                job.add("trace", traceback.format_exc())
                log.error("job %s (%s) failed: %s", job.id, job.label, traceback.format_exc())
            job.finished_at = now_iso()
            self.current = None
            self._emit(job)
