
from decimal import Decimal
from types import SimpleNamespace

import app.agent.graph as graph_module

from app.agent.graph import (
    analyze_arbitrage,
    explain_arbitrage_results,
    route_after_analysis,
    route_after_fetch,
    save_scan_results,
)


# --------------------------------------------------
# 1. Tests for routing after market-data collection
# --------------------------------------------------

def test_route_stops_when_error_exists():
    state = {
        "quotes": [],
        "error": "Market data collection failed.",
    }

    assert route_after_fetch(state) == "stop"


def test_route_stops_when_fewer_than_two_quotes():
    assert route_after_fetch({"quotes": []}) == "stop"

    assert route_after_fetch({
        "quotes": ["one quote"],
    }) == "stop"


def test_route_continues_with_two_quotes():
    state = {
        "quotes": ["quote one", "quote two"],
    }

    assert route_after_fetch(state) == "analyze"


# --------------------------------------------------
# 2. Tests for arbitrage analysis
# --------------------------------------------------

def test_analysis_failure_returns_error(monkeypatch):
    def raise_error(*args, **kwargs):
        raise RuntimeError("Simulated analysis failure")

    monkeypatch.setattr(
        graph_module,
        "compare_exchanges",
        raise_error,
    )

    state = {
        "quotes": ["quote one", "quote two"],
    }

    result = analyze_arbitrage(state)

    assert result["results"] == []
    assert result["error"] == "Arbitrage analysis failed."


def test_route_after_analysis_stops_when_error_exists():
    state = {
        "results": [],
        "error": "Arbitrage analysis failed.",
    }

    assert route_after_analysis(state) == "stop"


def test_route_after_analysis_continues_without_error():
    state = {
        "results": [],
        "error": "",
    }

    assert route_after_analysis(state) == "explain"


# --------------------------------------------------
# 3. Tests for LLM explanation and fallback
# --------------------------------------------------

def test_llm_failure_uses_fallback_explanation(monkeypatch):
    fake_result = SimpleNamespace(
        buy_exchange="Binance",
        sell_exchange="OKX",
        net_profit=Decimal("-0.25"),
        eligible=False,
        reason="Net profit is below the minimum threshold.",
    )

    def raise_llm_error(**kwargs):
        raise RuntimeError("Simulated Groq failure")

    monkeypatch.setattr(
        graph_module,
        "explain_scan",
        raise_llm_error,
    )

    result = explain_arbitrage_results({
        "results": [fake_result],
    })

    assert len(result["explanations"]) == 1

    explanation = result["explanations"][0]

    assert "LLM explanation unavailable" in explanation
    assert "Python decision: rejected." in explanation
    assert fake_result.reason in explanation


# --------------------------------------------------
# 4. Tests for saving scan results
# --------------------------------------------------

def test_save_failure_does_not_stop_other_records(monkeypatch):
    first_result = SimpleNamespace(
        buy_exchange="Binance",
        sell_exchange="OKX",
    )

    second_result = SimpleNamespace(
        buy_exchange="OKX",
        sell_exchange="Binance",
    )

    attempts = []

    def mock_record_scan(result):
        attempts.append(result)

        if result is first_result:
            raise RuntimeError("Simulated database failure")

    monkeypatch.setattr(
        graph_module.ledger,
        "record_scan",
        mock_record_scan,
    )

    result = save_scan_results({
        "results": [first_result, second_result],
    })

    # Both records should be attempted.
    assert len(attempts) == 2

    # The first failed; the second succeeded.
    assert result["saved_records"] == 1

    # The failure should be reported.
    assert len(result["save_errors"]) == 1
    assert "Binance -> OKX" in result["save_errors"][0]
