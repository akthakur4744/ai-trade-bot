# Insight-Alpha 2026 — Architecture

## Overview

Insight-Alpha is a multi-agent AI trading system for Indian equity markets. It combines deterministic technical analysis with LLM-driven interpretation to produce high-confidence, risk-controlled trade decisions.

**Design principle:** "Eliminate bad trades, not predict markets."

---

## System Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                             │
│   Kite Connect (OHLCV, LTP, WebSocket)  │  News RSS Feeds       │
│   Macro Indicators (Nifty, VIX)         │  Fundamental Data      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      REGIME DETECTION                            │
│  HMM-based market state classification (bull/bear/sideways)      │
│  Blocks strategies incompatible with current regime              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       STRATEGIES (8)                             │
│  MeanReversion │ Momentum │ BollingerSqueeze │ GoldenCross       │
│  VWAPReversion │ FundamentalTechnical │ PairsTrading │ Seasonal  │
│                                                                   │
│  Each strategy: scan(symbol, data) → StrategySignal | None       │
│  Each strategy: check_exit(position, data) → ExitSignal | None   │
└────────────────────────┬────────────────────────────────────────┘
                         │  raw signals
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AI AGENT PIPELINE                            │
│                                                                   │
│  1. Researcher  — Analyzes news against watchlist symbols         │
│     → news_strength, sentiment, catalyst_type                     │
│                                                                   │
│  2. Sentinel    — Identifies counter-signals and risks            │
│     → risk_flags, veto_reasons, confidence_penalty                │
│                                                                   │
│  3. Orchestrator — Scores and summarizes all signals              │
│     → confidence_breakdown, narrative, alpha_score                │
│                                                                   │
│  4. Stitch      — Consensus + dedup + cross-strategy ranking      │
│     → final ranked ScoredSignal list                              │
└────────────────────────┬────────────────────────────────────────┘
                         │  ScoredSignal[]
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SCORING & FILTERING                          │
│                                                                   │
│  Alpha Score:                                                     │
│    confidence = (news_strength × 0.25) + (signal_alignment × 0.30)│
│              + (market_confirmation × 0.25) + (liquidity × 0.10)  │
│              - (risk_penalty × 0.20)                              │
│                                                                   │
│  All filters must pass:                                           │
│    confidence ≥ 0.65  │  market_confirmation ≥ 0.6               │
│    liquidity ≥ 0.6    │  risk_penalty ≤ 0.4                       │
│                                                                   │
│  Ranking: confidence×0.4 + alignment×0.3 + confirmation×0.2      │
│         + news×0.1                                                │
└────────────────────────┬────────────────────────────────────────┘
                         │  filtered + ranked signals
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     RISK GUARDRAILS                              │
│                                                                   │
│  All 4 checks must pass — no exceptions:                          │
│  1. Order size ≤ ₹10,000 (max_capital_per_trade)                  │
│  2. Total deployed ≤ ₹30,000 (max_capital_deployed)               │
│  3. Realized PnL > -₹1,000 (max_daily_loss)                       │
│  4. Open positions < 3 (max_open_positions)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │  approved orders
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       EXECUTION                                  │
│                                                                   │
│  Paper Broker  — Simulated fills at LTP + slippage (5 bps)       │
│  Live Broker   — Real Kite Connect orders (NSE, MIS product)      │
│                                                                   │
│  Same code path — broker is swapped via config                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   APPROVAL WORKFLOW                               │
│                                                                   │
│  Pending Queue → Telegram notification with inline buttons        │
│    [🤖 BUY & Auto-Sell]  [✅ Manual BUY]  [❌ Ignore]             │
│  Dashboard also shows pending signals with same action buttons    │
│  Signals expire after 15 min if no user action                    │
└────────────────────────┬────────────────────────────────────────┘
                         │  user-approved orders
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       EXECUTION                                  │
│                                                                   │
│  Paper Broker  — Simulated fills at LTP + slippage (5 bps)       │
│  Live Broker   — Real Kite Connect orders (NSE, MIS product)      │
│                                                                   │
│  Same code path — broker is swapped via config                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AUTO-SELL MONITOR                               │
│                                                                   │
│  When user selects "Auto-Sell":                                   │
│    1. GTT OCO placed on exchange (stop loss + target)             │
│    2. Fly.io worker calls tick_auto_sell() every 60s              │
│                                                                   │
│  Exchange (GTT) — crash-safe, survives process death:             │
│    • Hard stop loss                                               │
│    • Target price                                                 │
│  Software (Fly.io always-on worker, 60s cadence):                │
│    • Trailing stop (updates GTT stop as it improves)              │
│    • Time-based exit (holding window expired)                     │
│    • Structure break (price reversal + volume spike)              │
│    • Confidence decay (AI confidence below floor)                 │
│                                                                   │
│  First trigger to fire → auto-exit. GTT cancelled on app exit.    │
│  Worker reloads trigger dict from DB each tick (cross-process     │
│  sync with telegram-poll Routine that writes new triggers).       │
│  User notified with reason, PnL, via (exchange/software).         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     NOTIFICATIONS                                │
│  Telegram Bot (interactive inline keyboards, free)               │
│  WhatsApp via Twilio (optional, paid)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Module Map

