
from typing import TypedDict
from decimal import Decimal

from langgraph.graph import StateGraph, START, END

from app.market_data.models import MarketQuote
from app.market_data.exchanges import fetch_all_quotes
from app.arbitrage.calculator import compare_exchanges
from app.arbitrage.calculator import ArbitrageResult
from app.paper_trading import ledger
from app.agent.llm import explain_scan

# 1. Define the information passed between graph nodes.
class AgentState(TypedDict, total=False):
    quotes: list[MarketQuote]
    results: list[ArbitrageResult]
    explanations: list[str]
    saved_records: int
    error: str


# 2. Node: fetch prices from the exchanges.
async def fetch_market_data(state: AgentState) -> dict:
    print("\n[1/3] Fetching market quotes...")

    try:
        quotes = await fetch_all_quotes()

        print(f"Received {len(quotes)} usable quote(s).")

        if len(quotes) < 2:
            return {
                "quotes": quotes,
                "error": (
                    "At least two valid exchange quotes are "
                    "required to compare arbitrage opportunities."
                ),
            }

        for quote in quotes:
            print(
                f"{quote.exchange}: "
                f"bid={quote.bid}, ask={quote.ask}"
            )

        return {"quotes": quotes}

    except Exception as exc:
        return {
            "quotes": [],
            "error": f"Market data collection failed: {exc}",
        }


# 3. Node: calculate arbitrage in both directions.
def analyze_arbitrage(state: AgentState) -> dict:
    print("\n[2/3] Analyzing arbitrage opportunities...")

    if state.get("error"):
        return {"results": []}

    quotes = state.get("quotes", [])

    if len(quotes) < 2:
        return {"results": []}

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

        return {"results": results}

    except Exception as exc:
        return {
            "results": [],
            "error": f"Arbitrage analysis failed: {exc}",
        }



def explain_arbitrage_results(state: AgentState) -> dict:
    """Explain calculated results without changing financial decisions."""
    print("\nExplaining scan results with Groq...")

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
            # The scanner must remain useful if the LLM is unavailable.
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



# 4. Node: save every calculated opportunity.
def save_scan_results(state: AgentState) -> dict:
    print("\n[3/3] Saving scan results...")

    results = state.get("results", [])
    saved_records = 0

    for result in results:
        ledger.record_scan(result)
        saved_records += 1

    print(f"Saved {saved_records} scan record(s).")

    return {"saved_records": saved_records}



def route_after_fetch(state: AgentState) -> str:
    """Stop safely if market data collection failed."""
    if state.get("error"):
        return "stop"

    if len(state.get("quotes", [])) < 2:
        return "stop"

    return "analyze"


# 5. Build the LangGraph workflow.

# 5. Build the LangGraph workflow.
builder = StateGraph(AgentState)

builder.add_node("fetch_market_data", fetch_market_data)
builder.add_node("analyze_arbitrage", analyze_arbitrage)
builder.add_node("save_scan_results", save_scan_results)
builder.add_node(
    "explain_arbitrage_results",
    explain_arbitrage_results,
)

builder.add_edge(START, "fetch_market_data")

# Choose the next node based on the market-data result.
builder.add_conditional_edges(
    "fetch_market_data",
    route_after_fetch,
    {
        "analyze": "analyze_arbitrage",
        "stop": END,
    },
)

builder.add_edge(
    "analyze_arbitrage",
    "explain_arbitrage_results",
)
builder.add_edge(
    "explain_arbitrage_results",
    "save_scan_results",
)
builder.add_edge("save_scan_results", END) 
# Compile the graph.
agent_graph = builder.compile()