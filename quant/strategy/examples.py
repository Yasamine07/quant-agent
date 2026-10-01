"""内置示例策略：双均线金叉/死叉、RSI 超买超卖。"""
from __future__ import annotations

import pandas as pd

from ..indicators import rsi, sma
from .base import Signal, Strategy


class MACrossStrategy(Strategy):
    """快慢均线金叉买入、死叉卖出。"""

    name = "ma_cross"

    def __init__(self, fast: int = 10, slow: int = 30):
        if fast >= slow:
            raise ValueError("fast 必须小于 slow")
        self.fast, self.slow = fast, slow

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["ma_fast"] = sma(out["close"], self.fast)
        out["ma_slow"] = sma(out["close"], self.slow)
        return out

    def generate(self, df: pd.DataFrame) -> Signal:
        if len(df) < 2:
            return Signal("HOLD", "数据不足")
        prev_f, cur_f = df["ma_fast"].iloc[-2], df["ma_fast"].iloc[-1]
        prev_s, cur_s = df["ma_slow"].iloc[-2], df["ma_slow"].iloc[-1]
        if pd.isna(prev_f) or pd.isna(cur_f) or pd.isna(prev_s) or pd.isna(cur_s):
            return Signal("HOLD", "均线未就绪")
        if prev_f <= prev_s and cur_f > cur_s:
            spread = abs(cur_f - cur_s) / cur_s
            return Signal("BUY", f"金叉(fast>{self.slow})", min(1.0, spread * 20))
        if prev_f >= prev_s and cur_f < cur_s:
            spread = abs(cur_f - cur_s) / cur_s
            return Signal("SELL", f"死叉(fast<{self.slow})", min(1.0, spread * 20))
        return Signal("HOLD", "无交叉")


class RSIStrategy(Strategy):
    """RSI 超卖(<oversold)买入、超买(>overbought)卖出。"""

    name = "rsi"

    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        self.period, self.oversold, self.overbought = int(period), float(oversold), float(overbought)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["rsi"] = rsi(out["close"], self.period)
        return out

    def generate(self, df: pd.DataFrame) -> Signal:
        if len(df) < self.period + 1:
            return Signal("HOLD", "数据不足")
        cur = df["rsi"].iloc[-1]
        if pd.isna(cur):
            return Signal("HOLD", "RSI 未就绪")
        if cur < self.oversold:
            return Signal("BUY", f"RSI={cur:.1f} 超卖", min(1.0, (self.oversold - cur) / self.oversold))
        if cur > self.overbought:
            return Signal("SELL", f"RSI={cur:.1f} 超买", min(1.0, (cur - self.overbought) / self.overbought))
        return Signal("HOLD", f"RSI={cur:.1f} 中性")
