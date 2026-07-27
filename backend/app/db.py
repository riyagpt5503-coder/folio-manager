import sqlite3
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = _REPO_ROOT / "data" / "portfolio.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    lot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    qty REAL NOT NULL,
    buy_date TEXT NOT NULL,
    buy_price REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL NOT NULL,
    date TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def create_position(symbol: str, qty: float, buy_date: str, buy_price: float) -> sqlite3.Row:
    conn = _connect()
    try:
        cursor = conn.execute(
            "INSERT INTO positions (symbol, qty, buy_date, buy_price) VALUES (?, ?, ?, ?)",
            (symbol, qty, buy_date, buy_price),
        )
        conn.commit()
        return conn.execute("SELECT * FROM positions WHERE lot_id = ?", (cursor.lastrowid,)).fetchone()
    finally:
        conn.close()


def list_positions() -> list[sqlite3.Row]:
    conn = _connect()
    try:
        return conn.execute("SELECT * FROM positions ORDER BY lot_id").fetchall()
    finally:
        conn.close()


def delete_position(lot_id: int) -> bool:
    conn = _connect()
    try:
        cursor = conn.execute("DELETE FROM positions WHERE lot_id = ?", (lot_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
