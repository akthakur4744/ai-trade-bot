"""Pairs Trading / Statistical Arbitrage strategy.

Find cointegrated pairs → trade the spread when it deviates from mean.
Entry: Z-score of spread > 2 (or < -2) → short the outperformer, long the underperformer
Exit:  Z-score reverts to 0 (or crosses through)

Market-neutral strategy — profits from relative moves, not market direction.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

from src.indicators.atr import compute_atr
from src.models import (
    ConfidenceBreakdown,
    Direction,
    ExitReason,
    ExitSignal,
    Position,
    StrategySignal,
)
from src.strategies.base import Strategy


def test_cointegration(series_a: pd.Series, series_b: pd.Series) -> tuple:
    """Test if two price series are cointegrated.

    Returns:
        Tuple of (is_cointegrated, p_value, hedge_ratio).
    """
    try:
        score, p_value, _ = coint(series_a, series_b)
        # OLS for hedge ratio
        hedge_ratio = np.polyfit(series_b, series_a, 1)[0]
        return p_value < 0.05, p_value, hedge_ratio
    except Exception:
        return False, 1.0, 0.0


def compute_spread_zscore(
    series_a: pd.Series, series_b: pd.Series, hedge_ratio: float, window: int = 20
) -> pd.Series:
    """Compute z-score of the spread between two series."""
    spread = series_a - hedge_ratio * series_b
    mean = spread.rolling(window=window).mean()
    std = spread.rolling(window=window).std()
    return (spread - mean) / std.replace(0, np.nan)


class PairsTradingStrategy(Strategy):
    """Pairs trading requires a paired symbol in config.

    Config must include:
        pair_symbol: The other symbol in the pair
        pair_data: DataFrame for the pair symbol
    """

    @property
    def name(self) -> str:
        return "pairs_trading"

    def scan(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[StrategySignal]:
        df = data.get("day")
        if df is None or len(df) < 60:
            return None

        pair_symbol = config.get("pair_symbol")
        pair_data = config.get("pair_data")
        if pair_symbol is None or pair_data is None:
            return None

        pair_df = pair_data.get("day")
        if pair_df is None or len(pair_df) < 60:
            return None

        # Align the two series
        common_idx = df.index.intersection(pair_df.index)
        if len(common_idx) < 60:
            return None

        series_a = df.loc[common_idx, "close"]
        series_b = pair_df.loc[common_idx, "close"]

        zscore_threshold = config.get("zscore_threshold", 2.0)
        zscore_window = config.get("zscore_window", 20)

        # Test cointegration
        is_coint, p_value, hedge_ratio = test_cointegration(series_a, series_b)
        if not is_coint:
            return None

        # Compute z-score
        zscore = compute_spread_zscore(series_a, series_b, hedge_ratio, zscore_window)
        current_z = zscore.iloc[-1]

        if pd.isna(current_z):
            return None

        direction = None
        if current_z > zscore_threshold:
            # Spread is wide — short A, long B (we signal short A)
            direction = Direction.SELL
        elif current_z < -zscore_threshold:
            # Spread is narrow — long A, short B
            direction = Direction.BUY

        if direction is None:
            return None

        current_price = series_a.iloc[-1]
        atr = compute_atr(df)
        current_atr = atr.iloc[-1]

        if pd.isna(current_atr):
            return None

        signal_strength = min(1.0, abs(current_z) / 4)

        if direction == Direction.BUY:
            stop_loss = current_price - (current_atr * 3)
            target = current_price + (current_atr * 2)
        else:
            stop_loss = current_price + (current_atr * 3)
            target = current_price - (current_atr * 2)

        return StrategySignal(
            symbol=symbol,
            direction=direction,
            strategy_name=self.name,
            entry_price=round(current_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            time_horizon="swing",
            confidence_inputs=ConfidenceBreakdown(
                signal_alignment=signal_strength,
                market_confirmation=1.0 - p_value,
            ),
            metadata={
                "pair_symbol": pair_symbol,
                "zscore": round(current_z, 3),
                "hedge_ratio": round(hedge_ratio, 4),
                "coint_pvalue": round(p_value, 4),
            },
        )

    def check_exit(
        self,
        position: Position,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[ExitSignal]:
        df = data.get("day")
        pair_data = config.get("pair_data")
        if df is None or pair_data is None:
            return None

        pair_df = pair_data.get("day")
        if pair_df is None:
            return None

        common_idx = df.index.intersection(pair_df.index)
        if len(common_idx) < 30:
            return None

        series_a = df.loc[common_idx, "close"]
        series_b = pair_df.loc[common_idx, "close"]

        _, _, hedge_ratio = test_cointegration(series_a, series_b)
        zscore = compute_spread_zscore(series_a, series_b, hedge_ratio)
        current_z = zscore.iloc[-1]

        if pd.isna(current_z):
            return None

        # Exit when z-score reverts near 0
        if abs(current_z) < 0.5:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.TARGET,
                urgency="MEDIUM",
                message=f"Spread z-score reverted to {current_z:.2f}",
            )

        return None
