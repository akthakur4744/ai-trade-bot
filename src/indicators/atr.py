"""Average True Range (ATR) indicator — measures volatility."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range.

    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR = EMA of True Range over `period`.

    Used for:
    - Position sizing (risk per share)
    - Stop-loss placement
    - Volatility-based filtering
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(span=period, adjust=False).mean()


def compute_atr_percent(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR as a percentage of close price — normalizes across price levels."""
    atr = compute_atr(df, period)
    return (atr / df["close"]) * 100
