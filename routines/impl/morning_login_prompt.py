"""Cloud Routine entrypoint: morning Kite login prompt.

Schedule: 08:55 IST every market day.
Idempotent — if a live session is already in Neon, exits 0 silently.
"""
from __future__ import annotations

import os
import sys

import structlog

from src.config import load_config
from src.data.kite_session import get_active_session, set_login_message_id
from src.notifications.telegram import TelegramNotifier
from src.storage.database import Database
from src.utils.market_calendar import is_market_open

logger = structlog.get_logger(__name__)


def main() -> int:
    if not is_market_open():
        logger.info("market_closed_skip")
        return 0

    cfg = load_config()
    db = Database(cfg.database.url)
    with db.get_session() as s:
        if get_active_session(s):
            logger.info("kite_session_already_active_skip")
            return 0

    api_key = os.environ.get("KITE_API_KEY", "")
    if not api_key:
        logger.error("missing_kite_api_key")
        return 2

    tg = TelegramNotifier()
    if not tg.is_configured:
        logger.error("telegram_not_configured")
        return 2

    login_url = f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
    msg_id = tg.send_plain(
        "🔐 Kite login required for today.\n"
        f"Tap: {login_url}\n"
        "(auto-captured by callback — no reply needed)"
    )
    if msg_id is None:
        return 1

    with db.get_session() as s:
        set_login_message_id(s, msg_id)
    logger.info("login_prompt_sent", message_id=msg_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
