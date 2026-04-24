"""Fly.io always-on worker: tick the auto-sell monitor every 60s.

Claude Code Routines have a 1-hour cron floor, which is too coarse for
the software-level exit triggers (trailing stop, time, structure break,
confidence decay). This worker runs those checks sub-minute during
market hours; exchange-level GTT stop+target already survives crashes.

Each tick re-reads the Kite session (handles daily 15:30 IST token
rollover) and re-loads auto-sell triggers from the DB, so positions
newly approved via the `telegram_poll` routine are picked up without
restarting the worker.

Deployed as part of `workers.main` alongside the trigger API.
Outside market hours it idles with a 5-minute sleep. Heartbeat key
`last_autosell_tick_ts` in `app_state` is watched by the heartbeat
Routine.
"""
from __future__ import annotations

import signal as signal_mod
import sys
import threading
import time
from datetime import datetime, timezone

import structlog

from src.config import load_config
from src.storage.database import Database
from src.storage.models import AppState
from src.utils.market_calendar import is_market_open

logger = structlog.get_logger(__name__)

HEARTBEAT_KEY = "last_autosell_tick_ts"
TICK_SECONDS = 60
IDLE_SLEEP_SECONDS = 300  # Market closed — loose poll.

_shutdown = False


def _on_signal(signum, _frame) -> None:
    global _shutdown
    logger.info("shutdown_requested", signal=signum)
    _shutdown = True


def _heartbeat(db: Database) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with db.get_session() as s:
        row = s.query(AppState).filter_by(key=HEARTBEAT_KEY).first()
        if row:
            row.value = now
        else:
            s.add(AppState(key=HEARTBEAT_KEY, value=now))
        s.commit()


def _sleep_interruptible(seconds: int) -> None:
    for _ in range(seconds):
        if _shutdown:
            return
        time.sleep(1)


def run_loop(stop_event: threading.Event | None = None) -> None:
    """Auto-sell main loop — safe to run in a thread (no signal registration)."""
    cfg = load_config()
    db = Database(cfg.database.url)

    logger.info("auto_sell_worker_starting", mode=cfg.execution.mode)

    engine = None  # Lazy-init on first market-open tick to defer heavy imports.

    def _sleep(seconds: int) -> None:
        if stop_event is not None:
            stop_event.wait(timeout=seconds)
        else:
            _sleep_interruptible(seconds)

    def _should_stop() -> bool:
        if stop_event is not None:
            return stop_event.is_set()
        return _shutdown

    while not _should_stop():
        if not is_market_open():
            _sleep(IDLE_SLEEP_SECONDS)
            continue

        if engine is None:
            from src.main import TradingEngine
            try:
                engine = TradingEngine(cfg)
            except Exception as e:
                logger.error("engine_init_failed", error=str(e))
                _sleep(IDLE_SLEEP_SECONDS)
                continue

        try:
            engine.tick_auto_sell()
        except Exception as e:
            logger.error("auto_sell_tick_error", error=str(e))

        try:
            _heartbeat(db)
        except Exception as e:
            logger.error("heartbeat_write_failed", error=str(e))

        _sleep(TICK_SECONDS)

    logger.info("auto_sell_worker_stopped")


def main() -> int:
    signal_mod.signal(signal_mod.SIGTERM, _on_signal)
    signal_mod.signal(signal_mod.SIGINT, _on_signal)
    run_loop()  # No stop_event — uses _shutdown global via _sleep_interruptible.
    return 0


if __name__ == "__main__":
    sys.exit(main())
