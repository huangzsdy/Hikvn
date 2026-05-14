"""
Moving Average Cross Strategy
Fast SMA(N) crosses above Slow SMA(M) -> +1 (buy)
Fast SMA(N) crosses below Slow SMA(M) -> -1 (sell)
Otherwise -> 0 (hold)
"""

from typing import Optional

import pandas as pd
import numpy as np

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

from .base_strategy import BaseStrategy


class MACrossStrategy(BaseStrategy):
    """Moving Average Cross Strategy."""

    def _init_params(self):
        """Initialize parameters."""
        self.fast_period: int = self.params.get("fast_period", 5)
        self.slow_period: int = self.params.get("slow_period", 20)

    def get_signal(self, kdata: pd.DataFrame) -> int:
        """
        Calculate MA cross signal.

        Args:
            kdata: DataFrame with 'close' column

        Returns:
            +1 (buy), -1 (sell), 0 (hold)
        """
        if len(kdata) < self.slow_period:
            return 0

        close = kdata["close"].values

        # Use TA-Lib if available
        if TALIB_AVAILABLE:
            fast_ma = talib.SMA(close, timeperiod=self.fast_period)
            slow_ma = talib.SMA(close, timeperiod=self.slow_period)
        else:
            # Fallback to pandas rolling (not recommended for production)
            fast_ma = pd.Series(close).rolling(self.fast_period).mean().values
            slow_ma = pd.Series(close).rolling(self.slow_period).mean().values

        # Need at least slow_period data to calculate MA
        if np.isnan(fast_ma[-1]) or np.isnan(slow_ma[-1]):
            return 0
        if np.isnan(fast_ma[-2]) or np.isnan(slow_ma[-2]):
            return 0

        # Cross detection
        current_cross = fast_ma[-1] - slow_ma[-1]
        prev_cross = fast_ma[-2] - slow_ma[-2]

        if prev_cross <= 0 and current_cross > 0:
            # Golden cross -> buy
            return 1
        elif prev_cross >= 0 and current_cross < 0:
            # Death cross -> sell
            return -1

        return 0


# 注册策略
from .factory import register_strategy
register_strategy("ma_cross", MACrossStrategy)