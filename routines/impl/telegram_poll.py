"""Cloud Routine entrypoint: Telegram callback poll.

Reads queued callback_query updates from Telegram and dispatches them to
the appropriate pipeline. Persists the next update offset in
`app_state['telegram_update_offset']` so consecutive runs don't
re-process updates.

Routing:
  - `memory_update:<id>:<approve|reject>`  → PostmortemPipeline.handle_memory_callback
      (lightweight — only needs DB + MemoryWriter + Telegram; no Claude agent)
  - `approve|ignore|auto_sell:<signal_id>` → TradingEngine._handle_telegram_callback
      (heavy — lazy-imported only when one of these callbacks arrives)
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import structlog
from sqlalchemy.exc import OperationalError

from src.config import load_config
from src.notifications.telegram import TelegramNotifier
from src.storage.database import Database
from src.storage.models import AppState

logger = structlog.get_logger(__name__)

OFFSET_KEY = "telegram_update_offset"
HEARTBEAT_KEY = "last_telegram_poll_ts"


def _get_offset(db) -> int:
    try:
        with db.get_session() as s:
            row = s.query(AppState).filter_by(key=OFFSET_KEY).first()
            if not row:
                return 0
            try:
                return int(row.value)
            except ValueError:
                return 0
    except Exception as exc:
        logger.warning("db_offset_read_failed", error=str(exc))
        return 0


def _set_offset(db, offset: int) -> None:
    try:
        with db.get_session() as s:
            row = s.query(AppState).filter_by(key=OFFSET_KEY).first()
            if row:
                row.value = str(offset)
            else:
                s.add(AppState(key=OFFSET_KEY, value=str(offset)))
            s.commit()
    except OperationalError as exc:
        logger.warning("telegram_poll_set_offset_failed", error=str(exc).split("\n")[0])


def _heartbeat(db) -> None:
    try:
        with db.get_session() as s:
            row = s.query(AppState).filter_by(key=HEARTBEAT_KEY).first()
            now = datetime.now(timezone.utc).isoformat()
            if row:
                row.value = now
            else:
                s.add(AppState(key=HEARTBEAT_KEY, value=now))
            s.commit()
    except OperationalError as exc:
        logger.warning("telegram_poll_heartbeat_failed", error=str(exc).split("\n")[0])


class _CallbackRouter:
    """Lazily constructs pipelines needed for each callback class."""

    def __init__(self, cfg, db, tg):
        self._cfg = cfg
        self._db = db
        self._tg = tg
        self._memory = None
        self._engine = None

    def _memory_pipeline(self):
        if self._memory is None:
            from src.feedback.memory_writer import MemoryWriter
            from src.feedback.postmortem_pipeline import PostmortemPipeline
            self._memory = PostmortemPipeline(
                agent=None,
                writer=MemoryWriter(),
                telegram=self._tg,
                db=self._db,
            )
        return self._memory

    def _engine_instance(self):
        if self._engine is None:
            from src.main import TradingEngine
            self._engine = TradingEngine(self._cfg)
        return self._engine

    def handle(self, action: str, signal_id: str) -> None:
        logger.info("telegram_callback", action=action, signal_id=signal_id)

        if action == "memory_update":
            try:
                pending_id_str, sub_action = signal_id.split(":", 1)
                pending_id = int(pending_id_str)
            except (ValueError, AttributeError):
                logger.warning("memory_callback_malformed", signal_id=signal_id)
                return
            self._memory_pipeline().handle_memory_callback(pending_id, sub_action)
            return

        if action in ("approve", "ignore", "auto_sell"):
            engine = self._engine_instance()
            engine._handle_telegram_callback(action, signal_id)
            return

        logger.warning("telegram_callback_unknown_action", action=action)

    def cleanup(self) -> None:
        if self._engine is not None:
            try:
                self._engine._telegram.stop_callback_polling()
            except Exception:
                pass


def main() -> int:
    cfg = load_config()
    tg = TelegramNotifier()
    if not tg.is_configured:
        logger.error("telegram_not_configured")
        return 2

    db = Database(cfg.database.url)
    router = _CallbackRouter(cfg, db, tg)
    offset = _get_offset(db)
    try:
        next_offset = tg.process_updates_once(offset, handler=router.handle)
    finally:
        router.cleanup()

    if next_offset != offset:
        _set_offset(db, next_offset)
    _heartbeat(db)
    logger.info("telegram_poll_done", offset_before=offset, offset_after=next_offset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
