# Insight-Alpha 2026 — AI Trading Agent Dashboard

Build a professional trading dashboard web application for an AI-powered equity trading agent that operates on Indian stock markets (NSE) via Zerodha Kite Connect. The app should use **mock/sample data** (provided below) and be ready to wire up to a REST API later.

---

## App Overview

**Name:** Insight-Alpha 2026
**Tagline:** AI-Powered Equity Trading Intelligence

This is a monitoring and analytics dashboard for an autonomous trading system that:
- Scans 20 Nifty 50 stocks every 15 minutes during market hours (09:15–15:30 IST)
- Uses 4 AI agents (Researcher, Sentinel, Orchestrator, Stitch) to analyze news, macro context, and technical signals
- Generates scored trading signals with deterministic alpha scoring
- Applies strict risk guardrails before every trade
- Supports paper trading (simulated) and live trading modes

The dashboard is **read-only** — it monitors the agent, it does not control it. Users observe signals, positions, trades, and performance.

---

## Design System

### Theme
- **Dark mode** trading terminal aesthetic (dark background: `#0a0e17`, cards: `#111827`, borders: `#1e293b`)
- Clean, data-dense layout inspired by Bloomberg Terminal and TradingView
- Monospace font for numbers/prices (`JetBrains Mono` or `Fira Code`), sans-serif for labels (`Inter`)

### Color Palette
| Purpose | Color | Hex |
|---------|-------|-----|
| Background | Near black | `#0a0e17` |
| Card/Surface | Dark gray | `#111827` |
| Border | Slate | `#1e293b` |
| Text primary | White | `#f1f5f9` |
| Text secondary | Gray | `#94a3b8` |
| BUY / Bullish / Profit | Green | `#22c55e` |
| SELL / Bearish / Loss | Red | `#ef4444` |
| Neutral | Amber | `#f59e0b` |
| Accent / Links | Blue | `#3b82f6` |
| High confidence | Emerald | `#10b981` |
| Low confidence | Orange | `#f97316` |
| Regime: BULL | Green | `#22c55e` |
| Regime: BEAR | Red | `#ef4444` |
| Regime: RANGE_BOUND | Amber | `#f59e0b` |
| Regime: CHOPPY | Purple | `#a855f7` |

### Typography
- All prices displayed in INR with rupee symbol: `₹2,845.50`
- Percentages with 1 decimal: `+1.2%`, `-0.8%`
- Confidence scores to 2 decimals: `0.72`
- Timestamps in IST: `14:30 IST` or `2026-04-11 14:30 IST`
- Use thousand separators for INR amounts: `₹10,000`

### Layout
- Persistent left sidebar navigation (collapsible to icons)
- Top bar showing: current time (IST), market status (OPEN/CLOSED), execution mode badge (PAPER/LIVE), regime indicator
- All pages are responsive but optimized for desktop (1440px+)

---

## Navigation (Left Sidebar)

1. **Dashboard** (home icon) — Overview
2. **Signals** (zap icon) — Signal Pipeline
3. **Positions** (briefcase icon) — Open Positions
4. **Trades** (history icon) — Trade History
5. **Analytics** (bar-chart icon) — Performance Analytics
6. **Watchlist** (eye icon) — Stock Watchlist
7. **Settings** (gear icon) — Configuration

---

## Data Models

### MarketRegime (enum)
```
BULL | BEAR | RANGE_BOUND | CHOPPY
```

### MacroSnapshot
```
nifty_price: number          // e.g., 22450.30
nifty_change_pct: number     // e.g., +0.85
banknifty_price: number      // e.g., 48230.15
banknifty_change_pct: number // e.g., +1.12
india_vix: number            // e.g., 14.25
vix_change_pct: number       // e.g., -3.50
advances: number             // e.g., 1280
declines: number             // e.g., 720
breadth_ratio: number        // e.g., 1.78
market_direction: string     // "bullish" | "neutral" | "bearish"
is_risk_off: boolean         // true if VIX > 20 or Nifty < -1%
```

### ConfidenceBreakdown
```
news_strength: number        // 0.0–1.0, weight: 0.25
signal_alignment: number     // 0.0–1.0, weight: 0.30
market_confirmation: number  // 0.0–1.0, weight: 0.25
liquidity_score: number      // 0.0–1.0, weight: 0.10
risk_penalty: number         // 0.0–1.0, weight: 0.20 (subtracted)
```

### ScoredSignal
```
id: string
symbol: string               // e.g., "RELIANCE"
exchange: string             // "NSE"
direction: "BUY" | "SELL"
strategy_name: string        // e.g., "mean_reversion"
sentiment: "BULLISH" | "BEARISH" | "NEUTRAL"
confidence: number           // 0.0–1.0 (computed alpha score)
strength: "STRONG" | "MODERATE" | "WEAK"
final_score: number          // 0.0–1.0 (ranking score)
confidence_breakdown: ConfidenceBreakdown
entry_price: number
stop_loss: number
target_price: number
time_horizon: "intraday" | "swing" | "positional"
regime: MarketRegime
key_drivers: string[]        // e.g., ["Oversold RSI at 28", "Volume spike 2.3x"]
risks: string[]              // e.g., ["Weak sector momentum", "VIX elevated"]
summary: string              // AI-generated one-line thesis
status: "pending" | "approved" | "rejected" | "expired" | "executed"
created_at: datetime
```

### Position
```
symbol: string
direction: "BUY" | "SELL"
quantity: number
entry_price: number
current_price: number
stop_loss: number
target_price: number
order_id: string
strategy_name: string
entry_time: datetime
unrealized_pnl: number       // (current_price - entry_price) * quantity
capital_deployed: number      // entry_price * quantity
pnl_pct: number              // unrealized_pnl / capital_deployed * 100
```

