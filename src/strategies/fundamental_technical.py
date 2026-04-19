"""Fundamental Value + Technical Trigger strategy.

Selection: Low P/E (below sector avg) + High EPS growth (>15% YoY)
           + Healthy D/E (<1.0) + ROE > 15%
Entry:     Technical trigger — RSI oversold or EMA crossover on selected stocks
Exit:      Technical reversal or fundamental deterioration

Combines "what to buy" (fundamentals) with "when to buy" (technicals).
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from src.indicators.atr import compute_atr
from src.indicators.moving_averages import compute_ema, detect_crossover
from src.indicators.rsi import compute_rsi
from src.models import (
    ConfidenceBreakdown,
    Direction,
    ExitReason,
    ExitSignal,
    Position,
    StrategySignal,
)
from src.strategies.base import Strategy


class FundamentalTechnicalStrategy(Strategy):
    @property
    def name(self) -> str:
        return "fundamental_technical"

    def scan(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[StrategySignal]:
        df = data.get("day")
        if df is None or len(df) < 60:
            return None

        # Fundamental filters — data comes from external fundamental_data module
        fundamentals = config.get("fundamentals", {})
        if not fundamentals:
            return None

        pe_ratio = fundamentals.get("pe_ratio")
        eps_growth = fundamentals.get("eps_growth")
        de_ratio = fundamentals.get("de_ratio")
        roe = fundamentals.get("roe")
        sector_pe = fundamentals.get("sector_pe_avg", 25)

        # Fundamental screen
        max_pe_mult = config.get("max_pe_sector_multiplier", 0.8)
        min_eps_growth = config.get("min_eps_growth", 0.15)
        max_de = config.get("max_de_ratio", 1.0)
        min_roe = config.get("min_roe", 0.15)

        if pe_ratio is None or eps_growth is None:
            return None

        # Check fundamentals pass
        if pe_ratio > sector_pe * max_pe_mult:
            return None
        if eps_growth < min_eps_growth:
            return None
        if de_ratio is not None and de_ratio > max_de:
            return None
        if roe is not None and roe < min_roe:
            return None

        # Fundamental quality score (0-1)
        fund_score = 0.0
        fund_score += min(0.3, (sector_pe - pe_ratio) / sector_pe)  # Value discount
        fund_score += min(0.3, eps_growth / 0.5)  # Growth premium
        if roe is not None:
            fund_score += min(0.2, (roe - min_roe) / 0.3)
        if de_ratio is not None:
            fund_score += min(0.2, (max_de - de_ratio) / max_de)

        # Technical trigger — RSI oversold or bullish EMA crossover
        rsi = compute_rsi(df)
        ema_20 = compute_ema(df, 20)
        ema_50 = compute_ema(df, 50)
        crossover = detect_crossover(ema_20, ema_50)
        atr = compute_atr(df)

        current_rsi = rsi.iloc[-1]
        current_cross = crossover.iloc[-1]
        current_price = df["close"].iloc[-1]
        current_atr = atr.iloc[-1]

        if pd.isna(current_rsi) or pd.isna(current_atr):
            return None

        # Need technical trigger
        tech_trigger = False
        tech_score = 0.0

        if current_rsi < 35:  # Oversold on fundamentally sound stock
            tech_trigger = True
            tech_score = min(1.0, (35 - current_rsi) / 20)
        elif current_cross == 1:  # Bullish crossover
            tech_trigger = True
            tech_score = 0.6

        if not tech_trigger:
            return None

        atr_stop_mult = config.get("atr_stop_multiplier", 2.0)
        stop_loss = current_price - (current_atr * atr_stop_mult)
        target = current_price + (current_atr * 4)

        return StrategySignal(
            symbol=symbol,
            direction=Direction.BUY,  # Fundamental strategy is long-only
            strategy_name=self.name,
            entry_price=round(current_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            time_horizon="swing",
            confidence_inputs=ConfidenceBreakdown(
                signal_alignment=tech_score,
                market_confirmation=fund_score,
            ),
            metadata={
                "pe_ratio": pe_ratio,
                "eps_growth": eps_growth,
                "de_ratio": de_ratio,
                "roe": roe,
                "rsi": round(current_rsi, 2),
                "ema_crossover": int(current_cross),
                "fundamental_score": round(fund_score, 3),
            },
        )

    def check_exit(
        self,
        position: Position,
        data: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[ExitSignal]:
        df = data.get("day")
        if df is None or len(df) < 25:
            return None

        rsi = compute_rsi(df)
        current_rsi = rsi.iloc[-1]

        if pd.isna(current_rsi):
            return None

        # Exit if overbought
        if current_rsi > 75:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.TARGET,
                urgency="MEDIUM",
                message=f"RSI overbought at {current_rsi:.0f} — take profit",
            )

        return None
