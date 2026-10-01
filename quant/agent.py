"""自动交易 Agent：轮询行情 → 策略信号 → 风控 → 模拟盘执行 → 持久化。"""
from __future__ import annotations

import threading
import time
from typing import Any

from .data.feed import DataFeed, get_feed
from .execution.base import BrokerAdapter
from .execution.paper import PaperBroker
from .portfolio import Portfolio
from .risk import circuit_breaker, hit_stop_loss, position_qty
from .storage import Storage
from .strategy.base import Signal, Strategy, get_strategy


class LiveAgent:
    """单标的轮询式自动交易（当前版本逐个 symbol 顺序执行）。"""

    def __init__(self, cfg: dict[str, Any], storage: Storage | None = None):
        self.cfg = cfg
        self.feed: DataFeed = get_feed(cfg["data"]["feed"])
        self.strategy: Strategy = get_strategy(cfg["strategy"]["name"], cfg["strategy"].get("params") or {})
        self.symbols: list[str] = cfg["agent"]["symbols"]
        self.interval = float(cfg["agent"]["poll_interval_sec"])
        self.stop_loss_pct = float(cfg["risk"]["stop_loss_pct"])
        self.max_pos_pct = float(cfg["risk"]["max_position_pct"])
        self.max_dd_pct = float(cfg["risk"]["max_drawdown_pct"])
        self.storage = storage or Storage(cfg.get("db", "quant.db"))
        self.portfolio = Portfolio(
            initial_cash=float(cfg["portfolio"]["initial_cash"]),
            commission=float(cfg["portfolio"]["commission"]),
        )
        self.broker: BrokerAdapter = self._make_broker()
        self._last_price: dict[str, float] = {}
        self._equity_history: list[float] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_signal: Signal | None = None
        self.last_error: str | None = None

    def _make_broker(self) -> BrokerAdapter:
        if self.cfg["broker"]["paper"]:
            return PaperBroker(self.portfolio, lambda syms: self._prices(syms))
        from .execution.alpaca import AlpacaBroker

        a = self.cfg["broker"]["alpaca"]
        return AlpacaBroker(a.get("api_key", ""), a.get("secret_key", ""), a.get("base_url", ""))

    def _prices(self, symbols: list[str]) -> dict[str, float]:
        out = {}
        for s in symbols:
            if s in self._last_price:
                out[s] = self._last_price[s]
        # 实时轮询时用最新 K 线收盘价近似市价（日线场景可接受，文档已注明）
        for s in symbols:
            if s not in out:
                try:
                    bars = self.feed.get_bars(s, days=5)
                    out[s] = float(bars["close"].iloc[-1])
                except Exception:
                    pass
        return out

    # ---------- 单轮决策 ----------
    def run_once(self) -> None:
        self.last_error = None
        prices = {}
        try:
            for sym in self.symbols:
                bars = self.feed.get_bars(sym, days=int(self.cfg["data"]["lookback_days"]))
                bars = self.strategy.prepare(bars)
                price = float(bars["close"].iloc[-1])
                prices[sym] = price
                self._last_price[sym] = price

                # 止损检查
                pos = self.portfolio.positions.get(sym)
                if pos and hit_stop_loss(pos, price, self.stop_loss_pct):
                    self.broker.market_order(sym, pos.qty, "SELL", time.strftime("%Y-%m-%d %H:%M:%S"), "止损")
                    self.storage.append_trade(self.portfolio.trades[-1])

                # 策略信号
                sig = self.strategy.generate(bars)
                self.last_signal = sig
                if sig.side == "BUY" and sym not in self.portfolio.positions:
                    equity = self.portfolio.equity(prices)
                    qty = position_qty(equity, price, self.max_pos_pct)
                    if qty > 0 and not circuit_breaker(self._equity_history + [equity], self.max_dd_pct):
                        self.broker.market_order(sym, qty, "BUY", time.strftime("%Y-%m-%d %H:%M:%S"), sig.reason)
                        self.storage.append_trade(self.portfolio.trades[-1])
                elif sig.side == "SELL" and sym in self.portfolio.positions:
                    self.broker.market_order(sym, self.portfolio.positions[sym].qty, "SELL",
                                             time.strftime("%Y-%m-%d %H:%M:%S"), sig.reason)
                    self.storage.append_trade(self.portfolio.trades[-1])

            now = time.strftime("%Y-%m-%d %H:%M:%S")
            eq = self.portfolio.equity(prices)
            self._equity_history.append(eq)
            del self._equity_history[:-2000]
            self.storage.append_equity(now, eq)
            self.storage.save_state(
                "agent",
                {
                    "running": self.is_running(),
                    "cash": round(self.portfolio.cash, 2),
                    "equity": round(eq, 2),
                    "positions": {s: {"qty": p.qty, "avg_price": p.avg_price}
                                  for s, p in self.portfolio.positions.items()},
                    "last_signal": (self.last_signal.side if self.last_signal else "HOLD"),
                    "last_update": now,
                },
            )
        except Exception as e:  # 单轮失败不影响循环
            self.last_error = f"{type(e).__name__}: {e}"

    # ---------- 启停 ----------
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="quant-agent", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"
            self._stop.wait(self.interval)

    def state(self) -> dict:
        prices = self._last_price
        eq = self.portfolio.equity(prices) if prices else self.portfolio.cash
        return {
            "running": self.is_running(),
            "cash": round(self.portfolio.cash, 2),
            "equity": round(eq, 2),
            "positions": {s: {"qty": p.qty, "avg_price": p.avg_price} for s, p in self.portfolio.positions.items()},
            "last_signal": self.last_signal.side if self.last_signal else "HOLD",
            "last_update": time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_error": self.last_error,
        }
