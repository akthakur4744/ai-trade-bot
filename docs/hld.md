# Insight-Alpha 2026 — High-Level Design (HLD)

## 1. Introduction

Insight-Alpha is an AI-powered equity trading agent for Indian markets (NSE) via Zerodha Kite Connect. It combines deterministic technical analysis with LLM-driven news interpretation to produce high-confidence, risk-controlled trade decisions.

**Design Principle:** "Eliminate bad trades, not predict markets."

**Modes:** Paper trading (simulated execution, default) and Live trading (real Zerodha orders).

---

## 2. System Context

```
                    ┌────────────────────┐
                    │     User           │
                    │  (Trader/Investor) │
                    └────────┬───────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
      ┌──────────────┐ ┌──────────┐ ┌──────────────┐
      │  Telegram     │ │  Web     │ │  CLI         │
      │  Bot          │ │  Dashboard│ │  (standalone)│
      └──────┬───────┘ └────┬─────┘ └──────┬───────┘
             │              │              │
             └──────────────┼──────────────┘
                            │
                            ▼
              ┌──────────────────────────────┐
              │      Trading Engine           │
              │  (Orchestrates full pipeline) │
              └──────────────┬───────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ Zerodha Kite │  │ Claude API   │  │ News RSS     │
  │ Connect      │  │ (Anthropic)  │  │ Feeds        │
  └──────────────┘  └──────────────┘  └──────────────┘
```

### External Dependencies

| System | Purpose | Protocol |
|--------|---------|----------|
| Zerodha Kite Connect | Market data (OHLCV, LTP), order placement, GTT | REST API, WebSocket |
| Claude API (Anthropic) | News interpretation, signal scoring, memory drafts | REST API (tool_use) |
| Telegram Bot API | Interactive notifications with inline keyboards | HTTP polling |
| News RSS Feeds | Market news for sentiment analysis | HTTP/RSS |
| Supabase Postgres | Persistent state: two projects (`paper`, `live`) | PostgreSQL |
| Cloudflare Worker | Kite OAuth callback + CCR HTTPS proxy (`/heartbeat/state`, `/memory/sweep`) | HTTPS |
| Fly.io | Always-on worker: auto-sell tick (60s daemon) + HTTP trigger API for CCR delegation | Docker + Fly Machines |
| GitHub REST API | Opens PR per approved memory update | HTTPS (fine-grained PAT) |

---

## 3. Architecture Overview

### 3.1 Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                         │
│   FastAPI Dashboard  │  Telegram Bot  │  CLI                 │
├─────────────────────────────────────────────────────────────┤
│                    APPLICATION LAYER                          │
│   TradingEngine (main.py) — orchestrates full pipeline       │
│   ├── Approval Workflow (pending queue, expiry, actions)     │
│   └── Scheduling (APScheduler, market-hours loop)            │
├─────────────────────────────────────────────────────────────┤
│                    DOMAIN LAYER                              │
│   ┌─────────┐ ┌──────────┐ ┌────────┐ ┌─────────┐          │
│   │ Data    │ │ Analysis │ │ Risk   │ │Execution│          │
│   │ Pipeline│ │ Pipeline │ │ Layer  │ │ Layer   │          │
│   └─────────┘ └──────────┘ └────────┘ └─────────┘          │
├─────────────────────────────────────────────────────────────┤
│                    PERSISTENCE LAYER                          │
│   SQLAlchemy ORM + Alembic  │  Supabase Postgres (paper + live)  │
│   9 tables: Signal, Trade, DailyMetric,                      │
│   PositionState, AutoSellTriggerState, PendingSignalState,   │
│   PendingMemoryUpdate, AppState (+ SQLite offline-dev)        │
├─────────────────────────────────────────────────────────────┤
│                    INFRASTRUCTURE LAYER                       │
│   Kite Connect  │  Claude API  │  Telegram  │  News Feeds    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Component Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                           TRADING ENGINE                              │
│                                                                       │
│  ┌──────────────┐    ┌─────────────────────────────────┐             │
│  │ Data Layer   │    │ AI Agent Pipeline                │             │
│  │              │    │                                   │             │
│  │ KiteClient   │───▶│ Researcher (Haiku)  ───────────▶│             │
│  │ MarketData   │    │ Sentinel (Sonnet)   ───────────▶│             │
│  │ NewsFeed     │    │ Orchestrator (Sonnet) ─────────▶│             │
│  │ MacroData    │    │ Stitch (pure Python)             │             │
│  └──────────────┘    └──────────┬──────────────────────┘             │
│                                 │ ScoredSignal[]                      │
│  ┌──────────────┐    ┌──────────▼──────────────────────┐             │
│  │ Strategies   │    │ Scoring & Filtering              │             │
│  │ (8 impls)    │───▶│ AlphaModel + Filters + Ranking  │             │
│  └──────────────┘    └──────────┬──────────────────────┘             │
│                                 │                                     │
│  ┌──────────────┐    ┌──────────▼──────────────────────┐             │
│  │ Regime       │    │ Risk Layer                       │             │
│  │ Detector     │───▶│ Guardrails │ PositionSizing      │             │
│  │ (HMM)        │    │ Portfolio  │ KillSwitch           │             │
│  └──────────────┘    └──────────┬──────────────────────┘             │
│                                 │                                     │
│  ┌──────────────┐    ┌──────────▼──────────────────────┐             │
│  │ Notifications│    │ Execution Layer                  │             │
│  │ Telegram     │◀───│ OrderManager │ PaperBroker       │             │
│  │ WhatsApp     │    │ AutoSellManager │ LiveBroker      │             │
│  └──────────────┘    └──────────┬──────────────────────┘             │
│                                 │                                     │
│                      ┌──────────▼──────────────────────┐             │
│                      │ Persistence Layer                │             │
│                      │ Supabase Postgres (paper + live DBs) │             │
│                      │ 9 tables, Alembic migrations     │             │
│                      └─────────────────────────────────┘             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Pipeline

