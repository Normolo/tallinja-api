from __future__ import annotations

import asyncio
import time

import pytest

from app.errors import CircuitOpen
from app.resilience import CircuitBreaker, RateLimiter


async def test_breaker_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=10)
    await cb.acquire()
    await cb.record_failure()  # 1 — still closed
    await cb.acquire()
    await cb.record_failure()  # 2 — opens
    with pytest.raises(CircuitOpen):
        await cb.acquire()
    assert cb.state == "open"


async def test_breaker_success_resets_failures():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=10)
    await cb.acquire()
    await cb.record_failure()
    await cb.acquire()
    await cb.record_success()  # resets the count
    await cb.acquire()
    await cb.record_failure()  # only 1 since reset -> still closed
    await cb.acquire()  # does not raise


async def test_breaker_half_open_trial_recovers():
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05)
    await cb.acquire()
    await cb.record_failure()  # opens immediately
    with pytest.raises(CircuitOpen):
        await cb.acquire()
    await asyncio.sleep(0.06)  # cooldown elapses
    await cb.acquire()  # half-open trial allowed
    assert cb.state == "half_open"
    await cb.record_success()
    assert cb.state == "closed"


async def test_breaker_half_open_failure_reopens():
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05)
    await cb.acquire()
    await cb.record_failure()
    await asyncio.sleep(0.06)
    await cb.acquire()  # trial
    await cb.record_failure()  # trial fails -> reopen
    with pytest.raises(CircuitOpen):
        await cb.acquire()


async def test_circuit_open_reports_retry_after():
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=30)
    await cb.acquire()
    await cb.record_failure()
    with pytest.raises(CircuitOpen) as exc_info:
        await cb.acquire()
    assert 0 < exc_info.value.retry_after_seconds <= 30


async def test_rate_limiter_spaces_calls():
    rl = RateLimiter(0.1)
    await rl.wait()  # first call sets the clock
    start = time.monotonic()
    await rl.wait()  # second must wait ~0.1s
    assert time.monotonic() - start >= 0.09


async def test_rate_limiter_zero_interval_is_noop():
    rl = RateLimiter(0)
    await rl.wait()
    await rl.wait()  # no delay, no error
