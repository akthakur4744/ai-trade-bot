"""Market data fetching via Kite Connect — historical candles, LTP, and market depth."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd
import structlog
from kiteconnect import KiteConnect

logger = structlog.get_logger(__name__)


class MarketDataFetcher:
    """Fetches market data from Kite Connect with rate limiting.

    Kite rate limits: 3 req/s for historical data, 10 req/s for other endpoints.
    """

    def __init__(self, kite: KiteConnect, rate_limit_per_sec: int = 3) -> None:
        self.kite = kite
        self._min_interval = 1.0 / rate_limit_per_sec
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between API calls."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def get_historical_data(
        self,
        instrument_token: int,
        interval: str = "15minute",
        lookback_days: int = 60,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV candles.

        Args:
            instrument_token: Kite instrument token.
            interval: Candle interval — "minute", "3minute", "5minute",
                     "10minute", "15minute", "30minute", "60minute", "day".
            lookback_days: Number of days to look back (if from_date not specified).
            from_date: Start date.
            to_date: End date (defaults to now).

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        to_date = to_date or datetime.now()
        from_date = from_date or (to_date - timedelta(days=lookback_days))

        self._rate_limit()
        try:
            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval,
            )
        except Exception as e:
            logger.error("historical_data_error", instrument_token=instrument_token, error=str(e))
            return pd.DataFrame()

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        return df

    def get_ltp(self, instruments: list[str]) -> dict[str, float]:
        """Fetch Last Traded Price for multiple instruments.

        Args:
            instruments: List of "EXCHANGE:SYMBOL" strings, e.g. ["NSE:RELIANCE", "NSE:TCS"]

        Returns:
            Dict of instrument -> LTP
        """
        self._rate_limit()
        try:
            data = self.kite.ltp(instruments)
            return {key: val["last_price"] for key, val in data.items()}
        except Exception as e:
            logger.error("ltp_error", instruments=instruments, error=str(e))
            return {}

    def get_quote(self, instruments: list[str]) -> dict:
        """Fetch full quote (OHLC, volume, depth) for instruments.

        Args:
            instruments: List of "EXCHANGE:SYMBOL" strings.

        Returns:
            Raw quote dict from Kite.
        """
        self._rate_limit()
        try:
            return self.kite.quote(instruments)
        except Exception as e:
            logger.error("quote_error", instruments=instruments, error=str(e))
            return {}

    def get_market_depth(self, instrument: str) -> dict:
        """Fetch market depth (order book) for a single instrument.

        Args:
            instrument: "EXCHANGE:SYMBOL" string.

        Returns:
            Dict with 'buy' and 'sell' depth arrays.
        """
        quote = self.get_quote([instrument])
        if instrument in quote:
            return quote[instrument].get("depth", {})
        return {}

    def get_ohlc_batch(
        self,
        instrument_tokens: dict[str, int],
        interval: str = "15minute",
        lookback_days: int = 60,
    ) -> dict[str, pd.DataFrame]:
        """Fetch historical data for multiple symbols.

        Args:
            instrument_tokens: Dict of symbol -> instrument_token.
            interval: Candle interval.
            lookback_days: Days of history.

        Returns:
            Dict of symbol -> DataFrame.
        """
        result: dict[str, pd.DataFrame] = {}
        for symbol, token in instrument_tokens.items():
            df = self.get_historical_data(token, interval, lookback_days)
            if not df.empty:
                result[symbol] = df
                logger.debug("fetched_candles", symbol=symbol, rows=len(df))
            else:
                logger.warning("empty_candles", symbol=symbol)
        return result
