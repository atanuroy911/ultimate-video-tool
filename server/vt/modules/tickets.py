"""In-process tickets for interruptible JSON-producing module calls."""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, CancelledError
from typing import Callable

from .envelope import CallResult


_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="vt-module")
_TICKETS: dict[str, tuple[Future, threading.Event]] = {}
_LOCK = threading.RLock()


def submit(run: Callable[[threading.Event], CallResult]) -> str:
    ticket = "t" + uuid.uuid4().hex[:12]
    cancelled = threading.Event()
    future = _POOL.submit(run, cancelled)
    with _LOCK:
        _TICKETS[ticket] = (future, cancelled)
    return ticket


def wait(ticket: str, timeout: float | None = None) -> CallResult:
    with _LOCK:
        future, _ = _TICKETS[ticket]
    try:
        return future.result(timeout=timeout)
    except CancelledError:
        return CallResult(ok=False, status="cancelled", summary="The step was cancelled.")


def cancel(ticket: str) -> bool:
    with _LOCK:
        future, event = _TICKETS[ticket]
    event.set()
    return future.cancel() or not future.done()
