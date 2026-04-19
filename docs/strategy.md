# Insight-Alpha 2026 — Strategy Reference

## Priority Hierarchy

Based on empirical backtesting research, parameters are applied in this order:

```
1. Risk Management    — Capital preservation. Without this, nothing else matters.
2. Regime Detection   — Match strategy to market state. Wrong env = guaranteed losses.
3. Factor Synergy     — Quality + Value + Momentum multi-factor approach.
4. Discipline         — Automated rules eliminate emotional deviation.
5. Sentiment Analysis — AI-driven news interpretation as a signal gate.
6. Technical Signals  — Entry/exit timing.
7. Microstructure     — Minimize slippage and execution friction.
```

---

## Indicator Performance Reference

From longitudinal backtesting research:

| Indicator | Win Rate | Gain/Loss Ratio | Classification |
|-----------|----------|-----------------|----------------|
| RSI (14) | 79.4% | 0.77 | High frequency, small gains |
| Bollinger Bands | 77.8% | 0.72 | Mean reversion |
| Donchian Channels | 74.1% | 0.71 | Breakout |
| Williams %R | 71.7% | 0.70 | Overbought/oversold |
| ADX (14) | 53.6% | 1.21 | Trend confirmation |
| Stochastics | 44.9% | 1.63 | Momentum reversal |
| Ichimoku Cloud | 42.3% | 2.11 | Comprehensive trend |
| MACD (12,26,9) | 40.1% | 2.01 | Trend momentum |
| EMA (50) | 30.7% | 3.34 | Trend filter |
| SMA (50) | 28.6% | 4.14 | Highest total return |

**Key insight:** SMA-based trend following wins only 28.6% of the time but earns 4.14× per win vs loss. The system must tolerate frequent small losses to capture large trends.

**Synergy:** RSI + MACD + EMA together outperforms any single indicator. RSI prevents overbought entries, MACD confirms direction, EMA filters trend.

---

## Market Regime States

The regime detector must classify market state before any strategy runs:

| State | ADX | Volatility | Action |
|-------|-----|------------|--------|
| TRENDING_LOW_VOL | > 25 | Low | Aggressive trend-following |
| TRENDING_HIGH_VOL | > 25 | High | Trend with 50% reduced sizing |
| MEAN_REVERTING | < 25 | Normal | RSI/Bollinger oscillator strategies |
| SIDEWAYS_CHOP | < 20 | Variable | Halt trading, move to cash |

**VIX/VIX3M ratio:** ratio > 1.0 (backwardation) indicates acute market stress — pause mean-reversion strategies.

---

## Implemented Strategies

### 1. Mean Reversion

**Regime:** MEAN_REVERTING only

**Logic:**
- Stock deviates significantly from VWAP (> 2 ATR)
- RSI confirms oversold/overbought (< 30 or > 70)
- Volume spike confirms institutional activity
- Bollinger Band %B at extremes (< 0.05 or > 0.95)

**Exit:**
- Price returns to VWAP ± 0.5 ATR
- Confidence decay > 40% from entry
- Time-based exit if position > 90 min

---

### 2. Momentum

**Regime:** TRENDING_LOW_VOL, TRENDING_HIGH_VOL

**Logic:**
- Price breaks above 20-day high on strong volume (> 1.5× avg)
- EMA(20) > EMA(50) > EMA(200) (full stack alignment)
- ADX > 25 confirms trend strength
- RSI 50–70 (momentum zone, not overbought)

**Exit:**
- EMA stack breaks (EMA20 crosses below EMA50)
- ADX falls below 20 (trend fading)
- Trailing stop: 2× ATR below recent high

---

### 3. Bollinger Squeeze

**Regime:** Any trending regime

**Logic:**
- Bollinger Band width at 52-week low (volatility compression)
- Inside Keltner Channel (squeeze confirmation)
- Directional bias from RSI + MACD histogram direction
- Entry on first candle that closes outside Bollinger Band

