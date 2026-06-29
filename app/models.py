"""Pydantic models describing the normalized API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Departure(BaseModel):
    """A single upcoming departure from a stop, as shown on the timetable board."""

    route: str = Field(..., description="Route number / short name, e.g. '13'")
    destination: str | None = Field(None, description="Headsign / where the bus is going")
    scheduled: str | None = Field(None, description="Scheduled time as shown, 'HH:MM'")
    estimated: str | None = Field(None, description="Real-time estimated time, 'HH:MM' if present")
    minutes_away: int | None = Field(None, description="Minutes until departure, if the board shows it")
    realtime: bool = Field(False, description="True when a live/estimated time was provided")


class Stop(BaseModel):
    code: str = Field(..., description="Public stop code (the 'bus_stop' query value)")
    name: str | None = Field(None, description="Human-readable stop name, if present on the page")


class DeparturesResponse(BaseModel):
    stop: Stop
    retrieved_at: datetime = Field(..., description="UTC timestamp of when the board was fetched")
    cached: bool = Field(False, description="True if served from the in-process cache")
    departures: list[Departure]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