### Trade (closed)
```
id: string
symbol: string
direction: "BUY" | "SELL"
quantity: number
entry_price: number
exit_price: number
stop_loss: number
target_price: number
pnl: number                  // in INR
pnl_pct: number              // percentage
holding_duration_min: number
exit_reason: "STOP_LOSS" | "TARGET" | "TIME_BASED" | "CONFIDENCE_DECAY" | "STRUCTURE_BREAK" | "MANUAL" | "KILL_SWITCH"
strategy_name: string
execution_mode: "paper" | "live"
slippage_bps: number
created_at: datetime
exit_at: datetime
```

### DailyMetrics
```
date: string                 // "2026-04-11"
total_trades: number
winning_trades: number
losing_trades: number
total_pnl: number
max_drawdown: number
max_capital_deployed: number
signals_generated: number
signals_approved: number
signals_rejected: number
win_rate: number
profit_factor: number
sharpe_ratio: number
avg_pnl_per_trade: number
```

### StrategyStats
```
strategy_name: string
total_trades: number
winners: number
losers: number
win_rate: number
total_pnl: number
profit_factor: number
expectancy: number
avg_holding_minutes: number
target_hit_rate: number
max_win: number
max_loss: number
```

### RiskGuardrails
```
max_capital_per_trade: number    // 10000
max_capital_deployed: number     // 30000
max_daily_loss: number           // 1000
max_open_positions: number       // 3
current_deployed: number
current_daily_pnl: number
current_open_positions: number
kill_switch_active: boolean
```

### WatchlistStock
```
symbol: string
sector: string
current_price: number
change_pct: number
rsi: number
ema_alignment: "bullish" | "bearish" | "neutral"  // EMA 20/50/200 alignment
adx: number
volume_ratio: number           // vs 20-bar average
atr: number
has_active_signal: boolean
```

---

## Page 1: Dashboard (Home)

The main overview page. Dense but scannable.

### Top Bar (persistent across all pages)
- Left: App logo + name "Insight-Alpha"
- Center: Current time in IST (live clock), Market status badge ("MARKET OPEN" green / "MARKET CLOSED" gray)
- Right: Execution mode badge ("PAPER MODE" amber outlined / "LIVE MODE" red filled), Last scan time ("Last scan: 14:15 IST")

### Row 1: Market Context (4 cards in a row)

**Card 1: Nifty 50**
- Large price: `₹22,450.30`
- Change: `+190.75 (+0.85%)` in green
- Small sparkline of today's movement

**Card 2: Bank Nifty**
- Large price: `₹48,230.15`
- Change: `+535.20 (+1.12%)` in green

**Card 3: India VIX**
- Large value: `14.25`
- Change: `-0.52 (-3.50%)` in green (VIX down = good)
- Label: "Risk-Off: No" in green or "Risk-Off: Yes" in red

**Card 4: Market Breadth**
- Advances: 1280 (green) / Declines: 720 (red)
- Breadth ratio: 1.78
- Horizontal bar showing advance/decline ratio visually

### Row 2: Regime & Portfolio (2 cards)

**Card 5: Market Regime (wide)**
- Large regime label: "BULL" with green background pill
- 4-bar horizontal chart showing regime probabilities:
  - Bull: 55% (green bar)
  - Bear: 15% (red bar)
  - Range-Bound: 20% (amber bar)
  - Choppy: 10% (purple bar)
- Label: "Detected via HMM on Nifty 50 daily data"

**Card 6: Portfolio Summary (wide)**
- 2x2 grid of key metrics:
  - **Capital Deployed:** `₹18,500 / ₹30,000` with progress bar (61.7%)
  - **Today's PnL:** `+₹485.00` in green
  - **Open Positions:** `2 / 3` with progress bar
  - **Win Rate Today:** `66.7%` (2W / 1L)

### Row 3: Risk Guardrails (single wide card)

4 horizontal gauges side by side, each showing current vs limit:

1. **Trade Capital:** `₹8,200 / ₹10,000` — green gauge (82%)
2. **Total Deployed:** `₹18,500 / ₹30,000` — green gauge (61.7%)
3. **Daily Loss Limit:** `₹215 / ₹1,000` — green gauge (21.5%), label "₹785 remaining"
4. **Positions:** `2 / 3` — amber gauge (66.7%)

Each gauge: green if < 70%, amber if 70-90%, red if > 90%. Kill switch indicator: green dot "ACTIVE" or red flashing "TRIGGERED".

### Row 4: Activity Feed (full width)

A scrollable feed showing the last 10 events, newest first:
```
14:30  Signal APPROVED  RELIANCE BUY  confidence: 0.78  → Executed
14:30  Signal REJECTED  WIPRO BUY    confidence: 0.58  → Below threshold
14:15  Scan completed   5 signals generated, 2 approved
14:15  Exit triggered   HDFCBANK     reason: TARGET    pnl: +₹320.00
14:00  Scan completed   3 signals generated, 1 approved
```

Each row: timestamp, event type (color-coded badge), details, outcome.

---

## Page 2: Signal Pipeline

Visualizes the full signal generation and filtering pipeline.

### Pipeline Header
Horizontal flow diagram showing stages with counts:
```
[Raw Signals: 8] → [AI Scored: 8] → [Filtered: 3] → [Ranked: 2] → [Executed: 2]
```
Each stage is a pill/badge. Arrows connect them. Numbers update per cycle.

### Signal Cards (main content)

Display signals as cards in a grid (2-3 per row). Each card contains:

**Card Header:**
- Direction badge: green "BUY" or red "SELL"
- Symbol in large text: "RELIANCE"
- Strategy badge: "mean_reversion" in blue pill
- Status badge: "APPROVED" green / "REJECTED" red / "PENDING" amber / "EXECUTED" blue

**Card Body:**

Left section:
- **Sentiment:** BULLISH (green) / BEARISH (red) / NEUTRAL (amber)
- **Confidence:** `0.78` with color (green if >= 0.65, red if < 0.65)
- **Strength:** 3 stars for STRONG, 2 for MODERATE, 1 for WEAK
- **Final Score:** `0.81`

