"""Google Chat webhook notifications.

Sends trading signal cards to a Google Chat space via incoming webhook.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
import structlog

from src.models import ScoredSignal

logger = structlog.get_logger(__name__)

GCHAT_WEBHOOK_ENV = "GCHAT_WEBHOOK_URL"


class GChatNotifier:
    """Send formatted signal notifications to Google Chat."""

    def __init__(self, webhook_url: Optional[str] = None, timeout: float = 10.0) -> None:
        self._webhook_url = webhook_url or os.getenv(GCHAT_WEBHOOK_ENV, "")
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._webhook_url)

    def send_signal(self, signal: ScoredSignal) -> bool:
        """Send a trading signal as a formatted card.

        Returns:
            True if sent successfully.
        """
        if not self.is_configured:
            logger.warning("gchat_not_configured")
            return False

        payload = self._format_signal(signal)
        return self._send(payload)

    def send_daily_summary(self, summary: Dict[str, Any]) -> bool:
        """Send end-of-day summary."""
        if not self.is_configured:
            return False

        text = self._format_daily_summary(summary)
        return self._send({"text": text})

    def send_alert(self, message: str) -> bool:
        """Send a plain text alert (kill switch, errors, etc.)."""
        if not self.is_configured:
            return False
        return self._send({"text": f"⚠️ ALERT: {message}"})

    def _send(self, payload: Dict[str, Any]) -> bool:
        try:
            response = httpx.post(
                self._webhook_url,
                json=payload,
                timeout=self._timeout,
            )
            if response.status_code == 200:
                logger.info("gchat_sent", status=200)
                return True
            else:
                logger.warning(
                    "gchat_send_failed",
                    status=response.status_code,
                    body=response.text[:200],
                )
                return False
        except httpx.HTTPError as e:
            logger.error("gchat_http_error", error=str(e))
            return False

    @staticmethod
    def _format_signal(signal: ScoredSignal) -> Dict[str, Any]:
        """Format signal as Google Chat card."""
        direction_emoji = "🟢" if signal.direction.value == "BUY" else "🔴"
        strength_stars = {"STRONG": "⭐⭐⭐", "MODERATE": "⭐⭐", "WEAK": "⭐"}

        header = f"{direction_emoji} {signal.direction.value} {signal.symbol}"

        sections = [
            f"*Strategy:* {signal.strategy_name}",
            f"*Sentiment:* {signal.sentiment.value} | *Strength:* {strength_stars.get(signal.strength.value, '⭐')}",
            f"*Confidence:* {signal.confidence:.2f} | *Score:* {signal.final_score:.2f}",
            f"*Entry:* ₹{signal.entry_price:.2f} | *Stop:* ₹{signal.stop_loss:.2f} | *Target:* ₹{signal.target_price:.2f}" if signal.target_price else f"*Entry:* ₹{signal.entry_price:.2f} | *Stop:* ₹{signal.stop_loss:.2f}",
        ]

        if signal.key_drivers:
            sections.append(f"*Drivers:* {', '.join(signal.key_drivers[:3])}")
        if signal.risks:
            sections.append(f"*Risks:* {', '.join(signal.risks[:2])}")
        if signal.summary:
            sections.append(f"*Summary:* {signal.summary}")
        if signal.regime:
            sections.append(f"*Regime:* {signal.regime.value}")

        return {"text": f"*{header}*\n" + "\n".join(sections)}

    @staticmethod
    def _format_daily_summary(summary: Dict[str, Any]) -> str:
        lines = [
            "📊 *Daily Summary*",
            f"Trades: {summary.get('total_trades', 0)}",
            f"Win Rate: {summary.get('win_rate', 0):.1%}",
            f"PnL: ₹{summary.get('realized_pnl', 0):.2f}",
            f"Open Positions: {summary.get('open_positions', 0)}",
            f"Capital Deployed: ₹{summary.get('capital_deployed', 0):.2f}",
        ]
        if summary.get("regime"):
            lines.append(f"Regime: {summary['regime']}")
        return "\n".join(lines)
