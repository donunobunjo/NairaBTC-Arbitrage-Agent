
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.market_data.models import MarketQuote
from app.arbitrage.calculator import calculate_direction
from app.paper_trading import ledger


@pytest.fixture
def temporary_database(tmp_path, monkeypatch):
    """Give each test its own temporary SQLite database."""
    monkeypatch.setattr(
        ledger,
        "DATABASE_PATH",
        tmp_path / "test_paper_trading.db",
    )
    ledger.initialize_database()


def make_profitable_result():
    """Create a deterministic profitable example for testing."""
    now = datetime.now(timezone.utc)

    buy = MarketQuote(
        exchange="Exchange A",
        symbol="BTC/USDT",
        bid=Decimal("99"),
        ask=Decimal("100"),
        timestamp=now,
        source="unit test",
    )

    sell = MarketQuote(
        exchange="Exchange B",
        symbol="BTC/USDT",
        bid=Decimal("102"),
        ask=Decimal("103"),
        timestamp=now,
        source="unit test",
    )

    return calculate_direction(
        buy,
        sell,
        trade_size_btc=Decimal("0.1"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        min_net_profit=Decimal("0"),
        now=now,
    )


def test_rejected_scan_cannot_be_executed(temporary_database):
    result = make_profitable_result()
    result.eligible = False
    result.reason = "Test rejection."

    ledger.record_scan(result)

    with pytest.raises(ValueError, match="not eligible"):
        ledger.execute_paper_trade(1)


def test_missing_scan_cannot_be_executed(temporary_database):
    with pytest.raises(ValueError, match="not found"):
        ledger.execute_paper_trade(999999)


def test_profitable_scan_updates_virtual_balance(temporary_database):
    result = make_profitable_result()
    assert result.eligible is True

    ledger.record_scan(result)
    outcome = ledger.execute_paper_trade(1)

    assert outcome["status"] == "paper_executed"
    assert Decimal(outcome["net_profit"]) == Decimal("0.2")
    assert Decimal(outcome["new_balance"]) == Decimal("1000.2")

    portfolio = ledger.get_portfolio()
    assert Decimal(str(portfolio["current_balance"])) == Decimal("1000.2")


def test_same_scan_cannot_be_executed_twice(temporary_database):
    ledger.record_scan(make_profitable_result())
    ledger.execute_paper_trade(1)

    with pytest.raises(ValueError, match="already been executed"):
        ledger.execute_paper_trade(1)
