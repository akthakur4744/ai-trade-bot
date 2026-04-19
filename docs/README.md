# Insight-Alpha 2026 — Documentation

## Contents

| File | Description |
|------|-------------|
| [hld.md](hld.md) | High-Level Design: system context, component diagram, data model, database schema, persistence strategy |
| [architecture.md](architecture.md) | Full system pipeline, module map, agent design, persistence layer, approval workflow, auto-sell system, web dashboard APIs |
| [strategy.md](strategy.md) | All strategies, indicator reference, alpha scoring, risk rules |
| [claude.md](claude.md) | AI agent design, prompt engineering, MCP integration guide |
| [trading-strategies.md](trading-strategies.md) | Stock selection methodology and strategy deep-dives |
| [ai_market_intelligence_agent_prd.md](ai_market_intelligence_agent_prd.md) | Original product requirements document |

## Quick Links

- **Setup:** See root [README.md](../README.md)
- **Dev conventions:** See root [CLAUDE.md](../CLAUDE.md)
- **Config reference:** See [../config/default.yaml](../config/default.yaml)
- **Watchlist:** See [../config/watchlist.yaml](../config/watchlist.yaml)

## Key Concepts

### Approval Workflow
Signals are never auto-executed. They queue for user approval via Telegram buttons or the web dashboard. Primary action: BUY & Auto-Sell (executes + AI-managed exit). Also available: Manual BUY (user-managed exit), Ignore. See [architecture.md](architecture.md) for details.

### Auto-Sell System
When enabled per-trade, the system creates 6 AI-defined exit triggers (stop loss, target, trailing stop, time, structure break, confidence decay) and monitors them continuously. No human intervention required after enabling. See [architecture.md](architecture.md) for details.

### Web Dashboard
FastAPI dashboard at `http://127.0.0.1:8000` handles Kite OAuth login, engine control, signal approval, auto-sell monitoring, market insights, and portfolio view. Start with `python start.py`.
