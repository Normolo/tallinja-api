"""Pydantic models describing the normalized API responses.

Field shapes mirror what the "My Next Bus" board actually displays: relative
times ("6 min", "+30 min") rather than clock times, and a full line name per
route. See ``app/parser.py`` for how these map onto the page markup.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Departure(BaseModel):
    """A single upcoming departure from a stop, as shown on the board."""

    route: str = Field(..., description="Route number / short name, e.g. '31', 'N40', 'TD12'")
    line_name: str | None = Field(
        None, description="Full line name as shown, e.g. 'Valletta - Bugibba'"
    )
    minutes_away: int | None = Field(
        None,
        description=(
            "Exact minutes until departure when the board shows a precise value "
            "(e.g. 6), or 0 for 'Due'. Null when the board shows only a bound such "
            "as '+30 min' (lower) or '< 2 min' (upper)."
        ),
    )
    display_time: str | None = Field(
        None, description="Time text exactly as displayed, e.g. '6 min' or '+30 min'"
    )
    realtime: bool = Field(
        False, description="True when this departure is live GPS-tracked (active row)"
    )
    following_time: str | None = Field(
        None, description="Time of the departure after next, when shown (e.g. '+30 min')"
    )


class Stop(BaseModel):
    code: str = Field(..., description="Public stop code (the 'bus_stop' query value)")
    name: str | None = Field(None, description="Human-readable stop name, e.g. 'Naxxar'")


class DeparturesResponse(BaseModel):
    stop: Stop
    retrieved_at: datetime = Field(..., description="UTC timestamp of when the board was fetched")
    cached: bool = Field(False, description="True if served from the in-process cache")
    departures: list[Departure]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
