"""风控模块：仓位管理、止损、熔断。"""
from __future__ import annotations

from .portfolio import Position


def position_qty(equity: float, price: float, max_position_pct: float) -> int:
    """按权益的一定比例计算可买整数股数。"""
    if price <= 0 or equity <= 0:
        return 0
    return int(equity * max_position_pct // price)


def hit_stop_loss(position: Position, price: float, stop_loss_pct: float) -> bool:
    """当前价较持仓成本回撤超过 stop_loss_pct 时触发止损。"""
    if position.avg_price <= 0:
        return False
    return price <= position.avg_price * (1.0 - stop_loss_pct)


def drawdown_from_peak(equity_series: list[float]) -> float:
    """当前相对历史峰值的回撤比例（0~1）。"""
    if not equity_series:
        return 0.0
    peak = max(equity_series)
    if peak <= 0:
        return 0.0
    return (peak - equity_series[-1]) / peak


def circuit_breaker(equity_series: list[float], max_drawdown_pct: float) -> bool:
    """回撤超过阈值 → 熔断（停止开新仓）。"""
    return drawdown_from_peak(equity_series) >= max_drawdown_pct