**Exit:**
- Band expansion reverses (BW contracts again)
- Target: 2× Bollinger width from entry

---

### 4. Golden Cross

**Regime:** TRENDING_LOW_VOL

**Logic:**
- EMA(50) crosses above EMA(200) (golden cross)
- Cross confirmed for at least 3 bars (avoids whipsaws)
- Volume on cross day > 1.2× 20-day average
- RSI not overbought (< 70) at entry

**Exit:**
- Death cross: EMA(50) crosses below EMA(200)
- Stop: 3× ATR below entry

---

### 5. VWAP Reversion

**Regime:** MEAN_REVERTING, intraday

**Logic:**
- Price deviates from VWAP by > 1.5 standard deviations
- Orderflow shows absorption (volume spike without further price move)
- Time: works best 09:30–13:00 IST (morning session)
- Confirmed by Stochastic %K crossing %D in oversold/overbought zone

**Exit:**
- Price returns to VWAP
- Time-based: 45 min max hold for intraday reversal

---

### 6. Fundamental-Technical (Planned)

Combines Piotroski FSCORE (quality filter) with technical entry timing.

FSCORE ≥ 7 + V/P ratio (undervaluation) + technical breakout = highest-quality setup.

Research shows FSCORE + V/P combined: **17.94% annual hedge return** vs 7.44% for FSCORE alone.

---

## Alpha Scoring Formula

```
confidence = (news_strength   × 0.25)
           + (signal_alignment × 0.30)
           + (market_confirm   × 0.25)
           + (liquidity_score  × 0.10)
           - (risk_penalty     × 0.20)
```

All filters must pass before execution:

| Filter | Threshold |
|--------|-----------|
| confidence | ≥ 0.65 |
| market_confirmation | ≥ 0.60 |
| liquidity_score | ≥ 0.60 |
| risk_penalty | ≤ 0.40 |

Final ranking:
```
final_score = confidence×0.4 + signal_alignment×0.3 + market_confirmation×0.2 + news_strength×0.1
```

---

## Sentiment Decay

News signals lose relevance over time:

```
news_strength_t = news_strength_0 × (1 - 0.15)^(t / 30)
```

- 15% decay every 30 minutes
- After 2 hours: news_strength reduced to ~52% of original
- After 4 hours: reduced to ~27% — unlikely to trigger a trade

---

## Macro Guard

When `regime_detector.predict(nifty_daily) == BEAR`:
- Cap bullish confidence at **0.60** (cannot exceed filter threshold of 0.65 without very strong other factors)
- This prevents the system from going long in confirmed bear markets

---

## Risk Rules (Non-Negotiable)

```
1. max_capital_per_trade:  ₹10,000
2. max_capital_deployed:   ₹30,000  (3 positions max at full size)
3. max_daily_loss:         ₹1,000   (kill switch triggers)
4. max_open_positions:     3
```

**Position sizing methods** (configurable):
- `fixed_pct`: Risk 2% of capital per trade, size = risk / stop_distance
- `atr`: ATR-based, size = (risk_INR) / (2 × ATR)
- `kelly`: Kelly criterion — `f = (p × b - q) / b` where p=win_rate, b=avg_win/avg_loss

**Always use fractional Kelly (0.25–0.5×)** to avoid over-leveraging on historical win rate estimates.

---

## Expectancy Formula

Track this metric to validate the edge:

```
Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
```

Target: Expectancy > ₹0 per trade. Minimum 50 trades before drawing conclusions.

---

## Transition: Paper → Live

Validate paper trading before going live:

| Metric | Minimum Threshold |
|--------|-------------------|
| Paper trading duration | 4+ weeks |
| Total trades | 50+ |
| Win rate | > 45% (trend) or > 60% (mean-reversion) |
| Max drawdown | < 15% of capital |
| Expectancy | > ₹50/trade after costs |
| Sharpe ratio | > 1.0 |

Start live with 25% of planned capital. Run paper and live concurrently for 2 weeks to validate execution matches simulation.
