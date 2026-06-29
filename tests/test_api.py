from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_invalid_stop_code_returns_400():
    resp = client.get("/api/v1/stops/abc/departures")
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_stop_code"


@respx.mock
def test_departures_happy_path(board_html):
    respx.get(settings.base_url).mock(return_value=httpx.Response(200, text=board_html))
    resp = client.get("/api/v1/stops/1090/departures")
    assert resp.status_code == 200
    body = resp.json()
    assert body["stop"]["code"] == "1090"
    assert body["stop"]["name"] == "Naxxar"
    assert body["cached"] is False
    assert len(body["departures"]) == 11
    assert body["departures"][0]["route"] == "31"
    assert body["departures"][0]["minutes_away"] == 6


@respx.mock
def test_second_request_is_cached(board_html):
    route = respx.get(settings.base_url).mock(
        return_value=httpx.Response(200, text=board_html)
    )
    client.get("/api/v1/stops/1090/departures")
    resp = client.get("/api/v1/stops/1090/departures")
    assert resp.json()["cached"] is True
    assert route.call_count == 1  # origin hit only once within TTL


@respx.mock
def test_stop_not_found_returns_404():
    respx.get(settings.base_url).mock(return_value=httpx.Response(404))
    resp = client.get("/api/v1/stops/1090/departures")
    assert resp.status_code == 404
    assert resp.json()["error"] == "stop_not_found"


@respx.mock
def test_upstream_error_returns_502():
    respx.get(settings.base_url).mock(return_value=httpx.Response(403))
    resp = client.get("/api/v1/stops/1090/departures")
    assert resp.status_code == 502
    assert resp.json()["error"] == "upstream_unavailable"


@respx.mock
def test_failed_stop_is_negative_cached():
    # Simulate the origin hanging on an unknown code (a transport error).
    route = respx.get(settings.base_url).mock(side_effect=httpx.ConnectError("hang"))
    first = client.get("/api/v1/stops/9990/departures")
    second = client.get("/api/v1/stops/9990/departures")
    assert first.status_code == 502
    assert second.status_code == 502
    assert "negative-cached" in second.json()["detail"]
    assert route.call_count == 1  # second request never reached the origin


@respx.mock
def test_circuit_opens_after_repeated_failures():
    # Every distinct stop misses the cache and hits the (failing) origin.
    route = respx.get(settings.base_url).mock(return_value=httpx.Response(503))
    threshold = settings.circuit_failure_threshold
    for i in range(threshold):
        assert client.get(f"/api/v1/stops/100{i}/departures").status_code == 502

    # Breaker is now open: the next call fast-fails as 503 without hitting origin.
    resp = client.get("/api/v1/stops/2000/departures")
    assert resp.status_code == 503
    assert resp.json()["error"] == "upstream_circuit_open"
    assert "Retry-After" in resp.headers
    assert route.call_count == threshold  # the open-circuit call did NOT reach origin
