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

- `EXECUTION_MODE`, `DATABASE_URL_PAPER` or `DATABASE_URL_LIVE`,
  `KITE_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` all set in the
  trigger env.
- `is_market_open(today)` is true (use `src/utils/market_calendar.py`).

## Behavior

1. If market closed today → exit 0, silent.
2. Check `kite_session` in Neon `app_state`:
   - Token present AND `expires_at > now` → exit 0 (nothing to do).
3. Build login URL: `https://kite.zerodha.com/connect/login?api_key=<KITE_API_KEY>&v=3`.
4. Send Telegram message:
   ```
   🔐 Kite login required for today.
   Tap: <login url>
   (auto-captured by callback — no reply needed)
   ```
5. Store the returned `message_id` via `kite_session.set_login_message_id()`.
6. Exit 0.

## Failure modes

- Telegram send fails → exit non-zero so the routine run shows red in the UI;
  heartbeat will also catch the stale token at 09:10.
- Neon unreachable → exit non-zero.

## Implementation sketch

```python
# routines/impl/morning_login_prompt.py  (tiny — kept separate so the trigger
# boots with minimum imports)
import os
from src.config import load_config
from src.storage.database import Database
from src.data.kite_session import get_active_session, set_login_message_id
from src.notifications.telegram import TelegramNotifier
from src.utils.market_calendar import is_market_open
from datetime import date

def main() -> int:
    if not is_market_open(date.today()):
        return 0
    cfg = load_config()
    db = Database(cfg.database.url)
    with db.get_session() as s:
        if get_active_session(s):
            return 0
    tg = TelegramNotifier(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_CHAT_ID"],
    )
    url = f"https://kite.zerodha.com/connect/login?api_key={os.environ['KITE_API_KEY']}&v=3"
    msg_id = tg.send_alert_with_message_id(f"🔐 Kite login required.\nTap: {url}")
    if msg_id is None:
        return 1
    with db.get_session() as s:
        set_login_message_id(s, msg_id)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

See `cloudflare-worker/README.md` for the redirect-handler half.
