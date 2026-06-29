"""Domain errors mapped to HTTP responses in the API layer."""

from __future__ import annotations


class TallinjaError(Exception):
    """Base class for expected, user-facing failures."""

    status_code = 502
    error = "upstream_error"


class InvalidStopCode(TallinjaError):
    status_code = 400
    error = "invalid_stop_code"


class StopNotFound(TallinjaError):
    status_code = 404
    error = "stop_not_found"


class UpstreamUnavailable(TallinjaError):
    status_code = 502
    error = "upstream_unavailable"


class ParseError(TallinjaError):
    status_code = 502
    error = "parse_error"
