
import asyncio

from app.market_data.exchanges import fetch_all_quotes


async def main():
    quotes = await fetch_all_quotes()

    if not quotes:
        print("No market quotes were retrieved.")
        return

    for quote in quotes:
        print("-" * 45)
        print(f"Exchange:  {quote.exchange}")
        print(f"Symbol:    {quote.symbol}")
        print(f"Bid:       {quote.bid}")
        print(f"Ask:       {quote.ask}")
        print(f"Timestamp: {quote.timestamp.isoformat()}")
        print(f"Source:    {quote.source}")

    if len(quotes) < 2:
        print("\nNot enough quotes to compare exchanges.")
        return

    print("\nBoth exchanges returned quotes.")
    print("Next: validate freshness and calculate the spread.")


if __name__ == "__main__":
    asyncio.run(main())
