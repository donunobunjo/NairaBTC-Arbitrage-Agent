
import asyncio
from decimal import Decimal

from app.market_data.exchanges import fetch_all_quotes
from app.arbitrage.calculator import compare_exchanges
from app.paper_trading.ledger import initialize_database, record_scan

async def main():
    print("=" * 65)
    print("        NAIRABTC AGENT - ARBITRAGE SCANNER")
    print("=" * 65)

    # Step 1: Fetch live quotes from supported exchanges.
    print("\nFetching live BTC/USDT market quotes...\n")


    initialize_database()
    quotes = await fetch_all_quotes()

    # Step 2: Check whether we received enough quotes.
    if len(quotes) < 2:
        print("ERROR: We need quotes from both exchanges to compare prices.")
        print("Check your internet connection and try again.")
        return

    # Step 3: Display the prices received.
    for quote in quotes:
        print(f"Exchange: {quote.exchange}")
        print(f"Trading pair: {quote.symbol}")
        print(f"Best bid (sell price): {quote.bid}")
        print(f"Best ask (buy price):  {quote.ask}")
        print(f"Timestamp: {quote.timestamp.isoformat()}")
        print(f"Source: {quote.source}")
        print("-" * 65)

    # Step 4: Set our paper-trading assumptions.
    trade_size_btc = Decimal("0.001")
    fee_rate = Decimal("0.001")
    slippage_rate = Decimal("0.0005")
    minimum_net_profit = Decimal("0")

    print("\nPAPER-TRADING ASSUMPTIONS")
    print(f"BTC trade size: {trade_size_btc}")
    print(f"Fee per side: {fee_rate * 100}%")
    print(f"Estimated slippage per side: {slippage_rate * 100}%")
    print(f"Minimum net profit: {minimum_net_profit} USDT")
    print("\nNote: These are illustrative assumptions, not verified exchange fees.")
    print("Actual fees depend on your account, trading tier, and order type.")

    # Step 5: Compare both buy/sell directions.
    results = compare_exchanges(
        quotes[0],
        quotes[1],
        trade_size_btc=trade_size_btc,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        min_net_profit=minimum_net_profit,
        max_quote_age_seconds=30,
    )

    # Step 6: Print the estimated results.
    print("\n" + "=" * 65)
    print("                 ARBITRAGE ANALYSIS")
    print("=" * 65)



    # Save both arbitrage directions to the ledger.
    for result in results:
        record_scan(result)

    print("\nScan results saved to paper_trading.db.")



    # Display the results.
    for index, result in enumerate(results, start=1):
        print(f"\nDirection {index}:")
        print(f"Buy on: {result.buy_exchange}")
        print(f"Sell on: {result.sell_exchange}")
        print(f"Buy price (ask): {result.buy_price} USDT")
        print(f"Sell price (bid): {result.sell_price} USDT")
        # print(f"Gross profit after estimated slippage: {result.gross_profit:.8f} USDT")
        print(f"Raw gross profit before costs: {result.gross_profit:.8f} USDT")
        print(f"Estimated buy fee: {result.buy_fee:.8f} USDT")
        print(f"Estimated sell fee: {result.sell_fee:.8f} USDT")
        print(f"Estimated slippage cost: {result.estimated_slippage:.8f} USDT")
        print(f"Estimated net profit: {result.net_profit:.8f} USDT")
        print(f"Estimated net return: {result.net_return_pct:.6f}%")
        print(f"Eligible: {'YES' if result.eligible else 'NO'}")
        print(f"Reason: {result.reason}")

    # Step 7: Summarize the best eligible direction.
    eligible_results = [result for result in results if result.eligible]

    print("\n" + "=" * 65)

    if eligible_results:
        best = max(eligible_results, key=lambda result: result.net_profit)
        print("POTENTIAL PAPER-TRADING OPPORTUNITY")
        print(f"Buy on {best.buy_exchange}; sell on {best.sell_exchange}")
        print(f"Estimated net profit: {best.net_profit:.8f} USDT")
    else:
        print("NO QUALIFYING OPPORTUNITY")
        print("Neither direction exceeded the configured profit threshold.")

    print("=" * 65)
    print("\nReminder: This is an estimate, not a guarantee of executable profit.")
    print("It excludes transfer costs, order-book depth, and execution risk.")


if __name__ == "__main__":
    asyncio.run(main())
