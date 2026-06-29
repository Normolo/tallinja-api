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


class CircuitOpen(TallinjaError):
    """Raised when the breaker is open: we refuse to call the origin during the
    cooldown so we don't deepen an upstream block."""

    status_code = 503
    error = "upstream_circuit_open"

    def __init__(self, retry_after_seconds: float = 0.0):
        self.retry_after_seconds = max(0.0, retry_after_seconds)
        super().__init__(
            "Upstream temporarily unavailable (circuit open); retry in "
            f"{self.retry_after_seconds:.0f}s"
        )
