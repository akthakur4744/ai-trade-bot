# Routine: Memory Approval Sweeper

**Schedule:** hourly (cron: `15 * * * *` UTC — any hour).

## Purpose

Expire `pending_memory_updates` rows with `status='pending'` older than 60
minutes. On expiry:
- Mark row `status='expired'`.
- Edit the original Telegram message to "⏱ Expired".
- If a GitHub PR was already opened (shouldn't be, but defensive): close it.

## Behavior (HTTPS-only — two-step via CF Worker)

Two-step to avoid Telegram/DB divergence if a Telegram edit fails mid-batch:

1. `GET $CF_BASE/memory/sweep?mode=<mode>` — fetch expired rows (no DB mutation yet). Returns `{ expired: [{id, telegram_message_id, title}] }`.
2. For each row: call `TelegramNotifier.update_memory_message(msg_id, "expired")` (HTTPS to Telegram ✓).
3. `POST $CF_BASE/memory/sweep?mode=<mode>` body `{"ids":[...]}` — mark rows as `status='expired'` in Supabase.

No SQLAlchemy, no direct Postgres connection from CCR.

## Required env vars

| Var | Purpose |
|-----|---------|
| `HEARTBEAT_STATE_URL` | CF Worker URL (base derived by stripping `/heartbeat/state`) |
| `HEARTBEAT_TOKEN` | Auth token for CF Worker |
| `EXECUTION_MODE` | `paper` or `live` |
| `TELEGRAM_BOT_TOKEN` | Bot token for editing messages |
| `TELEGRAM_CHAT_ID` | Chat ID |

## Entrypoint

```python
# routines/impl/memory_approval_sweeper.py  (HTTPS-only, no SQLAlchemy)
python -m routines.impl.memory_approval_sweeper
```
