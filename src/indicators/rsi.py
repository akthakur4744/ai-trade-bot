"""Relative Strength Index (RSI) indicator."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    """Calculate RSI using exponential moving average of gains/losses.

    Args:
        df: DataFrame with OHLCV data.
        period: RSI lookback period.
        column: Price column to use.

    Returns:
        Series of RSI values (0-100).
    """
    delta = df[column].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def detect_rsi_divergence(
    df: pd.DataFrame, rsi: pd.Series, lookback: int = 20
) -> pd.Series:
    """Detect bullish/bearish divergence between price and RSI.

    Returns:
        Series with values: 1 (bullish divergence), -1 (bearish divergence), 0 (none).
    """
    price = df["close"]
    result = pd.Series(0, index=df.index)

    for i in range(lookback, len(df)):
        window_price = price.iloc[i - lookback : i + 1]
        window_rsi = rsi.iloc[i - lookback : i + 1]

        # Bullish: price makes lower low, RSI makes higher low
        if window_price.iloc[-1] < window_price.min() * 1.01 and window_rsi.iloc[-1] > window_rsi.min():
            result.iloc[i] = 1
        # Bearish: price makes higher high, RSI makes lower high
        elif window_price.iloc[-1] > window_price.max() * 0.99 and window_rsi.iloc[-1] < window_rsi.max():
            result.iloc[i] = -1

    return result
