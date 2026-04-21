"""Zerodha Kite Connect authentication wrapper with daily token caching."""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

import structlog
from kiteconnect import KiteConnect

logger = structlog.get_logger(__name__)

TOKEN_CACHE_PATH = Path.home() / ".insight_alpha" / "kite_token.json"


class KiteClient:
    """Manages Kite Connect authentication and provides the KiteConnect instance.

    Kite access tokens expire daily. This wrapper:
    - Caches the access token for the current day
    - Provides a method to complete the login flow
    - Exposes the authenticated KiteConnect instance
    """

    def __init__(self, db=None) -> None:
        self.api_key = os.getenv("KITE_API_KEY", "")
        self.api_secret = os.getenv("KITE_API_SECRET", "")
        if not self.api_key:
            raise ValueError("KITE_API_KEY environment variable is required")
        self.kite = KiteConnect(api_key=self.api_key)
        self._access_token: str | None = None
        # Optional: when provided, `authenticate()` reads the session from
        # Neon `app_state` (populated by the Cloudflare Worker on mobile login)
        # before falling back to the legacy file cache.
        self._db = db

    @property
    def login_url(self) -> str:
        """URL to redirect user for Zerodha login."""
        return self.kite.login_url()

    def authenticate(self, request_token: str | None = None) -> None:
        """Authenticate with Kite Connect.

        First tries to load today's cached token. If not available or expired,
        uses the provided request_token to generate a new session.

        Args:
            request_token: Token received from Zerodha login redirect.
                          Required on first auth of the day.
        """
        # Prefer the Neon-backed session (written by the Cloudflare login
        # redirect Worker). This is the production path for cloud Routines.
        if self._db is not None:
            from src.data.kite_session import get_active_session
            with self._db.get_session() as s:
                session = get_active_session(s)
            if session:
                self._access_token = session.access_token
                self.kite.set_access_token(session.access_token)
                logger.info("kite_auth_from_neon", expires_at=str(session.expires_at))
                return

        # Try cached token first
        cached = self._load_cached_token()
        if cached:
            self._access_token = cached
            self.kite.set_access_token(cached)
            logger.info("kite_auth_cached", date=str(date.today()))
            return

        # Need fresh token
        if not request_token:
            raise ValueError(
                f"No cached token for today. Complete login at: {self.login_url}"
            )

        if not self.api_secret:
            raise ValueError("KITE_API_SECRET environment variable is required")

        session = self.kite.generate_session(request_token, api_secret=self.api_secret)
        self._access_token = session["access_token"]
        self.kite.set_access_token(self._access_token)
        self._save_token(self._access_token)
        logger.info("kite_auth_fresh", date=str(date.today()))

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None

    def _load_cached_token(self) -> str | None:
        """Load cached access token if it's from today."""
        if not TOKEN_CACHE_PATH.exists():
            return None
        try:
            data = json.loads(TOKEN_CACHE_PATH.read_text())
            if data.get("date") == str(date.today()):
                return data.get("access_token")
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _save_token(self, access_token: str) -> None:
        """Cache access token with today's date."""
        TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE_PATH.write_text(
            json.dumps({"access_token": access_token, "date": str(date.today())})
        )


def get_instruments(kite: KiteConnect, exchange: str = "NSE") -> dict[str, int]:
    """Fetch instrument list and return symbol -> instrument_token mapping.

    Rate-limited: call once per session, cache the result.
    """
    instruments = kite.instruments(exchange)
    return {i["tradingsymbol"]: i["instrument_token"] for i in instruments}