Center section — Confidence Breakdown Radar Chart:
- 5-axis radar/spider chart showing:
  - News Strength (NS)
  - Signal Alignment (SA)
  - Market Confirmation (MC)
  - Liquidity Score (LS)
  - Risk Penalty (RP) — inverted so lower is better
- Each axis 0–1 scale
- Fill color: green if approved, red if rejected

Right section:
- **Entry:** `₹2,845.50`
- **Stop:** `₹2,790.00` (with distance: `-1.95%`)
- **Target:** `₹2,940.00` (with distance: `+3.32%`)
- **R:R Ratio:** `1:1.70`
- **Time Horizon:** "intraday" badge

**Card Footer:**
- **Key Drivers:** bulleted list (max 3): "Oversold RSI at 28", "Volume spike 2.3x avg", "EMA 20/50 bullish alignment"
- **Risks:** bulleted list in red text (max 2): "Weak sector momentum", "Approaching resistance at ₹2,950"
- **AI Summary:** italic text: "Mean reversion setup with strong volume confirmation; RSI oversold bounce in progress with multiple timeframe alignment"

### Filters Bar (above cards)
- Filter by: Strategy (dropdown), Direction (BUY/SELL/All), Status (dropdown), Min Confidence (slider)
- Sort by: Confidence, Final Score, Created Time
- Toggle: Show rejected signals (off by default)

---

## Page 3: Open Positions

### Summary Bar
- Total Unrealized PnL: `+₹485.00` (green)
- Capital Deployed: `₹18,500`
- Positions: `2 of 3`

### Positions Table

| Symbol | Dir | Qty | Entry | Current | P&L (₹) | P&L (%) | Stop | Target | Strategy | Entry Time | Held |
|--------|-----|-----|-------|---------|----------|---------|------|--------|----------|------------|------|
| RELIANCE | BUY | 3 | ₹2,845.50 | ₹2,878.30 | +₹98.40 | +1.15% | ₹2,790.00 | ₹2,940.00 | mean_reversion | 11:15 IST | 3h 15m |
| ICICIBANK | BUY | 8 | ₹1,182.25 | ₹1,230.60 | +₹386.80 | +4.09% | ₹1,150.00 | ₹1,250.00 | momentum | 10:30 IST | 4h 0m |

**Row styling:**
- P&L column: green text for profit, red for loss
- Highlight row amber if current price is within 1% of stop loss
- Highlight row blue if current price is within 1% of target

**Per-row expandable detail:**
- Mini price chart showing entry → current with stop/target horizontal lines
- Signal confidence breakdown that led to this trade
- Time remaining (if time-based exit at 90 min applies)

### Empty State
When no positions: "No open positions. The agent will scan for opportunities at the next interval." with next scan countdown.

---

## Page 4: Trade History

### Summary Cards (top row, 4 cards)
- **Total Trades:** 47
- **Win Rate:** 61.7% (29W / 18L)
- **Total PnL:** `+₹3,240.50`
- **Avg PnL/Trade:** `+₹68.94`

### Daily PnL Bar Chart
- Horizontal axis: last 20 trading days
- Vertical axis: PnL in INR
- Green bars for profitable days, red bars for losing days
- Hover: shows date, PnL, trade count, win rate

### Trades Table (full width, paginated)

| Date | Symbol | Dir | Entry | Exit | P&L (₹) | P&L (%) | Duration | Exit Reason | Strategy | Mode |
|------|--------|-----|-------|------|----------|---------|----------|-------------|----------|------|
| Apr 11 | HDFCBANK | BUY | ₹1,645.00 | ₹1,685.00 | +₹320.00 | +2.43% | 45 min | TARGET | momentum | paper |
| Apr 11 | TCS | BUY | ₹3,420.00 | ₹3,395.00 | -₹75.00 | -0.73% | 90 min | TIME_BASED | golden_cross | paper |
| Apr 11 | RELIANCE | BUY | ₹2,810.00 | ₹2,855.00 | +₹225.00 | +1.60% | 55 min | TARGET | mean_reversion | paper |

**Filters:**
- Date range picker
- Symbol search
- Strategy dropdown
- Exit reason dropdown
- Direction (BUY/SELL)
- Min/Max PnL

**Row click:** Expands to show full signal details (confidence breakdown, key drivers, risks, AI summary) that generated this trade.

**Exit reason badges** with colors:
- TARGET: green
- STOP_LOSS: red
- TIME_BASED: amber
- CONFIDENCE_DECAY: orange
- STRUCTURE_BREAK: purple
- KILL_SWITCH: red flashing

---

## Page 5: Performance Analytics

### Row 1: Key Metrics (6 cards)
- **Win Rate:** 61.7% — circular progress ring
- **Profit Factor:** 1.84 — number with green/red color (green if > 1)
- **Expectancy:** ₹68.94/trade — with trend arrow
- **Sharpe Ratio:** 1.42 — number
- **Avg Holding:** 52 min — number
- **Max Drawdown:** ₹820 — in red

### Row 2: Equity Curve (wide chart)
- Line chart showing cumulative PnL over time
- X-axis: dates (last 30 days)
- Y-axis: cumulative PnL in INR
- Green fill below the line when positive
- Red fill when in drawdown
- Hover: date, cumulative PnL, trade count that day

### Row 3: Two charts side by side

**Chart 1: Win/Loss Distribution**
- Histogram of trade PnL amounts
- X-axis: PnL buckets (₹-500 to ₹500 in ₹50 increments)
- Green bars for wins, red bars for losses
- Vertical line at ₹0

**Chart 2: Exit Reason Breakdown**
- Donut chart showing distribution of exit reasons
- TARGET: 45% (green)
- STOP_LOSS: 25% (red)
- TIME_BASED: 18% (amber)
- CONFIDENCE_DECAY: 8% (orange)
- STRUCTURE_BREAK: 4% (purple)

### Row 4: Per-Strategy Performance Table

