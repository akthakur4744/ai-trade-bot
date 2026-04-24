"""Cloud Routine entrypoint: signal scan.

Session check via Cloudflare Worker proxy (HTTPS). Scan delegated to the
Fly.io worker trigger API which runs engine.run_cycle() with full DB access.
Returns 200 immediately (async); heartbeat written by the Fly.io side.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import httpx
import structlog

from src.utils.market_calendar import is_market_open

logger = structlog.get_logger(__name__)

_HTTP_TIMEOUT_SEC = 30.0   # /trigger/scan returns immediately (async endpoint)


def _is_session_active(url: str, token: str, mode: str) -> bool:
    try:
        resp = httpx.get(url, params={"mode": mode},
                         headers={"X-Heartbeat-Token": token}, timeout=_HTTP_TIMEOUT_SEC)
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
    if not is_market_open():
        logger.info("market_closed_skip")
        return 0

    url           = os.environ.get("HEARTBEAT_STATE_URL")
    token         = os.environ.get("HEARTBEAT_TOKEN")
    mode          = os.environ.get("EXECUTION_MODE", "paper")
    fly_url       = os.environ.get("FLY_WORKER_URL")
    trigger_token = os.environ.get("TRIGGER_API_TOKEN")

    if not all([url, token, fly_url, trigger_token]):
        logger.error("signal_scan_misconfigured",
                     have_state_url=bool(url), have_token=bool(token),
                     have_fly_url=bool(fly_url), have_trigger_token=bool(trigger_token))
        return 1

    if not _is_session_active(url, token, mode):
        logger.warning("kite_session_stale_skip")
        return 0

    try:
        resp = httpx.post(
            f"{fly_url}/trigger/scan",
            headers={"X-Trigger-Token": trigger_token},
            timeout=_HTTP_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        logger.info("scan_triggered", response=resp.json())
    except Exception as e:
        logger.error("scan_trigger_failed", error=str(e))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