| Directory | Responsibility |
|-----------|---------------|
| `src/data/` | Kite Connect client, OHLCV fetcher, WebSocket, news/macro/fundamentals, `universe_selector` (daily dynamic stock scoring) |
| `src/indicators/` | Pure functions: RSI, EMA, ATR, MACD, Bollinger, VWAP, ADX, Stochastic |
| `src/strategies/` | 8 strategy implementations extending `Strategy` ABC |
| `src/agents/` | 4 Claude-powered agents: Researcher, Sentinel, Orchestrator, Stitch |
| `src/scoring/` | Alpha model, filters, ranking, sentiment decay |
| `src/regime/` | HMM-based market regime detector |
| `src/risk/` | Guardrails, position sizing (fixed/ATR/Kelly), portfolio, kill switch |
| `src/execution/` | Broker ABC, PaperBroker, LiveBroker, OrderManager, AutoExitMonitor, AutoSellManager |
| `src/notifications/` | Telegram (interactive inline keyboards) and WhatsApp (Twilio) notifiers |
| `src/web/` | FastAPI dashboard, Kite OAuth flow, engine control, approval workflow APIs |
| `src/storage/` | SQLAlchemy ORM (9 tables + Alembic migrations), Supabase Postgres (paper/live DBs); SQLite retained as offline-dev fallback |
| `src/feedback/` | PostmortemAgent, PostmortemPipeline, MemoryWriter (Telegram-gated), MemoryContext, WeeklyReviewAgent, FeedbackTracker, Reporter |
| `config/` | YAML configs: default, paper, live, strategies/, watchlist.yaml (30 core), extended_universe.yaml (105 dynamic candidates) |
| `scripts/` | CLI tools: kite_auth.py (manual daily OAuth), kite_auto_login.py (local debug only — NOT automated login), backtest_cli.py |
| `workers/` | Fly.io combined entrypoint (`main.py`): auto-sell tick daemon thread (60s) + FastAPI trigger API on port 8080 (`trigger_api.py`) |
| `routines/` | Cloud Routine definitions: morning-login-prompt, signal-scan, telegram-poll, heartbeat, memory-approval-sweeper, etc. All routines make HTTPS-only calls — no direct DB access from signal-scan, telegram-poll, or memory-approval-sweeper |
| `cloudflare-worker/` | Kite OAuth callback + HTTPS proxy for CCR routines: `/heartbeat/state`, `/memory/sweep` (GET + POST) |
| `tests/` | unit/, integration/, backtest/ |

---

## AI Agent Architecture

### Why 4 Agents?

A single monolithic prompt produces inconsistent results and misses adversarial angles. The 4-agent pipeline enforces separation of concerns:

```
Researcher  →  "What is the news saying?"
               Sentiment analysis, catalyst identification, news_strength score

Sentinel    →  "What could go wrong?"
               Counter-signals, risk flags, sector headwinds, why NOT to trade

Orchestrator → "What is the final verdict?"
               Synthesizes all inputs → alpha score + confidence breakdown + narrative

Stitch      →  "After dedup and ranking, what do we execute?"
               Cross-signal consensus, sector diversification, final ranked list
```

### Agent Tool Use

All agents use Claude's `tool_use` feature for **structured JSON output** — never free-text parsing:

```python
# Example: Orchestrator tool definition
SCORE_SIGNAL_TOOL = {
    "name": "score_signal",
    "input_schema": {
        "type": "object",
        "properties": {
            "confidence": {"type": "number"},
            "confidence_breakdown": {...},
            "narrative": {"type": "string"},
            "veto": {"type": "boolean"},
        }
    }
}
```

---

## Data Flow — Timing