### 4.1 Full Pipeline Flow

```
Data Sources (Kite, News, Macro)
    ↓
Regime Detection (HMM — bull/bear/sideways/choppy)
    ↓
Dynamic Universe Selection (once/day: score 105 candidates → pick top 20)
    ↓
Strategies x 8 (scan 30 core + 20 dynamic = 50 symbols → raw StrategySignal[])
    ↓
AI Agents (Researcher → Sentinel → Orchestrator → Stitch)
    ↓
Alpha Scoring & Filtering (confidence >= 0.65)
    ↓
Risk Guardrails (4 checks, non-negotiable)
    ↓
Pending Queue → Telegram/Dashboard (BUY & Auto-Sell / Manual BUY / Ignore)
    ↓
Execution (Paper Broker / Live Broker)
    ↓
Auto-Sell Monitor (stop / target / trailing / time / confidence / structure)
    ↓
Exit Notification → Feedback Tracker → Daily Metrics
```

### 4.2 Market-Hours Schedule

| Time (IST) | Component | Event |
|------------|-----------|-------|
| 08:55 | Cloud Routine | `morning-login-prompt` — post Telegram link for manual Kite OAuth |
| 09:00 | Cloud Routine | `pre-market-check` — macro snapshot, watchlist health |
| 09:10 | signal-scan Routine | `load_instruments()` + GTT reconciliation |
| 09:15 | — | Market opens |
| Every 60s | Fly.io worker | `tick_auto_sell()` — software exit conditions |
| Every hour | signal-scan Routine | Session check via CF Worker → `POST /trigger/scan` to Fly.io (async, returns 200 immediately). `run_cycle()` runs as Fly.io background task |
| Continuous | telegram-poll Routine | `POST /trigger/poll` to Fly.io — offset read/dispatch/write all happen on Fly.io side with full DB access |
| 15:15 | signal-scan Routine | Auto-exit MIS positions approaching EOD |
| 15:30 | — | Market closes |
| 15:35 | signal-scan Routine | `send_daily_summary()` — PnL, win rate, daily metrics |
| 15:40 Fri | Cloud Routine | `weekly-review` — WeeklyReviewAgent draft → Telegram gate |

### 4.3 Scan Cycle Detail

Each `run_cycle()` execution:

1. Expire old pending signals (>15 min)
2. Monitor auto-sell positions (check exit triggers)
3. Fetch macro context (Nifty, VIX, market direction)
4. Update market regime (HMM)
5. Fetch news headlines
6. Run Researcher agent on news
7. Refresh dynamic universe if first cycle of the day (score 105 candidates → pick top 20; cached for rest of day)
8. Scan all 8 strategies across 30 core + 20 dynamic = 50 symbols
9. Run Sentinel agent (risk assessment)
10. Score via Orchestrator agent
11. Filter (confidence, liquidity, risk checks)
12. Stitch (consensus, dedup, rank)
13. Queue top signals for user approval
14. Check exits on manually-managed positions

