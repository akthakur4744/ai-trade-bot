"""Volume Weighted Average Price (VWAP) indicator — institutional benchmark for intraday."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculate VWAP for intraday data.

    VWAP = cumulative(typical_price * volume) / cumulative(volume)

    Assumes data is for a single trading session. For multi-day data,
    use compute_vwap_sessions() with session reset.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum()
    return cumulative_tp_vol / cumulative_vol.replace(0, np.nan)


def compute_vwap_sessions(df: pd.DataFrame) -> pd.Series:
    """Calculate VWAP with daily session reset for multi-day intraday data.

    Groups by date and computes VWAP within each trading session.
    """
    result = pd.Series(np.nan, index=df.index)

    for date_val, group in df.groupby(df.index.date):
        typical_price = (group["high"] + group["low"] + group["close"]) / 3
        cumulative_tp_vol = (typical_price * group["volume"]).cumsum()
        cumulative_vol = group["volume"].cumsum()
        vwap = cumulative_tp_vol / cumulative_vol.replace(0, np.nan)
        result.loc[group.index] = vwap

    return result


def compute_vwap_deviation(df: pd.DataFrame, vwap: pd.Series, atr: pd.Series) -> pd.Series:
    """Price deviation from VWAP in ATR units.

    Positive = above VWAP, Negative = below VWAP.
    Values > 2 or < -2 suggest mean reversion opportunity.
    """
    return (df["close"] - vwap) / atr.replace(0, np.nan)