```
08:55 IST  — morning-login-prompt Routine: post Telegram link for manual Kite OAuth
09:00 IST  — pre-market-check Routine: macro snapshot, watchlist health
09:10 IST  — load_instruments(): Fetch Kite instrument tokens for watchlist (inside signal-scan)
             — reconcile_gtt_on_startup(): Check GTT status on exchange, re-place if needed
09:15 IST  — Market opens
Every 60s  — Fly.io auto-sell-tick worker: tick_auto_sell()
               → re-auth Kite (reads token from Supabase app_state)
               → reload trigger dict from DB (syncs with telegram-poll engine)
               → check software exit conditions (trailing, time, structure, confidence)
               → update GTT stop leg if trailing stop improved (rate-limited)
               → write last_autosell_tick_ts heartbeat to app_state
Every hour — signal-scan Cloud Routine: run_cycle()
               → expire pending signals older than 15 min
               → fetch macro + news
               → refresh dynamic universe (once/day: score 105 candidates → pick top 20)
               → scan strategies across 30 core + 20 dynamic = 50 symbols
               → AI pipeline (Researcher → Sentinel → Orchestrator → Stitch)
               → filter + rank → risk check
               → queue signals for user approval (Telegram + Dashboard)
               → check exits on non-auto-sell positions
Continuous — telegram-poll Cloud Routine: receives button presses
               → BUY & Auto-Sell: execute order + create exit triggers
               → Manual BUY: execute order, user manages exit
               → Ignore: discard signal
               → Memory approval: apply diffs → open GitHub PR
15:15 IST  — Auto-exit: close MIS positions approaching EOD
15:35 IST  — send_daily_summary(): PnL, win rate, regime, notifications
```

---

## Execution Modes

### Paper Mode (`execution.mode: paper`)
- Uses real Kite market data (quotes, candles)
- Simulates fills at LTP + 5 bps slippage
- No real Kite order APIs called
- Tracks virtual portfolio in SQLite
- Default mode — use for validation

### Live Mode (`execution.mode: live`)
- Places real orders via `kite.place_order()`
- Requires `CONFIRM_LIVE_TRADING=true` env var
- Same strategy/risk code path as paper
- Only the broker implementation differs

---

## Approval Workflow

Signals are never auto-executed. The system uses an approval-based workflow:

```
Signal found → PendingSignal created → Telegram notification sent with inline keyboard
                                        ├── [🤖 BUY & Auto-Sell] → Execute + AI exit triggers (recommended)
                                        ├── [✅ Manual BUY]       → Execute, manual exit
                                        └── [❌ Ignore]           → Signal discarded

No action within 15 min → Signal expires → User notified
```

**Dashboard also shows pending signals** with the same 3 action buttons, enabling approval from either Telegram or the web interface.

**Telegram Notification Contents:**
- Stock name and Recommendation (BUY/SELL)
- Entry / Stop Loss / Target prices with expected return %
- Horizon: Short Term (1-3 days) or Medium Term (4-10 days)
- Rationale: AI-generated summary with drivers and risks
- Action buttons: BUY & Auto-Sell (primary) | Manual BUY | Ignore

---

## Auto-Sell System

When a user selects "Auto-Sell" on a signal, the system creates AI-defined exit triggers and monitors the position continuously with zero human intervention.

### Exit Conditions (first to trigger wins)

| Condition | Description | Priority |
|-----------|-------------|----------|
| Stop Loss | Hard stop at signal's stop_loss price | HIGH |
| Target | Profit booking at calculated target price | LOW |
| Trailing Stop | % from peak price (protects gains, only fires above entry) | MEDIUM |
| Time-Based | Holding window expired (intraday: 90min, swing: 8h) | MEDIUM |
| Structure Break | Price reversal with >1.5x volume spike | HIGH |
| Confidence Decay | Re-scored AI confidence drops below floor | MEDIUM |

### How Trailing Stop Works

```
Entry: ₹2500  |  Trailing: 1.5%  |  Peak tracks highest price

Price rises to ₹2580 → trailing stop at ₹2541 (2580 × 0.985)
Price rises to ₹2620 → trailing stop moves up to ₹2581
Price drops to ₹2575 → trailing stop holds at ₹2581 → EXIT TRIGGERED
```

Trailing stop only activates when price is above entry (protecting gains, not cutting losses early — that's the hard stop loss's job).

### Exit Notification

When any exit condition triggers, the user receives:
- Reason for exit (stop loss / target / trailing / time / structure / confidence)
- Urgency level (HIGH / MEDIUM / LOW)
- Exit details (entry price, exit price, PnL, quantity)
- Full execution details

### GTT Exchange-Level Protection

