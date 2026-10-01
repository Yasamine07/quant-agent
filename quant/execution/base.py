"""券商适配器接口。新增市场只需实现此协议并注册。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BrokerAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def market_order(self, symbol: str, qty: int, side: str, time: str, reason: str = "") -> dict:
        """市价单。side: BUY / SELL。返回成交结果 dict。"""

    @abstractmethod
    def get_prices(self, symbols: list[str]) -> dict[str, float]:
        """获取一批标的最新价。"""
