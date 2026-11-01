"""A tiny single-worker job queue (the GPU is the bottleneck, so jobs run one at a time)."""
from __future__ import annotations

import logging
import queue
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..util import now_iso


log = logging.getLogger("vt.jobs")


class Cancelled(Exception):
    pass


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
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def public(self) -> dict:
        """JSON-safe view (asdict would try to deep-copy the cancel Event, which cannot be pickled)."""
        return {k: getattr(self, k) for k in ("id", "kind", "project", "label", "status", "stage", "frac", "msg", "result", "error", "created_at")}


class JobManager:
    def __init__(self, on_event: Callable[[dict], None]):
        self.jobs: dict[str, Job] = {}
        self._q: "queue.Queue[tuple[Job, Callable[[Callable], Any]]]" = queue.Queue()
        self._on_event = on_event
        self._t = threading.Thread(target=self._worker, daemon=True, name="vt-jobs")
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
            self._emit(job)

            last = {"t": 0.0}

            def progress(stage: str, frac: float, msg: str = "") -> None:
                import time
                if job.cancel.is_set():
                    raise Cancelled()
                job.stage, job.frac, job.msg = stage, float(frac), str(msg)
                now = time.time()
                if now - last["t"] > 0.25 or frac in (0.0, 1.0):  # throttle websocket chatter
                    last["t"] = now
                    self._emit(job)

            try:
                job.result = fn(progress)
                job.status, job.frac = "done", 1.0
            except Cancelled:
                job.status = "cancelled"
            except Exception as e:  # noqa: BLE001
                job.status = "error"
                job.error = str(e)                      # plain message for the UI; the traceback goes to the server log only
                log.error("job %s (%s) failed: %s", job.id, job.label, traceback.format_exc())
            self._emit(job)