| Strategy | Trades | Win Rate | Total PnL | Profit Factor | Expectancy | Avg Hold | Target Hit | Max Win | Max Loss |
|----------|--------|----------|-----------|---------------|------------|----------|------------|---------|----------|
| mean_reversion | 15 | 73.3% | +₹1,480 | 2.45 | +₹98.67 | 38 min | 66.7% | ₹380 | -₹180 |
| momentum | 12 | 58.3% | +₹920 | 1.62 | +₹76.67 | 55 min | 50.0% | ₹450 | -₹220 |
| bollinger_squeeze | 8 | 62.5% | +₹540 | 1.78 | +₹67.50 | 42 min | 50.0% | ₹290 | -₹150 |
| golden_cross | 6 | 50.0% | +₹180 | 1.25 | +₹30.00 | 72 min | 33.3% | ₹310 | -₹250 |
| vwap_reversion | 4 | 50.0% | +₹95 | 1.18 | +₹23.75 | 35 min | 50.0% | ₹180 | -₹160 |
| pairs_trading | 2 | 50.0% | +₹25 | 1.08 | +₹12.50 | 65 min | 50.0% | ₹90 | -₹65 |

Color the Win Rate and PnL columns: green if positive/above 50%, red otherwise.

### Row 5: Daily Performance Heatmap
- Calendar-style grid (like GitHub contribution graph) showing last 60 trading days
- Color intensity based on daily PnL: dark green for best days, dark red for worst days, gray for no trades
- Hover: date, PnL, trades, win rate

---

## Page 6: Watchlist

### Sector Filter Tabs
Horizontal tabs: All | Banking | IT | Energy | FMCG | Auto | Pharma | Finance | Telecom | Industrial

### Watchlist Table

| Symbol | Sector | Price | Change | RSI | Trend | ADX | Vol Ratio | ATR | Signal |
|--------|--------|-------|--------|-----|-------|-----|-----------|-----|--------|
| RELIANCE | Energy | ₹2,878.30 | +1.15% | 42.3 | Bullish | 28.5 | 1.4x | 45.2 | Active |
| TCS | IT | ₹3,395.00 | -0.73% | 55.1 | Neutral | 18.2 | 0.9x | 62.8 | — |
| HDFCBANK | Banking | ₹1,685.00 | +2.43% | 61.8 | Bullish | 32.1 | 1.8x | 28.4 | Active |
| INFY | IT | ₹1,520.75 | +0.45% | 48.7 | Neutral | 15.3 | 0.7x | 35.1 | — |
| ICICIBANK | Banking | ₹1,230.60 | +4.09% | 68.2 | Bullish | 35.8 | 2.1x | 22.6 | Active |
| SBIN | Banking | ₹785.40 | +0.92% | 52.4 | Bullish | 24.1 | 1.1x | 18.3 | — |
| KOTAKBANK | Banking | ₹1,842.15 | -0.35% | 44.6 | Neutral | 16.8 | 0.8x | 32.5 | — |
| AXISBANK | Banking | ₹1,125.80 | +1.78% | 57.9 | Bullish | 26.3 | 1.3x | 24.7 | — |
| HINDUNILVR | FMCG | ₹2,415.60 | -0.22% | 38.1 | Bearish | 21.4 | 0.6x | 42.1 | — |
| ITC | FMCG | ₹448.25 | +0.67% | 50.3 | Neutral | 19.7 | 1.0x | 8.5 | — |
| LT | Industrial | ₹3,280.90 | +1.05% | 59.4 | Bullish | 27.9 | 1.2x | 58.3 | — |
| MARUTI | Auto | ₹12,450.00 | +0.38% | 46.2 | Neutral | 17.5 | 0.9x | 215.0 | — |
| TATAMOTORS | Auto | ₹685.30 | +2.15% | 63.7 | Bullish | 30.2 | 1.6x | 14.8 | — |
| SUNPHARMA | Pharma | ₹1,720.45 | -0.58% | 35.6 | Bearish | 22.8 | 0.7x | 31.2 | — |
| BAJFINANCE | Finance | ₹7,250.00 | +1.32% | 54.8 | Bullish | 25.6 | 1.1x | 135.0 | — |
| BHARTIARTL | Telecom | ₹1,580.20 | +0.75% | 51.2 | Neutral | 20.3 | 0.9x | 28.9 | — |
| WIPRO | IT | ₹465.80 | -1.05% | 32.4 | Bearish | 14.6 | 0.5x | 9.2 | — |
| TATASTEEL | Industrial | ₹142.55 | +1.85% | 58.3 | Bullish | 29.4 | 1.5x | 3.8 | — |
| POWERGRID | Industrial | ₹298.70 | +0.42% | 47.1 | Neutral | 18.9 | 0.8x | 5.6 | — |
| ASIANPAINT | FMCG | ₹2,820.40 | -0.15% | 41.5 | Neutral | 16.2 | 0.7x | 48.3 | — |

**Column formatting:**
- **Change:** green if positive, red if negative
- **RSI:** red text if < 30 (oversold) or > 70 (overbought), amber if 30-40 or 60-70, green otherwise
- **Trend:** green "Bullish" / red "Bearish" / gray "Neutral" — based on EMA 20/50/200 alignment
- **ADX:** bold if > 25 (strong trend)
- **Vol Ratio:** green if > 1.2x (volume spike), gray otherwise
- **Signal:** green "Active" badge if the stock has an active signal, dash otherwise

**Row click:** Expands to show a detail panel with:
- Mini indicator dashboard: RSI gauge, MACD histogram, Bollinger Band position, VWAP deviation
- Last 3 signals generated for this stock
- Sector peers comparison

---

## Page 7: Settings (Read-Only)

Display current configuration in organized cards. All values are read-only (displayed, not editable).

### Card 1: Execution
- Mode: `PAPER` (amber badge)
- Slippage: `5 bps`
- Fill delay: `100ms`

### Card 2: Risk Limits
- Max capital per trade: `₹10,000`
- Max capital deployed: `₹30,000`
- Max daily loss: `₹1,000`
- Max open positions: `3`
- Position sizing method: `fixed_percentage`