---

## 5. Module Map

| Directory | Responsibility | Key Classes |
|-----------|---------------|-------------|
| `src/data/` | Market data ingestion + dynamic universe scoring | `KiteClient`, `MarketDataFetcher`, `NewsFeed`, `MacroDataFetcher`, `select_dynamic_universe()` |
| `src/indicators/` | Technical indicators (pure functions) | `compute_rsi()`, `compute_ema()`, `compute_atr()`, etc. |
| `src/strategies/` | 8 strategy implementations | `MeanReversion`, `Momentum`, `BollingerSqueeze`, `GoldenCross`, `VWAPReversion`, `Seasonal` |
| `src/agents/` | 4 Claude-powered AI agents | `ResearcherAgent`, `SentinelAgent`, `OrchestratorAgent`, `StitchAgent` |
| `src/scoring/` | Alpha model, filters, ranking | `AlphaModel`, `apply_filters()`, `rank_signals()` |
| `src/regime/` | Market regime classification | `RegimeDetector` (HMM-based) |
| `src/risk/` | Risk management | `Portfolio`, `KillSwitch`, `Guardrails`, `PositionSizing` |
| `src/execution/` | Order execution | `OrderManager`, `PaperBroker`, `LiveBroker`, `AutoSellManager` |
| `src/notifications/` | User notifications | `TelegramNotifier`, `WhatsAppNotifier` |
| `src/storage/` | Database ORM + persistence | `Database`, `Signal`, `Trade`, `PositionState`, `AutoSellTriggerState`, `PendingSignalState`, `AppState` |
| `src/feedback/` | Performance tracking | `FeedbackTracker`, `Reporter` |
| `src/web/` | Web dashboard | FastAPI app, Jinja2 templates, OAuth flow |
| `config/` | YAML configuration | `default.yaml`, `paper.yaml`, `live.yaml`, `watchlist.yaml` |

---

## 6. Data Model

### 6.1 Domain Models (Pydantic — runtime)

```
StrategySignal          ScoredSignal            PendingSignal
├── symbol              ├── symbol              ├── signal_id
├── direction           ├── direction           ├── signal: ScoredSignal
├── strategy_name       ├── confidence          ├── created_at
├── entry_price         ├── final_score         ├── expiry_minutes (15)
├── stop_loss           ├── confidence_breakdown├── telegram_message_id
├── target_price        ├── key_drivers[]       ├── status
└── time_horizon        ├── risks[]             └── action
                        ├── summary
                        └── regime

Position                AutoSellTrigger         ExitSignal
├── symbol              ├── symbol              ├── symbol
├── direction           ├── stop_loss           ├── reason (enum)
├── quantity            ├── target_price        ├── urgency
├── entry_price         ├── trailing_stop_pct   └── message
├── stop_loss           ├── max_hold_minutes
├── order_id            ├── confidence_floor
├── capital_deployed    ├── highest_price
└── unrealized_pnl      ├── created_at
                        └── is_active
```

### 6.2 Database Schema (SQLAlchemy ORM — persistence)

