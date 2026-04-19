# Trading Strategies & Stock Selection Parameters
### A Comprehensive Guide for Building an Algorithmic Trading Agent

---

## 1. What Makes Trading Successful?

Successful trading boils down to three pillars:

1. **Edge** — A statistically proven strategy that generates positive expected returns over many trades.
2. **Risk Management** — Position sizing, stop-losses, and drawdown control that ensure survival during losing streaks.
3. **Discipline & Execution** — Removing emotion through automation; following rules without deviation.

> A strategy with a 40% win rate and a 3:1 risk-reward ratio will outperform one with a 60% win rate and a 1:0.5 ratio. It's not about being right often — it's about making more when you're right than you lose when you're wrong.

---

## 2. Stock Selection Parameters — Stack Ranked

Parameters are grouped into tiers by their proven impact on trading success.

### Tier 1 — Highest Impact (Must-Have)

| # | Parameter | Category | Why It Matters |
|---|-----------|----------|----------------|
| 1 | **Relative Strength Index (RSI)** | Technical — Momentum | Consistently the most reliable indicator in backtests across 100 years of Dow data. Identifies overbought (>70) and oversold (<30) conditions. Divergences between RSI and price are strong reversal signals. |
| 2 | **Volume & On-Balance Volume (OBV)** | Technical — Volume | Volume precedes price. Rising price + rising OBV = genuine trend. Rising price + falling OBV = weak move likely to reverse. Most traders ignore volume — that's an edge. |
| 3 | **Earnings Per Share (EPS) Growth** | Fundamental | The single most important driver of stock prices long-term. Consistent YoY EPS growth (>15%) identifies compounders. |
| 4 | **Price-to-Earnings (P/E) Ratio** | Fundamental — Valuation | Tells you what investors pay per dollar of earnings. Compare to sector average and the stock's own historical range. Low P/E relative to growth = potential undervaluation. |
| 5 | **Moving Averages (EMA 20/50/200)** | Technical — Trend | Price above 200-day MA = bullish regime. The 50/200 crossover ("Golden Cross" / "Death Cross") is one of the most widely tracked signals. |
| 6 | **Average True Range (ATR)** | Technical — Volatility | Essential for position sizing and stop-loss placement. Set stops at 1.5–2x ATR to avoid being stopped out by normal noise. |

### Tier 2 — High Impact (Strong Edge)

| # | Parameter | Category | Why It Matters |
|---|-----------|----------|----------------|
| 7 | **MACD (Moving Average Convergence Divergence)** | Technical — Momentum | Research shows MACD-based intelligent strategies are the safest and most effective among classical indicators. Histogram flips and divergences provide leading signals. |
| 8 | **Bollinger Bands** | Technical — Volatility | The "squeeze" (bands narrowing) reliably predicts breakouts. Band-walk (price riding upper/lower band) confirms strong trends. |
| 9 | **PEG Ratio** | Fundamental — Growth-adjusted Valuation | P/E divided by earnings growth rate. PEG < 1 = potentially undervalued. Solves the problem of high P/E stocks that are actually cheap relative to their growth. |
| 10 | **Debt-to-Equity (D/E) Ratio** | Fundamental — Financial Health | High leverage amplifies risk. D/E > 2 in non-financial sectors is a red flag. Low-debt companies survive recessions better. |
| 11 | **VWAP (Volume Weighted Average Price)** | Technical — Intraday | The institutional benchmark. Price above VWAP = buyers in control. Critical for intraday and swing trading entries. |
| 12 | **Return on Equity (ROE)** | Fundamental — Profitability | Measures how efficiently a company generates profits from shareholders' equity. ROE > 15% consistently = quality business. |

### Tier 3 — Moderate Impact (Confirmatory & Filtering)

| # | Parameter | Category | Why It Matters |
|---|-----------|----------|----------------|
| 13 | **ADX (Average Directional Index)** | Technical — Trend Strength | ADX > 25 = strong trend worth trading. ADX < 20 = ranging market, use mean-reversion. Filters out choppy conditions. |
| 14 | **Stochastic Oscillator** | Technical — Momentum | Best in range-bound markets. %K/%D crossovers below 20 or above 80 signal reversals. |
| 15 | **Price-to-Book (P/B) Ratio** | Fundamental — Valuation | Useful for capital-heavy sectors (banks, manufacturing). P/B < 1 can indicate deep value or distress. |
| 16 | **Revenue Growth (YoY)** | Fundamental — Growth | Revenue is harder to manipulate than earnings. Consistent >10% YoY growth signals expanding market share. |
| 17 | **Free Cash Flow (FCF)** | Fundamental — Quality | Positive and growing FCF = real cash generation, not accounting profit. Companies with strong FCF can self-fund growth, pay dividends, buy back shares. |
| 18 | **Dividend Yield & Payout Ratio** | Fundamental — Income | Sustainable dividends (payout ratio < 60%) signal management confidence. Very high yields (>8%) are often traps — the price may have fallen for good reason. |
| 19 | **Donchian Channels** | Technical — Breakout | One of the most consistent indicators over 100 years of data. Simple highest-high/lowest-low breakout system. |
| 20 | **Fibonacci Retracements** | Technical — Support/Resistance | 38.2%, 50%, 61.8% levels act as magnets for price. Useful for identifying entry points during pullbacks in trending stocks. |

