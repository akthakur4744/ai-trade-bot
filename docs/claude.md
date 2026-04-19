# AI Agent Design — Claude Integration

## Overview

Insight-Alpha uses Claude for **interpreting unstructured data** — news, earnings transcripts, macro commentary. All numerical scoring is deterministic Python. Claude never directly decides trade sizes or risk parameters.

```
Unstructured Data (news, text)  →  Claude  →  Structured JSON scores
Structured scores               →  Python  →  Alpha model → Orders
```

This separation ensures reproducibility, debuggability, and protection against LLM inconsistency in quantitative decisions.

---

## The 4 Agents

### Researcher Agent
**Purpose:** Transform raw news into structured market intelligence.

**Inputs:**
- News items (title, summary, source, timestamp)
- Macro context (Nifty level, VIX, market direction)
- Watchlist symbols

**Output (via tool_use):**
```json
{
  "symbol_impacts": {
    "RELIANCE": {
      "news_strength": 0.72,
      "sentiment": "BULLISH",
      "catalyst_type": "EARNINGS_BEAT",
      "urgency": "HIGH",
      "confidence": 0.85
    }
  },
  "macro_sentiment": "NEUTRAL",
  "summary": "Q4 results beat expectations by 12%..."
}
```

**Model:** `claude-haiku-4-5` (fast, cost-effective for high-frequency news processing)

---

### Sentinel Agent
**Purpose:** Adversarial risk identification — argue against the trade.

**Inputs:**
- Researcher output
- Strategy signals
- Current open positions
- Macro context

**Output (via tool_use):**
```json
{
  "risk_flags": [
    {"symbol": "RELIANCE", "flag": "SECTOR_HEADWIND", "severity": "MEDIUM", "reason": "Oil prices falling"},
    {"symbol": "RELIANCE", "flag": "EARNINGS_PRICED_IN", "severity": "LOW"}
  ],
  "veto_symbols": [],
  "overall_risk_level": "MODERATE"
}
```

**Key rules:**
- If Sentinel flags `VETO`, the signal is dropped regardless of confidence score
- Sentinel runs after Researcher, before Orchestrator
- Model: `claude-sonnet-4-6` (needs strong reasoning for adversarial analysis)

---

### Orchestrator Agent
**Purpose:** Synthesize all signals into a final scored, narrated recommendation.

**Inputs:**
- Strategy signals
- Researcher output
- Sentinel output
- Macro context
- Market regime

**Output (via tool_use):**
```json
{
  "scored_signals": [
    {
      "symbol": "RELIANCE",
      "direction": "LONG",
      "confidence": 0.78,
      "confidence_breakdown": {
        "news_strength": 0.72,
        "signal_alignment": 0.85,
        "market_confirmation": 0.70,
        "liquidity_score": 0.90,
        "risk_penalty": 0.15
      },
      "narrative": "Strong earnings beat with bullish technical setup...",
      "regime_compatible": true
    }
  ]
}
```

**Model:** `claude-sonnet-4-6` (full reasoning for synthesis)

---

### Stitch Agent
**Purpose:** Deterministic post-processing — dedup, consensus, rank.

**This agent is pure Python** — no LLM call needed. It:
1. Deduplicates signals for the same symbol (picks highest confidence)
2. Enforces sector diversification (max 1 signal per sector)
3. Final ranking: `confidence×0.4 + alignment×0.3 + confirmation×0.2 + news×0.1`
4. Returns top N signals (limited by `max_open_positions`)

---

## Prompt Engineering Principles

### Tool Use for Structured Output
All agents use `tool_use` instead of asking Claude to return JSON in text:

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[SCORE_SIGNAL_TOOL],
    tool_choice={"type": "tool", "name": "score_signal"},
    messages=[{"role": "user", "content": prompt}]
)
# Extract structured data — no JSON parsing fragility
result = response.content[0].input
```

### System Prompt Structure
Each agent has a focused system prompt:
1. **Role** — What this agent is and what it does
2. **Context** — Market-specific knowledge (Indian markets, IST, Nifty)
3. **Rules** — Explicit constraints (never recommend position sizes, always flag uncertainty)
4. **Format** — How to use the tool (never return free text for decisions)

### Retry Logic
All agents retry up to 3 times on:
- API rate limit errors (exponential backoff)
- Malformed tool responses (re-prompt with error context)
- Timeout (30s default)

If all retries fail, the agent returns a conservative default (HOLD/no signal).

---

## Sentiment Scoring

Claude's news_strength output is a float 0.0–1.0:

| Score | Interpretation |
|-------|----------------|
| 0.0–0.3 | Noise / irrelevant |
| 0.3–0.5 | Mildly relevant |
| 0.5–0.7 | Meaningful catalyst |
| 0.7–0.85 | Strong signal |
| 0.85–1.0 | Major catalyst (earnings beat, M&A, regulatory) |

**Sentiment gate:** Technical BUY signals are only executed if `news_strength ≥ 0.65` OR if `market_confirmation ≥ 0.75` (strong technical case overrides weak news).

---

## MCP Integration (Future)

The system is designed to integrate with Claude via Model Context Protocol:

```python
# Future: MCP tools for live market data
tools = [
    {"name": "get_ltp", "description": "Get last traded price"},
    {"name": "get_historical", "description": "Get OHLCV candles"},
    {"name": "place_order", "description": "Place a paper/live order"},
    {"name": "get_portfolio", "description": "Current positions and P&L"},
]
```

This would enable Claude to directly query market data during analysis rather than receiving pre-fetched summaries.

---

## Cost Management

| Agent | Model | Frequency | Estimated cost/day |
|-------|-------|-----------|-------------------|
| Researcher | claude-haiku-4-5 | Every 15 min | ~$0.10 |
| Sentinel | claude-sonnet-4-6 | Per signal | ~$0.15 |
| Orchestrator | claude-sonnet-4-6 | Per cycle | ~$0.20 |
| Stitch | Python (no LLM) | Per cycle | $0.00 |

**Total estimated:** ~$0.45/trading day for a 20-symbol watchlist.

Reduce costs:
- Cache Researcher output for symbols with no new news
- Use Haiku for Researcher (adequate for sentiment classification)
- Disable AI agents during low-volatility, no-news periods
