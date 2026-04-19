# Insight-Alpha 2026 — Architecture

> Full version: [docs/architecture.md](docs/architecture.md)

## Pipeline at a Glance

```
Data Sources (Kite, News, Macro)
    ↓
Regime Detection (HMM — bull/bear/sideways/chop)
    ↓
Strategies × 8 (scan → raw signals)
    ↓
AI Agents (Researcher → Sentinel → Orchestrator → Stitch)
    ↓
Alpha Scoring & Filtering (confidence ≥ 0.65)
    ↓
Risk Guardrails (4 checks, non-negotiable)
    ↓
Pending Queue → Telegram Notification (BUY & Auto-Sell / Manual BUY / Ignore)
    ↓
Execution (Paper Broker / Live Broker)
    ↓
Auto-Sell Monitor (stop / target / trailing / time / confidence)
    ↓
Exit Notification (Telegram + Dashboard)
```

## Module Map

| Directory | What It Does |
|-----------|-------------|
| `src/data/` | Kite client, OHLCV, WebSocket, news/macro/fundamentals |
| `src/indicators/` | Pure functions: RSI, EMA, ATR, MACD, Bollinger, VWAP, ADX |
| `src/strategies/` | 8 strategy classes extending `Strategy` ABC |
| `src/agents/` | 4 Claude agents: Researcher, Sentinel, Orchestrator, Stitch |
| `src/scoring/` | Alpha model, filters, ranking, sentiment decay |
| `src/regime/` | HMM-based market regime detector |
| `src/risk/` | Guardrails, position sizing, portfolio, kill switch |
| `src/execution/` | PaperBroker, LiveBroker, OrderManager, AutoExitMonitor, AutoSellManager |
| `src/notifications/` | Telegram (interactive buttons) + WhatsApp notifiers |
| `src/web/` | FastAPI dashboard, Kite OAuth, engine control, approval workflow |
| `src/storage/` | SQLAlchemy ORM (7 tables), persistence layer, SQLite/PostgreSQL |
| `src/feedback/` | Performance tracking + reporting |

## Alpha Score Formula

```
confidence = (news_strength × 0.25) + (signal_alignment × 0.30)
           + (market_confirm × 0.25) + (liquidity × 0.10)
           - (risk_penalty × 0.20)
```

Filters: confidence ≥ 0.65 | market_confirmation ≥ 0.6 | liquidity ≥ 0.6 | risk_penalty ≤ 0.4

## Risk Guardrails (Never Bypass)

1. Order size ≤ ₹10,000
2. Total deployed ≤ ₹30,000
3. Daily loss > -₹1,000
4. Open positions < 3

See [docs/architecture.md](docs/architecture.md) for full details and [docs/hld.md](docs/hld.md) for the High-Level Design.
