"""Abstract base class for all trading strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import pandas as pd

from src.models import ExitSignal, Position, StrategySignal


class Strategy(ABC):
    """Base class that all strategies must extend.

    Each strategy is responsible for:
    1. scan() — Analyze market data and return a signal if conditions are met
    2. check_exit() — Check if an existing position should be closed
    3. name — Unique identifier for the strategy
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy name used in logging and DB."""

    @abstractmethod
    def scan(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[StrategySignal]:
        """Scan market data for entry signals.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE").
            data: Dict of interval -> DataFrame. Keys like "5minute", "15minute", "day".
                  Each DataFrame has columns: open, high, low, close, volume.
            config: Strategy-specific config parameters.

        Returns:
            StrategySignal if entry conditions are met, None otherwise.
        """

    @abstractmethod
    def check_exit(
        self,
        position: Position,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[ExitSignal]:
        """Check if an open position should be closed based on strategy logic.

        This is separate from the auto-exit monitor (stop-loss, time-based, etc.)
        and handles strategy-specific exit conditions.

        Args:
            position: The open position to evaluate.
            data: Dict of interval -> DataFrame with current market data.
            config: Strategy-specific config parameters.

        Returns:
            ExitSignal if exit conditions met, None otherwise.
        """

    def validate_data(self, data: Dict[str, pd.DataFrame], min_bars: int = 50) -> bool:
        """Check that data has enough bars for indicator calculation."""
        for interval, df in data.items():
            if df is None or len(df) < min_bars:
                return False
        return True

    @staticmethod
    def _get_df(data: Dict[str, pd.DataFrame], *keys: str) -> Optional[pd.DataFrame]:
        """Get the first available DataFrame from data dict by key priority.

        Avoids `data.get(k1) or data.get(k2)` which fails on DataFrames.
        """
        for key in keys:
            df = data.get(key)
            if df is not None:
                return df
        return None
