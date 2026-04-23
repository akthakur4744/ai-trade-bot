"""Cloud Routine entrypoint: morning Kite login prompt.

Schedule: 08:55 IST every market day.
Idempotent — if a live session is already active (checked via Cloudflare Worker
proxy over HTTPS), exits 0 silently.

The Cloud Routine sandbox has HTTPS-only egress; Neon is unreachable on port
5432. Session state is read via GET /heartbeat/state on the Cloudflare Worker
(same env vars as heartbeat: HEARTBEAT_STATE_URL, HEARTBEAT_TOKEN).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import httpx
import structlog

from src.notifications.telegram import TelegramNotifier
from src.utils.market_calendar import is_trading_day

logger = structlog.get_logger(__name__)

_HTTP_TIMEOUT_SEC = 10.0


def _is_session_active(url: str, token: str, mode: str) -> bool:
    """Return True if a valid Kite session exists, via CF Worker proxy."""
    try:
        resp = httpx.get(
            url,
            params={"mode": mode},
            headers={"X-Heartbeat-Token": token},
            timeout=_HTTP_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        state = resp.json()
    except Exception as e:
        logger.warning("session_check_failed", error=str(e))
        return False

    if not state.get("kite_access_token_present"):
        return False
    exp_raw = state.get("kite_session_expires_at")
    if not exp_raw:
        return False
    try:
        exp = datetime.fromisoformat(exp_raw)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return datetime.now(timezone.utc) < exp


def main() -> int:
    from datetime import date
    if not is_trading_day(date.today()):
        logger.info("non_market_day_skip")
        return 0

    url = os.environ.get("HEARTBEAT_STATE_URL")
    token = os.environ.get("HEARTBEAT_TOKEN")
    mode = os.environ.get("EXECUTION_MODE", "paper")
    if not url or not token:
        logger.error("heartbeat_misconfigured", have_url=bool(url), have_token=bool(token))
        return 1

    if _is_session_active(url, token, mode):
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

    logger.info("login_prompt_sent", message_id=msg_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