### Card 3: Market Schedule
- Market hours: `09:15 - 15:30 IST`
- Scan interval: `15 minutes`
- Sentiment decay: `15% every 30 min`
- Max hold time: `90 minutes`

### Card 4: Active Strategies (toggle list, all read-only)
- Mean Reversion: ON (green)
- Momentum: ON (green)
- Golden Cross: ON (green)
- Bollinger Squeeze: ON (green)
- VWAP Reversion: ON (green)
- Pairs Trading: ON (green)
- Seasonal: OFF (gray)
- Breakout: OFF (gray)

### Card 5: Scoring Weights
Visual bar chart showing weights:
- Signal Alignment: 0.30 (longest bar)
- News Strength: 0.25
- Market Confirmation: 0.25
- Risk Penalty: 0.20 (in red)
- Liquidity Score: 0.10

### Card 6: Filter Thresholds
- Min confidence: `0.65`
- Min market confirmation: `0.60`
- Min liquidity score: `0.60`
- Max risk penalty: `0.40`

### Card 7: AI Agents
- Model: `claude-sonnet-4`
- Max retries: `3`
- Timeout: `30s`
- Max tokens: `2048`
- Agents: Researcher, Sentinel, Orchestrator, Stitch (4 badges)

### Card 8: Data Settings
- Candle intervals: 5min, 15min, Day
- Lookback: 60 days
- Rate limit: 3 req/s (historical), 10 req/s (other)
- Database: SQLite (paper) / PostgreSQL (live)

---

## Sample Data

Use the following realistic sample data to populate the app. All prices are in INR. All times are IST.

### Current State
```json
{
  "execution_mode": "paper",
  "market_status": "open",
  "current_time": "2026-04-12T14:30:00+05:30",
  "last_scan": "2026-04-12T14:15:00+05:30",
  "next_scan": "2026-04-12T14:30:00+05:30"
}
```

### Macro Snapshot
```json
{
  "nifty_price": 22450.30,
  "nifty_change_pct": 0.85,
  "banknifty_price": 48230.15,
  "banknifty_change_pct": 1.12,
  "india_vix": 14.25,
  "vix_change_pct": -3.50,
  "advances": 1280,
  "declines": 720,
  "breadth_ratio": 1.78,
  "market_direction": "bullish",
  "is_risk_off": false
}
```

### Market Regime
```json
{
  "current": "BULL",
  "probabilities": {
    "bull": 0.55,
    "bear": 0.15,
    "range_bound": 0.20,
    "choppy": 0.10
  }
}
```

### Risk Guardrails
```json
{
  "max_capital_per_trade": 10000,
  "max_capital_deployed": 30000,
  "max_daily_loss": 1000,
  "max_open_positions": 3,
  "current_deployed": 18500,
  "current_daily_pnl": -215,
  "current_open_positions": 2,
  "kill_switch_active": false
}
```

### Active Signals (5 signals from latest scan)
```json
[
  {
    "id": "sig_001",
    "symbol": "RELIANCE",
    "exchange": "NSE",
    "direction": "BUY",
    "strategy_name": "mean_reversion",
    "sentiment": "BULLISH",
    "confidence": 0.78,
    "strength": "STRONG",
    "final_score": 0.81,
    "confidence_breakdown": {
      "news_strength": 0.72,
      "signal_alignment": 0.85,
      "market_confirmation": 0.80,
      "liquidity_score": 0.75,
      "risk_penalty": 0.22
    },
    "entry_price": 2845.50,
    "stop_loss": 2790.00,
    "target_price": 2940.00,
    "time_horizon": "intraday",
    "regime": "BULL",
    "key_drivers": ["Oversold RSI at 28 with bullish divergence", "Volume spike 2.3x average", "EMA 20/50 bullish alignment confirmed"],
    "risks": ["Approaching resistance zone at 2950", "Energy sector underperforming Nifty by 0.5%"],
    "summary": "Mean reversion setup with strong volume confirmation; RSI oversold bounce in progress with multiple timeframe alignment supporting upside to 2940 target.",
    "status": "executed",
    "created_at": "2026-04-12T14:15:00+05:30"
  },
  {
    "id": "sig_002",
    "symbol": "ICICIBANK",
    "exchange": "NSE",
    "direction": "BUY",
    "strategy_name": "momentum",
    "sentiment": "BULLISH",
    "confidence": 0.74,
    "strength": "STRONG",
    "final_score": 0.77,
    "confidence_breakdown": {
      "news_strength": 0.65,
      "signal_alignment": 0.82,
      "market_confirmation": 0.78,
      "liquidity_score": 0.80,
      "risk_penalty": 0.18
    },
    "entry_price": 1182.25,
    "stop_loss": 1150.00,
    "target_price": 1250.00,
    "time_horizon": "intraday",
    "regime": "BULL",
    "key_drivers": ["ADX at 35.8 confirms strong uptrend", "Banking sector leading with +1.5% vs Nifty", "Breakout above 20-day high with volume"],
    "risks": ["RSI approaching overbought at 68", "Bank Nifty near resistance at 48500"],
    "summary": "Strong momentum continuation in ICICIBANK with banking sector tailwind; ADX confirms trend strength with clean breakout above consolidation range.",
    "status": "executed",
    "created_at": "2026-04-12T10:15:00+05:30"
  },
  {
    "id": "sig_003",
    "symbol": "TATAMOTORS",
    "exchange": "NSE",
    "direction": "BUY",
    "strategy_name": "bollinger_squeeze",
    "sentiment": "BULLISH",
    "confidence": 0.71,
    "strength": "MODERATE",
    "final_score": 0.73,
    "confidence_breakdown": {
      "news_strength": 0.60,
      "signal_alignment": 0.78,
      "market_confirmation": 0.72,
      "liquidity_score": 0.70,
      "risk_penalty": 0.25
    },
    "entry_price": 672.00,
    "stop_loss": 655.00,
    "target_price": 705.00,
    "time_horizon": "intraday",
    "regime": "BULL",
    "key_drivers": ["Bollinger bandwidth at 5th percentile — extreme squeeze", "Breakout above upper band with 1.6x volume", "Auto sector showing relative strength"],
    "risks": ["ADX still below 25 — trend not confirmed", "Earnings in 5 days — event risk"],
    "summary": "Volatility squeeze breakout in TATAMOTORS with strong volume; bandwidth contraction historically leads to directional moves, auto sector providing support.",
    "status": "approved",
    "created_at": "2026-04-12T14:15:00+05:30"
  },
  {
    "id": "sig_004",
    "symbol": "WIPRO",
    "exchange": "NSE",
    "direction": "BUY",
    "strategy_name": "mean_reversion",
    "sentiment": "NEUTRAL",
    "confidence": 0.58,
    "strength": "WEAK",
    "final_score": 0.54,
    "confidence_breakdown": {
      "news_strength": 0.40,
      "signal_alignment": 0.62,
      "market_confirmation": 0.55,
      "liquidity_score": 0.50,
      "risk_penalty": 0.35
    },
    "entry_price": 468.00,
    "stop_loss": 458.00,
    "target_price": 485.00,
    "time_horizon": "intraday",
    "regime": "BULL",
    "key_drivers": ["RSI at 32 — near oversold", "Price near lower Bollinger band"],
    "risks": ["IT sector weak — TCS and INFY both red", "Volume below average at 0.5x", "No catalyst for reversal"],
    "summary": "Weak mean reversion signal in WIPRO; oversold but lacking volume confirmation and sector headwind suggests limited upside potential.",
    "status": "rejected",
    "created_at": "2026-04-12T14:15:00+05:30"
  },
  {
    "id": "sig_005",
    "symbol": "HDFCBANK",
    "exchange": "NSE",
    "direction": "BUY",
    "strategy_name": "golden_cross",
    "sentiment": "BULLISH",
    "confidence": 0.69,
    "strength": "MODERATE",
    "final_score": 0.71,
    "confidence_breakdown": {
      "news_strength": 0.55,
      "signal_alignment": 0.75,
      "market_confirmation": 0.74,
      "liquidity_score": 0.72,
      "risk_penalty": 0.20
    },
    "entry_price": 1645.00,
    "stop_loss": 1610.00,
    "target_price": 1710.00,
    "time_horizon": "swing",
    "regime": "BULL",
    "key_drivers": ["EMA 50 crossed above EMA 200 on 15min chart", "Banking sector momentum strong", "Volume 1.8x on crossover candle"],
    "risks": ["Golden cross on 15min less reliable than daily", "Price already moved 1.5% from crossover point"],
    "summary": "Golden cross formation in HDFCBANK on 15-minute timeframe with strong volume confirmation; banking sector tailwind supports continuation.",
    "status": "expired",
    "created_at": "2026-04-12T11:30:00+05:30"
  }
]
```

