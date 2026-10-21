from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MarketQuote(BaseModel):
    exchange: str
    symbol: str = "BTC/NGN"

    bid: Decimal = Field(gt=0)
    ask: Decimal = Field(gt=0)

    timestamp: datetime
    source: str