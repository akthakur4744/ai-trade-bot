# Routine: Morning Login Prompt

**Schedule:** 08:55 IST every market day (cron: `25 3 * * 1-5` UTC).
**Floor:** hourly (Claude Code cloud Routines). The routine is idempotent — if a
fresh token already exists for today, it exits 0 without posting.

## Purpose

Post a one-tap Zerodha login link to Telegram. The user taps it on their phone,
logs into Kite in the real browser, and Zerodha redirects back to the
Cloudflare Worker (`cloudflare-worker/`) which writes the `access_token` to
Neon `app_state`. From that point, every other routine reads the token.

## Preconditions

- `HEARTBEAT_STATE_URL`, `HEARTBEAT_TOKEN`, `EXECUTION_MODE`,
  `KITE_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` all set in the
  trigger env.
- `is_trading_day(today)` is true (use `src/utils/market_calendar.py`).

## Behavior

1. If market closed today → exit 0, silent.
2. Check `kite_session` via Cloudflare Worker (`GET /heartbeat/state`):
   - Token present AND `expires_at > now` → exit 0 (nothing to do).
3. Build login URL: `https://kite.zerodha.com/connect/login?api_key=<KITE_API_KEY>&v=3`.
4. Send Telegram message:
   ```
   🔐 Kite login required for today.
   Tap: <login url>
   (auto-captured by callback — no reply needed)
   ```
5. Exit 0.

## Failure modes

- Telegram send fails → exit non-zero so the routine run shows red in the UI;
  heartbeat will also catch the stale token at 09:10.
- Cloudflare Worker unreachable → exits 0 and falls through to send the prompt
  (safe: if we can't confirm a session exists, better to prompt than to skip).

## Why CF Worker proxy instead of direct DB

The Cloud Routine sandbox has **HTTPS-only egress** — TCP port 5432 (Neon
Postgres) is blocked. Session state is read over HTTPS via `GET /heartbeat/state`
on the Cloudflare Worker, using the same `HEARTBEAT_STATE_URL` +
`HEARTBEAT_TOKEN` env vars as the `heartbeat` routine.

## Implementation sketch

```python
# routines/impl/morning_login_prompt.py
import httpx, os
from datetime import datetime, timezone
from src.notifications.telegram import TelegramNotifier
from src.utils.market_calendar import is_trading_day
from datetime import date

def _is_session_active(url, token, mode) -> bool:
    try:
        resp = httpx.get(url, params={"mode": mode},
                         headers={"X-Heartbeat-Token": token}, timeout=10.0)
        resp.raise_for_status()
        state = resp.json()
    except Exception:
        return False  # can't confirm — fall through to send prompt
    if not state.get("kite_access_token_present"):
        return False
    exp_raw = state.get("kite_session_expires_at")
    if not exp_raw:
        return False
    exp = datetime.fromisoformat(exp_raw).replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < exp

def main() -> int:
    if not is_trading_day(date.today()):
        return 0
    url = os.environ.get("HEARTBEAT_STATE_URL")
    token = os.environ.get("HEARTBEAT_TOKEN")
    mode = os.environ.get("EXECUTION_MODE", "paper")
    if _is_session_active(url, token, mode):
        return 0
    tg = TelegramNotifier()
    login_url = f"https://kite.zerodha.com/connect/login?api_key={os.environ['KITE_API_KEY']}&v=3"
    msg_id = tg.send_plain(f"🔐 Kite login required for today.\nTap: {login_url}\n"
                           "(auto-captured by callback — no reply needed)")
    return 0 if msg_id else 1

if __name__ == "__main__":
    raise SystemExit(main())
```

See `cloudflare-worker/README.md` for the redirect-handler half.
