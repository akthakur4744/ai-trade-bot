"""Moving average indicators — EMA, SMA."""

from __future__ import annotations

import pandas as pd


def compute_ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Calculate Exponential Moving Average.

    Args:
        df: DataFrame with OHLCV data.
        period: EMA period.
        column: Price column to use.

    Returns:
        Series of EMA values.
    """
    return df[column].ewm(span=period, adjust=False).mean()


def compute_sma(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Calculate Simple Moving Average."""
    return df[column].rolling(window=period).mean()


def detect_crossover(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """Detect crossover events between two moving averages.

    Returns:
        Series with values: 1 (golden cross / bullish), -1 (death cross / bearish), 0 (none).
    """
    prev_fast = fast.shift(1)
    prev_slow = slow.shift(1)

    golden = (prev_fast <= prev_slow) & (fast > slow)
    death = (prev_fast >= prev_slow) & (fast < slow)

    result = pd.Series(0, index=fast.index)
    result[golden] = 1
    result[death] = -1
    return result


def compute_ema_alignment(df: pd.DataFrame, short: int = 20, medium: int = 50, long: int = 200) -> pd.Series:
    """Check if EMAs are in bullish/bearish alignment.

    Returns:
        Series: 1 (bullish: short > medium > long), -1 (bearish: short < medium < long), 0 (mixed).
    """
    ema_s = compute_ema(df, short)
    ema_m = compute_ema(df, medium)
    ema_l = compute_ema(df, long)

    bullish = (ema_s > ema_m) & (ema_m > ema_l)
    bearish = (ema_s < ema_m) & (ema_m < ema_l)

    result = pd.Series(0, index=df.index)
    result[bullish] = 1
    result[bearish] = -1
    return result
