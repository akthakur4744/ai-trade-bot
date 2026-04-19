"""Seasonal / Calendar strategy.

Entry: Based on known calendar patterns — month-of-year effects,
       day-of-week effects, pre-holiday rallies, expiry effects
Exit:  End of the seasonal window or technical invalidation

0.6% per trade, ~7% annualized. Low conviction but consistent.
Best used as a tiebreaker or confirmation layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

import pandas as pd

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

# Indian market calendar effects (empirically observed)
# Positive months: Nov, Dec, Jan (festival season + year-end flows)
# Negative months: May, Jun (monsoon uncertainty)
# Day effects: Monday tends negative, Friday tends positive (Nifty)
BULLISH_MONTHS = {11, 12, 1, 3}
BEARISH_MONTHS = {5, 6, 9}
BULLISH_WEEKDAYS = {4}  # Friday = 4
BEARISH_WEEKDAYS = {0}  # Monday = 0


class SeasonalStrategy(Strategy):
    @property
    def name(self) -> str:
        return "seasonal"

    def scan(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[StrategySignal]:
        df = data.get("day")
        if df is None or len(df) < 30:
            return None

        now = datetime.now()
        month = now.month
        weekday = now.weekday()

        # Score seasonal bias
        seasonal_score = 0.0
        if month in BULLISH_MONTHS:
            seasonal_score += 0.4
        elif month in BEARISH_MONTHS:
            seasonal_score -= 0.4

        if weekday in BULLISH_WEEKDAYS:
            seasonal_score += 0.2
        elif weekday in BEARISH_WEEKDAYS:
            seasonal_score -= 0.2

        # Check for pre-expiry effect (last Thursday of month = NSE expiry)
        days_to_month_end = (pd.Timestamp(now).days_in_month - now.day)
        if days_to_month_end <= 3 and weekday <= 3:
            seasonal_score += 0.15  # Pre-expiry bullish bias

        min_score = config.get("min_seasonal_score", 0.3)
        if abs(seasonal_score) < min_score:
            return None

        direction = Direction.BUY if seasonal_score > 0 else Direction.SELL
        current_price = df["close"].iloc[-1]
        atr = compute_atr(df)
        current_atr = atr.iloc[-1]

        if pd.isna(current_atr):
            return None

        atr_stop_mult = config.get("atr_stop_multiplier", 2.0)

        if direction == Direction.BUY:
            stop_loss = current_price - (current_atr * atr_stop_mult)
            target = current_price + (current_atr * 2)
        else:
            stop_loss = current_price + (current_atr * atr_stop_mult)
            target = current_price - (current_atr * 2)

        return StrategySignal(
            symbol=symbol,
            direction=direction,
            strategy_name=self.name,
            entry_price=round(current_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            time_horizon="intraday",
            confidence_inputs=ConfidenceBreakdown(
                signal_alignment=min(1.0, abs(seasonal_score)),
            ),
            metadata={
                "month": month,
                "weekday": weekday,
                "seasonal_score": round(seasonal_score, 3),
            },
        )

    def check_exit(
        self,
        position: Position,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[ExitSignal]:
        # Seasonal strategy has no strategy-specific exit;
        # relies on auto-exit monitor (time-based, stop-loss, target)
        return None
