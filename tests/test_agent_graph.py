
from app.agent.graph import route_after_fetch


def test_route_stops_when_error_exists():
    state = {
        "quotes": [],
        "error": "Market data collection failed.",
    }

    assert route_after_fetch(state) == "stop"


def test_route_stops_when_fewer_than_two_quotes():
    state = {
        "quotes": [],
    }

    assert route_after_fetch(state) == "stop"

    state = {
        "quotes": ["one quote"],
    }

    assert route_after_fetch(state) == "stop"


def test_route_continues_with_two_quotes():
    state = {
        "quotes": ["quote one", "quote two"],
    }

    assert route_after_fetch(state) == "analyze"
