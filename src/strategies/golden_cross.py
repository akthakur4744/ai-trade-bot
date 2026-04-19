"""Golden Cross / Death Cross strategy using EMA 50/200.

Entry: EMA 50 crosses above EMA 200 → BUY (Golden Cross)
       EMA 50 crosses below EMA 200 → SELL (Death Cross)
Exit:  Reverse crossover or price breaks below short EMA

Low win rate (~30%) but high gain/loss ratio (4.14x).
Must tolerate frequent small losses for large trend captures.
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from src.indicators.atr import compute_atr
from src.indicators.moving_averages import compute_ema, detect_crossover
from src.indicators.volume import compute_volume_ratio
from src.models import (
    ConfidenceBreakdown,
    Direction,
    ExitReason,
    ExitSignal,
    Position,
    StrategySignal,
)
from src.strategies.base import Strategy


class GoldenCrossStrategy(Strategy):
    @property
    def name(self) -> str:
        return "golden_cross"

    def scan(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[StrategySignal]:
        # Use daily data for cross detection, intraday for timing
        df_daily = data.get("day")
        if df_daily is None or len(df_daily) < 210:
            return None

        fast_period = config.get("fast_period", 50)
        slow_period = config.get("slow_period", 200)
        volume_threshold = config.get("volume_threshold", 1.3)
        atr_stop_mult = config.get("atr_stop_multiplier", 2.5)

        ema_fast = compute_ema(df_daily, fast_period)
        ema_slow = compute_ema(df_daily, slow_period)
        crossover = detect_crossover(ema_fast, ema_slow)
        atr = compute_atr(df_daily)
        vol_ratio = compute_volume_ratio(df_daily)

        current_cross = crossover.iloc[-1]
        current_price = df_daily["close"].iloc[-1]
        current_atr = atr.iloc[-1]
        current_vol = vol_ratio.iloc[-1]

        if pd.isna(current_atr) or current_cross == 0:
            return None

        # Require above-average volume for confirmation
        if current_vol < volume_threshold:
            return None

        direction = Direction.BUY if current_cross == 1 else Direction.SELL

        # Calculate trend strength — distance between EMAs as % of price
        ema_spread = abs(ema_fast.iloc[-1] - ema_slow.iloc[-1]) / current_price
        trend_strength = min(1.0, ema_spread * 50)  # Normalize

        if direction == Direction.BUY:
            stop_loss = current_price - (current_atr * atr_stop_mult)
            # Trend-following: no fixed target, let it run
            target = current_price + (current_atr * 5)
        else:
            stop_loss = current_price + (current_atr * atr_stop_mult)
            target = current_price - (current_atr * 5)

        return StrategySignal(
            symbol=symbol,
            direction=direction,
            strategy_name=self.name,
            entry_price=round(current_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            time_horizon="swing",
            confidence_inputs=ConfidenceBreakdown(
                signal_alignment=trend_strength,
                market_confirmation=min(1.0, current_vol / 2),
            ),
            metadata={
                "crossover": int(current_cross),
                "ema_fast": round(ema_fast.iloc[-1], 2),
                "ema_slow": round(ema_slow.iloc[-1], 2),
                "ema_spread_pct": round(ema_spread * 100, 3),
                "volume_ratio": round(current_vol, 2),
            },
        )

    def check_exit(
        self,
        position: Position,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[ExitSignal]:
        df_daily = data.get("day")
        if df_daily is None or len(df_daily) < 55:
            return None

        fast_period = config.get("fast_period", 50)
        slow_period = config.get("slow_period", 200)

        ema_fast = compute_ema(df_daily, fast_period)
        ema_slow = compute_ema(df_daily, slow_period)
        crossover = detect_crossover(ema_fast, ema_slow)

        current_cross = crossover.iloc[-1]
        current_price = df_daily["close"].iloc[-1]

        # Exit on reverse crossover
        if position.direction == Direction.BUY and current_cross == -1:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.STRUCTURE_BREAK,
                urgency="HIGH",
                message="Death cross detected — EMA 50 crossed below EMA 200",
            )
        elif position.direction == Direction.SELL and current_cross == 1:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.STRUCTURE_BREAK,
                urgency="HIGH",
                message="Golden cross detected — EMA 50 crossed above EMA 200",
            )

        # Also exit if price breaks below fast EMA (for longs)
        if position.direction == Direction.BUY and current_price < ema_fast.iloc[-1] * 0.98:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.STRUCTURE_BREAK,
                urgency="MEDIUM",
                message=f"Price {current_price:.2f} broke below EMA {fast_period}: {ema_fast.iloc[-1]:.2f}",
            )

        return None
