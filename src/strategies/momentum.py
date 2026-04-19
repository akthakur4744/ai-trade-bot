"""Momentum / Trend Following strategy.

Entry: ADX > 25 (strong trend) + EMA alignment (short > medium > long)
       + volume expansion + price above key EMAs
Exit:  ADX drops below 20 or EMA alignment breaks

1-1.5% monthly excess returns in trending markets.
Suffers in choppy/range-bound conditions — requires regime filter.
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from src.indicators.adx import compute_adx
from src.indicators.atr import compute_atr
from src.indicators.moving_averages import compute_ema, compute_ema_alignment
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


class MomentumStrategy(Strategy):
    @property
    def name(self) -> str:
        return "momentum"

    def scan(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[StrategySignal]:
        df = self._get_df(data, "15minute", "day")
        if df is None or len(df) < 210:
            return None

        adx_threshold = config.get("adx_threshold", 25)
        volume_threshold = config.get("volume_threshold", 1.3)
        atr_stop_mult = config.get("atr_stop_multiplier", 2.0)
        ema_short = config.get("ema_short", 20)
        ema_medium = config.get("ema_medium", 50)
        ema_long = config.get("ema_long", 200)

        adx, plus_di, minus_di = compute_adx(df)
        alignment = compute_ema_alignment(df, ema_short, ema_medium, ema_long)
        atr = compute_atr(df)
        vol_ratio = compute_volume_ratio(df)

        current_adx = adx.iloc[-1]
        current_align = alignment.iloc[-1]
        current_plus = plus_di.iloc[-1]
        current_minus = minus_di.iloc[-1]
        current_price = df["close"].iloc[-1]
        current_atr = atr.iloc[-1]
        current_vol = vol_ratio.iloc[-1]

        if pd.isna(current_adx) or pd.isna(current_atr):
            return None

        # Require strong trend
        if current_adx < adx_threshold:
            return None

        # Require EMA alignment
        if current_align == 0:
            return None

        # Require volume confirmation
        if current_vol < volume_threshold:
            return None

        # Direction from EMA alignment and DI
        if current_align == 1 and current_plus > current_minus:
            direction = Direction.BUY
        elif current_align == -1 and current_minus > current_plus:
            direction = Direction.SELL
        else:
            return None

        # Trend strength from ADX level
        trend_strength = min(1.0, (current_adx - adx_threshold) / 25)
        di_spread = abs(current_plus - current_minus) / max(current_plus + current_minus, 1)

        if direction == Direction.BUY:
            stop_loss = current_price - (current_atr * atr_stop_mult)
            target = current_price + (current_atr * 4)
        else:
            stop_loss = current_price + (current_atr * atr_stop_mult)
            target = current_price - (current_atr * 4)

        return StrategySignal(
            symbol=symbol,
            direction=direction,
            strategy_name=self.name,
            entry_price=round(current_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            confidence_inputs=ConfidenceBreakdown(
                signal_alignment=trend_strength,
                market_confirmation=min(1.0, di_spread + current_vol / 3),
            ),
            metadata={
                "adx": round(current_adx, 2),
                "plus_di": round(current_plus, 2),
                "minus_di": round(current_minus, 2),
                "alignment": int(current_align),
                "volume_ratio": round(current_vol, 2),
            },
        )

    def check_exit(
        self,
        position: Position,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[ExitSignal]:
        df = self._get_df(data, "15minute", "day")
        if df is None or len(df) < 30:
            return None

        adx_exit = config.get("adx_exit_threshold", 20)
        ema_short = config.get("ema_short", 20)
        ema_medium = config.get("ema_medium", 50)
        ema_long = config.get("ema_long", 200)

        adx, _, _ = compute_adx(df)
        alignment = compute_ema_alignment(df, ema_short, ema_medium, ema_long)

        current_adx = adx.iloc[-1]
        current_align = alignment.iloc[-1]

        if pd.isna(current_adx):
            return None

        # Exit if trend weakens
        if current_adx < adx_exit:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.STRUCTURE_BREAK,
                urgency="MEDIUM",
                message=f"Trend weakened — ADX dropped to {current_adx:.0f} (threshold: {adx_exit})",
            )

        # Exit if alignment breaks
        expected_align = 1 if position.direction == Direction.BUY else -1
        if current_align != expected_align and current_align != 0:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.STRUCTURE_BREAK,
                urgency="HIGH",
                message=f"EMA alignment reversed to {current_align}",
            )

        return None
