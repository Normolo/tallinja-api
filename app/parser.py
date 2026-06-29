"""Parses the Tallinja "My Next Bus" board (HTML) into normalized departures.

Targets the real markup of ``service-information.publictransport.com.mt/timetable``
(captured in ``tests/fixtures/stop_1090.html``). Structure:

    <div class="station-text"><h1>Naxxar - 1090</h1></div>      # "<name> - <code>"

    <div class="line-item">
      <div class="line_icon" id="l31"><p class="line-number">31</p></div>
      <div class="line-name-container"><h2>Valletta - Bugibba</h2></div>
      <div class="line-time-container-active">                  # "-active" => live GPS
        <lord-icon .../>
        <h4>6 min</h4>                                         # next departure
        <h5>+30 min</h5>                                       # the one after
      </div>
    </div>

Non-tracked rows use ``<div class="line-time-container">`` with a single
``<h4>`` whose text is a lower bound like ``+30 min`` (meaning "more than 30
minutes away" — not an exact value, so ``minutes_away`` stays null there).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, FeatureNotFound

from .errors import ParseError
from .models import Departure, Stop


def _make_soup(html: str) -> BeautifulSoup:
    """Parse with lxml when installed, else fall back to the stdlib parser.

    lxml is faster but needs a C build; ``html.parser`` ships with Python, so the
    service runs on a bare interpreter without compiling anything.
    """
    try:
        return BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        return BeautifulSoup(html, "html.parser")

# Exact minutes only when there is no leading "+": "6 min" -> 6, "+30 min" -> bound.
_MINUTES_RE = re.compile(r"^\s*(\+)?\s*(\d+)\s*min", re.IGNORECASE)
_DUE_RE = re.compile(r"\b(due|now|arriving)\b", re.IGNORECASE)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_stop(soup: BeautifulSoup, stop_code: str) -> Stop:
    """Stop name from ``.station-text h1`` (``"<name> - <code>"``).

    The code shown on the page is canonical (the origin drops leading zeros, so a
    request for ``0366`` renders ``"Zejtun - 366"``). We therefore strip a
    trailing ``" - <number>"`` generically rather than matching the requested
    code, and keep ``stop.code`` as the value the caller asked for.
    """
    name: str | None = None
    el = soup.select_one(".station-text h1")
    if el is not None:
        text = _clean(el.get_text())
        m = re.search(r"^(?P<name>.*?)\s*[-–]\s*\d+\s*$", text)
        name = (m.group("name").strip() if m else text) or None
    return Stop(code=stop_code, name=name)


def _parse_minutes(display_time: str | None) -> int | None:
    if not display_time:
        return None
    if _DUE_RE.search(display_time):
        return 0
    m = _MINUTES_RE.match(display_time)
    if m and not m.group(1):  # exact value, no leading "+"
        return int(m.group(2))
    # Bounds like "+30 min" (lower) or "< 2 min" (upper) are not exact values, so
    # minutes_away stays null; the precise text is preserved in display_time.
    return None


def _parse_line_item(item) -> Departure | None:
    route_el = item.select_one(".line-number")
    if route_el is None:
        return None
    route = _clean(route_el.get_text())
    if not route:
        return None

    name_el = item.select_one(".line-name-container h2")
    line_name = _clean(name_el.get_text()) if name_el else None

    active = item.select_one(".line-time-container-active")
    container = active or item.select_one(".line-time-container")
    realtime = active is not None

    display_time: str | None = None
    following_time: str | None = None
    if container is not None:
        h4 = container.find("h4")
        h5 = container.find("h5")
        display_time = _clean(h4.get_text()) if h4 else None
        following_time = _clean(h5.get_text()) if h5 else None

    return Departure(
        route=route,
        line_name=line_name,
        minutes_away=_parse_minutes(display_time),
        display_time=display_time,
        realtime=realtime,
        following_time=following_time,
    )


def parse_board(html: str, stop_code: str) -> tuple[Stop, list[Departure]]:
    """Parse board HTML into a ``Stop`` and its departures.

    An empty board (stop exists but no lines listed) yields an empty list — that
    is not an error. ``ParseError`` is raised only if the HTML can't be parsed.
    """
    try:
        soup = _make_soup(html)
    except Exception as exc:  # pragma: no cover - bs4 rarely fails outright
        raise ParseError(f"Could not parse board HTML: {exc}") from exc

    stop = _extract_stop(soup, stop_code)

    departures: list[Departure] = []
    for item in soup.select(".line-item"):
        departure = _parse_line_item(item)
        if departure is not None:
            departures.append(departure)

    return stop, departures
