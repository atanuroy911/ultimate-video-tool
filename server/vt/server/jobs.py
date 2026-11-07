"""A tiny single-worker job queue (the GPU is the bottleneck, so jobs run one at a time)."""
from __future__ import annotations

import logging
import errno
import re
import queue
import threading
import time
import traceback
import uuid
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ..util import Cancelled, now_iso, read_json, write_json
from ..modules.calls import redact


log = logging.getLogger("vt.jobs")


DIRECTED = {"media", "plan", "qa", "autofix", "director", "polish", "context", "publish", "scene-direction", "redraw", "shorts"}      # the jobs that ask an AI about a video


class JobBusy(Exception):
    """The same kind of job is already running for this project and the caller asked not to start another."""

    def __init__(self, job: "Job"):
        super().__init__(f"{job.label} is already running")
        self.job = job


class ServerRestarting(Exception):
    pass


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
    interrupted: bool = False
    lines: list = field(default_factory=list, repr=False)      # the job's own log: every step it reports and every log line it writes (newest 3000), shown on the Server page
    seq: int = 0
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def public(self) -> dict:
        """JSON-safe view (asdict would try to deep-copy the cancel Event, which cannot be pickled)."""
        return redact({k: getattr(self, k) for k in ("id", "kind", "project", "label", "status", "stage", "frac", "msg", "result", "error", "created_at", "started_at", "finished_at", "interrupted")})

    def add(self, level: str, text: str) -> None:
        self.seq += 1
        self.lines.append({"n": self.seq, "t": round(time.time(), 2), "level": level, "text": redact(text)[:2000]})
        if len(self.lines) > 3200:
            del self.lines[:200]

    def log_after(self, after: int = 0) -> dict:
        return redact({"lines": [ln for ln in list(self.lines) if ln["n"] > after], "status": self.status})


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
    def __init__(self, on_event: Callable[[dict], None], store: Optional[Callable[[], Path]] = None):
        self.current: Optional[Job] = None
        self.jobs: dict[str, Job] = {}
        self._lock = threading.RLock()
        self._accepting = True
        self._store = store
        self._recovered: set[Path] = set()
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
        # API requests run in different threads. Checking and registering must
        # be one operation or two clicks can both find no existing job.
        with self._lock:
            if not self._accepting:
                raise ServerRestarting("The server is restarting. It will reconnect shortly; then try again.")
            if when_busy != "queue":
                for j in self.jobs.values():
                    if j.kind == kind and j.project == project and j.status in ("queued", "running"):
                        if when_busy == "reuse":
                            return j
                        raise JobBusy(j)
            job = Job(id=uuid.uuid4().hex[:10], kind=kind, project=project, label=label)
            self.jobs[job.id] = job
            self._emit(job)
            self._q.put((job, fn))
            return job

    def snapshot(self) -> list[Job]:
        """Copy the collection before API/worker threads can add another job."""
        with self._lock:
            return list(self.jobs.values())

    def pause_submissions(self) -> bool:
        with self._lock:
            if any(job.status in ("queued","running") for job in self.jobs.values()) or not self._accepting:
                return False
            self._accepting = False
            return True

    def resume_submissions(self) -> None:
        with self._lock:
            self._accepting = True

    @property
    def restarting(self) -> bool:
        with self._lock:
            return not self._accepting

    def recover(self) -> None:
        """At server startup, expose unfinished work as interrupted, never replay it.

        A Continue request runs the normal pipeline with force=False: its input
        hashes and finished-stage outputs decide what can safely be reused.
        """
        if self._store is None:
            return
        from ..project import Project

        with self._lock:
            folder = self._store()
            if folder in self._recovered:
                return
            interrupted_projects = set()
            for file in sorted(folder.glob("*.json")):
                try:
                    data = read_json(file)
                    if not isinstance(data, dict) or data.get("id") != file.stem or not re.fullmatch(r"[A-Za-z0-9_-]+", file.stem):
                        raise ValueError("invalid job record")
                    keys = Job("", "", None, "").public()
                    job = Job(**{key: value for key, value in data.items() if key in keys})
                    if job.status in ("queued", "running"):
                        if job.kind == "pipeline" and job.project:
                            interrupted_projects.add(job.project)
                        job.status, job.interrupted = "error", True
                        job.error = "The server stopped before this job finished. You can continue; completed stages are kept."
                        job.finished_at = now_iso()
                        job.add("warning", job.error)
                        self.jobs[job.id] = job
                        self._emit(job)
                    else:
                        self.jobs[job.id] = job
                except (OSError, ValueError, TypeError):
                    log.warning("Could not recover job record %s", file.name, exc_info=True)
            for project in Project.list_all():
                try:
                    if project.meta().status != "processing" and project.id not in interrupted_projects:
                        continue
                    project.update_meta(status="interrupted")
                    # Upgrades from the memory-only queue have no saved job.
                    if not any(j.project == project.id and j.interrupted and j.kind == "pipeline" for j in self.snapshot()):
                        job = Job(uuid.uuid4().hex[:10], "pipeline", project.id, "Make video", status="error", interrupted=True,
                                  error="The server stopped before this video finished. You can continue; completed stages are kept.", finished_at=now_iso())
                        self.jobs[job.id] = job
                        self._emit(job)
                except (OSError, ValueError):
                    log.warning("Could not recover project %s", project.id, exc_info=True)
            self._recovered.add(folder)

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
        for j in self.snapshot():
            if j.project == project and j.kind in kinds and j.status in ("queued", "running"):
                return j
        return None

    def _emit(self, job: Job) -> None:
        with self._lock:
            public = job.public()
            if self._store is not None:
                try:
                    write_json(self._store() / f"{job.id}.json", public)
                except (OSError, TypeError, ValueError):
                    log.warning("Could not save job %s for restart recovery", job.id, exc_info=True)
            self._on_event({"type": "job", "job": public})

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
                if job.kind == "pipeline":
                    from ..pipeline import ORDER
                    order = [*ORDER, "render", "check", "publish"]
                    if stage in order and job.stage in order and order.index(stage) < order.index(job.stage):
                        return  # a heartbeat from a finished stage arrived late
                frac = max(0.0, min(1.0, float(frac)))
                frac = max(frac, job.frac) if stage == job.stage else frac
                if stage != job.stage or (msg and msg != job.msg):
                    job.add("step", f"{stage} · {int(float(frac) * 100)}%" + (f" · {msg}" if msg else ""))
                job.stage, job.frac, job.msg = stage, frac, str(msg)
                now = time.time()
                if now - last["t"] > 0.25 or frac in (0.0, 1.0):  # throttle websocket chatter
                    last["t"] = now
                    self._emit(job)

            try:
                with self._directed(job):
                    job.result = fn(progress)
                if job.cancel.is_set():
                    raise Cancelled()
                job.status, job.frac = "done", 1.0
                job.add("info", "Finished")
            except Cancelled:
                job.status = "cancelled"
                job.result = None
                job.msg = "Stopped by you. Continue when you are ready."
                job.add("warning", "Cancelled")
            except Exception as e:  # noqa: BLE001
                job.status = "error"
                full = isinstance(e, OSError) and (e.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)) or getattr(e, "winerror", None) in (39, 112))
                job.error = "The server needs more disk space. Free some space, then try this job again. Completed stages are kept." if full else str(e)
                job.add("error", job.error)
                job.add("trace", traceback.format_exc())
                log.error("job %s (%s) failed: %s", job.id, redact(job.label), redact(traceback.format_exc()))
            job.finished_at = now_iso()
            self.current = None
            self._emit(job)
