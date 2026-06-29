from __future__ import annotations

from app.parser import parse_board


def test_parses_stop_name_without_code_suffix(board_html):
    stop, _ = parse_board(board_html, "1090")
    assert stop.code == "1090"
    assert stop.name == "Naxxar"


def test_parses_all_departures(board_html):
    _, departures = parse_board(board_html, "1090")
    routes = [d.route for d in departures]
    assert routes == ["31", "103", "202", "203", "238", "260", "46", "49", "N40", "S30", "TD12"]


def test_active_row_is_realtime_with_exact_minutes(board_html):
    _, departures = parse_board(board_html, "1090")
    first = departures[0]
    assert first.route == "31"
    assert first.line_name == "Valletta - Bugibba"
    assert first.realtime is True
    assert first.display_time == "6 min"
    assert first.minutes_away == 6
    assert first.following_time == "+30 min"


def test_lower_bound_time_has_null_minutes(board_html):
    _, departures = parse_board(board_html, "1090")
    line_103 = next(d for d in departures if d.route == "103")
    assert line_103.realtime is False
    assert line_103.display_time == "+30 min"
    assert line_103.minutes_away is None  # "+30 min" is a bound, not exact
    assert line_103.following_time is None


def test_alphanumeric_routes_parsed(board_html):
    _, departures = parse_board(board_html, "1090")
    by_route = {d.route: d for d in departures}
    assert by_route["N40"].line_name == "San Giljan - Mosta - San Giljan"
    assert by_route["S30"].line_name == "Valletta - Gharghur - Mosta - Bugibba"
    assert by_route["TD12"].line_name == "Sliema - Mosta"


def test_empty_board_is_not_an_error(empty_html):
    stop, departures = parse_board(empty_html, "9999")
    assert stop.name == "Test Stop"
    assert departures == []
