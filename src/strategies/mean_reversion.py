"""Mean Reversion strategy using RSI.

Entry: RSI < oversold (30) with volume confirmation → BUY
       RSI > overbought (70) with volume confirmation → SELL
Exit:  RSI crosses back to neutral zone (40-60)

Historical stats: 79.4% win rate, 0.77 avg gain per trade.
Best in range-bound markets; dangerous in strong trends.
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from src.indicators.atr import compute_atr
from src.indicators.rsi import compute_rsi, detect_rsi_divergence
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


class MeanReversionStrategy(Strategy):
    @property
    def name(self) -> str:
        return "mean_reversion"

    def scan(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[StrategySignal]:
        df = self._get_df(data, "15minute", "5minute")
        if df is None or len(df) < 50:
            return None

        rsi_period = config.get("rsi_period", 14)
        oversold = config.get("oversold", 30)
        overbought = config.get("overbought", 70)
        volume_threshold = config.get("volume_threshold", 1.2)
        atr_stop_mult = config.get("atr_stop_multiplier", 2.0)
        atr_target_mult = config.get("atr_target_multiplier", 3.0)

        rsi = compute_rsi(df, period=rsi_period)
        atr = compute_atr(df)
        vol_ratio = compute_volume_ratio(df)
        divergence = detect_rsi_divergence(df, rsi)

        current_rsi = rsi.iloc[-1]
        current_price = df["close"].iloc[-1]
        current_atr = atr.iloc[-1]
        current_vol = vol_ratio.iloc[-1]
        current_div = divergence.iloc[-1]

        if pd.isna(current_rsi) or pd.isna(current_atr):
            return None

        direction = None
        signal_strength = 0.0

        # Oversold → BUY
        if current_rsi < oversold and current_vol >= volume_threshold:
            direction = Direction.BUY
            # Stronger signal when RSI is deeper oversold
            signal_strength = min(1.0, (oversold - current_rsi) / oversold)
            # Bullish divergence adds confirmation
            if current_div == 1:
                signal_strength = min(1.0, signal_strength + 0.2)

        # Overbought → SELL
        elif current_rsi > overbought and current_vol >= volume_threshold:
            direction = Direction.SELL
            signal_strength = min(1.0, (current_rsi - overbought) / (100 - overbought))
            if current_div == -1:
                signal_strength = min(1.0, signal_strength + 0.2)

        if direction is None:
            return None

        # Calculate stop and target using ATR
        if direction == Direction.BUY:
            stop_loss = current_price - (current_atr * atr_stop_mult)
            target = current_price + (current_atr * atr_target_mult)
        else:
            stop_loss = current_price + (current_atr * atr_stop_mult)
            target = current_price - (current_atr * atr_target_mult)

        return StrategySignal(
            symbol=symbol,
            direction=direction,
            strategy_name=self.name,
            entry_price=round(current_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            confidence_inputs=ConfidenceBreakdown(
                signal_alignment=signal_strength,
                market_confirmation=min(1.0, current_vol / 2),
            ),
            metadata={
                "rsi": round(current_rsi, 2),
                "volume_ratio": round(current_vol, 2),
                "divergence": int(current_div),
                "atr": round(current_atr, 2),
            },
        )

    def check_exit(
        self,
        position: Position,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[ExitSignal]:
        df = self._get_df(data, "15minute", "5minute")
        if df is None or len(df) < 20:
            return None

        rsi = compute_rsi(df, period=config.get("rsi_period", 14))
        current_rsi = rsi.iloc[-1]
        if pd.isna(current_rsi):
            return None

        exit_lower = config.get("exit_rsi_lower", 40)
        exit_upper = config.get("exit_rsi_upper", 60)

        # Exit when RSI returns to neutral zone
        if position.direction == Direction.BUY and current_rsi >= exit_upper:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.TARGET,
                urgency="MEDIUM",
                message=f"RSI reverted to {current_rsi:.0f} (exit zone >= {exit_upper})",
            )
        elif position.direction == Direction.SELL and current_rsi <= exit_lower:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.TARGET,
                urgency="MEDIUM",
                message=f"RSI reverted to {current_rsi:.0f} (exit zone <= {exit_lower})",
            )

        return None
