
from app.paper_trading.ledger import (
    initialize_database,
    get_portfolio,
    get_recent_records,
)


def main():
    initialize_database()

    portfolio = get_portfolio()
    records = get_recent_records()

    print("NAIRABTC AGENT - PAPER-TRADING LEDGER")
    print("-" * 45)
    print(f"Initial virtual balance: {portfolio['initial_balance']} USDT")
    print(f"Current virtual balance: {portfolio['current_balance']} USDT")
    print(f"Saved scan records: {len(records)}")

    for record in records:
        print(record)


if __name__ == "__main__":
    main()
