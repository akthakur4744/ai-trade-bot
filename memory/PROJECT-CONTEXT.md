# Project Context

> Static background read by every Claude agent on startup. Update rarely.

## Mission
Insight-Alpha 2026 — AI equity trading agent for Indian markets (NSE/BSE) via Zerodha Kite Connect.
Core principle: **"Eliminate bad trades, not predict markets."**

## Capital & Risk Envelope
- Max capital per trade: ₹10,000
- Max total deployed: ₹30,000
- Max daily loss: ₹1,000
- Max open positions: 3

## Priority Order
Risk > Regime > Factors > Discipline > Sentiment > Technicals

## Memory System
See [TRADING-STRATEGY.md](TRADING-STRATEGY.md) for the binding rulebook, [LEARNINGS.md](LEARNINGS.md) for validated patterns, [MISTAKES.md](MISTAKES.md) for postmortems, and [WEEKLY-REVIEW.md](WEEKLY-REVIEW.md) for Friday retrospectives.

All memory writes are **Telegram-gated** — see `CLAUDE.md § Memory System` for the approval flow.
