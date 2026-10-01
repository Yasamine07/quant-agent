"""SQLite 持久化：权益曲线、交易记录、Agent 状态（线程安全）。"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .portfolio import Trade

_SCHEMA = """
CREATE TABLE IF NOT EXISTS equity (
    ts TEXT PRIMARY KEY,
    equity REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty INTEGER NOT NULL,
    price REAL NOT NULL,
    pnl REAL NOT NULL DEFAULT 0,
    reason TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, path: str | Path = "quant.db"):
        self.path = str(path)
        # check_same_thread=False：Agent 后台线程写、API 线程读
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def append_equity(self, ts: str, equity: float) -> None:
        with self._lock:
            self._conn.execute("INSERT OR REPLACE INTO equity (ts, equity) VALUES (?, ?)", (ts, float(equity)))
            self._conn.commit()

    def append_trade(self, t: Trade) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO trades (ts, symbol, side, qty, price, pnl, reason) VALUES (?,?,?,?,?,?,?)",
                (t.time, t.symbol, t.side, t.qty, t.price, t.pnl, t.reason),
            )
            self._conn.commit()

    def save_state(self, key: str, value: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False))
            )
            self._conn.commit()

    def load_state(self, key: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def equity_curve(self, limit: int = 5000) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, equity FROM equity ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{"time": ts, "equity": eq} for ts, eq in reversed(rows)]

    def trades(self, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, symbol, side, qty, price, pnl, reason FROM trades ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"time": ts, "symbol": s, "side": side, "qty": q, "price": p, "pnl": pnl, "reason": r}
            for ts, s, side, q, p, pnl, r in reversed(rows)
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