```
┌─────────────────────────────────────────────────────────────┐
│                    DATABASE TABLES (9)                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  CORE TABLES (trade lifecycle)                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐           │
│  │ signals  │───▶│ trades   │    │ daily_metrics│           │
│  │          │    │          │    │              │           │
│  │ id (PK)  │    │ id (PK)  │    │ id (PK)     │           │
│  │ symbol   │    │ signal_id│    │ date (UQ)   │           │
│  │ sentiment│    │ symbol   │    │ total_trades │           │
│  │ confidence│   │ direction│    │ total_pnl   │           │
│  │ strategy │    │ entry_price│  │ win_rate    │           │
│  │ status   │    │ exit_price│   │ profit_factor│          │
│  │ final_score│  │ pnl      │    │ sharpe_ratio│           │
│  │ created_at│   │ exit_reason│  └──────────────┘           │
│  └──────────┘    │ created_at│                               │
│                  └──────────┘                                │
│                                                               │
│  STATE TABLES (survive restarts)                             │
│  ┌────────────────┐  ┌───────────────────────┐              │
│  │ position_state │  │ auto_sell_trigger_state│              │
│  │                │  │                        │              │
│  │ id (PK)        │  │ id (PK)               │              │
│  │ symbol (UQ)    │  │ symbol (UQ)           │              │
│  │ direction      │  │ position_entry_price  │              │
│  │ quantity       │  │ position_direction    │              │
│  │ entry_price    │  │ stop_loss             │              │
│  │ stop_loss      │  │ target_price          │              │
│  │ order_id       │  │ trailing_stop_pct     │              │
│  │ strategy_name  │  │ max_hold_minutes      │              │
│  │ capital_deployed│ │ confidence_floor      │              │
│  │ updated_at     │  │ highest_price         │              │
│  └────────────────┘  │ created_at            │              │
│                      │ is_active             │              │
│  ┌────────────────┐  │ exit_strategy (text)  │              │
│  │pending_signal_ │  └───────────────────────┘              │
│  │     state      │                                          │
│  │                │  ┌───────────────────────┐              │
│  │ id (PK)        │  │ app_state             │              │
│  │ signal_id (UQ) │  │                        │              │
│  │ signal_json    │  │ id (PK)               │              │
│  │ created_at     │  │ key (UQ)              │              │
│  │ expiry_minutes │  │ value (JSON text)     │              │
│  │ telegram_msg_id│  │ updated_at            │              │
│  │ status         │  └───────────────────────┘              │
│  │ action         │                                          │
│  └────────────────┘  ┌───────────────────────┐              │
│                      │ pending_memory_updates │              │
│                      │                        │              │
│                      │ id (PK)               │              │
│                      │ trade_id / week_str   │              │
│                      │ diff_json (text)      │              │
│                      │ status (pending/…)    │              │
│                      │ telegram_msg_id       │              │
│                      │ created_at            │              │
│                      └───────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

**Core tables** store the historical record of signals, trades, and daily performance.

**State tables** store runtime state that must survive application restarts:
- `position_state` — open positions tracked by Portfolio
- `auto_sell_trigger_state` — active AI exit triggers per position
- `pending_signal_state` — signals awaiting user approval (ScoredSignal serialized as JSON)
- `app_state` — key-value store for kill switch state and portfolio daily counters

Tables are auto-created by `Base.metadata.create_all()` — no migration tool required.

### 6.3 Persistence Strategy

| State | Persisted? | Mechanism | Restore on Startup |
|-------|-----------|-----------|-------------------|
| Open positions | Yes | `position_state` table, saved on add/close | Portfolio loads from DB, cross-checks against trades table for stale entries |
| Auto-sell triggers | Yes | `auto_sell_trigger_state` table, saved on create/deactivate, price tracking batch-updated | AutoSellManager loads active triggers, preserves original `created_at` for time-based exits |
| Pending signals | Yes | `pending_signal_state` table, ScoredSignal as JSON | TradingEngine loads pending signals, skips expired, re-emits to dashboard |
| Kill switch | Yes | `app_state` key `kill_switch` | KillSwitch loads; if triggered_date is today, restores triggered state; otherwise ignores (natural day reset) |
| Daily PnL counters | Yes | `app_state` key `portfolio_counters` | Portfolio loads; if different day, reconstructs from trades table |
| Total realized PnL | Yes | `app_state` key `portfolio_counters` | Falls back to `SUM(trades.pnl)` on first run |
| Trade outcomes (feedback) | Reconstructed | From `trades` table | FeedbackTracker queries completed trades and rebuilds stats |
| Dashboard history | Reconstructed | From `signals` and `trades` tables | EngineState repopulated from DB on engine start |
| Market regime | Recalculated | Not persisted | Fresh HMM prediction on first cycle |
| Instrument tokens | Recalculated | Not persisted | Re-fetched from Kite API |

**SQLite WAL mode** is enabled for concurrent read/write safety between the engine thread and the web server thread.

---

## 7. AI Agent Architecture

### 7.1 Agent Pipeline

```
            News + Macro
                │
                ▼
        ┌───────────────┐
        │  Researcher    │  Model: claude-haiku-4-5
        │  (Sentiment)   │  Output: news_strength, sentiment, catalysts
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │  Sentinel      │  Model: claude-sonnet-4-6
        │  (Risk)        │  Output: risk_flags, counter_arguments, veto
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │  Orchestrator  │  Model: claude-sonnet-4-6
        │  (Scoring)     │  Output: confidence_breakdown, narrative, alpha_score
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │  Stitch        │  Pure Python (no LLM)
        │  (Consensus)   │  Output: deduped, ranked ScoredSignal[]
        └───────────────┘
