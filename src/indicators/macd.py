"""MACD (Moving Average Convergence Divergence) indicator."""

from __future__ import annotations

import pandas as pd


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close",
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD line, signal line, and histogram.

    Args:
        df: DataFrame with OHLCV data.
        fast: Fast EMA period.
        slow: Slow EMA period.
        signal: Signal line EMA period.
        column: Price column.

    Returns:
        Tuple of (macd_line, signal_line, histogram).
    """
    ema_fast = df[column].ewm(span=fast, adjust=False).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def detect_macd_crossover(macd_line: pd.Series, signal_line: pd.Series) -> pd.Series:
    """Detect MACD/signal line crossover.

    Returns:
        Series: 1 (bullish crossover), -1 (bearish crossover), 0 (none).
    """
    prev_macd = macd_line.shift(1)
    prev_signal = signal_line.shift(1)

    bullish = (prev_macd <= prev_signal) & (macd_line > signal_line)
    bearish = (prev_macd >= prev_signal) & (macd_line < signal_line)

    result = pd.Series(0, index=macd_line.index)
    result[bullish] = 1
    result[bearish] = -1
    return result
