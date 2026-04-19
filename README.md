# Insight-Alpha 2026

AI-powered equity trading agent for Indian markets using Zerodha Kite Connect.

## What It Does

- Analyzes news, macro indicators, and technical signals in real-time
- Uses 4 AI agents (Researcher, Sentinel, Orchestrator, Stitch) for multi-layer analysis
- Produces high-confidence directional theses with confidence scores
- Sends interactive Telegram notifications with BUY & Auto-Sell / Manual BUY / Ignore buttons
- Auto-Sell mode: AI-managed exit with stop loss, trailing stop, target, time & confidence decay triggers
- GTT exchange-level protection: stop loss + target on Zerodha exchange survive app crashes
- Enforces strict risk guardrails before every trade
- Web dashboard for Kite OAuth login, engine control, and real-time monitoring
- Full state persistence — positions, triggers, pending signals survive restarts
- Supports paper trading (simulated) and live trading (Zerodha)
- Self-improving memory loop: postmortems and weekly reviews propose edits to `memory/*.md`, gated by Telegram approval and committed to git

## Quick Start

```bash
# Install dependencies
pip install -e .

# Copy and configure environment
cp .env.example .env
# Edit .env with your Zerodha API key, Claude API key, Telegram bot token

# Start web dashboard (recommended)
python start.py
# Opens browser -> Login with Zerodha -> Start Engine -> Monitor + Approve trades

# Or run standalone (requires manual Kite auth first)
python scripts/kite_auth.py
python -m src.main

# Fully-automated daily Kite login (External TOTP required — see below)
python scripts/kite_auto_login.py
./scripts/install_cron.sh   # schedule it daily at 08:55 local time

# Run tests
pytest tests/
```

## How It Works

```
Market Data + News + Macro
        |
   AI Analysis Pipeline (Researcher -> Sentinel -> Orchestrator -> Stitch)
        |
   Scoring & Filtering (confidence >= 0.65)
        |
   Risk Guardrails (4 checks, non-negotiable)
        |
   Pending Queue -> Telegram Notification with Action Buttons
        |
   [BUY & Auto-Sell] -> Execute trade + AI monitors exit conditions (recommended)
   [Manual BUY]      -> Execute trade, manual exit management
   [Ignore]          -> Signal discarded
        |
   Auto-Sell Monitor (stop loss / target / trailing / time / confidence decay)
        |
   Exit Notification -> User informed with PnL and reason
```

## Telegram Notifications

When the engine finds a high-confidence signal, you get a clean, action-oriented Telegram notification:

- **Stock** name and **Recommendation** (BUY/SELL)
- Entry / Stop Loss / Target prices with **expected return %**
- **Horizon**: Short Term (1-3 days) or Medium Term (4-10 days)
- **Rationale**: AI-generated summary combining drivers, analysis, and risks
- **2 action buttons**: BUY & Auto-Sell (primary) | Manual BUY | Ignore

**BUY & Auto-Sell** (recommended) buys the stock and creates AI-defined exit triggers that run without human intervention:

*Exchange-level (GTT OCO on Zerodha — survives app crashes):*
- Hard stop loss
- Profit target

*Software-level (app monitoring — intelligent exits):*
- Trailing stop (moves with price to protect gains; updates GTT stop on exchange as it improves)
- Time-based exit (holding window)
- Structure break (price reversal with volume)
- Confidence decay (AI confidence drops)

When any exit condition triggers, the position is closed automatically and you get notified with PnL, exit reason, and whether exit was via exchange GTT or app software.

## Web Dashboard

Dark-themed dashboard at `http://127.0.0.1:8000`:

- One-click Zerodha OAuth login (no manual token copy-paste)
- Engine start/stop controls + manual cycle trigger
- Pending signals panel with BUY & Auto-Sell / Manual BUY / Ignore buttons
- Auto-Sell monitor showing active triggers with levels and time remaining
- Market insights (macro context, news sentiment, AI research, risk assessment)
- Open positions with PnL and exit management type (Auto/Manual)
- Activity log and recent signals table

