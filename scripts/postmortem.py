"""Manually trigger a postmortem for a closed trade.

Usage: python scripts/postmortem.py <order_id>

Same code path the auto-sell exit handler calls. Drafts the postmortem and
sends a Telegram approval message. Diffs are applied only on Approve.
"""

from __future__ import annotations

import os
import sys

import structlog

from src.config import load_config
from src.feedback.memory_writer import MemoryWriter
from src.feedback.postmortem_agent import PostmortemAgent
from src.feedback.postmortem_pipeline import PostmortemPipeline
from src.notifications.telegram import TelegramNotifier
from src.storage.database import Database


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/postmortem.py <order_id>", file=sys.stderr)
        return 2

    order_id = sys.argv[1]
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )
    log = structlog.get_logger(__name__)

    mode = os.getenv("EXECUTION_MODE", "paper")
    config = load_config(mode)

    db = Database(config.database.url)
    db.create_tables()
    telegram = TelegramNotifier()
    pipeline = PostmortemPipeline(
        agent=PostmortemAgent(config.agents),
        writer=MemoryWriter(),
        telegram=telegram,
        db=db,
    )

    pending_id = pipeline.enqueue_postmortem_for_closed_trade(order_id)
    if pending_id:
        log.info("postmortem_drafted", pending_id=pending_id, order_id=order_id)
        return 0
    log.error("postmortem_failed", order_id=order_id)
    return 1


if __name__ == "__main__":
    sys.exit(main())