### Open Positions (2 active)
```json
[
  {
    "symbol": "RELIANCE",
    "direction": "BUY",
    "quantity": 3,
    "entry_price": 2845.50,
    "current_price": 2878.30,
    "stop_loss": 2790.00,
    "target_price": 2940.00,
    "order_id": "ORD_20260412_001",
    "strategy_name": "mean_reversion",
    "entry_time": "2026-04-12T11:15:00+05:30",
    "unrealized_pnl": 98.40,
    "capital_deployed": 8536.50,
    "pnl_pct": 1.15
  },
  {
    "symbol": "ICICIBANK",
    "direction": "BUY",
    "quantity": 8,
    "entry_price": 1182.25,
    "current_price": 1230.60,
    "stop_loss": 1150.00,
    "target_price": 1250.00,
    "order_id": "ORD_20260412_002",
    "strategy_name": "momentum",
    "entry_time": "2026-04-12T10:30:00+05:30",
    "unrealized_pnl": 386.80,
    "capital_deployed": 9458.00,
    "pnl_pct": 4.09
  }
]
```

### Trade History (15 recent closed trades)
```json
[
  {"id": "t001", "symbol": "HDFCBANK", "direction": "BUY", "quantity": 8, "entry_price": 1645.00, "exit_price": 1685.00, "stop_loss": 1610.00, "target_price": 1710.00, "pnl": 320.00, "pnl_pct": 2.43, "holding_duration_min": 45, "exit_reason": "TARGET", "strategy_name": "momentum", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-12T09:30:00+05:30", "exit_at": "2026-04-12T10:15:00+05:30"},
  {"id": "t002", "symbol": "TCS", "direction": "BUY", "quantity": 3, "entry_price": 3420.00, "exit_price": 3395.00, "stop_loss": 3380.00, "target_price": 3480.00, "pnl": -75.00, "pnl_pct": -0.73, "holding_duration_min": 90, "exit_reason": "TIME_BASED", "strategy_name": "golden_cross", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-12T09:45:00+05:30", "exit_at": "2026-04-12T11:15:00+05:30"},
  {"id": "t003", "symbol": "RELIANCE", "direction": "BUY", "quantity": 5, "entry_price": 2810.00, "exit_price": 2855.00, "stop_loss": 2770.00, "target_price": 2880.00, "pnl": 225.00, "pnl_pct": 1.60, "holding_duration_min": 55, "exit_reason": "TARGET", "strategy_name": "mean_reversion", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-11T13:00:00+05:30", "exit_at": "2026-04-11T13:55:00+05:30"},
  {"id": "t004", "symbol": "BAJFINANCE", "direction": "BUY", "quantity": 1, "entry_price": 7180.00, "exit_price": 7135.00, "stop_loss": 7100.00, "target_price": 7300.00, "pnl": -45.00, "pnl_pct": -0.63, "holding_duration_min": 62, "exit_reason": "STOP_LOSS", "strategy_name": "momentum", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-11T10:30:00+05:30", "exit_at": "2026-04-11T11:32:00+05:30"},
  {"id": "t005", "symbol": "SBIN", "direction": "BUY", "quantity": 12, "entry_price": 778.00, "exit_price": 792.50, "stop_loss": 765.00, "target_price": 800.00, "pnl": 174.00, "pnl_pct": 1.86, "holding_duration_min": 38, "exit_reason": "TARGET", "strategy_name": "mean_reversion", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-11T11:00:00+05:30", "exit_at": "2026-04-11T11:38:00+05:30"},
  {"id": "t006", "symbol": "TATAMOTORS", "direction": "BUY", "quantity": 14, "entry_price": 665.00, "exit_price": 678.50, "stop_loss": 650.00, "target_price": 690.00, "pnl": 189.00, "pnl_pct": 2.03, "holding_duration_min": 48, "exit_reason": "TARGET", "strategy_name": "bollinger_squeeze", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-10T12:15:00+05:30", "exit_at": "2026-04-10T13:03:00+05:30"},
  {"id": "t007", "symbol": "INFY", "direction": "BUY", "quantity": 6, "entry_price": 1535.00, "exit_price": 1510.00, "stop_loss": 1505.00, "target_price": 1580.00, "pnl": -150.00, "pnl_pct": -1.63, "holding_duration_min": 72, "exit_reason": "STOP_LOSS", "strategy_name": "golden_cross", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-10T09:30:00+05:30", "exit_at": "2026-04-10T10:42:00+05:30"},
  {"id": "t008", "symbol": "AXISBANK", "direction": "BUY", "quantity": 8, "entry_price": 1112.00, "exit_price": 1138.00, "stop_loss": 1090.00, "target_price": 1145.00, "pnl": 208.00, "pnl_pct": 2.34, "holding_duration_min": 41, "exit_reason": "TARGET", "strategy_name": "momentum", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-10T11:00:00+05:30", "exit_at": "2026-04-10T11:41:00+05:30"},
  {"id": "t009", "symbol": "LT", "direction": "BUY", "quantity": 3, "entry_price": 3250.00, "exit_price": 3220.00, "stop_loss": 3210.00, "target_price": 3320.00, "pnl": -90.00, "pnl_pct": -0.92, "holding_duration_min": 90, "exit_reason": "TIME_BASED", "strategy_name": "vwap_reversion", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-09T13:30:00+05:30", "exit_at": "2026-04-09T15:00:00+05:30"},
  {"id": "t010", "symbol": "MARUTI", "direction": "BUY", "quantity": 1, "entry_price": 12380.00, "exit_price": 12290.00, "stop_loss": 12250.00, "target_price": 12550.00, "pnl": -90.00, "pnl_pct": -0.73, "holding_duration_min": 85, "exit_reason": "STOP_LOSS", "strategy_name": "bollinger_squeeze", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-09T10:15:00+05:30", "exit_at": "2026-04-09T11:40:00+05:30"},
  {"id": "t011", "symbol": "ICICIBANK", "direction": "BUY", "quantity": 9, "entry_price": 1165.00, "exit_price": 1188.00, "stop_loss": 1145.00, "target_price": 1200.00, "pnl": 207.00, "pnl_pct": 1.97, "holding_duration_min": 52, "exit_reason": "TARGET", "strategy_name": "mean_reversion", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-09T11:45:00+05:30", "exit_at": "2026-04-09T12:37:00+05:30"},
  {"id": "t012", "symbol": "KOTAKBANK", "direction": "BUY", "quantity": 5, "entry_price": 1830.00, "exit_price": 1812.00, "stop_loss": 1800.00, "target_price": 1880.00, "pnl": -90.00, "pnl_pct": -0.98, "holding_duration_min": 68, "exit_reason": "STOP_LOSS", "strategy_name": "momentum", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-08T09:30:00+05:30", "exit_at": "2026-04-08T10:38:00+05:30"},
  {"id": "t013", "symbol": "BHARTIARTL", "direction": "BUY", "quantity": 6, "entry_price": 1565.00, "exit_price": 1590.00, "stop_loss": 1540.00, "target_price": 1610.00, "pnl": 150.00, "pnl_pct": 1.60, "holding_duration_min": 44, "exit_reason": "TARGET", "strategy_name": "mean_reversion", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-08T12:00:00+05:30", "exit_at": "2026-04-08T12:44:00+05:30"},
  {"id": "t014", "symbol": "SUNPHARMA", "direction": "BUY", "quantity": 5, "entry_price": 1708.00, "exit_price": 1695.00, "stop_loss": 1685.00, "target_price": 1750.00, "pnl": -65.00, "pnl_pct": -0.76, "holding_duration_min": 90, "exit_reason": "TIME_BASED", "strategy_name": "vwap_reversion", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-08T10:00:00+05:30", "exit_at": "2026-04-08T11:30:00+05:30"},
  {"id": "t015", "symbol": "HINDUNILVR", "direction": "BUY", "quantity": 4, "entry_price": 2395.00, "exit_price": 2420.00, "stop_loss": 2365.00, "target_price": 2450.00, "pnl": 100.00, "pnl_pct": 1.04, "holding_duration_min": 35, "exit_reason": "CONFIDENCE_DECAY", "strategy_name": "mean_reversion", "execution_mode": "paper", "slippage_bps": 5, "created_at": "2026-04-07T13:15:00+05:30", "exit_at": "2026-04-07T13:50:00+05:30"}
]
```

