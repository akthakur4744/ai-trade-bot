# Insight-Alpha 2026 — Strategy Reference

> Full version: [docs/strategy.md](docs/strategy.md)

## Priority Hierarchy

```
1. Risk Management     — Capital preservation first, always
2. Regime Detection    — Wrong regime = wrong strategy = guaranteed loss
3. Factor Synergy      — Quality + Value + Momentum combined
4. Discipline          — Automated rules, no emotion
5. Sentiment Analysis  — News as a signal gate (strength ≥ 0.65)
6. Technical Signals   — Entry/exit timing
7. Microstructure      — Minimize slippage, spread, execution lag
```

## Enabled Strategies

| Strategy | Regime | Win Rate Profile |
|----------|--------|-----------------|
| Mean Reversion | MEAN_REVERTING | High win rate, small gains |
| Momentum | TRENDING | Low win rate, large gains |
| Bollinger Squeeze | Any trending | Volatility breakout |
| Golden Cross | TRENDING_LOW_VOL | EMA(50) × EMA(200) crossover |
| VWAP Reversion | MEAN_REVERTING | Intraday only |

## Indicator Performance (Research-Backed)

| Indicator | Win Rate | Gain/Loss Ratio |
|-----------|----------|-----------------|
| RSI | 79.4% | 0.77 |
| Bollinger Bands | 77.8% | 0.72 |
| MACD | 40.1% | 2.01 |
| EMA (50) | 30.7% | 3.34 |
| SMA (50) | 28.6% | **4.14** |

SMA trend-following: only 28.6% wins but each win earns 4.14× the average loss.

## Paper → Live Transition Checklist

- [ ] 4+ weeks paper trading
- [ ] 50+ trades completed  
- [ ] Expectancy > ₹50/trade
- [ ] Max drawdown < 15%
- [ ] Sharpe ratio > 1.0
- [ ] Set `EXECUTION_MODE=live` + `CONFIRM_LIVE_TRADING=true`

See [docs/strategy.md](docs/strategy.md) for full details.
