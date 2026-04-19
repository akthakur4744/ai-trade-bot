"""Bollinger Bands indicator."""

from __future__ import annotations

import pandas as pd


def compute_bollinger_bands(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, column: str = "close"
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands (upper, middle, lower).

    Args:
        df: DataFrame with OHLCV data.
        period: SMA period for the middle band.
        std_dev: Number of standard deviations for upper/lower bands.
        column: Price column.

    Returns:
        Tuple of (upper_band, middle_band, lower_band).
    """
    middle = df[column].rolling(window=period).mean()
    std = df[column].rolling(window=period).std()

    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    return upper, middle, lower


def compute_bandwidth(upper: pd.Series, lower: pd.Series, middle: pd.Series) -> pd.Series:
    """Calculate Bollinger Bandwidth — measures squeeze/expansion.

    Low bandwidth = squeeze (volatility contraction, breakout imminent).
    """
    return (upper - lower) / middle


def detect_squeeze(bandwidth: pd.Series, lookback: int = 120, percentile: float = 5.0) -> pd.Series:
    """Detect Bollinger Band squeeze — bandwidth at historic lows.

    Args:
        bandwidth: Bollinger bandwidth series.
        lookback: Rolling window for percentile calculation.
        percentile: Threshold percentile (lower = tighter squeeze).

    Returns:
        Boolean Series — True when bandwidth is at or below the percentile.
    """
    rolling_pct = bandwidth.rolling(window=lookback).quantile(percentile / 100)
    return bandwidth <= rolling_pct


def compute_pct_b(df: pd.DataFrame, upper: pd.Series, lower: pd.Series) -> pd.Series:
    """%B indicator — where price sits within the bands (0=lower, 1=upper)."""
    return (df["close"] - lower) / (upper - lower)
