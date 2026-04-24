"""Cloud Routine entrypoint: Telegram callback poll.

Delegates all DB-dependent logic (offset read/write, callback dispatch,
heartbeat) to the Fly.io worker trigger API which has full Postgres access.
"""
from __future__ import annotations

import os
import sys

import httpx
import structlog

logger = structlog.get_logger(__name__)

_HTTP_TIMEOUT_SEC = 60.0


def main() -> int:
    fly_url       = os.environ.get("FLY_WORKER_URL")
    trigger_token = os.environ.get("TRIGGER_API_TOKEN")

    if not fly_url or not trigger_token:
        logger.error("telegram_poll_misconfigured",
                     have_fly_url=bool(fly_url), have_trigger_token=bool(trigger_token))
        return 1

    try:
        resp = httpx.post(
            f"{fly_url}/trigger/poll",
            headers={"X-Trigger-Token": trigger_token},
            timeout=_HTTP_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info("telegram_poll_done", **result)
    except Exception as e:
        logger.error("poll_trigger_failed", error=str(e))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
