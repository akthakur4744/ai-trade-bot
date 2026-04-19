"""Macro data fetcher — VIX, global indices, crude, DXY.

Provides market context layer for the Orchestrator and regime detection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import structlog
from kiteconnect import KiteConnect

logger = structlog.get_logger(__name__)

# Kite instrument tokens for macro indicators
# These need to be populated after fetching instrument list
MACRO_INSTRUMENTS = {
    "NIFTY50": {"exchange": "NSE", "symbol": "NIFTY 50"},
    "BANKNIFTY": {"exchange": "NSE", "symbol": "NIFTY BANK"},
    "INDIAVIX": {"exchange": "NSE", "symbol": "INDIA VIX"},
}


@dataclass
class MacroSnapshot:
    """Point-in-time snapshot of macro market context."""

    timestamp: datetime
    nifty_price: Optional[float] = None
    nifty_change_pct: Optional[float] = None
    banknifty_price: Optional[float] = None
    banknifty_change_pct: Optional[float] = None
    india_vix: Optional[float] = None
    vix_change_pct: Optional[float] = None
    # Advance/decline for market breadth (from NSE APIs)
    advances: int = 0
    declines: int = 0
    breadth_ratio: float = 0.0  # advances / (advances + declines)

    @property
    def is_risk_off(self) -> bool:
        """Simple risk-off detection: VIX > 20 or Nifty down > 1%."""
        if self.india_vix and self.india_vix > 20:
            return True
        if self.nifty_change_pct and self.nifty_change_pct < -1.0:
            return True
        return False

    @property
    def market_direction(self) -> str:
        """Broad market direction from Nifty change."""
        if self.nifty_change_pct is None:
            return "NEUTRAL"
        if self.nifty_change_pct > 0.5:
            return "BULLISH"
        elif self.nifty_change_pct < -0.5:
            return "BEARISH"
        return "NEUTRAL"


class MacroDataFetcher:
    """Fetches macro market context from Kite Connect."""

    def __init__(self, kite: KiteConnect) -> None:
        self._kite = kite

    def get_snapshot(self) -> MacroSnapshot:
        """Fetch current macro snapshot."""
        snapshot = MacroSnapshot(timestamp=datetime.utcnow())

        try:
            # Fetch Nifty 50 and India VIX via quotes
            instruments = ["NSE:NIFTY 50", "NSE:NIFTY BANK", "NSE:INDIA VIX"]
            quotes = self._kite.quote(instruments)

            if "NSE:NIFTY 50" in quotes:
                q = quotes["NSE:NIFTY 50"]
                snapshot.nifty_price = q.get("last_price")
                ohlc = q.get("ohlc", {})
                if ohlc.get("close") and snapshot.nifty_price:
                    snapshot.nifty_change_pct = (
                        (snapshot.nifty_price - ohlc["close"]) / ohlc["close"]
                    ) * 100

            if "NSE:NIFTY BANK" in quotes:
                q = quotes["NSE:NIFTY BANK"]
                snapshot.banknifty_price = q.get("last_price")
                ohlc = q.get("ohlc", {})
                if ohlc.get("close") and snapshot.banknifty_price:
                    snapshot.banknifty_change_pct = (
                        (snapshot.banknifty_price - ohlc["close"]) / ohlc["close"]
                    ) * 100

            if "NSE:INDIA VIX" in quotes:
                q = quotes["NSE:INDIA VIX"]
                snapshot.india_vix = q.get("last_price")

        except Exception as e:
            logger.error("macro_fetch_error", error=str(e))

        logger.debug(
            "macro_snapshot",
            nifty=snapshot.nifty_price,
            vix=snapshot.india_vix,
            direction=snapshot.market_direction,
        )
        return snapshot
