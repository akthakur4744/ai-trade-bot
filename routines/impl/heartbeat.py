"""Cloud Routine entrypoint: watchdog.

Emits a single consolidated Telegram alert if any of these are stale:
  - last_signal_scan_ts  (> 90 min = 1.5 × scan cadence)
  - last_telegram_poll_ts (> 90 min)
  - last_autosell_tick_ts (> 2 min — only checked during market hours)
  - kite_session missing/expired during market hours
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import structlog
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from src.config import load_config
from src.data.kite_session import get_active_session
from src.notifications.telegram import TelegramNotifier
from src.storage.models import AppState
from src.utils.market_calendar import is_market_open

logger = structlog.get_logger(__name__)

THRESHOLDS_MIN = {
    "last_signal_scan_ts": 90,
    "last_telegram_poll_ts": 90,
    "last_autosell_tick_ts": 2,
}

_CONNECT_TIMEOUT_SEC = 4   # per-IP attempt; libpq tries each DNS address in turn
_STMT_TIMEOUT_MS = 5000


def _make_engine(url: str):
    """Minimal, fast-fail engine for the heartbeat watchdog."""
    if url.startswith("sqlite"):
        return create_engine(url, echo=False)
    # pool_pre_ping disabled: this is a cold pool, so all checkouts create
    # a fresh connection anyway. Keeping it enabled would fire an extra
    # SELECT 1 with no timeout before our statement_timeout is active.
    engine = create_engine(
        url,
        echo=False,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=False,
        connect_args={"connect_timeout": _CONNECT_TIMEOUT_SEC},
    )

    # Neon's pooled endpoint rejects `options=-c statement_timeout=...` in the
    # libpq startup packet, so we apply it via SET on each new connection.
    @event.listens_for(engine, "connect")
    def _set_timeout(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute(f"SET statement_timeout = {_STMT_TIMEOUT_MS}")
        cur.close()

    return engine


def _read_ts(session: Session, key: str):
    row = session.query(AppState).filter_by(key=key).first()
    if not row:
        return None
    try:
        ts = datetime.fromisoformat(row.value)
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main() -> int:
    cfg = load_config()
    engine = _make_engine(cfg.database.url)
    SessionLocal = sessionmaker(bind=engine)

    now = datetime.now(timezone.utc)
    alerts: list[str] = []
    market_open = is_market_open()

    try:
        with SessionLocal() as session:
            for key, max_age_min in THRESHOLDS_MIN.items():
                if key == "last_autosell_tick_ts" and not market_open:
                    continue
                ts = _read_ts(session, key)
                if ts is None:
                    if market_open:
                        alerts.append(f"{key}: never seen")
                    continue
                age = (now - ts).total_seconds() / 60.0
                if age > max_age_min:
                    alerts.append(f"{key}: {age:.0f} min stale (threshold {max_age_min})")

            if market_open:
                if not get_active_session(session):
                    alerts.append("kite_session: not active")

    except Exception as e:
        alerts.append(f"db_unreachable: {e}")

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
