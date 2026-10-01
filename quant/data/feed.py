"""行情数据源：真实（Yahoo）与离线演示（Synthetic）两种，接口统一。"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

BAR_COLUMNS = ["open", "high", "low", "close", "volume"]


class DataUnavailable(Exception):
    """行情获取失败。"""


class DataFeed(ABC):
    """行情数据源接口。返回的 DataFrame 必须带 DatetimeIndex 与 BAR_COLUMNS 列。"""

    @abstractmethod
    def get_bars(self, symbol: str, days: int, interval: str = "1d") -> pd.DataFrame:
        """获取 symbol 最近 days 天的日线。"""


class YahooFeed(DataFeed):
    """Yahoo Finance 真实行情（美股等）。"""

    def get_bars(self, symbol: str, days: int, interval: str = "1d") -> pd.DataFrame:
        import yfinance as yf

        end = pd.Timestamp.today().normalize()
        start = end - pd.Timedelta(days=days + 15)  # 多留一点余量补齐非交易日
        df = yf.download(
            symbol,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval=interval,
            auto_adjust=True,
            progress=False,
        )
        if df is None or df.empty:
            raise DataUnavailable(f"Yahoo 未返回 {symbol} 的行情数据")
        if isinstance(df.columns, pd.MultiIndex):  # 单标的也可能出现多级列
            df.columns = df.columns.get_level_values(0)
        df = df[[c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]].copy()
        df.columns = BAR_COLUMNS[: len(df.columns)]
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.astype(float)
        return df.dropna()


class SyntheticFeed(DataFeed):
    """离线演示行情：几何随机游走，保证无网环境下全流程可跑通。"""

    def __init__(self, seed: int = 42, start_price: float = 100.0):
        self._rng = np.random.default_rng(seed)
        self._start_price = start_price

    def get_bars(self, symbol: str, days: int, interval: str = "1d") -> pd.DataFrame:
        if interval != "1d":
            raise DataUnavailable("离线数据仅支持日线")
        n = max(days, 60)
        rets = self._rng.normal(loc=0.0004, scale=0.018, size=n)
        close = self._start_price * np.exp(np.cumsum(rets))
        open_ = close * (1 + self._rng.normal(0, 0.004, size=n))
        high = np.maximum(open_, close) * (1 + np.abs(self._rng.normal(0, 0.006, size=n)))
        low = np.minimum(open_, close) * (1 - np.abs(self._rng.normal(0, 0.006, size=n)))
        volume = self._rng.integers(1_000_000, 10_000_000, size=n).astype(float)
        idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
        return pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=idx,
        )


def get_feed(name: str, seed: int = 42) -> DataFeed:
    if name == "yahoo":
        return YahooFeed()
    if name == "synthetic":
        return SyntheticFeed(seed=seed)
    raise ValueError(f"未知数据源: {name}（可选 yahoo / synthetic）")
