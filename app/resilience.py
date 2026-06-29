"""Resilience primitives that keep us from hammering a bot-protected origin.

* ``RateLimiter`` — enforces a minimum interval between origin fetches.
* ``CircuitBreaker`` — after repeated upstream failures, fast-fails for a
  cooldown instead of piling on more (slowloris-looking) connections, then
  probes with a single trial request before fully reopening.
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum

from .errors import CircuitOpen


class RateLimiter:
    """Serializes callers and spaces them at least ``min_interval`` apart."""

    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval = min_interval_seconds
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        if self._min_interval <= 0:
            return
        async with self._lock:
            delay = self._min_interval - (time.monotonic() - self._last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


class _State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """A standard closed/open/half-open breaker.

    Usage: ``await acquire()`` before the call (raises ``CircuitOpen`` when the
    circuit is open), then ``record_success()`` / ``record_failure()`` after.
    """

    def __init__(self, failure_threshold: int, cooldown_seconds: float) -> None:
        self._threshold = max(1, failure_threshold)
        self._cooldown = cooldown_seconds
        self._failures = 0
        self._state = _State.CLOSED
        self._opened_at = 0.0
        self._trial_in_flight = False
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state.value

    async def acquire(self) -> None:
        async with self._lock:
            if self._state is _State.OPEN:
                elapsed = time.monotonic() - self._opened_at
                if elapsed < self._cooldown:
                    raise CircuitOpen(self._cooldown - elapsed)
                # Cooldown elapsed: allow a single trial request through.
                self._state = _State.HALF_OPEN
                self._trial_in_flight = True
                return
            if self._state is _State.HALF_OPEN and self._trial_in_flight:
                # A probe is already in flight; keep fast-failing until it settles.
                raise CircuitOpen(self._cooldown)
            if self._state is _State.HALF_OPEN:
                self._trial_in_flight = True

    async def record_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._state = _State.CLOSED
            self._trial_in_flight = False

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            self._trial_in_flight = False
            if self._state is _State.HALF_OPEN or self._failures >= self._threshold:
                self._state = _State.OPEN
                self._opened_at = time.monotonic()
