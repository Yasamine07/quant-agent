"""向量化之外的事件驱动回测引擎：次日开盘成交、止损、仓位管理。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .portfolio import Portfolio, Trade
from .risk import position_qty
from .strategy.base import Strategy

TRADING_DAYS = 252


@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    metrics: dict[str, float]
    equity_curve: pd.DataFrame  # columns: equity, buyhold, signal(side), price
    trades: list[Trade] = field(default_factory=list)


def run_backtest(
    df: pd.DataFrame,
    strategy: Strategy,
    initial_cash: float = 10000.0,
    commission: float = 0.001,
    stop_loss_pct: float | None = 0.08,
    max_position_pct: float = 0.2,
) -> BacktestResult:
    """按日线回测：T 日收盘出信号，T+1 日开盘价成交；持仓每日收盘按市价估值。"""
    data = strategy.prepare(df)
    if len(data) < 60:
        raise ValueError("数据量不足（至少 60 根 K 线）")

    symbol = "SYMBOL"  # 回测单标的
    port = Portfolio(initial_cash, commission)
    closes = data["close"]
    bh_qty = initial_cash * (1 - commission) / closes.iloc[0]  # 买入持有基准（含小数股）

    pending: tuple[str, str] | None = None
    equity_records: list[tuple[pd.Timestamp, float, float, str, float, float, float, float]] = []

    for i in range(1, len(data)):
        ts = data.index[i]
        o, h, l, c = data["open"].iloc[i], data["high"].iloc[i], data["low"].iloc[i], data["close"].iloc[i]

        # 1) 执行上一交易日的信号（今日开盘价）
        if pending is not None:
            side, reason = pending
            if side == "BUY" and symbol not in port.positions:
                qty = position_qty(port.equity({symbol: o}), o, max_position_pct)
                if qty > 0:
                    port.buy(symbol, qty, o, ts.isoformat(), reason)
            elif side == "SELL" and symbol in port.positions:
                port.sell(symbol, port.positions[symbol].qty, o, ts.isoformat(), reason)
            pending = None

        # 2) 收盘止损检查
        if stop_loss_pct and symbol in port.positions:
            pos = port.positions[symbol]
            if c <= pos.avg_price * (1 - stop_loss_pct):
                port.sell(symbol, pos.qty, c, ts.isoformat(), "止损")

        # 3) 收盘生成新信号（下一交易日开盘执行）
        sig = strategy.generate(data.iloc[: i + 1])
        if sig.side in ("BUY", "SELL"):
            pending = (sig.side, sig.reason)

        # 4) 按收盘价估值
        equity = port.equity({symbol: c})
        equity_records.append((ts, equity, bh_qty * c, sig.side, o, h, l, c))

    curve = pd.DataFrame(equity_records, columns=["date", "equity", "buyhold", "signal", "open", "high", "low", "close"])
    curve = curve.set_index("date")
    metrics = _compute_metrics(curve["equity"], curve["buyhold"], port.trades, initial_cash)
    return BacktestResult(symbol, strategy.name, metrics, curve, port.trades)


def _compute_metrics(
    equity: pd.Series, buyhold: pd.Series, trades: list[Trade], initial_cash: float
) -> dict[str, float]:
    final = float(equity.iloc[-1])
    total_return = final / initial_cash - 1.0
    years = max(len(equity) / TRADING_DAYS, 1e-9)
    annualized = (final / initial_cash) ** (1 / years) - 1.0 if final > 0 else -1.0

    daily = equity.pct_change().dropna()
    std = float(daily.std())
    sharpe = float(daily.mean() / std * np.sqrt(TRADING_DAYS)) if std > 1e-12 else 0.0

    peak = equity.cummax()
    max_dd = float(((peak - equity) / peak).max())

    closed = [t for t in trades if t.side == "SELL"]
    wins = [t for t in closed if t.pnl > 0]
    win_rate = len(wins) / len(closed) if closed else 0.0
    total_pnl = sum(t.pnl for t in closed)
    bh_return = float(buyhold.iloc[-1] / initial_cash - 1.0)

    return {
        "final_equity": round(final, 2),
        "total_return": round(total_return, 4),
        "annualized_return": round(annualized, 4),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_dd, 4),
        "win_rate": round(win_rate, 4),
        "num_trades": len(trades),
        "total_pnl": round(total_pnl, 2),
        "buyhold_return": round(bh_return, 4),
    }
