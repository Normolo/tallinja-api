from __future__ import annotations

from bs4 import BeautifulSoup

from app.parser import parse_board


def test_stdlib_parser_handles_board_markup(board_html):
    # The fallback backend (no lxml) must read the same structure.
    soup = BeautifulSoup(board_html, "html.parser")
    assert len(soup.select(".line-item")) == 11
    assert soup.select_one(".station-text h1").get_text(strip=True) == "Naxxar - 1090"


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


def test_canonical_code_suffix_stripped_when_request_had_leading_zero(board_0366_html):
    # Requested "0366" but the page renders the canonical "Zejtun - 366".
    stop, departures = parse_board(board_0366_html, "0366")
    assert stop.code == "0366"  # echoes what the caller asked for
    assert stop.name == "Zejtun"  # trailing " - 366" stripped despite the mismatch
    assert [d.route for d in departures] == ["81"]


def test_exact_following_time_kept_as_text(board_0366_html):
    _, departures = parse_board(board_0366_html, "0366")
    dep = departures[0]
    assert dep.realtime is True
    assert dep.minutes_away == 9
    assert dep.display_time == "9 min"
    assert dep.following_time == "27 min"  # exact, not a "+30 min" bound


def test_imminent_upper_bound_time(imminent_html):
    # An active row showing "< 2 min": live, but not an exact value.
    _, departures = parse_board(imminent_html, "1090")
    dep = departures[0]
    assert dep.route == "202"
    assert dep.realtime is True
    assert dep.display_time == "< 2 min"
    assert dep.minutes_away is None  # "< 2 min" is an upper bound, not exact


def test_empty_board_is_not_an_error(empty_html):
    stop, departures = parse_board(empty_html, "9999")
    assert stop.name == "Test Stop"
    assert departures == []
