"""Volume-based indicators — OBV, volume spike detection."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_obv(df: pd.DataFrame) -> pd.Series:
    """Calculate On-Balance Volume (OBV).

    OBV adds volume on up days, subtracts on down days.
    Volume precedes price — OBV divergence signals potential moves.
    """
    direction = np.sign(df["close"].diff())
    direction.iloc[0] = 0
    return (df["volume"] * direction).cumsum()


def detect_volume_spike(
    df: pd.DataFrame, multiplier: float = 2.0, window: int = 20
) -> pd.Series:
    """Detect volume spikes relative to rolling average.

    Args:
        df: DataFrame with 'volume' column.
        multiplier: How many times above average to flag as spike.
        window: Rolling average window.

    Returns:
        Boolean Series — True on volume spike bars.
    """
    avg_volume = df["volume"].rolling(window=window).mean()
    return df["volume"] > (avg_volume * multiplier)


def compute_volume_ratio(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Calculate current volume as a ratio of rolling average.

    Returns:
        Series of volume ratios (1.0 = average, 2.0 = double average).
    """
    avg_volume = df["volume"].rolling(window=window).mean()
    return df["volume"] / avg_volume.replace(0, np.nan)
