# 📄 Product Requirements Document (PRD)
## AI Market Intelligence & Opportunity Filtering Agent (Insight-Alpha 2026 – Integrated v3)

---

# 1. Executive Summary

**Project Code:** Insight-Alpha-2026  
**Version:** 1.0.0-Final (Integrated)

## Objective

Build a high-confidence, semi-autonomous AI insights agent that identifies directional bias in equity markets using news, macro, and real-time technical signals.

## Vision

Insight-Alpha acts as a **high-frequency intelligent filter (5–15 min cycles)** that eliminates market noise and surfaces only the highest-confidence opportunities.

It produces structured **Directional Theses** with:
- Confidence Score
- Key Drivers
- Risks
- Exit Guidance

The system is **human-in-the-loop**, enabling informed trade approval rather than autonomous execution.

---

# 2. Product Goals & Success Metrics

## Primary Metrics

- **Directional Accuracy:** >75% (30-min horizon)
- **Signal Precision:** High (low false positives)
- **Signal Count:** ≤ 5/day

## System Metrics

- **Latency:** <15 seconds (event → notification)
- **Uptime:** 99.9% during market hours (09:15–15:30 IST)

## Behavioral Metrics

- High user approval rate
- Low signal churn

---

# 3. User Persona & Workflow

## Target User

- Systematic / semi-discretionary trader
- Needs high-confidence filtering, not raw signals

## Workflow

1. Data ingestion (5–15 min)
2. Multi-agent analysis
3. JSON bias output
4. Notification (WhatsApp/GChat)
5. User approval
6. Execution (via broker API)
7. Monitoring + exit reminder

---

# 4. System Architecture (Enhanced)

## 4.1 Multi-Agent System

### 1. Researcher Agent
- Extracts entities (stocks/sectors)
- Interprets news impact
- Generates initial sentiment

### 2. Sentinel Agent (Critic)
- Identifies counter-signals
- Challenges bullish/bearish bias
- Adds risk penalties

### 3. Orchestrator Agent
- Merges outputs
- Calculates final confidence
- Produces structured JSON

### 4. Stitch Agent
- Aggregates across timeframes/models
- Applies consensus logic
- Removes duplicates and conflicts

---

# 5. Data Ingestion Layer (Triple Verification)

System must ingest **3 independent signal streams**:

## 5.1 News Layer
- Real-time headlines (RSS/APIs)
- Source reliability scoring

## 5.2 Market Context Layer
- Index trends (Nifty, BankNifty)
- Volatility (VIX)
- Global cues (US indices, crude, DXY)

## 5.3 Technical Layer (Zerodha Data Integration)
- Price action (1m, 5m, 15m) via Zerodha Kite Connect APIs
- Volume spikes via Zerodha market data APIs
- Market depth via Zerodha order book data (Level 2/3)

---

# 6. Alpha Scoring Model (Enhanced)

## Base Formula

confidence =
  (news_strength * 0.25) +
  (signal_alignment * 0.30) +
  (market_confirmation * 0.25) +
  (liquidity_score * 0.10) -
  (risk_penalty * 0.20)

---

## 6.1 Scoring Inputs

### News Strength (NS)
- Source credibility
- Catalyst importance
- Recency (decay applied)

### Signal Alignment (SA)
- News vs price trend agreement
- Sector alignment

### Market Confirmation (MC)
- Price + volume validation

### Liquidity Score (LS)
- Volume participation
- Order book strength

### Risk Penalty (RP)
- Conflicting signals
- Macro divergence
- Event risk

---

## 6.2 Confidence Bands

- **0.7–1.0:** High confidence (eligible)
- **0.5–0.7:** Medium (filtered unless strong confirmation)
- **<0.5:** Rejected

---

# 7. Advanced Optimization Logic

## 7.1 Sentiment Decay

- Reduce news_strength by **15% every 30 min**

## 7.2 Whale Filter

- Validate institutional participation via order book
- Reject if retail-driven move

## 7.3 Macro Guard

- Cap bullish confidence at **0.6** if index is weak

---

# 8. Filtering Engine (Strict)

Signals must satisfy ALL:

- confidence ≥ 0.65
- market_confirmation ≥ 0.6
- liquidity_score ≥ 0.6
- risk_penalty ≤ 0.4

Reject if:
- conflicting sentiment
- weak volume
- news not confirmed by price

---

# 9. Stitch & Consensus Layer

## Rules

- Majority sentiment agreement
- Confidence variance ≤ 0.15
- Remove correlated stocks (same sector)

---

# 10. Ranking Engine

final_score =
  (confidence * 0.4) +
  (signal_alignment * 0.3) +
  (market_confirmation * 0.2) +
  (news_strength * 0.1)

Output: Top 3–5 opportunities

---

# 11. Output Specification

{
  "sentiment": "BULLISH",
  "confidence": 0.78,
  "confidence_breakdown": {
    "news_strength": 0.8,
    "signal_alignment": 0.75,
    "risk_penalty": 0.2
  },
  "strength": "STRONG",
  "key_drivers": ["Earnings beat", "Volume spike"],
  "risks": ["Weak global cues"],
  "time_horizon": "intraday",
  "summary": "Aligned news, price momentum, and sector strength"
}

---

## 12A. Zerodha Integration Details

### Purpose

Zerodha acts as both:
- Data provider (price, volume, depth)
- Execution layer (order placement)

### APIs Used

- Kite Connect REST APIs
- WebSocket for real-time ticks

### Capabilities

- Fetch LTP (Last Traded Price)
- Fetch historical candles (1m, 5m, 15m)
- Fetch market depth (Level 2/3)
- Place/modify/cancel orders
- Track positions and PnL