When auto-sell is enabled, the system places a **GTT OCO (Good Till Triggered, One Cancels Other)** order on the Zerodha exchange. This provides a dual-layer protection model:

```
┌─────────────────────────────────────────────────────────────────┐
│              DUAL PROTECTION MODEL                               │
│                                                                   │
│  EXCHANGE (Zerodha GTT OCO) — Safety Net                         │
│    ✓ Hard stop loss    — survives app crash                       │
│    ✓ Target price      — survives app crash                       │
│    ✓ Runs on exchange  — zero dependency on our app               │
│                                                                   │
│  APP (Software Monitoring) — Intelligence Layer                   │
│    ✓ Trailing stop     — moves with price, updates GTT stop leg   │
│    ✓ Time-based exit   — holding window expired                   │
│    ✓ Structure break   — price reversal + volume spike            │
│    ✓ Confidence decay  — AI re-scoring below floor                │
│                                                                   │
│  When app exits first → cancels GTT on exchange                   │
│  When GTT triggers first → app detects via status poll            │
└─────────────────────────────────────────────────────────────────┘
```

**GTT Trailing Stop Updates:**
- As trailing stop improves, the GTT stop leg is updated on exchange
- Rate-limited: only updates if improvement ≥ 0.5% AND cooldown ≥ 60s elapsed
- State machine: PENDING → ACTIVE → UPDATING → ACTIVE (or TRIGGERED/CANCELLED)

**Startup Reconciliation:**
- On restart, loads persisted GTT state from database
- Checks each GTT's status on exchange via API
- TRIGGERED → handles as exchange exit (no new order needed)
- CANCELLED/EXPIRED/NOT_FOUND → re-places GTT for unprotected positions
- ACTIVE → resumes normal monitoring

