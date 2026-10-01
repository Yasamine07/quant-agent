"""模拟盘组合：现金、持仓、成交记录与权益曲线。"""
from __future__ import annotations

from dataclasses import dataclass, field


class InsufficientFunds(Exception):
    pass


class NoPosition(Exception):
    pass


@dataclass
class Position:
    symbol: str
    qty: int
    avg_price: float


@dataclass
class Trade:
    time: str
    symbol: str
    side: str  # BUY / SELL
    qty: int
    price: float
    pnl: float
    reason: str = ""


@dataclass
class Portfolio:
    initial_cash: float = 10000.0
    commission: float = 0.001
    cash: float = field(init=False)
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cash = float(self.initial_cash)

    def market_value(self, prices: dict[str, float]) -> float:
        return sum(p.qty * prices[p.symbol] for p in self.positions.values() if p.symbol in prices)

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + self.market_value(prices)

    def buy(self, symbol: str, qty: int, price: float, time: str, reason: str = "") -> Trade:
        qty = int(qty)
        if qty <= 0:
            raise ValueError("买入数量必须为正")
        cost = qty * price
        fee = cost * self.commission
        if self.cash < cost + fee:
            raise InsufficientFunds(f"现金不足: 需要 {cost + fee:.2f}, 现有 {self.cash:.2f}")
        self.cash -= cost + fee
        pos = self.positions.get(symbol)
        if pos is None:
            self.positions[symbol] = Position(symbol, qty, price)
        else:
            total_qty = pos.qty + qty
            pos.avg_price = (pos.avg_price * pos.qty + cost) / total_qty
            pos.qty = total_qty
        trade = Trade(time, symbol, "BUY", qty, price, 0.0, reason)
        self.trades.append(trade)
        return trade

    def sell(self, symbol: str, qty: int, price: float, time: str, reason: str = "") -> Trade:
        pos = self.positions.get(symbol)
        if pos is None or pos.qty <= 0:
            raise NoPosition(f"没有 {symbol} 持仓可卖")
        qty = min(int(qty), pos.qty)
        proceeds = qty * price
        fee = proceeds * self.commission
        pnl = proceeds - fee - qty * pos.avg_price
        self.cash += proceeds - fee
        pos.qty -= qty
        if pos.qty == 0:
            del self.positions[symbol]
        trade = Trade(time, symbol, "SELL", qty, price, pnl, reason)
        self.trades.append(trade)
        return trade

    def close_all(self, prices: dict[str, float], time: str, reason: str = "") -> list[Trade]:
        out = []
        for symbol in list(self.positions):
            out.append(self.sell(symbol, self.positions[symbol].qty, prices.get(symbol, 0.0), time, reason))
        return out