### Execution Flow

1. User receives signal
2. User approves via UI/notification
3. System calls Zerodha API
4. Order is placed
5. Trade is tracked in system

### Risk Controls (Zerodha Layer)

- Max capital per trade enforced
- Daily loss limits enforced
- Order validation before placement

---

# 12. Notification System

## Channels
- WhatsApp
- Google Chat

## Payload Includes
- Confidence score
- Rationale
- Risk level
- Exit hint

---

# 13. Execution Layer (Zerodha Integration)

- User approval mandatory
- Zerodha Kite Connect API integration (order placement, positions, LTP, market depth)
- Risk limits enforced

---

# 14. Feedback Loop

Track:
- Outcome vs signal
- Drawdown
- Time to profit

Use for:
- Weight adjustment
- Filter tuning

---

# 15. Compliance & Safety

- No hallucination
- Source traceability required
- Human-in-the-loop mandatory
- Capital risk limits enforced

---

# 15A. Config-Driven Risk Guardrails (Execution Safety Layer)

The system MUST enforce configurable risk limits at the execution layer. These limits are centrally managed and applied BEFORE any order is placed.

## 15A.1 Configuration Model

A centralized config (DB or config service) defines:

- max_capital_per_trade (e.g., 10,000 INR)
- max_daily_loss (e.g., 1,000 INR)
- max_open_positions (e.g., 3)
- max_capital_deployed (e.g., 30,000 INR)
- per_trade_risk_pct (optional, e.g., 1–2% of capital)

Example:

{
  "max_capital_per_trade": 10000,
  "max_daily_loss": 1000,
  "max_open_positions": 3,
  "max_capital_deployed": 30000
}

---

## 15A.2 Enforcement Rules

Before order placement, the system MUST validate:

1. Trade Capital Check
- Order size ≤ max_capital_per_trade

2. Portfolio Exposure Check
- Total deployed capital ≤ max_capital_deployed

3. Daily Loss Check
- If realized PnL ≤ -max_daily_loss → BLOCK all new trades

4. Position Limit Check
- Open positions ≤ max_open_positions

---

## 15A.3 Runtime Behavior

- If any guardrail is violated → reject execution
- Send notification: "Trade blocked due to risk limits"
- Log event for audit

---

## 15A.4 Integration with Zerodha Execution

- Validation occurs BEFORE calling Kite Connect APIs
- Orders are only sent if all checks pass
- Post-trade, positions and PnL are updated in system state

---

## 15A.5 Advanced Enhancements (Future)

- Dynamic risk sizing based on confidence score
- Volatility-adjusted position sizing
- Auto-disable trading after consecutive losses

---

# 16. Performance Requirements

- Latency < 15 sec
- High availability
- Scalable pipeline

---

# 17. Testing Strategy

## Backtesting
- 30–60 day simulation

## Forward Testing
- Paper trading

---

# 19. Design Principles

- Conservative over aggressive
- Confirmation over prediction
- Quality over quantity
- Multi-layer validation

---

# 20. Expected Output (User Experience)

Based on AI analysis, the user receives a notification on WhatsApp or Google Chat with:

- Stock/Sector name
- Sentiment (BULLISH / BEARISH / NEUTRAL)
- Confidence score
- Key drivers (why this signal exists)
- Risks (what can go wrong)
- Suggested holding window and exit guidance (when to sell / invalidation condition)

## Interaction Flow

1. Alert Sent: User receives a high-confidence opportunity notification
2. Review: User evaluates confidence, rationale, and risks
3. Approval: User approves the trade
4. Execution: System places order via Zerodha Kite Connect
5. Monitoring: System tracks sentiment, price, and volume behavior
6. Exit Reminder: User receives a notification when:
   - Holding window is reached
   - OR invalidation condition is triggered (price reversal with volume)
   - OR confidence drops below threshold

7. Sell Notification:
   User receives a clear "SELL / EXIT" notification with:
   - Reason for exit (time-based / structure break / confidence decay)
   - Current sentiment shift (if any)
   - Urgency level (HIGH / MEDIUM)
   - Suggested action: Exit position immediately or gradually

---

## 20A. Auto-Sell Capability (Optional Advanced Feature)

The system SHOULD support an optional **Auto-Sell mode** directly from the notification layer.

### User Interaction

- Notification includes actions:
  - Approve Trade
  - Ignore
  - Enable Auto-Sell

### Auto-Sell Behavior

When user selects **Enable Auto-Sell**:

1. System creates an automated exit trigger based on AI-defined conditions:
   - Time-based exit (e.g., 30–90 mins)
   - Structure-based exit (price reversal with volume)
   - Confidence decay below threshold

2. System stores trigger as an active rule linked to the position

3. System continuously monitors:
   - Price action
   - Volume
   - Sentiment/confidence changes

4. When any exit condition is met:
   - System automatically places SELL order via Zerodha
   - No human intervention required

5. User receives notification:
   - "Position exited automatically"
   - Reason for exit
   - Execution details (price, time)

---

### Safety Controls

- Auto-sell only activates after explicit user consent
- Works within configured risk guardrails
- Can be disabled per trade or globally

---

### Benefits

- Eliminates emotional exit decisions
- Ensures disciplined execution
- Reduces missed exits during volatility

This feature transforms the system from **decision-support** to **semi-automated execution with controlled autonomy**.

---

# 21. Final Note

Insight-Alpha is designed to **eliminate bad trades, not predict markets**, by enforcing discipline, confirmation, and structured reasoning.

