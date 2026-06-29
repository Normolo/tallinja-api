"""Application configuration, overridable via environment variables (prefix ``TALLINJA_``)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TALLINJA_", env_file=".env", extra="ignore")

    # Origin timetable board. The public ``bus_stop`` query parameter is the stop *code*
    # (the number printed on the bus-stop pole / QR sign), e.g. 1090.
    base_url: str = "https://service-information.publictransport.com.mt/timetable"

    # Outgoing HTTP behaviour. The origin tarpits requests that don't look like a
    # real browser (a bare User-Agent connects but the response is withheld until
    # the read times out), so we send a full browser-like header set, not just a UA.
    # Shortened from 15s: a long timeout means a stalled request holds a
    # connection open, which the origin's bot protection reads as slowloris.
    request_timeout: float = 8.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )

    @property
    def request_headers(self) -> dict[str, str]:
        # Accept-Encoding is limited to gzip/deflate (decoded natively by httpx) to
        # avoid needing the optional brotli/zstd packages.
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    # Real-time data churns quickly, but we should not hammer the origin once per request.
    cache_ttl_seconds: float = 25.0

    # Resilience — be gentle with a bot-protected origin or it IP-blocks us.
    # Minimum spacing between consecutive origin fetches (across all stops).
    min_request_interval_seconds: float = 1.0
    # Consecutive upstream failures that trip the circuit breaker open.
    circuit_failure_threshold: int = 4
    # How long the breaker stays open (fast-failing) before allowing a trial.
    circuit_cooldown_seconds: float = 60.0
    # Remember a failed stop (e.g. an unknown code the origin hangs on) for this
    # long, so repeat requests fast-fail instead of re-incurring the full timeout
    # and stressing the breaker. Kept short so a transient blip self-heals.
    negative_cache_ttl_seconds: float = 30.0

    # HTTP backend used to fetch the board:
    #   "auto"  - use the curl binary when available, else httpx
    #   "curl"  - always shell out to curl
    #   "httpx" - always use httpx (used by the test suite)
    # The origin fingerprints TLS clients (JA3) and tarpits Python's httpx while
    # allowing curl, so curl is preferred for real traffic.
    http_backend: str = "auto"

    # Accepted stop codes are short numeric strings. Reject anything else early.
    stop_code_pattern: str = r"^\d{3,6}$"


settings = Settings()
