# Insight-Alpha 2026 — AI Trading Agent

## Project Overview

AI-powered equity trading agent for Indian markets via Zerodha Kite Connect. Multi-agent system (Researcher, Sentinel, Orchestrator, Stitch) that analyzes news, macro, and technical signals to produce high-confidence directional theses.

**Modes:** Paper trading (default) and live trading. Paper mode uses real market data with simulated execution. Live mode places real orders via Kite Connect.

**Approval Workflow:** Signals are not auto-executed. They go to a pending queue, user approves via Telegram buttons or the web dashboard. Primary action: BUY & Auto-Sell (executes + AI-managed exit). Also: Manual BUY (user-managed exit), Ignore.

## Architecture

```
Data Pipeline -> Indicators -> Strategies -> AI Agents -> Scoring -> Filtering -> Risk
    -> Pending Queue -> User Approval (Telegram/Dashboard) -> Execution -> Auto-Sell Monitor
```

- **4 AI Agents:** Researcher (sentiment), Sentinel (counter-signals), Orchestrator (scoring + summary), Stitch (consensus)
- **Alpha scoring is deterministic Python** — Claude is used only for interpreting unstructured data (news) and generating summaries
- **Paper/Live switch:** Single config value `execution.mode`. Same code path, different broker implementation.
- **Approval-based execution:** Signals queue for user approval via Telegram inline buttons or dashboard
- **Auto-Sell:** AI-defined exit triggers (stop, target, trailing stop, time, confidence decay, structure break) — no human intervention after enabling
- **GTT Exchange Protection:** Zerodha GTT OCO orders provide exchange-level stop loss + target that survive app crashes. App handles trailing stop, time, confidence, and structure break exits via software monitoring.

## Tech Stack

- Python 3.11+, `kiteconnect` (Zerodha), `anthropic` (Claude API)
- `pandas`/`numpy` for data, `pydantic` for config validation, `SQLAlchemy` for DB
- `FastAPI` + `Jinja2` for web dashboard, `uvicorn` for ASGI server
- SQLite (paper) / PostgreSQL (live), `APScheduler` for market-hours loop
- `structlog` for structured JSON logging
- Telegram Bot API for interactive push notifications with inline keyboards

## Project Structure

- `config/` — YAML configs (default.yaml, paper.yaml, live.yaml, strategies/, watchlist.yaml)
- `src/data/` — Kite Connect client, market data, WebSocket, news, macro, fundamentals
- `src/indicators/` — Technical indicators as pure functions (RSI, EMA, ATR, MACD, etc.)
- `src/strategies/` — 8 strategy implementations extending abstract `Strategy` base class
- `src/agents/` — Claude-powered AI agents (Researcher, Sentinel, Orchestrator, Stitch)
- `src/scoring/` — Alpha model, filters, ranking, sentiment decay
- `src/regime/` — HMM-based market regime detection
- `src/risk/` — Guardrails, position sizing, portfolio tracker, kill switch
- `src/execution/` — Broker ABC, paper broker, live broker, order manager, auto-exit, **auto-sell manager**
- `src/notifications/` — Telegram with interactive buttons (free, recommended), WhatsApp (Twilio)
- `src/storage/` — SQLAlchemy ORM (7 tables), persistence layer (positions, triggers, pending signals, app state)
- `src/feedback/` — Performance tracking and reporting
- `src/web/` — FastAPI dashboard (Kite OAuth, engine control, approval workflow, portfolio view)
- `tests/` — unit/, integration/, backtest/

## Coding Conventions

- **Indicators are pure functions**, not classes: `compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series`
- **Strategies extend `Strategy` ABC** with `scan()` and `check_exit()` methods
- **All config via pydantic models** — runtime validation on every value
- **Use `structlog`** for all logging — structured JSON, never print()
- **Type hints everywhere** — all function signatures fully typed
- **No TA-Lib** — custom indicator implementations using pandas/numpy only
- **Risk checks before every order** — never bypass guardrails
- **Signals require user approval** — never auto-execute without user action

## Risk Guardrails (Never Bypass)

All 4 checks must pass before any order placement:
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

**Notification format:** Stock, Recommendation, Entry/Target/Stop with expected return %, Horizon (Short Term 1-3d / Medium Term 4-10d), Rationale (AI summary + drivers + risks).

**Auto-Sell exit conditions** (all monitored continuously, first to trigger exits):

*Exchange-level (GTT OCO — survives app crashes):*
1. Hard stop loss
2. Target price

*Software-level (app monitoring — intelligent exits):*
3. Trailing stop (% from peak, protects gains; updates GTT stop leg as it improves)
4. Time-based exit (holding window expired)
5. Structure break (price reversal with volume spike)
6. Confidence decay (AI confidence drops below floor)

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
```

## Available Skills (in .claude/skills/)

These Claude Code skills are loaded on-demand for specialized trading analysis:

- **backtest-expert** — Systematic backtesting guidance, robustness testing, overfitting prevention
- **macro-regime-detector** — Cross-asset regime detection (concentration/broadening/contraction)
- **market-news-analyst** — Analysis of market-moving news events, impact ranking
- **position-sizer** — Risk-based position sizing (Fixed Fractional, ATR, Kelly Criterion)
- **signal-postmortem** — Post-trade analysis of signals vs outcomes
- **technical-analyst** — Chart-based technical analysis, trend/support/resistance identification

## Important Notes

- Market hours: 09:15 - 15:30 IST
- Kite access tokens expire daily — web dashboard handles OAuth login automatically
- Kite rate limits: 3 req/s (historical data), 10 req/s (other endpoints)
- Paper broker never calls Kite order APIs — only uses LTP for simulated fills
- Sentiment decay: 15% reduction to news_strength every 30 minutes
- Macro guard: Cap bullish confidence at 0.6 when market regime = bear
- Auto-sell triggers are per-position and deactivate after exit
- GTT OCO orders placed on exchange for every auto-sell position (stop loss + target)
- GTT trailing stop updates are rate-limited: 0.5% improvement threshold + 60s cooldown
- On startup, GTT reconciliation checks exchange status and re-places for unprotected positions
- Paper mode simulates GTT in-memory; live mode uses real Kite GTT APIs
- Telegram callback polling runs in a daemon thread, receives button presses in real-time
- Pending signals expire after 15 minutes if no user action
- Design principle: "Eliminate bad trades, not predict markets"
- Priority hierarchy: Risk > Regime > Factors > Discipline > Sentiment > Technicals
