"""回测引擎、组合、风控单元测试。"""
import pandas as pd

from quant.backtest import run_backtest
from quant.data.feed import SyntheticFeed
from quant.portfolio import InsufficientFunds, Portfolio
from quant.risk import circuit_breaker, hit_stop_loss, position_qty
from quant.strategy.base import get_strategy
from quant.strategy.examples import MACrossStrategy


def _mk_df(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": 1.0},
        index=pd.bdate_range("2024-01-01", periods=len(closes)),
    )


def test_ma_cross_emits_buy_on_trend_reversal():
    closes = [100.0] * 10 + [100 + i * 1.5 for i in range(1, 11)]
    strat = MACrossStrategy(fast=2, slow=4)
    df = strat.prepare(_mk_df(closes))
    sides = [strat.generate(df.iloc[: i + 1]).side for i in range(len(df))]
    assert "BUY" in sides


def test_backtest_runs_and_metrics_complete():
    feed = SyntheticFeed(seed=7)
    df = feed.get_bars("DEMO", days=300)
    strat = get_strategy("ma_cross")
    res = run_backtest(df, strat, initial_cash=10000.0)
    m = res.metrics
    assert m["final_equity"] > 0
    assert m["total_return"] > -1.0
    assert len(res.equity_curve) == len(df) - 1
    for key in ("annualized_return", "sharpe", "max_drawdown", "win_rate", "num_trades", "buyhold_return"):
        assert key in m


def test_portfolio_buy_sell_pnl():
    p = Portfolio(initial_cash=10000.0, commission=0.001)
    t_buy = p.buy("AAPL", 10, 100.0, "2024-01-01", "测试")
    assert t_buy.side == "BUY" and p.positions["AAPL"].qty == 10
    t_sell = p.sell("AAPL", 10, 120.0, "2024-01-02", "测试")
    expected_pnl = 10 * 120 - 10 * 120 * 0.001 - 10 * 100.0
    assert abs(t_sell.pnl - expected_pnl) < 1e-6
    assert p.cash > 10000.0  # 盈利


def test_portfolio_insufficient_funds():
    p = Portfolio(initial_cash=100.0, commission=0.001)
    try:
        p.buy("AAPL", 10, 100.0, "2024-01-01")
        assert False, "应抛出 InsufficientFunds"
    except InsufficientFunds:
        pass


def test_risk_helpers():
    assert position_qty(10000.0, 100.0, 0.2) == 20
    assert position_qty(10000.0, 0.0, 0.2) == 0
    from quant.portfolio import Position

    pos = Position("AAPL", 10, 100.0)
    assert hit_stop_loss(pos, 91.0, 0.08) is True
    assert hit_stop_loss(pos, 95.0, 0.08) is False
    assert circuit_breaker([100, 110, 90], 0.2) is False  # 回撤 18.2% < 20%
    assert circuit_breaker([100, 110, 80], 0.2) is True   # 回撤 27.3% > 20%
    assert circuit_breaker([100, 110, 105], 0.2) is False
