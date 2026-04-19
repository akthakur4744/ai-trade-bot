"""WhatsApp notifications via Twilio API.

Sends trading signal alerts to a WhatsApp number using Twilio's WhatsApp Business API.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
import structlog

from src.models import ScoredSignal

logger = structlog.get_logger(__name__)

TWILIO_SID_ENV = "TWILIO_ACCOUNT_SID"
TWILIO_TOKEN_ENV = "TWILIO_AUTH_TOKEN"
TWILIO_FROM_ENV = "TWILIO_WHATSAPP_FROM"  # e.g., "whatsapp:+14155238886"
TWILIO_TO_ENV = "TWILIO_WHATSAPP_TO"  # e.g., "whatsapp:+91XXXXXXXXXX"


class WhatsAppNotifier:
    """Send trading notifications via Twilio WhatsApp."""

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
        to_number: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self._sid = account_sid or os.getenv(TWILIO_SID_ENV, "")
        self._token = auth_token or os.getenv(TWILIO_TOKEN_ENV, "")
        self._from = from_number or os.getenv(TWILIO_FROM_ENV, "")
        self._to = to_number or os.getenv(TWILIO_TO_ENV, "")
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return all([self._sid, self._token, self._from, self._to])

    def send_signal(self, signal: ScoredSignal) -> bool:
        """Send trading signal notification."""
        if not self.is_configured:
            logger.warning("whatsapp_not_configured")
            return False
        message = self._format_signal(signal)
        return self._send(message)

    def send_alert(self, message: str) -> bool:
        """Send a plain text alert."""
        if not self.is_configured:
            return False
        return self._send(f"⚠️ ALERT: {message}")

    def send_daily_summary(self, summary: Dict[str, Any]) -> bool:
        """Send end-of-day summary."""
        if not self.is_configured:
            return False
        text = self._format_daily_summary(summary)
        return self._send(text)

    def _send(self, body: str) -> bool:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json"
        try:
            response = httpx.post(
                url,
                data={
                    "From": self._from,
                    "To": self._to,
                    "Body": body,
                },
                auth=(self._sid, self._token),
                timeout=self._timeout,
            )
            if response.status_code in (200, 201):
                logger.info("whatsapp_sent", status=response.status_code)
                return True
            else:
                logger.warning(
                    "whatsapp_send_failed",
                    status=response.status_code,
                    body=response.text[:200],
                )
                return False
        except httpx.HTTPError as e:
            logger.error("whatsapp_http_error", error=str(e))
            return False

    @staticmethod
    def _format_signal(signal: ScoredSignal) -> str:
        direction = "🟢 BUY" if signal.direction.value == "BUY" else "🔴 SELL"
        lines = [
            f"{direction} {signal.symbol}",
            f"Strategy: {signal.strategy_name}",
            f"Confidence: {signal.confidence:.2f} ({signal.strength.value})",
            f"Entry: ₹{signal.entry_price:.2f}",
            f"Stop: ₹{signal.stop_loss:.2f}",
        ]
        if signal.target_price:
            lines.append(f"Target: ₹{signal.target_price:.2f}")
        if signal.summary:
            lines.append(f"\n{signal.summary}")
        return "\n".join(lines)

    @staticmethod
    def _format_daily_summary(summary: Dict[str, Any]) -> str:
        return (
            f"📊 Daily Summary\n"
            f"Trades: {summary.get('total_trades', 0)}\n"
            f"Win Rate: {summary.get('win_rate', 0):.1%}\n"
            f"PnL: ₹{summary.get('realized_pnl', 0):.2f}\n"
            f"Open: {summary.get('open_positions', 0)}"
        )
