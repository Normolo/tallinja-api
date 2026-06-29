"""Ties fetch + parse + cache together behind one call the API layer uses."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from .cache import TTLCache
from .config import settings
from .errors import InvalidStopCode
from .fetcher import fetch_board_html
from .models import DeparturesResponse
from .parser import parse_board

_STOP_CODE_RE = re.compile(settings.stop_code_pattern)

# Cache the fully-built response so repeated hits within the TTL skip fetch+parse.
_cache: TTLCache[DeparturesResponse] = TTLCache(settings.cache_ttl_seconds)


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

    html = await fetch_board_html(code, client=client)
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
