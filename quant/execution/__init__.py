"""执行层：券商适配器（模拟盘 / 真实券商）。"""
from .base import BrokerAdapter
from .paper import PaperBroker

__all__ = ["BrokerAdapter", "PaperBroker"]
