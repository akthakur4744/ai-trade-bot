# Claude Code Routines

Operational playbooks for the Insight-Alpha trading agent. Each `.md` is
runnable in two modes:

1. **Cloud Routine** (primary) — scheduled via `/schedule` or the Claude
   Code dashboard. Cron floor is 1 hour.
2. **Local** — paste the contents into Claude Code interactively, or
   reference as `@routines/<name>.md`.

Every cloud-scheduled routine fail-fasts on `is_market_open(now) == False`
(see `src/utils/market_calendar.py`) and on a stale Kite session.

## Schedules

| Routine                         | Cron (UTC)             | IST window         | Notes                              |
|---------------------------------|------------------------|--------------------|------------------------------------|
| `morning-login-prompt.md`       | `25 3 * * 1-5`         | 08:55 daily        | Gated — idempotent                 |
| `pre-market-check.md`           | `30 3 * * 1-5`         | 09:00 daily        |                                    |
| `signal-scan.md`                | `0 4-10 * * 1-5`       | 09:30–15:30 hourly | Scan half of the engine            |
| `telegram-poll.md`              | `0 3-10 * * 1-5`       | 08:30–15:30 hourly | Processes approval callbacks       |
| `heartbeat.md`                  | `30 3-10 * * 1-5`      | 09:00–16:00 hourly | Watchdog for silent triggers       |
| `memory-approval-sweeper.md`    | `15 * * * *`           | every hour         | Expires stale memory PRs           |
| `signal-review.md`              | `0 5 * * 1-5`          | 10:30              | Checkpoint                         |
| `risk-audit.md`                 | `0 9 * * 1-5`          | 14:30              | Checkpoint                         |
| `end-of-day-report.md`          | `5 10 * * 1-5`         | 15:35              | Commit to `docs/reports/`          |
| `gtt-reconcile.md`              | `30 3 * * 1-5`         | 09:00              | Ensure every position has GTT OCO  |
| `weekly-performance-review.md`  | `10 10 * * 5`          | Fri 15:40          | Memory PR gated by Telegram        |
| `regime-check.md`               | `30 12 * * 0`          | Sun 18:00          |                                    |
| `strategy-backtest.md`          | weekend only           | —                  | Rate-limit budget                  |
| `postmortem-trade.md`           | on-demand / per trade  | —                  | Memory PR gated by Telegram        |
| `new-strategy-checklist.md`     | on-demand              | —                  | Stateless                          |
| `kite-token-health.md`          | on-demand              | —                  | Debug only                         |

`auto-sell-tick.md` does **not** run as a cloud Routine — the 1-hour floor
is too coarse. It runs as a 1-minute loop on the always-on Fly.io worker.

## Required secrets (Claude Code Routine env)

Set these in the Claude Code dashboard under each Routine's **Secrets** tab:

| Secret | Required by | Purpose |
|--------|-------------|---------|
| `DATABASE_URL_PAPER` | all except morning-login-prompt | Supabase paper DB |
| `DATABASE_URL_LIVE` | all except morning-login-prompt | Supabase live DB |
| `EXECUTION_MODE` | all | `paper` or `live` |
| `KITE_API_KEY` | morning-login-prompt, signal-scan, telegram-poll | Zerodha API |
| `KITE_API_SECRET` | signal-scan, telegram-poll | Zerodha API |
| `TELEGRAM_BOT_TOKEN` | all | Bot notifications |
| `TELEGRAM_CHAT_ID` | all | Your chat ID |
| `ANTHROPIC_API_KEY` | signal-scan, telegram-poll | Claude API |
| `GITHUB_TOKEN` | **telegram-poll only** | Open memory PRs (Contents + Pull requests write) |
| `HEARTBEAT_STATE_URL` | heartbeat, morning-login-prompt | Cloudflare Worker proxy URL |
| `HEARTBEAT_TOKEN` | heartbeat, morning-login-prompt | Auth token for the proxy |

`GITHUB_TOKEN` is a **fine-grained PAT** scoped to this repo with:
- Repository permissions → **Contents: Read & write**
- Repository permissions → **Pull requests: Read & write**

It is only needed on `telegram-poll` because that is the sole Routine that
can trigger `MemoryWriter` (via Telegram approve callbacks).

## Running locally

Cloud Routine cadence is the source of truth. For interactive development,
paste a routine into Claude Code or use `@routines/<name>.md`.
