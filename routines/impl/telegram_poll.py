"""Cloud Routine entrypoint: Telegram callback poll.

Reads queued callback_query updates from Telegram and dispatches them to
the same handler used by the long-poll daemon. Persists the next update
offset in `app_state['telegram_update_offset']` so consecutive runs don't
re-process updates.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import structlog

from src.config import load_config
from src.notifications.telegram import TelegramNotifier
from src.storage.database import Database
from src.storage.models import AppState

logger = structlog.get_logger(__name__)

OFFSET_KEY = "telegram_update_offset"
HEARTBEAT_KEY = "last_telegram_poll_ts"


def _get_offset(db) -> int:
    with db.get_session() as s:
        row = s.query(AppState).filter_by(key=OFFSET_KEY).first()
        if not row:
            return 0
        try:
            return int(row.value)
        except ValueError:
            return 0


def _set_offset(db, offset: int) -> None:
    with db.get_session() as s:
        row = s.query(AppState).filter_by(key=OFFSET_KEY).first()
        if row:
            row.value = str(offset)
        else:
            s.add(AppState(key=OFFSET_KEY, value=str(offset)))
        s.commit()


def _heartbeat(db) -> None:
    with db.get_session() as s:
        row = s.query(AppState).filter_by(key=HEARTBEAT_KEY).first()
        now = datetime.now(timezone.utc).isoformat()
        if row:
            row.value = now
        else:
            s.add(AppState(key=HEARTBEAT_KEY, value=now))
        s.commit()


def _handle(action: str, signal_id: str) -> None:
    """Dispatch a callback to the appropriate pipeline.

    TODO(Phase-E): wire to PostmortemPipeline.handle_memory_callback for
    `memory_update:*` events and to the pending-signal approval flow for
    `approve|ignore|auto_sell:*`. For now, log so we can verify the routine
    is picking up button presses.
    """
    logger.info("telegram_callback", action=action, signal_id=signal_id)


def main() -> int:
    cfg = load_config()
    db = Database(cfg.database.url)
    tg = TelegramNotifier()
    if not tg.is_configured:
        logger.error("telegram_not_configured")
        return 2

    offset = _get_offset(db)
    next_offset = tg.process_updates_once(offset, handler=_handle)
    if next_offset != offset:
        _set_offset(db, next_offset)
    _heartbeat(db)
    logger.info("telegram_poll_done", offset_before=offset, offset_after=next_offset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
