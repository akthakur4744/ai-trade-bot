# Insight-Alpha 2026 — AI Trading Agent

## Project Overview

AI equity trading agent, Indian markets via Zerodha Kite Connect. Multi-agent (Researcher, Sentinel, Orchestrator, Stitch): analyzes news, macro, technical signals → high-confidence directional theses.

**Modes:** Paper (default) + live. Paper = real data, simulated fills. Live = real orders via Kite.

**Approval Workflow:** Signals → pending queue → user approves via Telegram buttons or web dashboard. Actions: BUY & Auto-Sell (execute + AI-managed exit), Manual BUY (user-managed exit), Ignore.

## Architecture

```
Data Pipeline -> Indicators -> Strategies -> AI Agents -> Scoring -> Filtering -> Risk
    -> Pending Queue -> User Approval (Telegram/Dashboard) -> Execution -> Auto-Sell Monitor
```

- **4 AI Agents:** Researcher (sentiment), Sentinel (counter-signals), Orchestrator (scoring + summary), Stitch (consensus)
- **Alpha scoring is deterministic Python** — Claude only for unstructured data (news) + summaries
- **Paper/Live switch:** Single config value `execution.mode`. Same code path, different broker impl.
- **Approval-based execution:** Signals queue → user approves via Telegram inline buttons or dashboard
- **Auto-Sell:** AI-defined exit triggers (stop, target, trailing stop, time, confidence decay, structure break) — no human after enabling
- **GTT Exchange Protection:** Zerodha GTT OCO = exchange-level stop+target, survives crashes. App handles trailing stop, time, confidence, structure break via software.

## Tech Stack

- Python 3.11+, `kiteconnect` (Zerodha), `anthropic` (Claude API)
- `pandas`/`numpy` for data, `pydantic` for config validation, `SQLAlchemy` for DB
- `FastAPI` + `Jinja2` web dashboard, `uvicorn` ASGI
- SQLite (paper) / PostgreSQL (live), `APScheduler` for market-hours loop
- `structlog` structured JSON logging
- Telegram Bot API: interactive push notifications + inline keyboards

## Project Structure

- `config/` — YAML configs (default.yaml, paper.yaml, live.yaml, strategies/, watchlist.yaml)
- `src/data/` — Kite client, market data, WebSocket, news, macro, fundamentals
- `src/indicators/` — Technical indicators as pure functions (RSI, EMA, ATR, MACD, etc.)
- `src/strategies/` — 8 strategies extending abstract `Strategy` base class
- `src/agents/` — Claude-powered agents (Researcher, Sentinel, Orchestrator, Stitch)
- `src/scoring/` — Alpha model, filters, ranking, sentiment decay
- `src/regime/` — HMM-based market regime detection
- `src/risk/` — Guardrails, position sizing, portfolio tracker, kill switch
- `src/execution/` — Broker ABC, paper broker, live broker, order manager, auto-exit, **auto-sell manager**
- `src/notifications/` — Telegram w/ interactive buttons (free, recommended), WhatsApp (Twilio)
- `src/storage/` — SQLAlchemy ORM (7 tables): positions, triggers, pending signals, app state
- `src/feedback/` — Performance tracking + reporting
- `src/web/` — FastAPI dashboard (Kite OAuth, engine control, approval workflow, portfolio view)
- `tests/` — unit/, integration/, backtest/

## Coding Conventions

- **Indicators are pure functions**, not classes: `compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series`
- **Strategies extend `Strategy` ABC** with `scan()` and `check_exit()` methods
- **All config via pydantic models** — runtime validation on every value
- **Use `structlog`** — structured JSON, never print()
- **Type hints everywhere** — all signatures fully typed
- **No TA-Lib** — custom indicators via pandas/numpy only
- **Risk checks before every order** — never bypass guardrails
- **Signals require user approval** — never auto-execute without user action

## Risk Guardrails (Never Bypass)

