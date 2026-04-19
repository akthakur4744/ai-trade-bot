"""Stochastic Oscillator — momentum reversal timing."""

from __future__ import annotations

import pandas as pd


def compute_stochastic(
    df: pd.DataFrame, k_period: int = 14, d_period: int = 3
) -> tuple[pd.Series, pd.Series]:
    """Calculate Stochastic %K and %D.

    %K = (close - lowest_low) / (highest_high - lowest_low) * 100
    %D = SMA of %K

    Args:
        df: DataFrame with OHLCV data.
        k_period: Lookback period for %K.
        d_period: Smoothing period for %D.

    Returns:
        Tuple of (%K, %D).
    """
    lowest_low = df["low"].rolling(window=k_period).min()
    highest_high = df["high"].rolling(window=k_period).max()

    denominator = highest_high - lowest_low
    k = 100 * (df["close"] - lowest_low) / denominator.replace(0, float("nan"))
    d = k.rolling(window=d_period).mean()

    return k, d
