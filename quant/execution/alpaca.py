"""Alpaca 真实券商适配器（可选，实验性）。

启用方式：在 .env 中配置 ALPACA_API_KEY / ALPACA_SECRET_KEY，并把
config.yaml 的 broker.paper 设为 false。请务必先在 paper-api 模拟环境验证，
真实自动交易有亏损风险，本代码不构成任何投资建议。
"""
from __future__ import annotations

import requests

from .base import BrokerAdapter


class AlpacaBroker(BrokerAdapter):
    name = "alpaca"

    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://paper-api.alpaca.markets"):
        if not api_key or not secret_key:
            raise RuntimeError("缺少 ALPACA_API_KEY / ALPACA_SECRET_KEY（见 .env.example）")
        self._base = base_url.rstrip("/")
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        }

    def _request(self, method: str, path: str, **kw):
        resp = requests.request(method, f"{self._base}{path}", headers=self._headers, timeout=15, **kw)
        resp.raise_for_status()
        return resp.json()

    def get_prices(self, symbols: list[str]) -> dict[str, float]:
        # 简化实现：用最新报价接口（q 参数逗号分隔）
        data = self._request("GET", f"/v2/stocks/quotes?symbols={','.join(symbols)}")
        return {sym: float(v["latest_trade"]["p"]) for sym, v in data.items() if v}

    def market_order(self, symbol: str, qty: int, side: str, time: str, reason: str = "") -> dict:
        order = self._request(
            "POST",
            "/v2/orders",
            json={
                "symbol": symbol,
                "qty": str(qty),
                "side": side.lower(),
                "type": "market",
                "time_in_force": "day",
            },
        )
        return {"filled": int(order.get("filled_qty", 0)), "price": float(order.get("filled_avg_price", 0.0)),
                "side": side, "time": time, "order_id": order.get("id"), "status": order.get("status")}
