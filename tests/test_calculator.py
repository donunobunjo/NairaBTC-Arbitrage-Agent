
# from datetime import datetime, timezone
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

from app.market_data.models import MarketQuote
from app.arbitrage.calculator import (
    calculate_direction,
    compare_exchanges,
)


NOW = datetime.now(timezone.utc)


def make_quote(exchange, bid, ask):
    return MarketQuote(
        exchange=exchange,
        symbol="BTC/USDT",
        bid=Decimal(str(bid)),
        ask=Decimal(str(ask)),
        timestamp=NOW,
        source="unit test",
    )


def test_profitable_direction():
    buy = make_quote("Exchange A", "100", "100")
    sell = make_quote("Exchange B", "102", "102")

    result = calculate_direction(
        buy,
        sell,
        trade_size_btc=Decimal("1"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        now=NOW,
    )

    assert result.gross_profit == Decimal("2")
    assert result.net_profit == Decimal("2")
    assert result.eligible is True


def test_fees_can_remove_profit():
    buy = make_quote("Exchange A", "100", "100")
    sell = make_quote("Exchange B", "100.1", "100.1")

    result = calculate_direction(
        buy,
        sell,
        trade_size_btc=Decimal("1"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0"),
        now=NOW,
    )

    assert result.net_profit < 0
    assert result.eligible is False



def test_stale_quote_is_rejected():
    buy = make_quote("Exchange A", "100", "100")
    sell = make_quote("Exchange B", "102", "102")

    with pytest.raises(ValueError, match="stale"):
        calculate_direction(
            buy,
            sell,
            max_quote_age_seconds=30,
            now=NOW + timedelta(seconds=60),
        )



def test_both_directions_are_compared():
    a = make_quote("Exchange A", "100", "100")
    b = make_quote("Exchange B", "102", "102")

    results = compare_exchanges(
        a,
        b,
        trade_size_btc=Decimal("1"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        now=NOW,
    )

    assert len(results) == 2
    assert results[0].net_profit == Decimal("2")
    assert results[1].net_profit < 0
