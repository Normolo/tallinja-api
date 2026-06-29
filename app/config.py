"""Application configuration, overridable via environment variables (prefix ``TALLINJA_``)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TALLINJA_", env_file=".env", extra="ignore")

    # Origin timetable board. The public ``bus_stop`` query parameter is the stop *code*
    # (the number printed on the bus-stop pole / QR sign), e.g. 1090.
    base_url: str = "https://service-information.publictransport.com.mt/timetable"

    # Outgoing HTTP behaviour. A browser-like UA is used because the board is a public
    # page meant for phones; httpx honours HTTPS_PROXY from the environment by default.
    request_timeout: float = 10.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )

    # Real-time data churns quickly, but we should not hammer the origin once per request.
    cache_ttl_seconds: float = 25.0

    # Accepted stop codes are short numeric strings. Reject anything else early.
    stop_code_pattern: str = r"^\d{3,6}$"


settings = Settings()
