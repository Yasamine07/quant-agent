"""指标函数单元测试。"""
import numpy as np
import pandas as pd

from quant.indicators import ema, macd, rsi, sma


def test_sma_known_values():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    assert np.isnan(out.iloc[1])
    assert out.iloc[2] == 2.0
    assert out.iloc[3] == 3.0
    assert out.iloc[4] == 4.0


def test_ema_matches_pandas():
    s = pd.Series(np.arange(1.0, 31.0))
    assert np.allclose(ema(s, 10), s.ewm(span=10, adjust=False).mean())


def test_rsi_increasing_is_max():
    s = pd.Series(np.arange(1.0, 60.0))  # 单调上涨 → RSI≈100
    out = rsi(s, 14)
    assert out.iloc[-1] > 99.0


def test_rsi_decreasing_is_min():
    s = pd.Series(np.arange(60.0, 1.0, -1.0))  # 单调下跌 → RSI≈0
    out = rsi(s, 14)
    assert out.iloc[-1] < 1.0


def test_rsi_bounds():
    rng = np.random.default_rng(0)
    s = pd.Series(rng.normal(0, 1, 500).cumsum() + 100)
    out = rsi(s, 14).dropna()
    assert ((out >= 0) & (out <= 100)).all()


def test_macd_shapes_and_sign():
    s = pd.Series(np.arange(1.0, 101.0))
    line, sig, hist = macd(s, 12, 26, 9)
    assert len(line) == len(s)
    assert np.allclose(hist, line - sig)
    # 单调上涨 → DIF 为正
    assert line.iloc[-1] > 0
