"""Cloud Routine entrypoint: expire stale memory-update approval requests.

DB queries via Cloudflare Worker proxy (HTTPS). Two-step: fetch expired rows
first, edit Telegram messages, then mark rows expired — avoids Telegram/DB
divergence if messages fail.
"""
from __future__ import annotations

import os
import sys

import httpx
import structlog

from src.notifications.telegram import TelegramNotifier

logger = structlog.get_logger(__name__)

_HTTP_TIMEOUT_SEC = 15.0


def main() -> int:
    url   = os.environ.get("HEARTBEAT_STATE_URL")
    token = os.environ.get("HEARTBEAT_TOKEN")
    mode  = os.environ.get("EXECUTION_MODE", "paper")

    if not url or not token:
        logger.error("memory_sweeper_misconfigured", have_url=bool(url), have_token=bool(token))
        return 1

    base = url.rsplit("/heartbeat/state", 1)[0]
    tg   = TelegramNotifier()

    # Step 1: fetch expired rows (no DB mutation yet)
    try:
        resp = httpx.get(f"{base}/memory/sweep", params={"mode": mode},
                         headers={"X-Heartbeat-Token": token}, timeout=_HTTP_TIMEOUT_SEC)
        resp.raise_for_status()
        expired = resp.json().get("expired", [])
    except Exception as e:
        logger.warning("memory_sweeper_fetch_failed", error=str(e))
        logger.info("memory_sweeper_done", expired_count=0)
        return 0

    if not expired:
        logger.info("memory_sweeper_done", expired_count=0)
        return 0

    # Step 2: edit Telegram messages first
    for row in expired:
        if tg.is_configured and row.get("telegram_message_id"):
            tg.update_memory_message(row["telegram_message_id"], "expired")

    # Step 3: mark as expired in DB
    ids = [row["id"] for row in expired]
    try:
        httpx.post(f"{base}/memory/sweep", params={"mode": mode},
                   headers={"X-Heartbeat-Token": token},
                   json={"ids": ids}, timeout=_HTTP_TIMEOUT_SEC)
    except Exception as e:
        logger.warning("memory_sweeper_mark_failed", error=str(e))

    logger.info("memory_sweeper_done", expired_count=len(expired))
    return 0


if __name__ == "__main__":
    sys.exit(main())