```

### 7.2 Why 4 Agents?

| Agent | Role | Analogy |
|-------|------|---------|
| Researcher | "What is the news saying?" | Analyst |
| Sentinel | "What could go wrong?" | Devil's advocate |
| Orchestrator | "What is the final verdict?" | Portfolio manager |
| Stitch | "After dedup, what do we execute?" | Execution desk |

A single monolithic prompt produces inconsistent results and misses adversarial angles. The 4-agent pipeline enforces separation of concerns.

### 7.3 Structured Output

All agents use Claude's `tool_use` feature for structured JSON output — never free-text parsing. This eliminates JSON parse failures and ensures type-safe responses.

---

## 8. Risk Management

### 8.1 Guardrails (Non-Negotiable)

All 4 checks must pass before any order placement:

| Check | Limit | Purpose |
|-------|-------|---------|
| Order size | <= 10,000 INR | Cap single-trade exposure |
| Total deployed | <= 30,000 INR | Cap total portfolio exposure |
| Daily loss | > -1,000 INR | Daily loss circuit breaker |
| Open positions | < 3 | Concentration limit |

### 8.2 Kill Switch

When daily realized PnL exceeds `-max_daily_loss`, the kill switch triggers and blocks all new orders for the rest of the trading day. Resets automatically the next day. State is persisted to DB — survives restarts.

### 8.3 Position Sizing

Three methods available (configurable):
- **Fixed Fractional** — risk a fixed % of capital per trade
- **ATR-Based** — size based on volatility (ATR)
- **Kelly Criterion** — optimal sizing based on win rate and payoff ratio

### 8.4 Regime Guard

When market regime = BEAR, bullish signal confidence is capped at 0.6. This prevents bull strategies from firing in bear markets.

---

## 9. Approval Workflow

```
Engine finds signal
        │
        ▼
  ┌─────────────────┐
  │ Pending Queue    │◄──── Persisted to pending_signal_state table
  │ (in-memory +DB)  │
  └───────┬─────────┘
          │
    ┌─────┼──────┐
    ▼     ▼      ▼
Telegram  Dashboard
buttons   buttons
    │     │
    └──┬──┘
       ▼
 ┌───────────────────────────────────────────────┐
 │ User Action                                    │
 │                                                 │
 │ [BUY & Auto-Sell] → Execute + AI exit triggers │
 │ [Manual BUY]      → Execute, manual exit        │
 │ [Ignore]          → Signal discarded            │
 │ [No action 15min] → Signal expires              │
 └───────────────────────────────────────────────┘
```

---

## 10. Auto-Sell System

### Exit Conditions (first to trigger wins)

| # | Condition | Trigger | Priority |
|---|-----------|---------|----------|
| 1 | Stop Loss | Price hits hard stop | HIGH |
| 2 | Target | Price hits profit target | LOW |
| 3 | Trailing Stop | Price drops X% from peak (only above entry) | MEDIUM |
| 4 | Time-Based | Holding window expired | MEDIUM |
| 5 | Structure Break | Price reversal with >1.5x volume | HIGH |
| 6 | Confidence Decay | AI confidence drops below floor | MEDIUM |

### Trailing Stop Mechanism

```
Entry: 2500  |  Trailing: 1.5%  |  Tracks highest price

Price → 2580  →  stop at 2541 (2580 x 0.985)
Price → 2620  →  stop at 2581 (moves up)
Price → 2575  →  stop holds at 2581 → EXIT
```

### Persistence

Auto-sell triggers are persisted to `auto_sell_trigger_state` table. On restart:
- Active triggers are restored with original `created_at` (time-based exits remain accurate)
- `highest_price`/`lowest_price` tracking is preserved (trailing stops continue correctly)
- Deactivated triggers are not loaded

---

## 11. Execution Modes

| Aspect | Paper Mode | Live Mode |
|--------|-----------|-----------|
| Market Data | Real (Kite API) | Real (Kite API) |
| Order Execution | Simulated (LTP + 5 bps slippage) | Real (Kite `place_order()`) |
| Database | Supabase Postgres (`DATABASE_URL_PAPER`) | Supabase Postgres (`DATABASE_URL_LIVE`) |
| Config | `config/paper.yaml` | `config/live.yaml` |
| Safety | No real money risk | Requires `CONFIRM_LIVE_TRADING=true` |
| Code Path | Same pipeline | Same pipeline, different broker impl |

---

## 12. Web Dashboard

FastAPI + Jinja2 at `http://127.0.0.1:8000`.

