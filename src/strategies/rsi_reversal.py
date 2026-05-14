"""
RSI Reversal Strategy
RSI(14) < 30 -> +1 (buy, oversold)
RSI(14) > 70 -> -1 (sell, overbought)
Otherwise -> 0 (hold)
"""

import pandas as pd
import numpy as np

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

from .base_strategy import BaseStrategy


class RSIReversalStrategy(BaseStrategy):
    """RSI Reversal Strategy."""

    def _init_params(self):
        """Initialize parameters."""
        self.rsi_period: int = self.params.get("rsi_period", 14)
        self.oversold_threshold: int = self.params.get("oversold_threshold", 30)
        self.overbought_threshold: int = self.params.get("overbought_threshold", 70)

    def get_signal(self, kdata: pd.DataFrame) -> int:
        """
        Calculate RSI signal.

        Args:
            kdata: DataFrame with 'close' column

        Returns:
            +1 (buy), -1 (sell), 0 (hold)
        """
        if len(kdata) < self.rsi_period + 1:
            return 0

        close = kdata["close"].values

        # Use TA-Lib if available
        if TALIB_AVAILABLE:
            rsi = talib.RSI(close, timeperiod=self.rsi_period)
        else:
            # Fallback to manual RSI calculation
            rsi = self._manual_rsi(close, self.rsi_period)

        current_rsi = rsi[-1]
        if np.isnan(current_rsi):
            return 0

        if current_rsi < self.oversold_threshold:
            return 1  # Oversold -> buy
        elif current_rsi > self.overbought_threshold:
            return -1  # Overbought -> sell

        return 0

    def _manual_rsi(self, close: np.ndarray, period: int) -> np.ndarray:
        """Manual RSI calculation (fallback when TA-Lib not available)."""
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.zeros(len(close))
        avg_loss = np.zeros(len(close))

        # First average
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])

        # Subsequent averages
        for i in range(period + 1, len(close)):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period

        rs = np.zeros(len(close))
        rs[period:] = avg_gain[period:] / (avg_loss[period:] + 1e-10)
        rsi = np.zeros(len(close))
        rsi[period:] = 100 - (100 / (1 + rs[period:]))

        return rsi


# 注册策略
from .factory import register_strategy
register_strategy("rsi_reversal", RSIReversalStrategy)