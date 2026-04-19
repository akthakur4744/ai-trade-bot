# Insight-Alpha 2026 — Implementation Plan

## Context

AI-powered trading agent for Indian equities via Zerodha Kite Connect. Uses 4 AI agents (Researcher, Sentinel, Orchestrator, Stitch) to analyze news, macro, and technical signals, producing high-confidence directional theses. Supports **paper trading first**, then **live trading** after validation.

Design philosophy: "Eliminate bad trades, not predict markets" — conservative, multi-layer confirmation with human-in-the-loop.

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Language | Python 3.11+ | Kite Connect SDK is Python; data science ecosystem |
| Broker | `kiteconnect` | Official Zerodha SDK |
| AI Agents | `anthropic` SDK | Claude API (Sonnet for speed, Opus if needed) |
| Config | `pydantic` + `PyYAML` | Type-safe config with validation |
| Data | `pandas`, `numpy` | Financial data manipulation |
| Indicators | Custom (pandas/numpy) | Avoids TA-Lib C dependency; full control |
| Regime Detection | `hmmlearn` | HMM-based market state classification |
| Database | SQLite (paper) -> PostgreSQL (live) | SQLAlchemy abstracts the switch |
| Scheduling | `APScheduler` | In-process 5-15min cycle loop |
| HTTP | `httpx` | Async HTTP for news feeds, webhooks |
| Logging | `structlog` | Structured JSON logging for audit |
| Testing | `pytest` | Standard Python testing |
| Linting | `ruff` | Fast linter/formatter |

---

## Project Structure

