
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.market_data.models import MarketQuote


BINANCE_URL = "https://api.binance.com/api/v3/ticker/bookTicker"
OKX_URL = "https://www.okx.com/api/v5/market/ticker"

TIMEOUT_SECONDS = 10


async def get_binance_quote() -> MarketQuote:
    """Fetch the best BTC/USDT bid and ask from Binance."""

    async with httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS
    ) as client:
        response = await client.get(
            BINANCE_URL,
            params={"symbol": "BTCUSDT"},
        )
        response.raise_for_status()
        data = response.json()

    return MarketQuote(
        exchange="Binance",
        symbol="BTC/USDT",
        bid=Decimal(data["bidPrice"]),
        ask=Decimal(data["askPrice"]),
        timestamp=datetime.now(timezone.utc),
        source="Binance public bookTicker API",
    )


async def get_okx_quote() -> MarketQuote:
    """Fetch the best BTC/USDT bid and ask from OKX."""

    async with httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS
    ) as client:
        response = await client.get(
            OKX_URL,
            params={"instId": "BTC-USDT"},
        )
        response.raise_for_status()
        payload = response.json()

    if payload.get("code") != "0":
        raise ValueError(
            f"OKX returned an error: {payload.get('msg')}"
        )

    data = payload.get("data", [])

    if not data:
        raise ValueError("OKX returned no market data.")

    ticker = data[0]

    return MarketQuote(
        exchange="OKX",
        symbol="BTC/USDT",
        bid=Decimal(ticker["bidPx"]),
        ask=Decimal(ticker["askPx"]),
        timestamp=datetime.fromtimestamp(
            int(ticker["ts"]) / 1000,
            tz=timezone.utc,
        ),
        source="OKX public ticker API",
    )


async def fetch_all_quotes() -> list[MarketQuote]:
    """Fetch quotes independently so one failure doesn't
    prevent the other exchange from responding."""

    results = await asyncio.gather(
        get_binance_quote(),
        get_okx_quote(),
        return_exceptions=True,
    )

    quotes = []

    for exchange_name, result in zip(
        ["Binance", "OKX"], results
    ):
        if isinstance(result, Exception):
            print(
                f"WARNING: {exchange_name} quote failed: "
                f"{result}"
            )
        else:
            quotes.append(result)

    return quotes
