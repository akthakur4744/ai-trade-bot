# Routine: Signal Scan

**Schedule:** hourly during market hours (cron: `0 4-10 * * 1-5` UTC = 09:30–15:30 IST).
**Ideal cadence:** 5 min — but cloud Routines floor is 1 hour. The engine's
internal `scan_interval_minutes` is still honored within each run.

## Purpose

Run the full analysis pipeline once: fetch data → compute indicators → run
strategies → run AI agents → score → filter → enqueue pending signals. For
each qualifying signal, write a row to `pending_signal_state` and post a
Telegram approval card.

## Preconditions

- `is_market_open(now)` — else exit 0.
- CF Worker `/heartbeat/state` returns a live Kite session — else skip (heartbeat routine alerts separately).
- Risk guardrails met (daily loss floor, max positions, etc.) — checked inside `engine.run_cycle()` on the Fly.io side.

## Behavior (HTTPS-only — no direct DB access)

1. Check `is_market_open()` — exit 0 if closed.
2. Validate Kite session via `GET $HEARTBEAT_STATE_URL?mode=<mode>` (CF Worker).
3. If session active: `POST $FLY_WORKER_URL/trigger/scan` with `X-Trigger-Token`.
   - Fly.io returns `{"ok":true,"status":"accepted"}` immediately (async).
   - `engine.run_cycle()` runs in a background task on the Fly.io worker.
   - Heartbeat key `last_signal_scan_ts` is written to `app_state` after completion.
4. Exit 0.

No SQLAlchemy, no direct Supabase connection — pure HTTPS calls.

## Required env vars

| Var | Purpose |
|-----|---------|
| `HEARTBEAT_STATE_URL` | CF Worker URL, e.g. `https://insight-alpha.<sub>.workers.dev/heartbeat/state` |
| `HEARTBEAT_TOKEN` | Auth token for CF Worker |
| `EXECUTION_MODE` | `paper` or `live` |
| `FLY_WORKER_URL` | `https://insight-alpha-auto-sell.fly.dev` |
| `TRIGGER_API_TOKEN` | Shared secret for Fly.io trigger API |

## Implementation entrypoint

```python
# routines/impl/signal_scan.py  (HTTPS-only, no SQLAlchemy)
python -m routines.impl.signal_scan
```