### Features

| Feature | Description |
|---------|-------------|
| Kite OAuth | One-click Zerodha login |
| Engine Control | Start/Stop, manual cycle |
| Pending Signals | Signal cards with action buttons |
| Auto-Sell Monitor | Active triggers with levels and time remaining |
| Market Insights | Macro, news, AI research, risk assessment |
| Portfolio | Open positions, PnL, exit management type |
| Activity Log | Real-time alerts and trade confirmations |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Engine status, cycle count |
| GET | `/api/pending` | Pending signals awaiting approval |
| POST | `/api/signals/{id}/action` | Approve / Auto-Sell / Ignore |
| GET | `/api/auto-sell` | Active triggers and events |
| GET | `/api/portfolio` | Positions and PnL |
| GET | `/api/insights` | Latest cycle insights |
| GET | `/api/signals` | Recent signals history |
| GET | `/api/trades` | Recent trades history |
| GET | `/api/alerts` | Activity log |

---

## 13. Configuration

All configuration is in `config/` using YAML with Pydantic validation:

```
config/
├── default.yaml             # Base parameters for all components
├── paper.yaml               # Paper mode overrides
├── live.yaml                # Live mode overrides (stricter limits)
├── watchlist.yaml           # 30 core stocks — always scanned every cycle
├── extended_universe.yaml   # ~105 NSE candidates — scored daily, top 20 selected dynamically
└── strategies/              # Per-strategy parameter files
```

Key configuration areas:
- `execution.mode` — `paper` or `live`
- `risk.*` — guardrail limits, position sizing method
- `scoring.filters.*` — confidence/liquidity/risk thresholds
- `market.*` — timezone, open/close times, scan interval
- `agents.*` — model selection, temperature, retry config
- `database.url` — SQLite path (paper) or PostgreSQL URL (live)

---

## 14. Hybrid Stock Universe

Each scan cycle covers **50 symbols**: 30 static core names (highest-liquidity Nifty 50 subset, defined in `watchlist.yaml`) plus 20 dynamically-selected stocks (scored fresh once per trading day from a ~105-candidate extended pool in `extended_universe.yaml`).

### Dynamic Selection Scoring (`src/data/universe_selector.py`)

| Component | Weight | Formula |
|-----------|--------|---------|
| RSI extreme | 40% | `abs(rsi - 50) / 20` — extremes signal high-probability reversal/continuation setups |
| Volume spike | 30% | `min(1, vol_ratio / 2)` — 2× 20-day average volume = maximum score |
| ADX trend strength | 20% | `(adx - 15) / 25` clamped 0–1 — ADX 15→0, ADX 40→1 |
| EMA alignment | 10% | Bullish (short>medium>long)=1, mixed=0.5, bearish=0 |

**Regime sector boost:** +0.08 added to score for stocks in sectors favoured by the current `MarketRegime`:
- BULL → IT, Banking, Finance, Auto, Infrastructure
- BEAR → Pharma, Healthcare, FMCG, Power, Energy
- RANGE_BOUND → FMCG, Pharma, Consumer, Healthcare

**Sector cap:** maximum 5 stocks per sector in the dynamic 20 to enforce diversification.

### Caching

The dynamic 20 is computed once on the first scan cycle of each trading day and reused for all subsequent cycles that day. Extended universe instrument tokens are pre-fetched alongside core tokens in `load_instruments()` so no extra Kite API calls are needed at scan time.

---

