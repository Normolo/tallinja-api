"""Ties fetch + parse + cache together behind one call the API layer uses,
guarded by a rate limiter and circuit breaker so we don't hammer the origin.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from .cache import TTLCache
from .config import settings
from .errors import InvalidStopCode, StopNotFound, UpstreamUnavailable
from .fetcher import fetch_board_html
from .models import DeparturesResponse
from .parser import parse_board
from .resilience import CircuitBreaker, RateLimiter

_STOP_CODE_RE = re.compile(settings.stop_code_pattern)

# Cache the fully-built response so repeated hits within the TTL skip fetch+parse.
_cache: TTLCache[DeparturesResponse] = TTLCache(settings.cache_ttl_seconds)
_breaker = CircuitBreaker(settings.circuit_failure_threshold, settings.circuit_cooldown_seconds)
_rate_limiter = RateLimiter(settings.min_request_interval_seconds)


def validate_stop_code(stop_code: str) -> str:
    code = stop_code.strip()
    if not _STOP_CODE_RE.match(code):
        raise InvalidStopCode(f"'{stop_code}' is not a valid stop code")
    return code


async def get_departures(
    stop_code: str, client: httpx.AsyncClient | None = None
) -> DeparturesResponse:
    code = validate_stop_code(stop_code)

    cached = _cache.get(code)
    if cached is not None:
        return cached.model_copy(update={"cached": True})

    # Fast-fail while the breaker is open, then space out the actual origin call.
    await _breaker.acquire()
    await _rate_limiter.wait()
    try:
        html = await fetch_board_html(code, client=client)
    except StopNotFound:
        await _breaker.record_success()  # origin is healthy; this stop just doesn't exist
        raise
    except UpstreamUnavailable:
        await _breaker.record_failure()
        raise
    await _breaker.record_success()

    # A parse failure means the origin answered but the markup changed — that is
    # not an upstream-availability problem, so the breaker stays closed.
    stop, departures = parse_board(html, code)

    response = DeparturesResponse(
        stop=stop,
        retrieved_at=datetime.now(timezone.utc),
        cached=False,
        departures=departures,
    )
    _cache.set(code, response)
    return response


def clear_cache() -> None:
    _cache.clear()


def reset_for_tests(min_request_interval_seconds: float = 0.0) -> None:
    """Reset cache, breaker, and limiter between tests (state is module-global)."""
    global _breaker, _rate_limiter
    _cache.clear()
    _breaker = CircuitBreaker(
        settings.circuit_failure_threshold, settings.circuit_cooldown_seconds
    )
    _rate_limiter = RateLimiter(min_request_interval_seconds)
