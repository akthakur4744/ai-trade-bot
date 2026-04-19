"""Fundamental data fetcher — EPS, P/E, ROE, D/E for watchlist stocks.

Caches results daily since fundamentals don't change intraday.
Data sourced from NSE APIs or screener.in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)

NSE_QUOTE_URL = "https://www.nseindia.com/api/quote-equity"
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class FundamentalData:
    """Fundamental metrics for a stock."""

    symbol: str
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    eps_growth_yoy: Optional[float] = None  # Year-over-year EPS growth %
    de_ratio: Optional[float] = None  # Debt to Equity
    roe: Optional[float] = None  # Return on Equity
    pb_ratio: Optional[float] = None  # Price to Book
    market_cap: Optional[float] = None  # In crores
    sector: str = ""
    sector_pe_avg: Optional[float] = None
    fetched_at: Optional[datetime] = None


class FundamentalDataFetcher:
    """Fetches and caches fundamental data for watchlist stocks.

    Caches results for the current day — fundamentals are updated at most
    once per quarter (earnings), so daily caching is more than sufficient.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, FundamentalData] = {}
        self._cache_date: Optional[date] = None

    def _is_cache_valid(self) -> bool:
        return self._cache_date == date.today() and bool(self._cache)

    def get(self, symbol: str) -> Optional[FundamentalData]:
        """Get cached fundamental data for a symbol."""
        if self._is_cache_valid():
            return self._cache.get(symbol)
        return None

    def get_all(self) -> Dict[str, FundamentalData]:
        """Get all cached fundamental data."""
        if self._is_cache_valid():
            return dict(self._cache)
        return {}

    def fetch_nse(self, symbol: str) -> Optional[FundamentalData]:
        """Fetch fundamental data from NSE India API.

        Note: NSE may block automated requests. This is a best-effort approach.
        For production use, consider a paid data provider.
        """
        try:
            with httpx.Client(headers=NSE_HEADERS, follow_redirects=True, timeout=10) as client:
                # Need to first visit the main page for cookies
                client.get("https://www.nseindia.com")
                resp = client.get(NSE_QUOTE_URL, params={"symbol": symbol})

                if resp.status_code != 200:
                    logger.warning("nse_fetch_failed", symbol=symbol, status=resp.status_code)
                    return None

                data = resp.json()
                price_info = data.get("priceInfo", {})
                metadata = data.get("metadata", {})
                industry_info = data.get("industryInfo", {})

                fund = FundamentalData(
                    symbol=symbol,
                    pe_ratio=self._safe_float(metadata.get("pdSymbolPe")),
                    sector=industry_info.get("macro", ""),
                    sector_pe_avg=self._safe_float(metadata.get("pdSectorPe")),
                    fetched_at=datetime.utcnow(),
                )

                self._cache[symbol] = fund
                self._cache_date = date.today()
                return fund

        except Exception as e:
            logger.warning("nse_fetch_error", symbol=symbol, error=str(e))
            return None

    def set_manual(self, symbol: str, data: FundamentalData) -> None:
        """Manually set fundamental data (from external source or config)."""
        data.fetched_at = datetime.utcnow()
        self._cache[symbol] = data
        self._cache_date = date.today()
        logger.debug("fundamental_set_manual", symbol=symbol)

    def fetch_batch(self, symbols: list) -> Dict[str, FundamentalData]:
        """Fetch fundamentals for multiple symbols."""
        results = {}
        for symbol in symbols:
            data = self.fetch_nse(symbol)
            if data:
                results[symbol] = data
        return results

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
