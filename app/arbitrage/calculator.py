
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.market_data.models import MarketQuote


@dataclass
class ArbitrageResult:
    buy_exchange: str
    sell_exchange: str
    trade_size_btc: Decimal
    buy_price: Decimal
    sell_price: Decimal
    gross_profit: Decimal
    buy_fee: Decimal
    sell_fee: Decimal
    estimated_slippage: Decimal
    net_profit: Decimal
    net_return_pct: Decimal
    eligible: bool
    reason: str


def calculate_direction(
    buy_quote: MarketQuote,
    sell_quote: MarketQuote,
    trade_size_btc: Decimal = Decimal("0.001"),
    fee_rate: Decimal = Decimal("0.001"),
    slippage_rate: Decimal = Decimal("0.0005"),
    max_quote_age_seconds: int = 30,
    min_net_profit: Decimal = Decimal("0"),
    now: datetime | None = None,
) -> ArbitrageResult:
    """Estimate profitability of buying on one exchange
    and selling on another. This does not execute trades."""

    if trade_size_btc <= 0:
        raise ValueError("Trade size must be positive.")

    if fee_rate < 0 or slippage_rate < 0:
        raise ValueError("Fee and slippage rates cannot be negative.")

    if fee_rate >= 1 or slippage_rate >= 1:
        raise ValueError("Fee and slippage rates must be below 100%.")

    if buy_quote.symbol != sell_quote.symbol:
        raise ValueError("Quotes must use the same trading symbol.")

    if buy_quote.exchange == sell_quote.exchange:
        raise ValueError("Buy and sell exchanges must be different.")

    now = now or datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError("The current time must include a timezone.")

    for quote in (buy_quote, sell_quote):
        if quote.timestamp.tzinfo is None:
            raise ValueError("Quote timestamps must include a timezone.")

        age = (now - quote.timestamp).total_seconds()

        if age < -2:
            raise ValueError(
                f"{quote.exchange} quote timestamp is in the future."
            )

        if age > max_quote_age_seconds:
            raise ValueError(
                f"{quote.exchange} quote is stale: "
                f"{age:.1f} seconds old."
            )

        if quote.ask < quote.bid:
            raise ValueError(
                f"{quote.exchange} has an invalid bid/ask."
            )

    # Use executable sides of the order book:
    # buy at ask, sell at bid.
    effective_buy_price = buy_quote.ask * (
        Decimal("1") + slippage_rate
    )
    effective_sell_price = sell_quote.bid * (
        Decimal("1") - slippage_rate
    )

    buy_cost = effective_buy_price * trade_size_btc
    sell_proceeds = effective_sell_price * trade_size_btc

    buy_fee = buy_cost * fee_rate
    sell_fee = sell_proceeds * fee_rate

    gross_profit = (
        sell_proceeds
        - effective_buy_price * trade_size_btc
    )

    estimated_slippage = (
        (effective_buy_price - buy_quote.ask)
        + (sell_quote.bid - effective_sell_price)
    ) * trade_size_btc

    net_profit = (
        sell_proceeds
        - sell_fee
        - buy_cost
        - buy_fee
    )

    total_cost = buy_cost + buy_fee

    net_return_pct = (
        net_profit / total_cost * Decimal("100")
        if total_cost > 0
        else Decimal("0")
    )

    eligible = net_profit > min_net_profit

    return ArbitrageResult(
        buy_exchange=buy_quote.exchange,
        sell_exchange=sell_quote.exchange,
        trade_size_btc=trade_size_btc,
        buy_price=buy_quote.ask,
        sell_price=sell_quote.bid,
        gross_profit=gross_profit,
        buy_fee=buy_fee,
        sell_fee=sell_fee,
        estimated_slippage=estimated_slippage,
        net_profit=net_profit,
        net_return_pct=net_return_pct,
        eligible=eligible,
        reason=(
            "Estimated net profit exceeds the threshold."
            if eligible
            else "Estimated net profit does not exceed the threshold."
        ),
    )


def compare_exchanges(
    quote_a: MarketQuote,
    quote_b: MarketQuote,
    **kwargs,
) -> list[ArbitrageResult]:
    """Evaluate both possible buy/sell directions."""

    results = []

    for buy_quote, sell_quote in (
        (quote_a, quote_b),
        (quote_b, quote_a),
    ):
        try:
            result = calculate_direction(
                buy_quote,
                sell_quote,
                **kwargs,
            )
            results.append(result)
        except ValueError as exc:
            # Record why a direction could not be evaluated.
            results.append(
                ArbitrageResult(
                    buy_exchange=buy_quote.exchange,
                    sell_exchange=sell_quote.exchange,
                    trade_size_btc=kwargs.get(
                        "trade_size_btc", Decimal("0.001")
                    ),
                    buy_price=buy_quote.ask,
                    sell_price=sell_quote.bid,
                    gross_profit=Decimal("0"),
                    buy_fee=Decimal("0"),
                    sell_fee=Decimal("0"),
                    estimated_slippage=Decimal("0"),
                    net_profit=Decimal("0"),
                    net_return_pct=Decimal("0"),
                    eligible=False,
                    reason=str(exc),
                )
            )

    return results
