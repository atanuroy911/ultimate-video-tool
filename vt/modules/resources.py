"""Named, ordered resource locks shared by all executors in this process."""
from __future__ import annotations

import threading
from contextlib import contextmanager


_LOCKS: dict[str, threading.RLock] = {}
_GUARD = threading.Lock()


@contextmanager
def acquire(names: tuple[str, ...]):
    from contextlib import ExitStack

    with _GUARD:
        locks = [_LOCKS.setdefault(name, threading.RLock()) for name in sorted(set(names))]
    with ExitStack() as stack:
        for lock in locks:
            stack.enter_context(lock)
        yield
