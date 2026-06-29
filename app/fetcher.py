"""Fetches the raw HTML of a stop's timetable board from the origin site.

Two backends are supported (see ``Settings.http_backend``):

* **curl** — shells out to the system ``curl``. Preferred for real traffic
  because the origin fingerprints TLS clients (JA3) and tarpits Python's httpx
  (the TLS handshake completes, but the response is never sent) while letting
  curl through.
* **httpx** — the async HTTP client. Used by the test suite (mockable via
  respx) and as a fallback when no ``curl`` binary is present.
"""

from __future__ import annotations

import asyncio
import shutil

import httpx

from .config import settings
from .errors import StopNotFound, UpstreamUnavailable


def _resolve_backend(client: httpx.AsyncClient | None) -> str:
    """Pick the backend. An explicitly supplied client always means httpx."""
    if client is not None:
        return "httpx"
    backend = settings.http_backend
    if backend == "auto":
        return "curl" if shutil.which("curl") else "httpx"
    return backend


async def fetch_board_html(stop_code: str, client: httpx.AsyncClient | None = None) -> str:
    """Return the raw HTML for ``?bus_stop=<stop_code>``.

    Raises:
        StopNotFound: origin returned 404 for this stop code.
        UpstreamUnavailable: network error, timeout, or any other non-2xx status.
    """
    if _resolve_backend(client) == "curl":
        return await _fetch_with_curl(stop_code)
    return await _fetch_with_httpx(stop_code, client)


# --- httpx backend -----------------------------------------------------------


async def _fetch_with_httpx(stop_code: str, client: httpx.AsyncClient | None) -> str:
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

    return _check_status(resp.status_code, resp.text, stop_code)


# --- curl backend ------------------------------------------------------------


async def _fetch_with_curl(stop_code: str) -> str:
    """Fetch via the system curl, appending the HTTP status to stdout."""
    headers = settings.request_headers
    args = ["curl", "-sS", "--compressed", "-m", str(settings.request_timeout)]
    for key, value in headers.items():
        if key == "User-Agent":
            args += ["-A", value]
        else:
            args += ["-H", f"{key}: {value}"]
    # -G + --data-urlencode builds the query string safely; -w appends the status
    # code on its own final line so we can split it off the body.
    args += [
        "-G",
        "--data-urlencode",
        f"bus_stop={stop_code}",
        "-w",
        "\n%{http_code}",
        settings.base_url,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
    except OSError as exc:  # curl missing or not executable
        raise UpstreamUnavailable(f"Could not run curl: {exc}") from exc

    return _parse_curl_result(proc.returncode, stdout, stderr, stop_code)


def _parse_curl_result(returncode: int, stdout: bytes, stderr: bytes, stop_code: str) -> str:
    if returncode != 0:
        detail = stderr.decode("utf-8", "replace").strip() or f"exit code {returncode}"
        raise UpstreamUnavailable(f"Failed to reach timetable origin: curl: {detail}")

    text = stdout.decode("utf-8", "replace")
    body, _, code = text.rpartition("\n")
    try:
        status = int(code.strip())
    except ValueError as exc:
        raise UpstreamUnavailable("Could not read HTTP status from curl output") from exc

    return _check_status(status, body, stop_code)


# --- shared status handling --------------------------------------------------


def _check_status(status: int, body: str, stop_code: str) -> str:
    if status == 404:
        raise StopNotFound(f"No stop with code {stop_code}")
    if status >= 400:
        raise UpstreamUnavailable(f"Origin returned HTTP {status}")
    return body
