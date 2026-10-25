"""Clocks. Leases use a clock, so tests can use a manual one."""

from __future__ import annotations

import threading
import time
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float:
        """Seconds, never going backwards."""
        ...


class MonotonicClock:
    """The real clock."""

    def now(self) -> float:
        return time.monotonic()


class ManualClock:
    """A clock that only moves when told to. Thread safe."""

    def __init__(self, start: float = 0.0) -> None:
        self._t = float(start)
        self._lock = threading.Lock()

    def now(self) -> float:
        with self._lock:
            return self._t

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("a clock cannot go backwards")
        with self._lock:
            self._t += float(seconds)
