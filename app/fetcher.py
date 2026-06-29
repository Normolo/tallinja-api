"""Fetches the raw HTML of a stop's timetable board from the origin site."""

from __future__ import annotations

import httpx

from .config import settings
from .errors import StopNotFound, UpstreamUnavailable


async def fetch_board_html(stop_code: str, client: httpx.AsyncClient | None = None) -> str:
    """Return the raw HTML for ``?bus_stop=<stop_code>``.

    Raises:
        StopNotFound: origin returned 404 for this stop code.
        UpstreamUnavailable: network error, timeout, or any other non-2xx status.
    """
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=settings.request_timeout,
        headers=settings.request_headers,
        follow_redirects=True,
    )
    try:
        resp = await client.get(settings.base_url, params={"bus_stop": stop_code})
    except httpx.HTTPError as exc:  # timeouts, DNS, connection, proxy refusals
        # Some httpx errors (notably timeouts) stringify to "", so name the type.
        reason = f"{type(exc).__name__}: {exc}".rstrip(": ")
        raise UpstreamUnavailable(f"Failed to reach timetable origin: {reason}") from exc
    finally:
        if owns_client:
            await client.aclose()

    if resp.status_code == 404:
        raise StopNotFound(f"No stop with code {stop_code}")
    if resp.status_code >= 400:
        raise UpstreamUnavailable(f"Origin returned HTTP {resp.status_code}")
    return resp.text
