"""Parses a Tallinja stop timetable board (HTML) into normalized departures.

------------------------------------------------------------------------------
VERIFICATION NOTE
------------------------------------------------------------------------------
This parser targets the *documented* structure of the public board at
``service-information.publictransport.com.mt/timetable?bus_stop=<code>`` — a
lightweight, server-rendered page (the one behind the QR codes on bus-stop
signage) listing, per route: route number, destination, and a scheduled and/or
estimated time.

That host is blocked by this build environment's egress policy, so the exact
markup (table vs. div, class names) could not be confirmed against the live
page. The extraction is therefore deliberately *layout-tolerant*: it works off
text patterns (route tokens, ``HH:MM`` times, ``N min``) rather than brittle
selectors, and the few structural assumptions are the constants below.

To finalize against the real page: fetch one stop's HTML, drop it into
``tests/fixtures/`` and tighten ``_iter_departure_rows`` / ``_extract_stop_name``.
The public surface (``parse_board``) and its return types should not change.
------------------------------------------------------------------------------
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from .errors import ParseError
from .models import Departure, Stop

# --- Text patterns (origin-agnostic) -----------------------------------------

_TIME_RE = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")
# Route short-names in Malta: "13", "X1", "TD2", "N13", "202", "511".
_ROUTE_RE = re.compile(r"^[A-Z]{0,3}\d{1,3}[A-Z]?$")
_MINUTES_RE = re.compile(r"\b(\d{1,3})\s*min", re.IGNORECASE)
_DUE_RE = re.compile(r"\b(due|now|arriving)\b", re.IGNORECASE)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_stop_name(soup: BeautifulSoup, stop_code: str) -> str | None:
    """Best-effort stop name from the page heading / title.

    Adjust here once the real markup is known (e.g. a specific ``<h1 class=...>``).
    """
    for selector in ("h1", "h2", ".stop-name", "#stop-name", "title"):
        el = soup.select_one(selector)
        if not el:
            continue
        text = _clean(el.get_text())
        if not text:
            continue
        # Strip a leading "1090 - " / "Stop 1090:" style prefix if present.
        text = re.sub(rf"^\W*(?:stop\s*)?{re.escape(stop_code)}\s*[-:–]\s*", "", text, flags=re.I)
        text = re.sub(r"\s*[-–|]\s*(tallinja|malta public transport).*$", "", text, flags=re.I)
        if text and text.lower() not in {"timetable", stop_code.lower()}:
            return text
    return None


def _iter_departure_rows(soup: BeautifulSoup) -> list[list[str]]:
    """Yield each departure as an ordered list of cell texts.

    Tries a table layout first, then falls back to repeated list/row containers.
    This is the main spot to tighten once the live markup is confirmed.
    """
    rows: list[list[str]] = []

    # 1) Table layout: each <tr> with <td>s is a candidate departure.
    for tr in soup.select("table tr"):
        cells = [_clean(td.get_text()) for td in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)

    if rows:
        return rows

    # 2) Generic repeated-container layout (div/li rows).
    for container in soup.select(
        ".departure, .departure-row, .timetable-row, li.route, .route-row"
    ):
        cells = _row_cells_from_container(container)
        if cells:
            rows.append(cells)

    return rows


def _row_cells_from_container(container: Tag) -> list[str]:
    """Pull pseudo-cells out of a non-table row by reading its child elements."""
    parts = [_clean(child.get_text()) for child in container.find_all(recursive=False)]
    parts = [p for p in parts if p]
    if parts:
        return parts
    text = _clean(container.get_text())
    return [text] if text else []


def _row_to_departure(cells: list[str]) -> Departure | None:
    """Interpret a row's cells into a Departure, or ``None`` if it isn't one."""
    joined = " ".join(cells)

    route = _find_route(cells)
    if route is None:
        return None

    times = _TIME_RE.findall(joined)
    scheduled = times[0] if times else None
    estimated = times[1] if len(times) > 1 else None

    minutes: int | None = None
    if (m := _MINUTES_RE.search(joined)) is not None:
        minutes = int(m.group(1))
    elif _DUE_RE.search(joined):
        minutes = 0

    realtime = estimated is not None or minutes is not None
    destination = _find_destination(cells, route, times)

    return Departure(
        route=route,
        destination=destination,
        scheduled=scheduled,
        estimated=estimated,
        minutes_away=minutes,
        realtime=realtime,
    )


def _find_route(cells: list[str]) -> str | None:
    for cell in cells:
        token = cell.strip()
        if _ROUTE_RE.match(token):
            return token
    return None


def _find_destination(cells: list[str], route: str, times: list[str]) -> str | None:
    """The destination is the longest non-route, non-time cell."""
    candidates: list[str] = []
    for cell in cells:
        c = cell.strip()
        if not c or c == route or _ROUTE_RE.match(c):
            continue
        if c in times or _TIME_RE.fullmatch(c) or _MINUTES_RE.fullmatch(c):
            continue
        candidates.append(c)
    if not candidates:
        return None
    return max(candidates, key=len)


def parse_board(html: str, stop_code: str) -> tuple[Stop, list[Departure]]:
    """Parse board HTML into a ``Stop`` and its departures.

    An empty board (stop exists but nothing scheduled) yields an empty list — it
    is *not* an error. A ``ParseError`` is raised only when the HTML can't be
    parsed at all.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as exc:  # pragma: no cover - lxml rarely fails outright
        raise ParseError(f"Could not parse board HTML: {exc}") from exc

    stop = Stop(code=stop_code, name=_extract_stop_name(soup, stop_code))

    departures: list[Departure] = []
    for cells in _iter_departure_rows(soup):
        departure = _row_to_departure(cells)
        if departure is not None:
            departures.append(departure)

    return stop, departures
