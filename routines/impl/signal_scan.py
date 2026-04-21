"""Cloud Routine entrypoint: signal scan.

Runs one full `TradingEngine.run_cycle()`. Because the engine operates in
approval mode, no orders are placed — qualifying signals are written to
`pending_signal_state` and posted to Telegram with inline buttons.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import structlog

from src.config import load_config
from src.data.kite_session import get_active_session
from src.storage.database import Database
from src.storage.models import AppState
from src.utils.market_calendar import is_market_open

logger = structlog.get_logger(__name__)

HEARTBEAT_KEY = "last_signal_scan_ts"


def _heartbeat(db) -> None:
    with db.get_session() as s:
        row = s.query(AppState).filter_by(key=HEARTBEAT_KEY).first()
        now = datetime.now(timezone.utc).isoformat()
        if row:
            row.value = now
        else:
            s.add(AppState(key=HEARTBEAT_KEY, value=now))
        s.commit()


def main() -> int:
    if not is_market_open():
        logger.info("market_closed_skip")
        return 0

    cfg = load_config()
    db = Database(cfg.database.url)

    with db.get_session() as s:
        if not get_active_session(s):
            # heartbeat routine owns user-facing alert; stay silent here
            logger.warning("kite_session_stale_skip")
            return 0

    # Import lazily to keep cold-start light on market-closed / no-session exits.
    from src.main import TradingEngine

    engine = TradingEngine(cfg)
    try:
        engine.run_cycle()
    finally:
        # Stop the callback polling thread the engine starts in __init__
        try:
            engine._telegram.stop_callback_polling()
        except Exception:
            pass

    _heartbeat(db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
