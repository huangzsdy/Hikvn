# Base Strategy Class
# All strategies must inherit from this class

from abc import ABC, abstractmethod
from typing import Optional


class BaseStrategy(ABC):
    """Base class for all trading strategies."""

    def __init__(self, params: dict = None):
        """
        Initialize the strategy.

        Args:
            params: Strategy parameters dict
        """
        self.params = params or {}
        self._init_params()

    @abstractmethod
    def _init_params(self):
        """Initialize strategy parameters from self.params dict."""
        pass

    @abstractmethod
    def get_signal(self, kdata) -> int:
        """
        Generate trading signal.

        Args:
            kdata: K-line data (pandas DataFrame with datetime, open, high, low, close, volume)

        Returns:
            int: +1 (buy), -1 (sell), 0 (hold)
        """
        pass

    def on_bar(self, kdata):
        """Called when new bar data arrives."""
        pass

    def on_trade(self, trade):
        """Called when a trade is executed."""
        pass
