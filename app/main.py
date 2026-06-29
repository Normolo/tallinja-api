"""FastAPI application exposing the Tallinja bus-stop departure board as JSON."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import __version__
from .errors import CircuitOpen, TallinjaError
from .models import DeparturesResponse, ErrorResponse
from .service import get_departures

app = FastAPI(
    title="Tallinja API",
    version=__version__,
    description=(
        "Unofficial JSON API for Malta Public Transport (Tallinja) bus-stop "
        "departure boards. Mirrors the public `?bus_stop=<code>` timetable page."
    ),
)


@app.exception_handler(TallinjaError)
async def _handle_tallinja_error(_: Request, exc: TallinjaError) -> JSONResponse:
    headers: dict[str, str] = {}
    if isinstance(exc, CircuitOpen):
        headers["Retry-After"] = str(int(exc.retry_after_seconds) + 1)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=exc.error, detail=str(exc)).model_dump(),
        headers=headers,
    )


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get(
    "/api/v1/stops/{stop_code}/departures",
    response_model=DeparturesResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    tags=["departures"],
    summary="Live departures for a bus stop",
)
async def stop_departures(stop_code: str) -> DeparturesResponse:
    """Return upcoming departures for the given public stop code (e.g. ``1090``)."""
    return await get_departures(stop_code)
