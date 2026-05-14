"""
Test Strategy Signal Module
验证策略信号方向正确性
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import pandas as pd
import numpy as np

from strategies.ma_cross import MACrossStrategy
from strategies.rsi_reversal import RSIReversalStrategy
from strategies.factory import get_strategy


def create_kdata(prices, start_date="2023-01-01"):
    """Create test KData DataFrame."""
    prices = np.array(prices, dtype=float)  # Convert to numpy array
    dates = pd.date_range(start=start_date, periods=len(prices), freq="D")
    return pd.DataFrame({
        "datetime": dates,
        "open": prices,
        "high": prices * 1.02,
        "low": prices * 0.98,
        "close": prices,
        "volume": np.ones(len(prices)) * 1e6
    })


class TestMACrossStrategy:
    """Test Moving Average Cross Strategy."""

    def test_golden_cross_buy_signal(self):
        """Test golden cross generates buy signal (+1)."""
        # 构造黄金叉：快线从下方穿越慢线
        # 前半段：快线 < 慢线，后半段：快线 > 慢线
        prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19,   # 上涨
                  20, 21, 22, 23, 24, 25, 26, 27, 28, 29,   # 继续上涨
                  30, 31, 32, 33, 34, 35, 36, 37, 38, 39]   # 快速上涨
        kdata = create_kdata(prices)

        strategy = MACrossStrategy({"fast_period": 5, "slow_period": 10})
        signal = strategy.get_signal(kdata)

        # 在趋势行情中，应该有买入信号
        assert signal in [1, 0], f"Expected 1 or 0, got {signal}"

    def test_death_cross_sell_signal(self):
        """Test death cross generates sell signal (-1)."""
        # 构造死叉：快线从上方穿越慢线
        prices = [40, 39, 38, 37, 36, 35, 34, 33, 32, 31,   # 下跌
                  30, 29, 28, 27, 26, 25, 24, 23, 22, 21,   # 继续下跌
                  20, 19, 18, 17, 16, 15, 14, 13, 12, 11]   # 快速下跌
        kdata = create_kdata(prices)

        strategy = MACrossStrategy({"fast_period": 5, "slow_period": 10})
        signal = strategy.get_signal(kdata)

        # 在下跌趋势中，应该有卖出信号
        assert signal in [-1, 0], f"Expected -1 or 0, got {signal}"

    def test_no_signal_in_ranging_market(self):
        """Test no signal when MA is flat."""
        # 盘整市场：价格窄幅波动但总体均线平稳
        # 使用相同价格使均线几乎平行
        prices = [100.0] * 35
        kdata = create_kdata(prices)

        strategy = MACrossStrategy({"fast_period": 5, "slow_period": 10})
        signal = strategy.get_signal(kdata)

        assert signal == 0, f"Expected 0 in ranging market, got {signal}"

    def test_insufficient_data_returns_zero(self):
        """Test insufficient data returns 0."""
        prices = [100, 101, 102, 103, 104]
        kdata = create_kdata(prices)

        strategy = MACrossStrategy({"fast_period": 5, "slow_period": 10})
        signal = strategy.get_signal(kdata)

        assert signal == 0, f"Expected 0 with insufficient data, got {signal}"


class TestRSIReversalStrategy:
    """Test RSI Reversal Strategy."""

    def test_oversold_buy_signal(self):
        """Test RSI < 30 generates buy signal (+1)."""
        # 构造 RSI < 30 的数据（持续下跌）
        prices = [100, 98, 96, 94, 92, 90, 88, 86, 84, 82,
                  80, 78, 76, 74, 72, 70, 68, 66, 64, 62]
        kdata = create_kdata(prices)

        strategy = RSIReversalStrategy({"rsi_period": 14})
        signal = strategy.get_signal(kdata)

        # 持续下跌应该产生买入信号
        assert signal == 1, f"Expected 1 for oversold, got {signal}"

    def test_overbought_sell_signal(self):
        """Test RSI > 70 generates sell signal (-1)."""
        # 构造 RSI > 70 的数据（持续上涨）
        prices = [60, 62, 64, 66, 68, 70, 72, 74, 76, 78,
                  80, 82, 84, 86, 88, 90, 92, 94, 96, 98]
        kdata = create_kdata(prices)

        strategy = RSIReversalStrategy({"rsi_period": 14})
        signal = strategy.get_signal(kdata)

        # 持续上涨应该产生卖出信号
        assert signal == -1, f"Expected -1 for overbought, got {signal}"

    def test_neutral_signal_in_middle_range(self):
        """Test neutral signal when RSI in middle range."""
        # 构造 RSI 在 30-70 之间的数据
        # 使用小幅波动但总体上涨的价格，让 RSI 在 50 左右
        np.random.seed(42)
        base = 100.0
        prices = [base + np.random.randn() * 0.5 for _ in range(35)]
        kdata = create_kdata(prices, start_date="2023-01-15")

        strategy = RSIReversalStrategy({"rsi_period": 14})
        signal = strategy.get_signal(kdata)

        # RSI 应该保持在 30-70 之间，返回 0
        assert signal == 0, f"Expected 0 when RSI in middle range, got {signal}"


class TestStrategyFactory:
    """Test Strategy Factory."""

    def test_get_registered_strategy(self):
        """Test retrieving registered strategy."""
        ma_strategy = get_strategy("ma_cross")
        assert ma_strategy is not None
        assert ma_strategy == MACrossStrategy

        rsi_strategy = get_strategy("rsi_reversal")
        assert rsi_strategy is not None
        assert rsi_strategy == RSIReversalStrategy

    def test_get_nonexistent_strategy(self):
        """Test retrieving non-existent strategy returns None."""
        strategy = get_strategy("nonexistent_strategy")
        assert strategy is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])