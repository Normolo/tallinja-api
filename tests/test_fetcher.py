from __future__ import annotations

import pytest

from app.errors import StopNotFound, UpstreamUnavailable
from app.fetcher import _parse_curl_result, _resolve_backend


def test_resolve_backend_explicit_client_is_httpx():
    # A supplied client (as in tests) always selects httpx, regardless of config.
    assert _resolve_backend(object()) == "httpx"


def test_resolve_backend_honours_explicit_setting():
    from app.config import settings

    previous = settings.http_backend
    try:
        settings.http_backend = "curl"
        assert _resolve_backend(None) == "curl"
        settings.http_backend = "httpx"
        assert _resolve_backend(None) == "httpx"
    finally:
        settings.http_backend = previous


def test_parse_curl_result_success():
    stdout = b"<html>board</html>\n200"
    assert _parse_curl_result(0, stdout, b"", "1090") == "<html>board</html>"


def test_parse_curl_result_404_raises_stop_not_found():
    with pytest.raises(StopNotFound):
        _parse_curl_result(0, b"not found\n404", b"", "1090")


def test_parse_curl_result_500_raises_upstream():
    with pytest.raises(UpstreamUnavailable):
        _parse_curl_result(0, b"oops\n503", b"", "1090")


def test_parse_curl_result_nonzero_exit_raises_upstream():
    with pytest.raises(UpstreamUnavailable, match="curl: could not resolve host"):
        _parse_curl_result(6, b"", b"curl: could not resolve host", "1090")
