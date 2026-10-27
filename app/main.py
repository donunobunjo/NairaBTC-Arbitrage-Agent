
import secrets
from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.agent.graph import agent_graph
from app.paper_trading import ledger


class APISettings(BaseSettings):
    API_SECRET_KEY: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = APISettings()


async def verify_api_key(
    x_api_key: str | None = Header(default=None),
):
    """Reject requests without a valid API key."""
    if not x_api_key or not secrets.compare_digest(
        x_api_key, settings.API_SECRET_KEY
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key.",
        )


limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the local database when the API starts."""
    ledger.initialize_database()
    yield


app = FastAPI(
    title="NairaBTC Agent API",
    description=(
        "BTC/USDT arbitrage scanning using LangGraph, "
        "LangChain, Groq, and a SQLite paper-trading ledger. "
        "No real exchange orders are placed."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)


@app.get("/")
async def root():
    return {
        "name": "NairaBTC Agent",
        "status": "running",
        "description": "BTC/USDT arbitrage analysis API",
        "docs": "/docs",
        "real_trading_enabled": False,
    }



@app.get("/health")
async def health():
    """Check service and database availability."""
    try:
        ledger.get_portfolio()

        return {
            "status": "healthy",
            "service": "NairaBTC Agent",
            "database": "available",
            "real_trading_enabled": False,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Service or database is unavailable.",
        ) from exc



@app.post("/scan", dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
async def run_scan(request: Request):
    """Fetch market data, analyze, explain, and save results."""
    try:
        result = await agent_graph.ainvoke({})

        if result.get("error"):
            raise HTTPException(
                status_code=503,
                detail=result["error"],
            )

        results = result.get("results", [])
        save_errors = result.get("save_errors", [])

        response = {
            "status": (
                "completed_with_warnings"
                if save_errors
                else "completed"
            ),
            "quotes_received": len(result.get("quotes", [])),
            "records_saved": result.get("saved_records", 0),
            "save_errors_count": len(save_errors),
            "save_warnings": (
                ["One or more scan records could not be saved."]
                if save_errors
                else []
            ),
            "save_errors": save_errors,
            "results": [
                {
                    "buy_exchange": item.buy_exchange,
                    "sell_exchange": item.sell_exchange,
                    "trade_size_btc": str(item.trade_size_btc),
                    "buy_price": str(item.buy_price),
                    "sell_price": str(item.sell_price),
                    "gross_profit_usdt": str(item.gross_profit),
                    "net_profit_usdt": str(item.net_profit),
                    "eligible": item.eligible,
                    "reason": item.reason,
                }
                for item in results
            ],
            "explanations": result.get("explanations", []),
            "real_trading_enabled": False,
        }

        return response

    except HTTPException:
        raise
    except Exception as exc:
        # Keep implementation details out of the client response.
        raise HTTPException(
            status_code=500,
            detail="Scan failed.",
        ) from exc


@app.get("/scans", dependencies=[Depends(verify_api_key)])
async def recent_scans(
    limit: int = Query(default=10, ge=1, le=100),
):
    """Return recent saved scan records."""
    try:
        records = ledger.get_recent_records(limit=limit)
        return {
            "count": len(records),
            "records": records,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve scan records.",
        ) from exc


@app.get("/portfolio", dependencies=[Depends(verify_api_key)])
async def portfolio():
    """Return the virtual portfolio balance."""
    try:
        return ledger.get_portfolio()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve the virtual portfolio.",
        ) from exc
