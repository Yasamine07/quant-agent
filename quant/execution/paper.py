"""模拟盘执行器：订单直接作用于本地 Portfolio，不涉及真实资金。"""
from __future__ import annotations

from ..portfolio import Portfolio
from .base import BrokerAdapter


class PaperBroker(BrokerAdapter):
    name = "paper"

    def __init__(self, portfolio: Portfolio, price_provider):
        self.portfolio = portfolio
        self._prices = price_provider  # callable(symbols) -> dict[str, float]

    def get_prices(self, symbols: list[str]) -> dict[str, float]:
        return self._prices(symbols)

    def market_order(self, symbol: str, qty: int, side: str, time: str, reason: str = "") -> dict:
        price = self._prices([symbol]).get(symbol)
        if price is None:
            raise RuntimeError(f"无法获取 {symbol} 最新价")
        if side == "BUY":
            trade = self.portfolio.buy(symbol, qty, price, time, reason)
        elif side == "SELL":
            trade = self.portfolio.sell(symbol, qty, price, time, reason)
        else:
            raise ValueError(f"未知方向: {side}")
        return {"filled": trade.qty, "price": trade.price, "side": side, "time": trade.time}
