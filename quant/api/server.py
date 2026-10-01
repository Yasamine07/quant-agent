"""FastAPI 后端：看板数据接口 + 回测接口 + Agent 启停控制。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from ..agent import LiveAgent
from ..backtest import run_backtest
from ..config import PROJECT_ROOT, load_config
from ..data.feed import DataUnavailable, get_feed
from ..storage import Storage
from ..strategy.base import get_strategy

WEB_DIR = PROJECT_ROOT / "web"


def create_app(cfg: dict[str, Any] | None = None) -> FastAPI:
    cfg = cfg or load_config()
    storage = Storage(cfg.get("db", "quant.db"))
    agent = LiveAgent(cfg, storage)

    app = FastAPI(title="量化智能体", version="0.1.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    @app.get("/")
    def dashboard() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/state")
    def get_state() -> dict:
        return agent.state()

    @app.get("/api/equity")
    def get_equity(limit: int = Query(1000, ge=1, le=10000)) -> dict:
        return {"curve": storage.equity_curve(limit)}

    @app.get("/api/trades")
    def get_trades(limit: int = Query(200, ge=1, le=1000)) -> dict:
        return {"trades": storage.trades(limit)}

    @app.get("/api/strategies")
    def list_strategies() -> dict:
        return {"strategies": ["ma_cross", "rsi"], "symbols": cfg["agent"]["symbols"]}

    @app.post("/api/agent/start")
    def agent_start() -> dict:
        agent.start()
        return {"ok": True, "running": agent.is_running()}

    @app.post("/api/agent/stop")
    def agent_stop() -> dict:
        agent.stop()
        return {"ok": True, "running": agent.is_running()}

    @app.get("/api/backtest")
    def backtest(
        symbol: str = Query("AAPL"),
        strategy: str = Query("ma_cross"),
        days: int = Query(500, ge=60, le=1500),
        initial_cash: float = Query(10000.0, ge=100.0),
        stop_loss: float | None = Query(0.08, ge=0.0, le=0.5),
    ) -> dict:
        feed = get_feed(cfg["data"]["feed"])
        try:
            bars = feed.get_bars(symbol, days=days)
        except DataUnavailable as e:
            raise HTTPException(status_code=502, detail=str(e))
        strat = get_strategy(strategy, cfg["strategy"].get("params") or {})
        result = run_backtest(
            bars,
            strat,
            initial_cash=initial_cash,
            commission=float(cfg["portfolio"]["commission"]),
            stop_loss_pct=stop_loss,
            max_position_pct=float(cfg["risk"]["max_position_pct"]),
        )
        curve = result.equity_curve.reset_index()
        return {
            "symbol": symbol,
            "strategy": strategy,
            "metrics": result.metrics,
            "curve": {
                "dates": [d.strftime("%Y-%m-%d") for d in curve["date"]],
                "equity": [round(float(x), 2) for x in curve["equity"]],
                "buyhold": [round(float(x), 2) for x in curve["buyhold"]],
                "signals": [s for s in curve["signal"]],
                "ohlc": [
                    [d.strftime("%Y-%m-%d"), round(float(o), 2), round(float(c), 2),
                     round(float(low), 2), round(float(h), 2)]
                    for d, o, c, low, h in zip(curve["date"], curve["open"], curve["close"], curve["low"], curve["high"])
                ],
            },
            "trades": [
                {"time": t.time, "side": t.side, "qty": t.qty, "price": t.price, "pnl": t.pnl, "reason": t.reason}
                for t in result.trades
            ],
        }

    return app


app = create_app()
