
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.agent.graph import explain_arbitrage_results


def make_result():
    return SimpleNamespace(
        buy_exchange="Binance",
        sell_exchange="OKX",
        net_profit=Decimal("-0.25"),
        eligible=False,
        reason="Estimated fees and slippage exceed the price spread.",
    )


def test_groq_failure_uses_fallback_explanation():
    state = {"results": [make_result()]}

    with patch(
        "app.agent.graph.explain_scan",
        side_effect=RuntimeError("Groq API unavailable"),
    ):
        updated_state = explain_arbitrage_results(state)

    assert len(updated_state["explanations"]) == 1

    explanation = updated_state["explanations"][0]

    assert "unavailable" in explanation.lower()
    assert "rejected" in explanation.lower()
    assert "fees and slippage" in explanation.lower()


def test_successful_groq_response_is_preserved():
    state = {"results": [make_result()]}
    expected = "The estimated trade would lose 0.25 USDT."

    with patch(
        "app.agent.graph.explain_scan",
        return_value=expected,
    ):
        updated_state = explain_arbitrage_results(state)

    assert updated_state["explanations"] == [expected]


def test_empty_results_produce_empty_explanations():
    updated_state = explain_arbitrage_results({"results": []})

    assert updated_state["explanations"] == []