**Paper vs Live:**
- Paper mode: GTT simulated in-memory (stored in broker's `_orders` dict)
- Live mode: Real Kite GTT APIs (`place_gtt`, `modify_gtt`, `delete_gtt`, `get_gtt`)

**Configuration** (`execution.auto_sell` in config):
| Setting | Default | Description |
|---------|---------|-------------|
| `gtt_enabled` | `true` | Place GTT OCO on exchange for auto-sell positions |
| `gtt_update_threshold_pct` | `0.5` | Min trailing stop improvement % before updating GTT |
| `gtt_update_cooldown_sec` | `60` | Min seconds between GTT updates for same position |
| `gtt_max_retries` | `3` | Retry count for GTT placement failures |

### Safety Controls

- Auto-sell only activates after explicit user consent (button tap)
- Works within all configured risk guardrails
- Can be disabled per trade (choose Manual BUY instead of BUY & Auto-Sell)
- Auto-sell trigger deactivates after exit
- GTT on exchange provides crash-safe stop loss + target protection
- GTT state persisted to database — survives app restarts

---

## Web Dashboard

FastAPI + Jinja2 dashboard at `http://127.0.0.1:8000`:

| Feature | Description |
|---------|-------------|
| Kite OAuth | One-click Zerodha login via `/auth/login` → `/auth/callback` |
| Engine Control | Start/Stop engine, run single cycle manually |
| Pending Signals | Cards with signal analysis + BUY & Auto-Sell / Manual BUY / Ignore buttons |
| Auto-Sell Monitor | Active triggers with stop/target/trailing levels, time remaining |
| Market Insights | Macro context, news sentiment, AI research, risk assessment |
| Portfolio | Open positions with PnL, exit management type (Auto/Manual) |
| Activity Log | Real-time alerts, trade confirmations, errors |
| Signals Table | Recent signals with confidence, scores, price levels |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Engine status, cycle count, pending/auto-sell counts |
| GET | `/api/pending` | Pending signals awaiting approval |
| POST | `/api/signals/{id}/action` | Approve / Auto-Sell / Ignore a signal |
| GET | `/api/auto-sell` | Active triggers and recent auto-sell events |
| GET | `/api/portfolio` | Positions, PnL, auto-sell details per position |
| GET | `/api/insights` | Latest cycle insights (macro, news, research, scoring) |
| GET | `/api/signals` | Recent signals history |
| GET | `/api/trades` | Recent trades history |
| GET | `/api/alerts` | Activity log |

---

## Persistence Layer

All critical runtime state is persisted to the database and restored on application restart.

### Database Tables (9)

**Core tables** (trade lifecycle):
- `signals` — Generated trading signals with confidence breakdowns
- `trades` — Executed trades with entry/exit prices, PnL, exit reasons
- `daily_metrics` — Daily aggregate performance (win rate, profit factor, Sharpe)

**State tables** (survive restarts):
- `position_state` — Open positions (symbol, direction, quantity, prices, order_id)
- `auto_sell_trigger_state` — Active AI exit triggers (stop/target/trailing, price tracking, `created_at`, GTT trigger ID/status/stop price)
- `pending_signal_state` — Signals awaiting user approval (ScoredSignal serialized as JSON)
- `app_state` — Key-value store for kill switch state, portfolio counters, Kite token, heartbeat timestamps

**Memory approval table:**
- `pending_memory_updates` — Approved memory diffs queued for Telegram gate → GitHub PR flow

### What Survives a Restart

| State | Mechanism |
|-------|-----------|
| Open positions | Loaded from `position_state`, cross-checked against trades table |
| Auto-sell triggers | Loaded from `auto_sell_trigger_state` with preserved `created_at`, price tracking, and GTT state |
| GTT exchange orders | Reconciled against Zerodha exchange on startup; re-placed if missing/expired |
| Pending signals | Loaded from `pending_signal_state`, expired signals skipped |
| Kill switch | Loaded from `app_state`; if triggered today, restored; otherwise natural day reset |
| Daily PnL counters | Loaded from `app_state`; if different day, reconstructed from trades |
| Total realized PnL | Loaded from `app_state`; first-run fallback: `SUM(trades.pnl)` |
| Trade history (feedback) | Reconstructed from `trades` table on startup |
| Dashboard state | Repopulated from `signals` and `trades` tables on engine start |

Two separate Supabase Postgres projects are used — one per execution mode (`DATABASE_URL_PAPER`, `DATABASE_URL_LIVE`). SQLite is retained as an offline-dev fallback. Schema managed by Alembic; run `alembic upgrade head` after any `models.py` change.

For concurrent read/write safety in local dev (SQLite), WAL mode is enabled.

For the full database schema diagram, see [hld.md](hld.md).

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Alpha scoring is deterministic Python | Reproducible, debuggable, backtestable |
| Claude only interprets unstructured data | Avoids LLM inconsistency in numerical scoring |
| Tool use for structured output | Eliminates JSON parse failures |
| 4-agent debate pattern | Adversarial checking reduces false positives |
| HMM regime detection | Filters strategy-regime mismatches (biggest alpha leak) |
| Hybrid stock universe (30 core + 20 dynamic) | Keeps scan cost low while capturing high-setup midcaps; daily cache avoids 120× repeated API calls per day |
| Dynamic universe scoring (RSI + volume + ADX + EMA) | Picks the 20 names with the most active technical setups; regime sector boost aligns selection with current market phase |
| Sentiment decay (15%/30 min) | Prevents stale news from driving fresh entries |
| Macro guard (cap at 0.6 in bear) | Protects against bull strategies in bear markets |
| Approval-based execution | User stays in control, no surprise trades |
| Auto-sell with trailing stop | Protects gains systematically without manual monitoring |
| GTT OCO on exchange | Hard stop/target survives app crash; app adds trailing/time/confidence intelligence |
| GTT update rate limiting | Avoids API spam: 0.5% threshold + 60s cooldown for trailing stop updates |
| GTT startup reconciliation | Re-places protection for positions left unprotected after crash/restart |
| Telegram inline keyboards | Interactive mobile-first UX, free, instant |
| State persistence to DB | Survives restarts — no lost positions, triggers, or pending signals |
| Supabase Postgres (two projects) | Separate paper/live state; cloud-native, free tier, no ops overhead |
| Alembic migrations | Schema versioned — safe to evolve models.py without data loss |
| Cloud Routines (1h+ cadence) | Scheduled work: signal scan, telegram poll, heartbeat, reviews. All 5 core routines make HTTPS-only calls — CCR sandbox blocks TCP 5432/6543 |
| Fly.io always-on worker | Combined entrypoint (`workers/main.py`): auto-sell tick (60s daemon thread) + HTTP trigger API on port 8080. CCR delegates `run_cycle()` + Telegram poll here via `POST /trigger/scan` and `POST /trigger/poll` |
| Cloudflare Worker | Kite OAuth callback + HTTPS proxy for CCR: `/heartbeat/state`, `GET /memory/sweep`, `POST /memory/sweep` |
| GitHub PR per memory update | Memory changes require manual merge — no auto-commit to main |
| Pydantic config validation | Catches misconfiguration at startup, not at runtime |
| structlog JSON logging | Machine-parseable logs for analysis and alerting |