All 4 must pass before any order:
1. Order size <= max_capital_per_trade (10,000 INR)
2. Total deployed <= max_capital_deployed (30,000 INR)
3. Realized PnL > -max_daily_loss (1,000 INR)
4. Open positions < max_open_positions (3)

## Approval Workflow

```
Engine finds signal -> Pending Queue -> Telegram notification (with action buttons)
  - [BUY & Auto-Sell] -> Execute + AI creates exit triggers, auto-exits when conditions met (recommended)
  - [Manual BUY]      -> Execute, user manages exit manually
  - [Ignore]          -> Signal discarded
  - No action 15min   -> Signal expires
```

**Notification format:** Stock, Recommendation, Entry/Target/Stop + expected return %, Horizon (Short Term 1-3d / Medium Term 4-10d), Rationale (AI summary + drivers + risks).

**Auto-Sell exit conditions** (all monitored continuously, first triggers exit):

*Exchange-level (GTT OCO — survives crashes):*
1. Hard stop loss
2. Target price

*Software-level (intelligent exits):*
3. Trailing stop (% from peak, protects gains; updates GTT stop leg on improvement)
4. Time-based exit (holding window expired)
5. Structure break (price reversal + volume spike)
6. Confidence decay (AI confidence below floor)

## Key Formulas

**Alpha Score:**
```
confidence = (news_strength * 0.25) + (signal_alignment * 0.30) + (market_confirmation * 0.25) + (liquidity_score * 0.10) - (risk_penalty * 0.20)
```

**Filters (all must pass):** confidence >= 0.65, market_confirmation >= 0.6, liquidity_score >= 0.6, risk_penalty <= 0.4

**Ranking:**
```
final_score = (confidence * 0.4) + (signal_alignment * 0.3) + (market_confirmation * 0.2) + (news_strength * 0.1)
```

## Commands

```bash
# Start web dashboard (recommended — handles Kite auth + engine control)
python start.py

# Run the agent standalone (paper mode, requires pre-auth)
python -m src.main

# Run tests
pytest tests/

# Run linter
ruff check src/ tests/

# Backtest a strategy
python scripts/backtest_cli.py --strategy mean_reversion --period 2y

# Kite auth (manual — use dashboard instead)
python scripts/kite_auth.py

# Kite auto-login (fully automated daily login via External TOTP + headless browser)
# Requires: External 2FA TOTP enabled in Kite profile; KITE_USER_ID, KITE_PASSWORD,
# KITE_TOTP_SECRET in .env; `playwright install chromium` run once.
# ToS caveat: automated Kite login violates Zerodha ToS — use at your own risk.
python scripts/kite_auto_login.py              # headless; idempotent (no-op if cached)
python scripts/kite_auto_login.py --headed     # debug (visible browser; 30s pause on error)
./scripts/install_cron.sh                      # install launchd schedule (Mon-Fri 08:55 local)
./scripts/install_cron.sh uninstall            # remove the schedule
launchctl start com.insightalpha.kiteauth      # dry-run the scheduled job immediately
tail -f ~/.insight_alpha/auto_login.log        # watch scheduler output
```

## Available Skills (in .claude/skills/)

Claude Code skills, loaded on-demand for trading analysis:

- **backtest-expert** — Systematic backtesting, robustness testing, overfitting prevention
- **macro-regime-detector** — Cross-asset regime detection (concentration/broadening/contraction)
- **market-news-analyst** — Market-moving news analysis, impact ranking
- **position-sizer** — Risk-based sizing (Fixed Fractional, ATR, Kelly Criterion)
- **signal-postmortem** — Post-trade analysis: signals vs outcomes
- **technical-analyst** — Chart-based analysis, trend/support/resistance

## Memory System & Self-Improvement Loop

Curated markdown memory at `memory/` sits on top of the SQL layer and drives continuous learning. Every write is **Telegram-gated** — no file here is ever edited without explicit user approval.