### Daily Metrics (last 5 trading days)
```json
[
  {"date": "2026-04-12", "total_trades": 3, "winning_trades": 2, "losing_trades": 1, "total_pnl": 470.00, "max_drawdown": 75.00, "max_capital_deployed": 22000, "signals_generated": 12, "signals_approved": 5, "signals_rejected": 7, "win_rate": 66.7, "profit_factor": 2.18, "sharpe_ratio": 1.52, "avg_pnl_per_trade": 156.67},
  {"date": "2026-04-11", "total_trades": 4, "winning_trades": 3, "losing_trades": 1, "total_pnl": 354.00, "max_drawdown": 45.00, "max_capital_deployed": 25000, "signals_generated": 15, "signals_approved": 6, "signals_rejected": 9, "win_rate": 75.0, "profit_factor": 2.85, "sharpe_ratio": 1.68, "avg_pnl_per_trade": 88.50},
  {"date": "2026-04-10", "total_trades": 3, "winning_trades": 2, "losing_trades": 1, "total_pnl": 247.00, "max_drawdown": 150.00, "max_capital_deployed": 21000, "signals_generated": 10, "signals_approved": 4, "signals_rejected": 6, "win_rate": 66.7, "profit_factor": 1.65, "sharpe_ratio": 1.15, "avg_pnl_per_trade": 82.33},
  {"date": "2026-04-09", "total_trades": 3, "winning_trades": 1, "losing_trades": 2, "total_pnl": 27.00, "max_drawdown": 180.00, "max_capital_deployed": 28000, "signals_generated": 11, "signals_approved": 4, "signals_rejected": 7, "win_rate": 33.3, "profit_factor": 1.15, "sharpe_ratio": 0.45, "avg_pnl_per_trade": 9.00},
  {"date": "2026-04-08", "total_trades": 3, "winning_trades": 2, "losing_trades": 1, "total_pnl": 195.00, "max_drawdown": 90.00, "max_capital_deployed": 19000, "signals_generated": 9, "signals_approved": 3, "signals_rejected": 6, "win_rate": 66.7, "profit_factor": 1.61, "sharpe_ratio": 1.22, "avg_pnl_per_trade": 65.00}
]
```

