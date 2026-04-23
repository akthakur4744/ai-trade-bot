"""Cloud Routine entrypoint: watchdog.

Emits a single consolidated Telegram alert if any of these are stale:
  - last_signal_scan_ts   (> 90 min = 1.5 × scan cadence)
  - last_telegram_poll_ts (> 90 min)
  - last_autosell_tick_ts (> 2 min — only checked during market hours)
  - kite_session missing/expired during market hours

The cloud Routine sandbox cannot reach Neon on port 5432 (HTTPS-only
egress), so this reads `app_state` via the Cloudflare Worker proxy
(`GET /heartbeat/state`) instead of connecting to Postgres directly.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import httpx
import structlog

from src.notifications.telegram import TelegramNotifier
from src.utils.market_calendar import is_market_open

logger = structlog.get_logger(__name__)

THRESHOLDS_MIN = {
    "last_signal_scan_ts": 90,
    "last_telegram_poll_ts": 90,
    "last_autosell_tick_ts": 2,
}

_HTTP_TIMEOUT_SEC = 10.0


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _fetch_state(url: str, token: str, mode: str) -> dict:
    resp = httpx.get(
        url,
        params={"mode": mode},
        headers={"X-Heartbeat-Token": token},
        timeout=_HTTP_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    url = os.environ.get("HEARTBEAT_STATE_URL")
    token = os.environ.get("HEARTBEAT_TOKEN")
    mode = os.environ.get("EXECUTION_MODE", "paper")
    if not url or not token:
        logger.error("heartbeat_misconfigured", have_url=bool(url), have_token=bool(token))
        return 1

    now = datetime.now(timezone.utc)
    market_open = is_market_open()
    alerts: list[str] = []

    try:
        state = _fetch_state(url, token, mode)
    except Exception as e:
        alerts.append(f"state_fetch_failed: {e}")
        state = None

    if state is not None:
        for key, max_age_min in THRESHOLDS_MIN.items():
            if key == "last_autosell_tick_ts" and not market_open:
                continue
            ts = _parse_ts(state.get(key))
            if ts is None:
                if market_open:
                    alerts.append(f"{key}: never seen")
                continue
            age = (now - ts).total_seconds() / 60.0
            if age > max_age_min:
                alerts.append(f"{key}: {age:.0f} min stale (threshold {max_age_min})")

        if market_open:
            present = bool(state.get("kite_access_token_present"))
            exp = _parse_ts(state.get("kite_session_expires_at"))
            active = present and exp is not None and exp > now
            if not active:
                alerts.append("kite_session: not active")

    if not alerts:
        logger.info("heartbeat_ok")
        return 0

    tg = TelegramNotifier()
    if tg.is_configured:
        try:
            tg.send_alert("Heartbeat:\n- " + "\n- ".join(alerts))
        except Exception as exc:
            logger.warning("heartbeat_telegram_send_failed", error=str(exc))
    logger.warning("heartbeat_alerts", alerts=alerts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