**Files** (cadence / reader):
- `memory/PROJECT-CONTEXT.md` — static mission, read on every agent startup (rarely updated)
- `memory/TRADING-STRATEGY.md` — binding rulebook; rules graduate here from LEARNINGS.md (weekly, on approval)
- `memory/LEARNINGS.md` — distilled patterns, ≥2-occurrence promotion (weekly, on approval)
- `memory/MISTAKES.md` — append-only raw postmortems (per-trade, on approval)
- `memory/WEEKLY-REVIEW.md` — Friday retrospectives with letter grade (weekly, on approval)

**Flow:**
```
Trade closes → PostmortemAgent drafts MISTAKES/LEARNINGS/STRATEGY diffs via Claude
            → row inserted in `pending_memory_updates` table
            → Telegram message with [Approve & Commit] [Reject] buttons (60-min expiry)
            → Approve: MemoryWriter applies diffs + git commit + push, message edited to "Committed <sha>"
            → Reject: no file changes, message edited to "Rejected"
            → No action in 60 min: sweeper marks `expired`, message edited accordingly
Friday 15:40 IST → WeeklyReviewAgent drafts WEEKLY-REVIEW / LEARNINGS / STRATEGY diffs → same Telegram gate
```

**Rules (never bypass):**
- **No Claude agent may edit `memory/*.md` directly.** All writes go through `src/feedback/memory_writer.py::MemoryWriter`, which is only invoked by `src/feedback/postmortem_pipeline.py::PostmortemPipeline.handle_memory_callback()` after a Telegram approve.
- Orchestrator + Researcher read `TRADING-STRATEGY.md` and `LEARNINGS.md` into their system prompts at init time (`src/feedback/memory_context.py::build_memory_context()`). Any active rule or pattern must drop confidence by 0.1 and be cited in `key_drivers`/`risks` when a signal contradicts it.
- Config-value changes suggested by the weekly review open a PR — they are **not** auto-merged into `config/*.yaml`.
- `MISTAKES.md` + `LEARNINGS.md` are append-only with dedup on the first line of each section. `TRADING-STRATEGY.md` inserts under `## Active Rules`.

**Slash commands** (`.claude/commands/`):
- `/postmortem <order_id>` — manual postmortem (routes through approval flow)
- `/weekly-review` — run the Friday review on demand
- `/promote-learning "<pattern>"` — manual pattern promotion

**Key modules:**
- `src/feedback/postmortem_agent.py` — Claude-backed draft
- `src/feedback/postmortem_pipeline.py` — pipeline glue + callback handler
- `src/feedback/memory_writer.py` — the **only** writer to `memory/*.md`
- `src/feedback/memory_context.py` — injects memory into agent prompts
- `src/feedback/weekly_review_agent.py` — Friday review draft
- `src/storage/models.py::PendingMemoryUpdate` — approval-queue table
- `src/notifications/telegram.py::send_memory_update_for_approval` — approval UI

## Important Notes

- Market hours: 09:15 - 15:30 IST
- Kite tokens expire daily (SEBI mandate) — dashboard handles OAuth manually; `scripts/kite_auto_login.py` + External TOTP automates it fully. Script captures `request_token` via Playwright route interception + context request/response listeners, so it works even when the Kite app's configured redirect URI is unreachable. Token cache: `~/.insight_alpha/kite_token.json`.
- Kite rate limits: 3 req/s (historical), 10 req/s (other)
- Paper broker never calls Kite order APIs — LTP only for simulated fills
- Sentiment decay: 15% reduction to news_strength every 30min
- Macro guard: cap bullish confidence at 0.6 when regime = bear
- Auto-sell triggers per-position, deactivate after exit
- GTT OCO placed on exchange for every auto-sell position (stop + target)
- GTT trailing stop updates rate-limited: 0.5% improvement threshold + 60s cooldown
- On startup: GTT reconciliation checks exchange status, re-places for unprotected positions
- Paper mode simulates GTT in-memory; live uses real Kite GTT APIs
- Telegram callback polling: daemon thread, receives button presses real-time
- Pending signals expire after 15min with no action
- Design principle: "Eliminate bad trades, not predict markets"
- Priority: Risk > Regime > Factors > Discipline > Sentiment > Technicals