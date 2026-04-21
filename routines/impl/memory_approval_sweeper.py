"""Cloud Routine entrypoint: expire stale memory-update approval requests.

Marks any `pending_memory_updates` row with status='pending' and
`expires_at < now` as 'expired', and edits the associated Telegram message.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import structlog

from src.config import load_config
from src.notifications.telegram import TelegramNotifier
from src.storage.database import Database
from src.storage.models import PendingMemoryUpdate

logger = structlog.get_logger(__name__)


def main() -> int:
    cfg = load_config()
    db = Database(cfg.database.url)
    tg = TelegramNotifier()

    now = datetime.now(timezone.utc)
    with db.get_session() as s:
        expired = (
            s.query(PendingMemoryUpdate)
            .filter(PendingMemoryUpdate.status == "pending")
            .filter(PendingMemoryUpdate.expires_at < now)
            .all()
        )
        count = 0
        for row in expired:
            row.status = "expired"
            if tg.is_configured and row.telegram_message_id:
                tg.update_memory_message(row.telegram_message_id, "expired")
            count += 1
        s.commit()
    logger.info("memory_sweeper_done", expired_count=count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