### Strategy Stats
```json
[
  {"strategy_name": "mean_reversion", "total_trades": 15, "winners": 11, "losers": 4, "win_rate": 73.3, "total_pnl": 1480.00, "profit_factor": 2.45, "expectancy": 98.67, "avg_holding_minutes": 38, "target_hit_rate": 66.7, "max_win": 380.00, "max_loss": -180.00},
  {"strategy_name": "momentum", "total_trades": 12, "winners": 7, "losers": 5, "win_rate": 58.3, "total_pnl": 920.00, "profit_factor": 1.62, "expectancy": 76.67, "avg_holding_minutes": 55, "target_hit_rate": 50.0, "max_win": 450.00, "max_loss": -220.00},
  {"strategy_name": "bollinger_squeeze", "total_trades": 8, "winners": 5, "losers": 3, "win_rate": 62.5, "total_pnl": 540.00, "profit_factor": 1.78, "expectancy": 67.50, "avg_holding_minutes": 42, "target_hit_rate": 50.0, "max_win": 290.00, "max_loss": -150.00},
  {"strategy_name": "golden_cross", "total_trades": 6, "winners": 3, "losers": 3, "win_rate": 50.0, "total_pnl": 180.00, "profit_factor": 1.25, "expectancy": 30.00, "avg_holding_minutes": 72, "target_hit_rate": 33.3, "max_win": 310.00, "max_loss": -250.00},
  {"strategy_name": "vwap_reversion", "total_trades": 4, "winners": 2, "losers": 2, "win_rate": 50.0, "total_pnl": 95.00, "profit_factor": 1.18, "expectancy": 23.75, "avg_holding_minutes": 35, "target_hit_rate": 50.0, "max_win": 180.00, "max_loss": -160.00},
  {"strategy_name": "pairs_trading", "total_trades": 2, "winners": 1, "losers": 1, "win_rate": 50.0, "total_pnl": 25.00, "profit_factor": 1.08, "expectancy": 12.50, "avg_holding_minutes": 65, "target_hit_rate": 50.0, "max_win": 90.00, "max_loss": -65.00}
]
```

### Activity Feed Events
```json
[
  {"time": "14:30", "type": "signal_executed", "message": "Signal APPROVED — RELIANCE BUY — confidence: 0.78 — Executed"},
  {"time": "14:30", "type": "signal_rejected", "message": "Signal REJECTED — WIPRO BUY — confidence: 0.58 — Below threshold"},
  {"time": "14:15", "type": "scan_complete", "message": "Scan completed — 5 signals generated, 2 approved, 3 rejected"},
  {"time": "14:15", "type": "exit_triggered", "message": "Exit triggered — HDFCBANK BUY — reason: TARGET — pnl: +₹320.00"},
  {"time": "14:00", "type": "scan_complete", "message": "Scan completed — 3 signals generated, 1 approved"},
  {"time": "13:45", "type": "regime_update", "message": "Regime confirmed: BULL (55% probability) — no change"},
  {"time": "13:30", "type": "signal_executed", "message": "Signal APPROVED — TATAMOTORS BUY — confidence: 0.71 — Queued (position limit)"},
  {"time": "13:15", "type": "scan_complete", "message": "Scan completed — 4 signals generated, 1 approved"},
  {"time": "12:00", "type": "sentiment_decay", "message": "Sentiment decay applied — 3 signals reduced by 15%"},
  {"time": "10:30", "type": "signal_executed", "message": "Signal APPROVED — ICICIBANK BUY — confidence: 0.74 — Executed"}
]
```

---

## Additional UI Notes

1. **Loading states:** Use skeleton loaders matching the dark theme, not spinners
2. **Empty states:** Show helpful messages like "No signals generated yet. Next scan at 14:30 IST."
3. **Tooltips:** Add tooltips on all abbreviations (RSI, ADX, ATR, EMA, VWAP, VIX, PnL, R:R)
4. **Number animations:** Animate PnL and price changes with brief color flash (green flash on increase, red on decrease)
5. **Responsive:** Sidebar collapses to icons on tablet. Tables become scrollable horizontally on mobile.
6. **Refresh indicator:** Subtle pulse animation on the "Last scan" timestamp when data is fresh (< 1 min old)
7. **Keyboard shortcuts:** `1-7` to switch pages, `R` to refresh data, `F` to toggle filters
8. **Status badges** should use consistent styling: filled for active states (executed, approved), outlined for inactive (pending, expired), red filled for negative (rejected, kill_switch)
