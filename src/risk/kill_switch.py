"""Daily loss circuit breaker — halts all trading when loss limit is hit."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import structlog

from src.config import RiskConfig
from src.risk.portfolio import Portfolio

if TYPE_CHECKING:
    from src.storage.database import Database

logger = structlog.get_logger(__name__)


class KillSwitch:
    """Monitors daily PnL and blocks trading when max_daily_loss is breached.

    Once triggered, no new orders are allowed for the rest of the trading day.
    Resets automatically on the next trading day.
    """

    def __init__(
        self,
        portfolio: Portfolio,
        config: RiskConfig,
        db: Database | None = None,
    ) -> None:
        self._portfolio = portfolio
        self._config = config
        self._db = db
        self._triggered = False
        self._triggered_date: date | None = None

        if db:
            self._load_from_db()

    def _load_from_db(self) -> None:
        """Restore kill switch state from database."""
        assert self._db is not None
        data = self._db.load_app_state("kill_switch")
        if data and data.get("triggered"):
            saved_date = data.get("triggered_date", "")
            if saved_date == str(date.today()):
                self._triggered = True
                self._triggered_date = date.today()
                logger.info("kill_switch_restored", date=saved_date)

    def _persist(self) -> None:
        """Save kill switch state to database."""
        if not self._db:
            return
        self._db.save_app_state("kill_switch", {
            "triggered": self._triggered,
            "triggered_date": str(self._triggered_date) if self._triggered_date else None,
        })

    @property
    def is_triggered(self) -> bool:
        """Check if kill switch is active."""
        # Auto-reset on new day
        if self._triggered and self._triggered_date != date.today():
            self._triggered = False
            self._triggered_date = None
            self._persist()
            logger.info("kill_switch_reset", date=str(date.today()))

        return self._triggered

    def check(self) -> bool:
        """Evaluate daily PnL and trigger if threshold breached.

        Returns:
            True if trading is blocked.
        """
        if self.is_triggered:
            return True

        pnl = self._portfolio.realized_pnl_today
        if pnl <= -self._config.max_daily_loss:
            self._triggered = True
            self._triggered_date = date.today()
            self._persist()
            logger.critical(
                "kill_switch_triggered",
                realized_pnl=round(pnl, 2),
                max_daily_loss=self._config.max_daily_loss,
                date=str(date.today()),
            )
            return True

        return False

    def force_trigger(self, reason: str = "manual") -> None:
        """Manually trigger the kill switch."""
        self._triggered = True
        self._triggered_date = date.today()
        self._persist()
        logger.warning("kill_switch_forced", reason=reason, date=str(date.today()))

    def reset(self) -> None:
        """Manually reset the kill switch (use with caution)."""
        self._triggered = False
        self._triggered_date = None
        self._persist()
        logger.warning("kill_switch_manual_reset")
