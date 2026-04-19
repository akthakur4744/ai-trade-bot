"""VWAP Reversion strategy (Intraday).

Entry: Price deviates > 2 ATR from VWAP → trade back towards VWAP
Exit:  Price returns to VWAP or crosses through it

VWAP is the institutional benchmark for intraday fair value.
Large deviations tend to revert, especially in liquid large-caps.
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from src.indicators.atr import compute_atr
from src.indicators.volume import compute_volume_ratio
from src.indicators.vwap import compute_vwap_deviation, compute_vwap_sessions
from src.models import (
    ConfidenceBreakdown,
    Direction,
    ExitReason,
    ExitSignal,
    Position,
    StrategySignal,
)
from src.strategies.base import Strategy


class VWAPReversionStrategy(Strategy):
    @property
    def name(self) -> str:
        return "vwap_reversion"

    def scan(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[StrategySignal]:
        df = self._get_df(data, "5minute", "15minute")
        if df is None or len(df) < 30:
            return None

        deviation_threshold = config.get("deviation_atr_threshold", 2.0)
        volume_threshold = config.get("volume_threshold", 1.0)
        atr_stop_mult = config.get("atr_stop_multiplier", 1.5)

        vwap = compute_vwap_sessions(df)
        atr = compute_atr(df)
        deviation = compute_vwap_deviation(df, vwap, atr)
        vol_ratio = compute_volume_ratio(df)

        current_price = df["close"].iloc[-1]
        current_vwap = vwap.iloc[-1]
        current_dev = deviation.iloc[-1]
        current_atr = atr.iloc[-1]
        current_vol = vol_ratio.iloc[-1]

        if pd.isna(current_dev) or pd.isna(current_atr) or pd.isna(current_vwap):
            return None

        direction = None
        signal_strength = 0.0

        # Price far above VWAP → expect reversion down → SELL
        if current_dev > deviation_threshold and current_vol >= volume_threshold:
            direction = Direction.SELL
            signal_strength = min(1.0, current_dev / 4)

        # Price far below VWAP → expect reversion up → BUY
        elif current_dev < -deviation_threshold and current_vol >= volume_threshold:
            direction = Direction.BUY
            signal_strength = min(1.0, abs(current_dev) / 4)

        if direction is None:
            return None

        # Target is VWAP, stop is further from VWAP
        if direction == Direction.BUY:
            stop_loss = current_price - (current_atr * atr_stop_mult)
            target = current_vwap  # Revert to VWAP
        else:
            stop_loss = current_price + (current_atr * atr_stop_mult)
            target = current_vwap

        return StrategySignal(
            symbol=symbol,
            direction=direction,
            strategy_name=self.name,
            entry_price=round(current_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            time_horizon="intraday",
            confidence_inputs=ConfidenceBreakdown(
                signal_alignment=signal_strength,
                market_confirmation=min(1.0, current_vol / 2),
                liquidity_score=min(1.0, current_vol / 1.5),
            ),
            metadata={
                "vwap": round(current_vwap, 2),
                "deviation_atr": round(current_dev, 2),
                "volume_ratio": round(current_vol, 2),
            },
        )

    def check_exit(
        self,
        position: Position,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[ExitSignal]:
        df = self._get_df(data, "5minute", "15minute")
        if df is None or len(df) < 10:
            return None

        vwap = compute_vwap_sessions(df)
        current_price = df["close"].iloc[-1]
        current_vwap = vwap.iloc[-1]

        if pd.isna(current_vwap):
            return None

        # Exit when price touches/crosses VWAP
        if position.direction == Direction.BUY and current_price >= current_vwap:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.TARGET,
                urgency="MEDIUM",
                message=f"Price {current_price:.2f} reverted to VWAP {current_vwap:.2f}",
            )
        elif position.direction == Direction.SELL and current_price <= current_vwap:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.TARGET,
                urgency="MEDIUM",
                message=f"Price {current_price:.2f} reverted to VWAP {current_vwap:.2f}",
            )

        return None
