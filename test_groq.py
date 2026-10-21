
from app.agent.llm import explain_scan


if __name__ == "__main__":
    explanation = explain_scan(
        buy_exchange="Binance",
        sell_exchange="OKX",
        net_profit="-0.2451784",
        eligible=False,
        reason="Estimated fees and slippage exceed the price spread.",
    )

    print("\nNAIRABTC AGENT - GROQ TEST")
    print("-" * 40)
    print(explanation)
