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
def empty_html() -> str:
    return (FIXTURES / "stop_empty.html").read_text()


@pytest.fixture(autouse=True)
def _test_environment():
    # Force the httpx backend so respx can intercept; clear the cache around each
    # test so cached responses don't leak between cases.
    from app.config import settings
    from app.service import clear_cache

    previous_backend = settings.http_backend
    settings.http_backend = "httpx"
    clear_cache()
    yield
    settings.http_backend = previous_backend
    clear_cache()
