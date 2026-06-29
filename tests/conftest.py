from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def board_html() -> str:
    return (FIXTURES / "stop_1090.html").read_text()


@pytest.fixture
def empty_html() -> str:
    return (FIXTURES / "stop_empty.html").read_text()


@pytest.fixture(autouse=True)
def _clear_cache():
    from app.service import clear_cache

    clear_cache()
    yield
    clear_cache()
