"""Manually trigger a weekly review draft.

Usage: python scripts/weekly_review.py

Runs the same code path the Friday-16:40 IST scheduler fires. Drafts the review,
persists it to the pending_memory_updates table, and sends a Telegram approval
message. The diffs are only applied after you tap Approve.
"""

from __future__ import annotations

import os
import sys

import structlog

from src.config import load_config
from src.feedback.memory_writer import MemoryWriter
from src.feedback.postmortem_agent import PostmortemAgent
from src.feedback.postmortem_pipeline import PostmortemPipeline
from src.feedback.weekly_review_agent import WeeklyReviewAgent
from src.notifications.telegram import TelegramNotifier
from src.storage.database import Database


def main() -> int:
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
    agent = WeeklyReviewAgent(config.agents)

    pending_id = agent.run(db=db, telegram=telegram, writer_pipeline=pipeline)
    if pending_id:
        log.info("weekly_review_drafted", pending_id=pending_id)
        return 0
    log.error("weekly_review_failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