## Memory System & Self-Improvement Loop

A curated markdown memory layer under `memory/` drives continuous learning on top of the SQL trade log. **Every write is Telegram-gated** — no file is edited without explicit user approval.

| File | Purpose | Cadence |
|------|---------|---------|
| `memory/PROJECT-CONTEXT.md` | Static mission, capital, constraints | Rarely |
| `memory/TRADING-STRATEGY.md` | Binding rulebook agents must follow | Weekly (on approval) |
| `memory/LEARNINGS.md` | Distilled patterns, ≥2-occurrence promotion | Weekly (on approval) |
| `memory/MISTAKES.md` | Append-only per-trade postmortems | Per trade close (on approval) |
| `memory/WEEKLY-REVIEW.md` | Friday retrospective with letter grade | Weekly (on approval) |

**Flow:** trade closes → `PostmortemAgent` drafts MISTAKES/LEARNINGS/STRATEGY diffs via Claude → row queued in `pending_memory_updates` → Telegram message with `[Approve & Commit] [Reject]` (60-min expiry) → on approve, `MemoryWriter` applies diffs + `git commit` + `git push`. Friday 15:40 IST runs the weekly review through the same gate.

Orchestrator and Researcher read `TRADING-STRATEGY.md` + `LEARNINGS.md` into their system prompts on startup; signals contradicting an active rule drop confidence by 0.1 and must cite the rule.

Slash commands: `/postmortem <order_id>`, `/weekly-review`, `/promote-learning "<pattern>"`.

## Configuration

All configuration is in `config/`:
- `default.yaml` — Default parameters for all components
- `paper.yaml` — Paper trading overrides
- `live.yaml` — Live trading overrides (stricter risk limits)
- `strategies/` — Per-strategy parameters
- `watchlist.yaml` — Stock universe

Switch between paper and live via `execution.mode` in config.

## Risk Guardrails

Every order must pass all checks:
- Trade size <= 10,000 INR
- Total deployed <= 30,000 INR
- Daily loss < 1,000 INR
- Open positions < 3

Auto-sell only activates after explicit user consent. Works within all configured risk guardrails. Can be disabled per trade or globally.

**GTT Exchange Protection:** When auto-sell is enabled, a GTT OCO (Good Till Triggered, One Cancels Other) order is placed on the Zerodha exchange with stop loss + target. This provides a safety net even if the app crashes or loses connectivity. The app continues monitoring for smarter exits (trailing stop, time, confidence decay, structure break) and updates the GTT stop leg as trailing stop improves. On startup, the system reconciles persisted GTT state against the exchange and re-places protection for any unprotected positions.

## Data Persistence

All critical state survives application restarts:

| State | Storage |
|-------|---------|
| Open positions | `position_state` table |
| Auto-sell triggers | `auto_sell_trigger_state` table |
| Pending signals | `pending_signal_state` table |
| Kill switch, daily PnL | `app_state` key-value table |
| Trade history | `trades` table (existing) |

Database: SQLite (paper mode) / PostgreSQL (live mode). WAL mode enabled for concurrent access.

## Documentation

- `docs/hld.md` — High-Level Design: system context, component diagram, data model, persistence strategy
- `docs/architecture.md` — Full system pipeline, module map, agent design, persistence layer, data flow timing
- `docs/strategy.md` — All strategies, indicator reference, alpha scoring, risk rules
- `docs/claude.md` — AI agent design, prompt engineering, MCP integration guide
- `docs/trading-strategies.md` — Stock selection methodology and strategy deep-dives
- `docs/ai_market_intelligence_agent_prd.md` — Original product requirements document
- `plan.md` — Implementation roadmap with phases and timelines
- `CLAUDE.md` — Development conventions and project context

## Automated Daily Kite Login (optional)

Zerodha requires interactive 2FA every 24 hours (SEBI mandate — cannot be removed). With **External TOTP** enabled in your Kite profile, the full login can be scripted so the agent runs hands-off.

### One-time setup

