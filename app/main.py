
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from app.agent.graph import agent_graph
from app.paper_trading import ledger


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
    return {
        "status": "healthy",
        "service": "NairaBTC Agent",
        "real_trading_enabled": False,
    }


@app.post("/scan")
async def run_scan():
    """Fetch market data, analyze arbitrage, explain, and save results."""
    try:
        result = await agent_graph.ainvoke({})

        if result.get("error"):
            raise HTTPException(
                status_code=503,
                detail=result["error"],
            )

        return {
            "status": "completed",
            "quotes_received": len(result.get("quotes", [])),
            "records_saved": result.get("saved_records", 0),
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
                for item in result.get("results", [])
            ],
            "explanations": result.get("explanations", []),
            "real_trading_enabled": False,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Scan failed: {exc}",
        ) from exc


@app.get("/scans")
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


@app.get("/portfolio")
async def portfolio():
    """Return the virtual portfolio balance."""
    try:
        return ledger.get_portfolio()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve the virtual portfolio.",
        ) from exc
