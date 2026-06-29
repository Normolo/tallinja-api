from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def board_html() -> str:
    return (FIXTURES / "stop_1090.html").read_text()


@pytest.fixture
def board_0366_html() -> str:
    return (FIXTURES / "stop_0366.html").read_text()


@pytest.fixture
def imminent_html() -> str:
    return (FIXTURES / "stop_imminent.html").read_text()


@pytest.fixture
def empty_html() -> str:
    return (FIXTURES / "stop_empty.html").read_text()


@pytest.fixture(autouse=True)
def _test_environment():
    # Force the httpx backend so respx can intercept; reset cache + breaker +
    # rate limiter (all module-global) around each test, and disable inter-request
    # spacing so the suite stays fast and deterministic.
    from app.config import settings
    from app.service import reset_for_tests

    previous_backend = settings.http_backend
    settings.http_backend = "httpx"
    reset_for_tests(min_request_interval_seconds=0.0)
    yield
    settings.http_backend = previous_backend
    reset_for_tests(min_request_interval_seconds=0.0)
