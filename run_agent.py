
import asyncio

from app.agent.graph import agent_graph
from app.paper_trading import ledger


async def main():
    # Make sure the SQLite tables exist.
    ledger.initialize_database()

    print("=" * 50)
    print("NAIRABTC AGENT - LANGGRAPH SCANNER")
    print("=" * 50)

    # Run the complete graph.
    final_state = await agent_graph.ainvoke({})

    if final_state.get("error"):
        print(f"\nWarning: {final_state['error']}")

    print("\nScan completed.")
    print(
        "Records saved:",
        final_state.get("saved_records", 0),
    )
    print("No real exchange orders were placed.")


if __name__ == "__main__":
    asyncio.run(main())
