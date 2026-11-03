"""Per-run wall-time budget accounting for module calls."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass
class Budget:
    seconds: float
    spent: float = 0.0

    def __post_init__(self) -> None:
        self._lock = RLock()

    def allows(self, estimate: float) -> bool:
        with self._lock:
            return self.spent + estimate <= self.seconds

    def charge(self, elapsed: float) -> None:
        with self._lock:
            self.spent += elapsed

    @property
    def left(self) -> float:
        with self._lock:
            return max(0.0, self.seconds - self.spent)