1. **Enable External TOTP in Kite:** `kite.zerodha.com` → Profile → Settings → **Account** → find **External 2FA TOTP** → Enable. Kite shows a QR + a 32-character secret. Scan the QR in Google Authenticator (or Authy / 1Password) and **copy the secret string below the QR** — you need the raw secret, not the QR URL.

2. **Install deps and Playwright's browser binary:**
   ```bash
   pip install -e .
   playwright install chromium
   ```

3. **Add credentials to `.env`** (no quotes; keep `chmod 600`):
   ```
   KITE_USER_ID=your_client_id           # e.g. YGT823
   KITE_PASSWORD=your_kite_password
   KITE_TOTP_SECRET=YOUR_32_CHAR_SECRET  # A–Z and 2–7 only, no 0/1/8/9
   ```
   **Check length** — must be 32 characters:
   ```bash
   grep KITE_TOTP_SECRET .env | awk -F= '{print length($2)}'
   ```
   Beware `0` vs `O` and `1` vs `I/L` confusion when transcribing the secret.

4. **Sanity check the TOTP** — the code this prints must match your authenticator app at the same moment:
   ```bash
   .venv/bin/python -c "import pyotp, os; from dotenv import load_dotenv; load_dotenv(); print(pyotp.TOTP(os.environ['KITE_TOTP_SECRET'].strip().upper()).now())"
   ```

### Daily automation

```bash
# One-off run (headless; idempotent — no-op if today's token already cached)
.venv/bin/python scripts/kite_auto_login.py

# Debug run (visible browser; pauses 30s on error so you can inspect)
.venv/bin/python scripts/kite_auto_login.py --headed

# Install Mon–Fri 08:55 local-time schedule via launchd
./scripts/install_cron.sh

# Dry-run the schedule immediately
launchctl start com.insightalpha.kiteauth
tail -f ~/.insight_alpha/auto_login.log

# Uninstall the schedule
./scripts/install_cron.sh uninstall
```

Cache: `~/.insight_alpha/kite_token.json` (today's access_token, reused all day). Logs: `~/.insight_alpha/auto_login.log`.

### How it works

1. Playwright launches Chromium and navigates to your Kite Connect login URL.
2. Fills user_id + password → submits.
3. Generates a fresh 6-digit code via `pyotp.TOTP(secret).now()` → submits.
4. **Intercepts the redirect** to your app's configured callback URL via a Playwright route handler + context-level request/response listeners. This means the login works even if your Kite app's registered redirect URI (e.g. `http://127.0.0.1:8000/...`) isn't reachable — the script captures `request_token` from the URL query string before the browser actually tries to fetch it.
5. Hands `request_token` to the existing `KiteClient.authenticate()` which exchanges it for an `access_token` and caches it to disk.
6. `python start.py` / `python -m src.main` then start with zero prompts.

### Security

- `.env` must be `chmod 600` and is already in `.gitignore`.
- The script normalizes the TOTP secret (strips whitespace/dashes, uppercases, right-pads to a multiple of 8) — it does *not* correct transcription errors like `0`/`O`.
- On failure, error messages are truncated in the log (`error[:200]`) and do not contain credentials.
- Two retries max per run, then exits non-zero — so launchd surfaces the failure instead of silently hammering and risking account lockout.

### Caveats

- Automated Kite login violates Zerodha's developer terms. Enforcement is rare but the risk (account freeze) is yours.
- If Zerodha changes the login-page DOM, the script's selectors may need updating — they target stable attributes (`input[type='text']`, `input[type='password']`, `input[type='number']`, `button[type='submit']`) so drift should be minor.
- TOTP codes rotate every 30 seconds; if your machine clock is off by more than ~1 minute, codes will be rejected. Sync system time (`sudo sntp -sS time.apple.com` on macOS).

### Skipping this

To keep using manual dashboard OAuth, just don't set `KITE_USER_ID` / `KITE_PASSWORD` / `KITE_TOTP_SECRET`. The rest of the app is unaffected.

## License

Private — Not for redistribution.