## 14. Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Broker API | `kiteconnect` (Zerodha) |
| AI/LLM | `anthropic` (Claude API, tool_use) |
| Data Processing | `pandas`, `numpy` |
| Config Validation | `pydantic` |
| Database ORM | `SQLAlchemy` + Alembic migrations |
| Database | Supabase Postgres (paper + live); SQLite offline-dev fallback |
| Web Framework | `FastAPI` + `Jinja2` |
| ASGI Server | `uvicorn` |
| Scheduler | `APScheduler` (local); Cloud Routines (production) |
| Logging | `structlog` (JSON) |
| Notifications | Telegram Bot API, Twilio (WhatsApp) |
| Edge proxy | Cloudflare Worker (Kite OAuth callback) |
| Always-on worker | Fly.io Machines (`shared-cpu-1x`, 512MB — bumped to allow scan background task + auto-sell loop to coexist) |
| Memory audit | GitHub REST API (fine-grained PAT) |

---

## 15. Deployment

### Local Development / Paper Trading

```bash
pip install -e .
cp .env.example .env   # fill in KITE_API_KEY, ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, DATABASE_URL_PAPER
EXECUTION_MODE=paper alembic upgrade head
python start.py        # web dashboard + engine
```

### Cloud Topology (Production)

| Component | Platform | Purpose |
|-----------|----------|---------|
| Signal scan, Telegram poll, Heartbeat, Reviews | Claude Code Cloud Routines | Scheduled work (≥1h cadence). All 5 core routines use HTTPS only — CCR sandbox blocks TCP 5432/6543 |
| Auto-sell tick + Trigger API | Fly.io (`shared-cpu-1x`, 512MB, ~$4/mo) | 60s auto-sell loop (daemon thread) + FastAPI trigger API on port 8080. CCR delegates `run_cycle()` and Telegram polling here |
| Kite OAuth + CCR DB proxy | Cloudflare Worker (free tier) | OAuth callback + `/heartbeat/state` + `/memory/sweep` (GET + POST) for routines that can't reach Postgres |
| Persistence | Supabase Postgres (2 projects) | `paper` + `live` state, cloud-native |
| Memory audit trail | GitHub PRs (fine-grained PAT) | One PR per approved memory update (opened by Fly.io worker, not CCR) |

**Daily login flow:** `morning-login-prompt` Routine posts Telegram link at 08:55 IST → user taps on mobile → Zerodha redirects to Cloudflare Worker → Worker writes `access_token` to both Supabase DBs → all Routines and Fly worker read it via `get_active_session()`.

See `cloudflare-worker/README.md`, `routines/README.md`, and `workers/README.md` for full deploy steps.

---

## 16. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Deterministic alpha scoring | Reproducible, debuggable, backtestable |
| Hybrid stock universe (30 core + 20 dynamic) | Captures high-setup midcap opportunities without scanning 500+ symbols; daily cache keeps API cost at ~120 calls/day instead of 3,100+ |
| Dynamic selection inside scan loop | Single daily compute per first cycle; no separate scheduled routine; regime-aware sector tilts align opportunity discovery with market phase |
| Claude for unstructured data only | Avoids LLM inconsistency in numerical scoring |
| 4-agent debate pattern | Adversarial checking reduces false positives |
| Approval-based execution | User stays in control, no surprise trades |
| State persistence to DB | Survives restarts — no lost positions or triggers |
| Supabase Postgres (two projects) | Separate paper/live state; cloud-native, free tier, zero ops |
| Alembic migrations | Schema versioned — safe to evolve models.py |
| Cloud Routines (≥1h) | All scheduled work. CCR sandbox blocks TCP 5432/6543 — all 5 core routines use HTTPS-only calls via CF Worker + Fly.io trigger API |
| Fly.io always-on worker | Two responsibilities: (1) 60s auto-sell tick in daemon thread; (2) HTTP trigger API on port 8080 for CCR delegation (`/trigger/scan`, `/trigger/poll`) |
| Cloudflare Worker | Three responsibilities: (1) Kite OAuth callback; (2) `/heartbeat/state` HTTPS proxy; (3) `/memory/sweep` GET+POST for memory sweeper |
| GitHub PR per memory update | Memory changes need human merge — no accidental overwrite |
| Tool use for structured output | Eliminates JSON parse failures |
| HMM regime detection | Filters strategy-regime mismatches |
| Sentiment decay (15%/30min) | Prevents stale news from driving entries |
| Pydantic config validation | Catches misconfiguration at startup |

---

## 17. Priority Hierarchy

When signals conflict, the system follows this priority order:

```
Risk > Regime > Factors > Discipline > Sentiment > Technicals
```

Risk guardrails are never bypassed. Regime compatibility is checked before factor analysis. Discipline (position sizing, portfolio limits) comes before individual signal quality.