### Tier 4 — Contextual / Macro Filters

| # | Parameter | Category | Why It Matters |
|---|-----------|----------|----------------|
| 21 | **Sector & Industry Relative Strength** | Macro | Buy the strongest stocks in the strongest sectors. Sector rotation is one of the most persistent market patterns. |
| 22 | **Market Breadth** | Macro | Advance/Decline ratio, % of stocks above 200 MA. Healthy breadth confirms rallies; narrow breadth warns of fragility. |
| 23 | **Interest Rate Environment** | Macro | P/E ratios are far more sensitive to growth expectations when rates are low. Rising rates compress multiples. |
| 24 | **Insider Buying/Selling** | Sentiment | Insiders buy for one reason — they believe the stock will go up. Cluster buying is a strong bullish signal. |
| 25 | **Short Interest** | Sentiment | High short interest (>20% of float) can fuel short squeezes but also signals fundamental concern. |

---

## 3. Proven & Backtested Trading Strategies

### Strategy 1: Mean Reversion with RSI (Stocks)

**Edge:** Stocks are mean-reverting assets. Buying when RSI is oversold and selling when overbought has been consistently profitable.

- **Setup:** Weekly RSI(14) drops below 30 on a stock that is above its 200-day MA (to confirm long-term uptrend).
- **Entry:** Buy at close when RSI < 30.
- **Exit:** Sell when RSI crosses back above 50, OR after 10 trading days (whichever comes first).
- **Stop-loss:** 2x ATR(14) below entry.
- **Backtested Performance:** ~0.77% average gain per trade; ~12% annualized on consumer staples ETFs.
- **Best For:** Swing trading, 1–3 week holding periods.

### Strategy 2: Momentum / Trend Following

**Edge:** Stocks that have been going up tend to continue going up (3–12 month timeframe).

- **Setup:** Buy top 10% of stocks ranked by 12-month returns (excluding last month to avoid mean-reversion noise).
- **Rebalance:** Monthly.
- **Filter:** Only buy stocks above their 200-day MA and with ADX > 25.
- **Exit:** Sell when stock drops out of top 30% ranking OR crosses below 200-day MA.
- **Risk Management:** Equal-weight positions; max 5% per stock.
- **Backtested Performance:** Academic research (Jegadeesh & Titman) shows momentum generates 1–1.5% monthly excess returns historically.
- **Best For:** Medium-term portfolio management.

### Strategy 3: Bollinger Band Squeeze Breakout

**Edge:** Periods of low volatility (the "squeeze") are reliably followed by high-volatility moves.

- **Setup:** Bollinger Band width contracts to its lowest level in 120 days.
- **Entry:** Buy on a close above the upper band (bullish breakout); short on close below lower band.
- **Confirmation:** Volume should be >1.5x the 20-day average on the breakout day.
- **Exit:** Trailing stop at the 20-day MA (the middle Bollinger Band).
- **Stop-loss:** Opposite Bollinger Band at entry.
- **Best For:** Day trading and swing trading volatile stocks.

### Strategy 4: Golden Cross / Death Cross (50/200 MA)

**Edge:** Long-term trend following with one of the most battle-tested signals.

- **Setup:** 50-day EMA crosses above 200-day EMA (Golden Cross = buy); crosses below (Death Cross = sell/short).
- **Filter:** Confirm with ADX > 25 to avoid whipsaws in ranging markets.
- **Exit:** Opposite cross, OR trailing stop at 200-day MA.
- **Backtested Performance:** Reduces drawdowns by ~50% compared to buy-and-hold while capturing ~70–80% of upside.
- **Best For:** Long-term position trading, portfolio-level risk management.

### Strategy 5: VWAP Reversion (Intraday)

**Edge:** Institutional traders use VWAP as fair value. Extreme deviations from VWAP tend to revert.

- **Setup:** Stock trades >2 standard deviations from VWAP in the first 2 hours of the session.
- **Entry:** Fade the move (buy below VWAP, sell above) when price starts reverting.
- **Confirmation:** RSI divergence on 5-minute chart.
- **Exit:** VWAP itself (target the mean).
- **Stop-loss:** Beyond the extreme of the day.
- **Best For:** Intraday trading, high-volume stocks.

### Strategy 6: Seasonal / Calendar Strategy

**Edge:** Certain calendar windows show persistent outperformance due to structural reasons (rebalancing, fund flows).

- **Example — Russell 2000 Rebalance:** Buy Russell 2000 on the close of the first trading day after June 23rd; sell on the first trading day of July. Backtested over 30+ years with consistent positive returns.
- **Example — Turn of the Month:** Buy S&P 500 on the last trading day of the month; sell on the 3rd trading day of the next month. Makes ~0.6% per trade, ~7% annualized, while being invested only 33% of the time. Max drawdown is half of buy-and-hold.
- **Best For:** Low-frequency supplemental strategy in a diversified portfolio.

