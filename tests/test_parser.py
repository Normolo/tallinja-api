from __future__ import annotations

from app.parser import parse_board


def test_parses_stop_name(board_html):
    stop, _ = parse_board(board_html, "1090")
    assert stop.code == "1090"
    assert stop.name == "Valletta, Bus Terminus"


def test_parses_all_departures(board_html):
    _, departures = parse_board(board_html, "1090")
    routes = [d.route for d in departures]
    assert routes == ["13", "X1", "202", "TD2"]


def test_scheduled_and_estimated_times(board_html):
    _, departures = parse_board(board_html, "1090")
    first = departures[0]
    assert first.route == "13"
    assert first.destination == "Marsa"
    assert first.scheduled == "20:48"
    assert first.estimated == "20:51"
    assert first.realtime is True


def test_no_realtime_when_only_scheduled(board_html):
    _, departures = parse_board(board_html, "1090")
    x1 = next(d for d in departures if d.route == "X1")
    assert x1.scheduled == "20:55"
    assert x1.estimated is None
    assert x1.realtime is False


def test_due_maps_to_zero_minutes(board_html):
    _, departures = parse_board(board_html, "1090")
    r202 = next(d for d in departures if d.route == "202")
    assert r202.minutes_away == 0
    assert r202.realtime is True


def test_minutes_extracted(board_html):
    _, departures = parse_board(board_html, "1090")
    td2 = next(d for d in departures if d.route == "TD2")
    assert td2.minutes_away == 9
    assert td2.destination == "Sliema Ferries"


def test_empty_board_is_not_an_error(empty_html):
    stop, departures = parse_board(empty_html, "9999")
    assert stop.name == "Test Stop"
    assert departures == []
