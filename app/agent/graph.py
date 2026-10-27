
from typing import TypedDict
from decimal import Decimal

from langgraph.graph import StateGraph, START, END

from app.market_data.models import MarketQuote
from app.market_data.exchanges import fetch_all_quotes
from app.arbitrage.calculator import (
    ArbitrageResult,
    compare_exchanges,
)
from app.paper_trading import ledger
from app.agent.llm import explain_scan


# 1. Define the state shared between graph nodes.
class AgentState(TypedDict, total=False):
    quotes: list[MarketQuote]
    results: list[ArbitrageResult]
    explanations: list[str]
    saved_records: int
    error: str
    save_errors: list[str]


# 2. Fetch market prices from the exchanges.
async def fetch_market_data(state: AgentState) -> dict:
    print("\n[1/4] Fetching market quotes...")

    try:
        quotes = await fetch_all_quotes()

        print(f"Received {len(quotes)} usable quote(s).")

        for quote in quotes:
            print(
                f"{quote.exchange}: "
                f"bid={quote.bid}, ask={quote.ask}"
            )

        if len(quotes) < 2:
            return {
                "quotes": quotes,
                "error": (
                    "At least two valid exchange quotes are "
                    "required to compare arbitrage opportunities."
                ),
            }

        return {"quotes": quotes, "error": ""}

    except Exception:
        # Avoid exposing internal exception details in API responses.
        return {
            "quotes": [],
            "error": "Market data collection failed.",
        }


# 3. Calculate arbitrage using deterministic Python logic.
def analyze_arbitrage(state: AgentState) -> dict:
    print("\n[2/4] Analyzing arbitrage opportunities...")

    quotes = state.get("quotes", [])

    if len(quotes) < 2:
        return {
            "results": [],
            "error": "Insufficient quotes for arbitrage analysis.",
        }

    try:
        # Compare the first two available exchange quotes.
        results = compare_exchanges(
            quotes[0],
            quotes[1],
            trade_size_btc=Decimal("0.001"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
            min_net_profit=Decimal("0"),
            max_quote_age_seconds=30,
        )

        for result in results:
            print(
                f"{result.buy_exchange} -> "
                f"{result.sell_exchange}: "
                f"net profit={result.net_profit} USDT; "
                f"eligible={result.eligible}"
            )

        return {"results": results, "error": ""}

    except Exception:
        return {
            "results": [],
            "error": "Arbitrage analysis failed.",
        }


# 4. Explain results without allowing the LLM to decide eligibility.
def explain_arbitrage_results(state: AgentState) -> dict:
    print("\n[3/4] Explaining scan results with Groq...")

    explanations = []

    for result in state.get("results", []):
        try:
            explanation = explain_scan(
                buy_exchange=result.buy_exchange,
                sell_exchange=result.sell_exchange,
                net_profit=str(result.net_profit),
                eligible=result.eligible,
                reason=result.reason,
            )
        except Exception as exc:
            # Continue scanning even if the LLM is unavailable.
            explanation = (
                "LLM explanation unavailable. "
                f"Python decision: "
                f"{'eligible' if result.eligible else 'rejected'}. "
                f"Reason: {result.reason}"
            )
            print(f"Groq explanation failed: {exc}")

        explanations.append(explanation)

        print(f"\n{result.buy_exchange} -> {result.sell_exchange}")
        print(explanation)

    return {"explanations": explanations}


# 5. Save results and report individual database failures.
def save_scan_results(state: AgentState) -> dict:
    print("\n[4/4] Saving scan results...")

    saved_records = 0
    save_errors = []

    for result in state.get("results", []):
        try:
            ledger.record_scan(result)
            saved_records += 1
        except Exception as exc:
            # Don't let one failed record prevent attempts to save others.
            message = (
                f"Failed to save {result.buy_exchange} -> "
                f"{result.sell_exchange}."
            )
            save_errors.append(message)
            print(f"{message} Error: {exc}")

    print(f"Saved {saved_records} scan record(s).")

    if save_errors:
        print(f"Encountered {len(save_errors)} save error(s).")

    return {
        "saved_records": saved_records,
        "save_errors": save_errors,
    }


# 6. Route failed data collection or analysis to the end.
def route_after_fetch(state: AgentState) -> str:
    if state.get("error"):
        return "stop"

    if len(state.get("quotes", [])) < 2:
        return "stop"

    return "analyze"


def route_after_analysis(state: AgentState) -> str:
    if state.get("error"):
        return "stop"

    return "explain"


# 7. Build the LangGraph workflow.
builder = StateGraph(AgentState)

builder.add_node("fetch_market_data", fetch_market_data)
builder.add_node("analyze_arbitrage", analyze_arbitrage)
builder.add_node(
    "explain_arbitrage_results",
    explain_arbitrage_results,
)
builder.add_node("save_scan_results", save_scan_results)

builder.add_edge(START, "fetch_market_data")

builder.add_conditional_edges(
    "fetch_market_data",
    route_after_fetch,
    {
        "analyze": "analyze_arbitrage",
        "stop": END,
    },
)

builder.add_conditional_edges(
    "analyze_arbitrage",
    route_after_analysis,
    {
        "explain": "explain_arbitrage_results",
        "stop": END,
    },
)

builder.add_edge(
    "explain_arbitrage_results",
    "save_scan_results",
)
builder.add_edge("save_scan_results", END)

# Compile the graph.
agent_graph = builder.compile()
