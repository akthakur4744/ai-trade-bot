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

**One-time setup:**
1. Kite web → Profile → Settings → Account → enable **External 2FA TOTP**. Scan the QR in Google Authenticator / Authy **and copy the 32-char secret**.
2. Add to `.env` (keep `chmod 600`):
   ```
   KITE_USER_ID=your_client_id
   KITE_PASSWORD=your_password
   KITE_TOTP_SECRET=the_32_char_secret
   ```
3. Install Playwright browser once: `playwright install chromium`.

**Daily automation:**
```bash
python scripts/kite_auto_login.py              # headless run; idempotent
./scripts/install_cron.sh                       # schedule Mon–Fri 08:55 local
```
Logs: `~/.insight_alpha/auto_login.log`.

**Caveat:** Zerodha's developer terms disallow automated login. Enforcement is rare but the risk (account freeze) is yours. Omit this section to keep using manual dashboard OAuth.

## License

Private — Not for redistribution.
