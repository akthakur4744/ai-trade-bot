"""Cloud Routine entrypoint: watchdog.

Emits a single consolidated Telegram alert if any of these are stale:
  - last_signal_scan_ts  (> 90 min = 1.5 × scan cadence)
  - last_telegram_poll_ts (> 90 min)
  - last_autosell_tick_ts (> 2 min — only checked during market hours)
  - kite_session missing/expired during market hours
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import sqlalchemy.exc
import structlog

from src.config import load_config
from src.data.kite_session import get_active_session
from src.notifications.telegram import TelegramNotifier
from src.storage.database import Database
from src.storage.models import AppState
from src.utils.market_calendar import is_market_open

logger = structlog.get_logger(__name__)

THRESHOLDS_MIN = {
    "last_signal_scan_ts": 90,
    "last_telegram_poll_ts": 90,
    "last_autosell_tick_ts": 2,
}


def _read_ts(db, key: str):
    with db.get_session() as s:
        row = s.query(AppState).filter_by(key=key).first()
        if not row:
            return None
        try:
            ts = datetime.fromisoformat(row.value)
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def main() -> int:
    try:
        cfg = load_config()
        db = Database(cfg.database.url)

        now = datetime.now(timezone.utc)
        alerts: list[str] = []
        market_open = is_market_open()

        for key, max_age_min in THRESHOLDS_MIN.items():
            if key == "last_autosell_tick_ts" and not market_open:
                continue
            try:
                ts = _read_ts(db, key)
            except sqlalchemy.exc.OperationalError as exc:
                alerts.append(f"database unreachable: {exc.orig}")
                break
            if ts is None:
                if market_open:
                    alerts.append(f"{key}: never seen")
                continue
            age = (now - ts).total_seconds() / 60.0
            if age > max_age_min:
                alerts.append(f"{key}: {age:.0f} min stale (threshold {max_age_min})")

        if market_open and not any(a.startswith("database") for a in alerts):
            try:
                with db.get_session() as s:
                    if not get_active_session(s):
                        alerts.append("kite_session: not active")
            except sqlalchemy.exc.OperationalError as exc:
                alerts.append(f"database unreachable: {exc.orig}")

    except Exception as exc:  # noqa: BLE001
        logger.error("heartbeat_error", error=str(exc))
        alerts = [f"heartbeat error: {exc}"]

    if not alerts:
        logger.info("heartbeat_ok")
        return 0

    tg = TelegramNotifier()
    if tg.is_configured:
        tg.send_alert("Heartbeat:\n- " + "\n- ".join(alerts))
    logger.warning("heartbeat_alerts", alerts=alerts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