```
ai-trade-agent/
├── docs/                          # PRD & strategy docs
├── config/
│   ├── default.yaml               # All default params
│   ├── paper.yaml                 # Paper mode overrides
│   ├── live.yaml                  # Live mode overrides (stricter limits)
│   ├── strategies/                # Per-strategy params (8 files)
│   └── watchlist.yaml             # Stock universe (20-30 Nifty 50 stocks)
├── src/
│   ├── main.py                    # Entry point: market-hours scheduler loop
│   ├── config.py                  # Config loader (merges default + env overlay)
│   ├── data/
│   │   ├── kite_client.py         # Kite Connect auth wrapper (daily token refresh)
│   │   ├── market_data.py         # Historical candles, LTP, depth (pandas DataFrames)
│   │   ├── websocket_feed.py      # Real-time tick subscription
│   │   ├── news_feed.py           # RSS/API news ingestion
│   │   ├── macro_data.py          # VIX, DXY, crude, US indices
│   │   └── fundamental_data.py    # EPS, P/E, ROE, D/E (cached daily)
│   ├── indicators/
│   │   ├── rsi.py                 # Relative Strength Index
│   │   ├── moving_averages.py     # EMA 20/50/200, SMA
│   │   ├── volume.py              # OBV, volume spike detection
│   │   ├── atr.py                 # Average True Range
│   │   ├── macd.py                # MACD (12, 26, 9)
│   │   ├── bollinger.py           # Bollinger Bands
│   │   ├── vwap.py                # Volume Weighted Average Price
│   │   ├── adx.py                 # Average Directional Index
│   │   └── stochastic.py          # Stochastic oscillator
│   ├── strategies/
│   │   ├── base.py                # Abstract Strategy class (scan + check_exit)
│   │   ├── mean_reversion.py      # RSI-based mean reversion
│   │   ├── momentum.py            # Trend following (ADX + EMA alignment)
│   │   ├── bollinger_squeeze.py   # Bollinger Band squeeze breakout
│   │   ├── golden_cross.py        # EMA 50/200 crossover
│   │   ├── vwap_reversion.py      # Intraday VWAP reversion
│   │   ├── seasonal.py            # Calendar-based patterns
│   │   ├── pairs_trading.py       # Statistical arbitrage
│   │   └── fundamental_technical.py # Fundamental + technical combo
│   ├── agents/
│   │   ├── base_agent.py          # Claude API client, prompt templates, retry
│   │   ├── researcher.py          # Entity extraction, sentiment, news_strength
│   │   ├── sentinel.py            # Counter-signals, risk_penalty
│   │   ├── orchestrator.py        # Deterministic alpha score + Claude summary
│   │   └── stitch.py              # Cross-timeframe consensus, dedup, ranking
│   ├── scoring/
│   │   ├── alpha_model.py         # Confidence formula
│   │   ├── filters.py             # All-must-pass strict filtering
│   │   ├── ranking.py             # Final score ranking, top 3-5
│   │   └── sentiment_decay.py     # 15% / 30min news decay
│   ├── regime/
│   │   └── detector.py            # HMM with 4 states (bull/bear/range/chop)
│   ├── risk/
│   │   ├── guardrails.py          # Pre-trade: 4 checks
│   │   ├── position_sizing.py     # Fixed %, ATR-based, optional Kelly
│   │   ├── portfolio.py           # Open positions + deployed capital tracking
│   │   └── kill_switch.py         # Daily loss circuit breaker
│   ├── execution/
│   │   ├── broker.py              # Abstract Broker interface (ABC)
│   │   ├── paper_broker.py        # Simulated fills with real LTP + slippage
│   │   ├── live_broker.py         # Real Kite Connect order placement
│   │   ├── order_manager.py       # Signal -> guardrails -> size -> place -> track
│   │   └── auto_exit.py           # Time/structure/confidence-decay exit monitor
│   ├── notifications/
│   │   ├── whatsapp.py            # Twilio WhatsApp API
│   │   └── gchat.py               # Google Chat webhook
│   ├── storage/
│   │   ├── database.py            # SQLAlchemy engine/session
│   │   ├── models.py              # ORM: Signal, Trade, DailyMetric
│   │   └── migrations/            # Alembic
│   └── feedback/
│       ├── tracker.py             # Outcome vs signal, PnL, drawdown
│       └── reporter.py            # Daily/weekly Sharpe, win rate, profit factor
├── tests/
│   ├── unit/                      # Indicators, scoring, risk, strategies
│   ├── integration/               # Kite API, DB, agent pipeline
│   └── backtest/
│       ├── runner.py              # Replay historical data through strategy engine
│       ├── walk_forward.py        # Rolling window validation
│       └── fixtures/              # Sample OHLCV CSVs
├── scripts/
│   ├── kite_auth.py               # Manual daily token generation helper
│   ├── kite_auto_login.py         # Automated login via Playwright + External TOTP
│   ├── install_cron.sh            # Installs launchd schedule for daily auto-login
│   └── backtest_cli.py            # CLI for backtesting
├── pyproject.toml
├── .env.example
└── .gitignore
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal:** Project skeleton that fetches real market data and computes indicators.

1. **Project setup** — `pyproject.toml`, `.env.example`, `.gitignore`
2. **Config system** — `config/default.yaml` + `src/config.py` (pydantic models, YAML loading, env overlay)
3. **Kite Connect client** — Daily login flow (redirect -> request_token -> access_token), token caching
4. **Market data** — Historical OHLCV candles (1m/5m/15m/daily) and LTP as pandas DataFrames. Rate-limited at 3 req/s.
5. **Indicators** — Tier 1 (RSI, EMA 20/50/200, OBV, ATR) + Tier 2 (MACD, Bollinger, VWAP, ADX) as pure functions
6. **Database** — SQLAlchemy models (Signal, Trade, DailyMetric), SQLite

### Phase 2: Risk Management + Execution (Week 3-4)
**Goal:** Paper broker with real-time guardrails.

1. **Risk guardrails** — 4 PRD checks: trade capital (10K), portfolio exposure (30K), daily loss (1K), position limit (3)
2. **Position sizing** — Fixed % (1-2%), ATR-based, optional Kelly
3. **Portfolio tracker** — In-memory + DB sync
4. **Kill switch** — Daily loss circuit breaker
5. **Broker interface** — Abstract ABC + Paper broker (real LTP + slippage) + Live broker (Kite API)
6. **Order manager** — Signal -> guardrails -> sizing -> place -> track -> persist

**Paper <-> Live:** Single config `execution.mode: "paper" | "live"`. Same code path, different broker impl.

### Phase 3: Strategy Engine (Week 5-7)
**Goal:** All 8 strategies producing raw signals.

Build order (by complexity): Mean Reversion -> Golden Cross -> Momentum -> Bollinger Squeeze -> VWAP Reversion -> Fundamental+Technical -> Pairs Trading -> Seasonal

Also: news feed (RSS) and fundamental data (EPS, P/E, ROE).

### Phase 4: AI Agents (Week 8-10)
**Goal:** Four Claude-powered agents processing signals.

- **Researcher** — Entity extraction, sentiment, news_strength (Claude Sonnet)
- **Sentinel** — Counter-signals, risk_penalty (adversarial)
- **Orchestrator** — Deterministic alpha score + Claude summary
- **Stitch** — Cross-timeframe consensus, dedup, final ranking

**Key:** Alpha scoring is deterministic Python, not LLM. Claude used only for unstructured data interpretation and summaries.

### Phase 5: Regime Detection + Scoring (Week 11-12)
**Goal:** Context-aware scoring adapting to market conditions.

- HMM regime detector (4 states), alpha model formula, strict filters, ranking, sentiment decay, macro guard

### Phase 6: Notifications + Main Loop (Week 13-14)
**Goal:** Complete end-to-end pipeline during market hours.

```
09:15 IST: Auth, init, start WebSocket
Every 5-15 min: Fetch -> Strategies -> Agents -> Score -> Filter -> Risk -> Notify -> Execute
15:30 IST: Close, summarize, persist
```

### Phase 7: Feedback + Backtesting (Week 15-16)
**Goal:** Validate performance, enable improvement.

- Feedback tracker, daily/weekly reporter, backtest runner, walk-forward validation

---

## Alpha Scoring Model

```
confidence = (news_strength * 0.25) + (signal_alignment * 0.30) + (market_confirmation * 0.25) + (liquidity_score * 0.10) - (risk_penalty * 0.20)
```

### Filtering (all must pass)
- confidence >= 0.65
- market_confirmation >= 0.6
- liquidity_score >= 0.6
- risk_penalty <= 0.4

### Ranking
```
final_score = (confidence * 0.4) + (signal_alignment * 0.3) + (market_confirmation * 0.2) + (news_strength * 0.1)
```
Output: Top 3-5 opportunities

---

## Risk Guardrails (Config-Driven)

| Parameter | Default |
|-----------|---------|
| max_capital_per_trade | 10,000 INR |
| max_daily_loss | 1,000 INR |
| max_open_positions | 3 |
| max_capital_deployed | 30,000 INR |
| per_trade_risk_pct | 1-2% |

---

## Paper -> Live Transition Checklist

1. Backtest each strategy on 2+ years across multiple regimes
2. Walk-forward analysis validates out-of-sample performance
3. Paper trade for 3-6 months
4. Review: Sharpe > 1.0, max drawdown < 20%, profit factor > 1.5
5. Start live with 10-25% of intended capital
6. Scale only if live Sharpe within 70% of paper Sharpe
7. Kill switch always active

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Deterministic scoring, LLM for interpretation only | Reproducible, auditable, testable, cheaper |
| Custom indicators over TA-Lib | No C dependency headaches on macOS/CI |
| SQLite for paper, PostgreSQL for live | Zero ops overhead during dev |
| APScheduler over Celery | Single-process doesn't need distributed infra |
| Paper/live is a single config switch | Same code path, only broker impl differs |
| Start with 20-30 Nifty 50 stocks | High liquidity, reliable data |
| Priority: Risk > Regime > Factors > Discipline > Sentiment > Technicals | Per docs hierarchy |
