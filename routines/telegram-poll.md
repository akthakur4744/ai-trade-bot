# Routine: Telegram Poll

**Schedule:** hourly during market window (cron: `0 3-10 * * 1-5` UTC = 08:30–15:30 IST).
Cloud Routines floor is 1 hour; for faster approval latency, the always-on
auto-sell worker can call the same entrypoint every 30s.

## Purpose

Process pending Telegram button callbacks that accumulated since the last run:
- Signal approvals / rejections (`BUY & Auto-Sell`, `Manual BUY`, `Ignore`).
- Memory-update approvals / rejections (open or reject GitHub PR).

Replaces the long-polling daemon thread in `telegram.py::_poll_callbacks` for
remote execution.

## Preconditions

- `FLY_WORKER_URL` and `TRIGGER_API_TOKEN` set.
- Fly.io worker is running (auto-sell tick + trigger API).

## Behavior (HTTPS-only — delegates to Fly.io)

This routine is now a thin one-liner: it delegates all Telegram polling,
callback dispatch, offset persistence, and heartbeat writing to the Fly.io
trigger API which has full Postgres access.

1. `POST $FLY_WORKER_URL/trigger/poll` with `X-Trigger-Token` header.
2. Fly.io worker:
   - Reads `telegram_update_offset` from `app_state`.
   - Calls Telegram `getUpdates` (short poll, `timeout=0`).
   - Dispatches callbacks: signal approvals → `TradingEngine._handle_telegram_callback()`; memory approvals → `PostmortemPipeline.handle_memory_callback()`.
   - Persists updated offset + `last_telegram_poll_ts` to `app_state`.
3. Returns `{"ok":true,"offset_before":N,"offset_after":M}`.
4. CCR routine exits 0.

No SQLAlchemy, no direct Supabase connection, no Telegram API calls from CCR — pure HTTPS delegation.

## Required env vars

| Var | Purpose |
|-----|---------|
| `FLY_WORKER_URL` | `https://insight-alpha-auto-sell.fly.dev` |
| `TRIGGER_API_TOKEN` | Shared secret for Fly.io trigger API |

## Implementation entrypoint

```python
# routines/impl/telegram_poll.py  (HTTPS-only, no SQLAlchemy)
python -m routines.impl.telegram_poll
```
