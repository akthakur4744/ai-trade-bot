"""Average Directional Index (ADX) — measures trend strength."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_adx(df: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate ADX, +DI, and -DI.

    ADX > 25 indicates a strong trend. ADX < 20 indicates range-bound market.

    Args:
        df: DataFrame with OHLCV data.
        period: Smoothing period.

    Returns:
        Tuple of (adx, plus_di, minus_di).
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # Directional movement
    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    # True Range
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Smoothed averages
    atr = true_range.ewm(span=period, adjust=False).mean()
    smooth_plus = plus_dm.ewm(span=period, adjust=False).mean()
    smooth_minus = minus_dm.ewm(span=period, adjust=False).mean()

    # Directional indicators
    plus_di = 100 * smooth_plus / atr.replace(0, np.nan)
    minus_di = 100 * smooth_minus / atr.replace(0, np.nan)

    # ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(span=period, adjust=False).mean()

    return adx, plus_di, minus_di
