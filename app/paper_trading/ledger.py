from datetime import datetime, timezone
from decimal import Decimal
import sqlite3
from pathlib import Path

# Store the database in the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "paper_trading.db"


def get_connection():
    """Open a connection to the paper-trading database."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    """Create the tables if they do not already exist."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                initial_balance REAL NOT NULL,
                current_balance REAL NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS trade_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                buy_exchange TEXT NOT NULL,
                sell_exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                trade_size_btc TEXT NOT NULL,
                buy_price TEXT NOT NULL,
                sell_price TEXT NOT NULL,
                gross_profit TEXT NOT NULL,
                buy_fee TEXT NOT NULL,
                sell_fee TEXT NOT NULL,
                estimated_slippage TEXT NOT NULL,
                net_profit TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                executed_at TEXT
            )
        """)
        
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(trade_records)"
            ).fetchall()
        }

        if "executed_at" not in columns:
            connection.execute(
                "ALTER TABLE trade_records ADD COLUMN executed_at TEXT"
            )

        # Create the virtual portfolio only on first initialization.
        connection.execute("""
            INSERT OR IGNORE INTO portfolio (
                id, initial_balance, current_balance
            )
            VALUES (1, 1000.0, 1000.0)
        """)


def record_scan(result, symbol="BTC/USDT"):
    """Record an arbitrage result without executing a real trade."""
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).isoformat()

    status = "eligible" if result.eligible else "rejected"

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO trade_records (
                timestamp,
                buy_exchange,
                sell_exchange,
                symbol,
                trade_size_btc,
                buy_price,
                sell_price,
                gross_profit,
                buy_fee,
                sell_fee,
                estimated_slippage,
                net_profit,
                status,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            result.buy_exchange,
            result.sell_exchange,
            symbol,
            str(result.trade_size_btc),
            str(result.buy_price),
            str(result.sell_price),
            str(result.gross_profit),
            str(result.buy_fee),
            str(result.sell_fee),
            str(result.estimated_slippage),
            str(result.net_profit),
            status,
            result.reason,
        ))


def get_recent_records(limit=10):
    """Return the most recent scan records."""
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM trade_records
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [dict(row) for row in rows]


def get_portfolio():
    """Return the virtual portfolio balance."""
    with get_connection() as connection:
        row = connection.execute("""
            SELECT initial_balance, current_balance
            FROM portfolio
            WHERE id = 1
        """).fetchone()

    return dict(row)




def execute_paper_trade(record_id: int) -> dict:
    """Simulate a trade for an eligible scan; never place a real order."""

    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        record = connection.execute(
            "SELECT * FROM trade_records WHERE id = ?",
            (record_id,),
        ).fetchone()

        if record is None:
            raise ValueError(f"Scan record {record_id} was not found.")

        
        if record["executed_at"] is not None:
            raise ValueError("This scan has already been executed.")

        if record["status"] != "eligible":
            raise ValueError("This scan is not eligible for paper execution.")


        net_profit = Decimal(record["net_profit"])
        trade_size_btc = Decimal(record["trade_size_btc"])
        buy_price = Decimal(record["buy_price"])
        buy_fee = Decimal(record["buy_fee"])

        # Estimate the required virtual funds for the purchase.
        required_funds = trade_size_btc * buy_price + buy_fee

        portfolio = connection.execute(
            "SELECT current_balance FROM portfolio WHERE id = 1"
        ).fetchone()

        if portfolio is None:
            raise ValueError("Virtual portfolio has not been initialized.")

        current_balance = Decimal(str(portfolio["current_balance"]))

        if current_balance < required_funds:
            raise ValueError("Insufficient virtual funds for this trade.")

        new_balance = current_balance + net_profit

        connection.execute(
            """
            UPDATE portfolio
            SET current_balance = ?
            WHERE id = 1
            """,
            (str(new_balance),),
        )

        connection.execute(
            """
            UPDATE trade_records
            SET status = 'paper_executed', executed_at = ?
            WHERE id = ?
            """,
            (now, record_id),
        )

    return {
        "record_id": record_id,
        "status": "paper_executed",
        "net_profit": str(net_profit),
        "previous_balance": str(current_balance),
        "new_balance": str(new_balance),
        "executed_at": now,
    }

