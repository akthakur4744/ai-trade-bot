# Fly.io always-on worker(s)

Claude Code Routines have a 1-hour cron floor. Anything that needs
sub-minute cadence runs here. Today that's **auto-sell-tick**, co-located
with an HTTP **trigger API** that lets CCR routines delegate heavy
DB-dependent work.

## `main.py` — combined entrypoint

Runs two things in one Fly machine:

1. **Auto-sell tick loop** (`auto_sell_tick.run_loop`) in a daemon thread —
   60-second loop that ticks `TradingEngine.tick_auto_sell()`. Re-reads the
   Kite session (handles 15:30 IST token rollover), reloads auto-sell triggers
   from DB (so positions approved by the `telegram_poll` routine get picked up
   mid-session), and runs software-level exit checks (trailing stop, time,
   structure break, confidence decay). Writes `last_autosell_tick_ts` in
   `app_state` — the `heartbeat` Routine alerts if this goes stale during
   market hours.

2. **Trigger API** (`trigger_api.app`) via uvicorn on port 8080 — authenticated
   FastAPI endpoints called by CCR routines that cannot reach Supabase directly
   (CCR sandbox: HTTPS-only egress, port 5432/6543 blocked).

## Trigger API endpoints

All require `X-Trigger-Token: <TRIGGER_API_TOKEN>` header.

| Method | Path | Behaviour |
|--------|------|-----------|
| `POST` | `/trigger/scan` | **Async** — fires `engine.run_cycle()` in background, returns `{"ok":true,"status":"accepted"}` immediately. Writes `last_signal_scan_ts` heartbeat on completion. |
| `POST` | `/trigger/poll` | **Sync** — reads Telegram updates, dispatches callbacks (signal approvals + memory approvals), persists offset + `last_telegram_poll_ts`. |

## Deploy

```bash
# 1. Install flyctl and auth
curl -L https://fly.io/install.sh | sh
fly auth login

# 2. Create the app (one-time)
fly launch --no-deploy --name insight-alpha-auto-sell --region bom \
           --copy-config --dockerfile Dockerfile

# 3. Set secrets (paper mode only to start; mirror for live later)
fly secrets set \
  DATABASE_URL_PAPER="postgresql://postgres.<ref>:<pw>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres" \
  DATABASE_URL_LIVE="postgresql://postgres.<ref>:<pw>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres" \
  KITE_API_KEY="..." \
  KITE_API_SECRET="..." \
  TELEGRAM_BOT_TOKEN="..." \
  TELEGRAM_CHAT_ID="..." \
  ANTHROPIC_API_KEY="..." \
  TRIGGER_API_TOKEN="<new-random-secret>"

# 4. Deploy
fly deploy

# 5. Watch logs
fly logs

# 6. Toggle paper <-> live without redeploy
fly secrets set EXECUTION_MODE=live     # or "paper"
```

## Verifying trigger endpoints after deploy

```bash
FLY=https://insight-alpha-auto-sell.fly.dev
TTOKEN=<TRIGGER_API_TOKEN>

# Poll (safe any time — just fetches Telegram updates)
curl -s -X POST "$FLY/trigger/poll" -H "X-Trigger-Token: $TTOKEN" | jq .
# Expected: {"ok":true,"offset_before":N,"offset_after":M}

# Scan (only during market hours — triggers engine.run_cycle() async)
curl -s -X POST "$FLY/trigger/scan" -H "X-Trigger-Token: $TTOKEN" | jq .
# Expected: {"ok":true,"status":"accepted"}
# Then watch: fly logs | grep scan_cycle_complete
```

## Cost

`shared-cpu-1x / 512 MB` always-on in `bom` is ~$4/month at current
Fly pricing (bumped from 256 MB to give headroom when the auto-sell loop
and a scan background task coexist briefly). The free-tier allowance that
previously covered this was removed in 2024. Budget accordingly.
