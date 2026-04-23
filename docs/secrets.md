# Secrets — storage, rotation, recovery

All runtime secrets live in **three** places. Keep them in sync.

| Location                      | Purpose                                 | How to set                                       |
|-------------------------------|-----------------------------------------|--------------------------------------------------|
| Local `.env`                  | Developer workstation, CLI scripts      | Copy from `.env.example`                         |
| Claude Code trigger env       | Cloud Routines (signal-scan, etc.)      | `/schedule` config → env vars                    |
| Cloudflare Worker secrets     | Kite login redirect handler             | `wrangler secret put <NAME>`                     |
| Fly.io worker env             | `auto-sell-tick` loop                   | `fly secrets set <NAME>=...`                     |

## Inventory

| Name                    | Used by                         | Where                                   | Rotation                                |
|-------------------------|---------------------------------|-----------------------------------------|-----------------------------------------|
| `KITE_API_KEY`          | All routines, Worker, Fly       | .env + Claude + Cloudflare + Fly        | On compromise — regenerate in Kite dev  |
| `KITE_API_SECRET`       | Worker (generate_session)       | Cloudflare                              | Same                                    |
| `ANTHROPIC_API_KEY`     | All routines                    | .env + Claude                           | Rotate quarterly                        |
| `TELEGRAM_BOT_TOKEN`    | All routines, Worker            | .env + Claude + Cloudflare              | On compromise — BotFather               |
| `TELEGRAM_CHAT_ID`      | All routines, Worker            | .env + Claude + Cloudflare              | Stable — almost never rotates           |
| `DATABASE_URL_PAPER`    | Paper-mode routines, Worker     | .env + Claude + Cloudflare              | On compromise — Supabase reset password |
| `DATABASE_URL_LIVE`     | Live-mode routines, Worker      | .env + Claude + Cloudflare              | Same                                    |
| `GITHUB_PAT`            | Memory-merge flow (telegram-poll) | Claude trigger env                     | Rotate every 90 days                    |
| `HEARTBEAT_TOKEN`       | `heartbeat` routine, Worker     | Claude + Cloudflare                     | On compromise — rotate in both          |
| `HEARTBEAT_STATE_URL`   | `heartbeat` routine             | Claude                                  | Stable — Worker URL                     |

## Rotation drill

1. Generate the new value (Kite console / Supabase / GitHub / BotFather).
2. Update `.env` first; smoke-test locally.
3. `wrangler secret put NAME` → redeploy Worker.
4. `fly secrets set NAME=...` → Fly worker auto-restarts.
5. Update every Claude Code trigger that uses this secret.
6. Revoke the old value only after every location is updated.

## What's NO LONGER a secret

Removed from the system (but listed for clarity):

- `KITE_USER_ID`, `KITE_PASSWORD`, `KITE_TOTP_SECRET` — obsolete.
  The user logs in manually on mobile; the Worker consumes the redirect
  token. `scripts/kite_auto_login.py` remains as a manual debug tool only.
