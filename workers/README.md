# Fly.io always-on worker(s)

Claude Code Routines have a 1-hour cron floor. Anything that needs
sub-minute cadence runs here. Today that's just **auto-sell-tick**.

## `auto_sell_tick.py`

60-second loop that ticks `TradingEngine.tick_auto_sell()` — re-reads
the Kite session (handles 15:30 IST token rollover), re-loads
auto-sell triggers from DB (so positions approved by the `telegram_poll`
routine get picked up mid-session), and runs the software-level exit
checks (trailing stop, time, structure break, confidence decay).

Outside market hours it idles on a 5-minute poll. Writes
`last_autosell_tick_ts` in `app_state` — the `heartbeat` Routine alerts
if this goes stale during market hours.

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
  ANTHROPIC_API_KEY="..."

# 4. Deploy
fly deploy

# 5. Watch logs
fly logs

# 6. Toggle paper <-> live without redeploy
fly secrets set EXECUTION_MODE=live     # or "paper"
```

## Cost

`shared-cpu-1x / 256 MB` always-on in `bom` is ~$2/month at current
Fly pricing — the free-tier allowance that previously covered this was
removed in 2024. Budget accordingly.
