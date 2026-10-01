"""策略基类与注册表。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class Signal:
    """一次交易信号。side: BUY / SELL / HOLD。"""

    side: str
    reason: str = ""
    confidence: float = 0.0  # 0~1，策略自评置信度


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """给行情 DataFrame 追加指标列（只读拷贝，不污染原数据）。"""

    @abstractmethod
    def generate(self, df: pd.DataFrame) -> Signal:
        """基于截至当前的行情给出信号。df 需已 prepare。"""


def get_strategy(name: str, params: dict[str, Any] | None = None) -> Strategy:
    from .examples import MACrossStrategy, RSIStrategy

    registry: dict[str, type[Strategy]] = {
        "ma_cross": MACrossStrategy,
        "rsi": RSIStrategy,
    }
    if name not in registry:
        raise ValueError(f"未知策略: {name}（可选 {list(registry)}）")
    return registry[name](**(params or {}))