### Strategy 7: Pairs Trading / Statistical Arbitrage

**Edge:** Exploit the temporary divergence between two historically correlated stocks.

- **Setup:** Identify pairs with cointegration (not just correlation). Example: Coca-Cola and PepsiCo.
- **Entry:** When the price ratio deviates >2 standard deviations from its mean, buy the underperformer and short the outperformer.
- **Exit:** When the ratio reverts to the mean (z-score < 0.5).
- **Stop-loss:** Z-score exceeds 3.5 (spread is broken, assumption invalid).
- **Risk Management:** Dollar-neutral (equal capital long and short).
- **Best For:** Market-neutral strategies that profit regardless of market direction.

### Strategy 8: Fundamental Value + Technical Trigger

**Edge:** Combine fundamental cheapness with a technical catalyst for entry timing.

- **Screening (Fundamental):**
  - P/E below sector average
  - PEG < 1
  - ROE > 15%
  - D/E < 1
  - Positive FCF growth
  - EPS growth > 10% YoY
- **Entry (Technical):**
  - RSI drops below 35 (short-term oversold)
  - Price is near a Fibonacci retracement level (38.2% or 61.8%)
  - MACD histogram starts turning positive (momentum shift)
- **Exit:** Take profit at prior resistance; trail stop with 20-day EMA.
- **Best For:** Swing trading fundamentally strong stocks at technical discounts.

---

## 4. Key Performance Metrics for Your Agent

When backtesting and paper trading, track these metrics:

| Metric | What It Tells You | Good Benchmark |
|--------|-------------------|----------------|
| **Sharpe Ratio** | Risk-adjusted return | > 1.0 (solid), > 2.0 (excellent) |
| **Max Drawdown** | Worst peak-to-trough loss | < 20% for most strategies |
| **Win Rate** | % of profitable trades | 40–60% is typical for good strategies |
| **Profit Factor** | Gross profits / gross losses | 1.5–2.5 is ideal; >4.0 may signal overfitting |
| **Expectancy** | Average profit per trade | Must be >2–3x your transaction costs |
| **Recovery Factor** | Net profit / max drawdown | Higher = faster recovery from losses |
| **Sortino Ratio** | Like Sharpe but only penalizes downside volatility | > 1.5 |
| **Time Underwater** | Duration spent in drawdown | Shorter = psychologically easier |

---

## 5. Critical Pitfalls to Avoid

1. **Overfitting / Curve Fitting** — If your strategy has more than 4–5 parameters, you're probably fitting noise. Keep rules simple. One real-world case: a mean-reversion strategy backtested at 32% annual returns lost 24.5% in 3 months of live trading due to overfitting.

2. **Survivorship Bias** — If your data only includes currently listed stocks, you're ignoring the ones that went bankrupt. This inflates returns by several percentage points annually.

3. **Ignoring Transaction Costs** — A strategy showing 30% returns before costs might deliver only 15% after fees and slippage. Expect live drawdown to be 1.5–2x backtested drawdown.

4. **Data Snooping** — Testing 10,000 parameter combinations will produce strategies that look profitable by pure chance (~8.4% will show Sharpe > 1.0 randomly). Use walk-forward analysis and out-of-sample testing.

5. **Regime Blindness** — A strategy that works in bull markets may fail in bear markets. Always test across multiple market cycles (at least 10 years of data covering different regimes).

---

## 6. Recommended Agent Architecture

```
┌─────────────────────────────────────────────────────┐
│                  DATA PIPELINE                       │
│  Market Data → Fundamental Data → Sentiment Data     │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              SIGNAL GENERATION                       │
│  Technical Indicators + Fundamental Screens          │
│  + Macro Filters + Sentiment Scores                  │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              STRATEGY ENGINE                         │
│  Multiple strategies running in parallel             │
│  Each with independent entry/exit/sizing rules       │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              RISK MANAGEMENT                         │
│  Position sizing (Kelly Criterion / Fixed %)         │
│  Max drawdown limits → kill switch                   │
│  Correlation checks (avoid concentrated bets)        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              EXECUTION                               │
│  Paper Trading → Validation → Live Trading           │
│  Broker API (Alpaca, IBKR, Zerodha)                  │
└─────────────────────────────────────────────────────┘
```

---

## 7. Paper Trading → Live: The Transition Checklist

1. Backtest across 10+ years of data covering multiple market regimes.
2. Validate with walk-forward analysis (rolling in-sample/out-of-sample windows).
3. Paper trade for at least 3–6 months to confirm live performance matches backtest.
4. Start live with 10–25% of intended capital.
5. Scale up only if live Sharpe ratio remains within 70% of backtested Sharpe.
6. Monitor continuously — markets change, edges decay.

---

*Disclaimer: This document is for educational and research purposes only. Trading involves significant risk of loss. Most traders lose money. Always do your own due diligence before risking real capital.*
