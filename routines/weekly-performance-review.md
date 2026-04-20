# Weekly Performance Review (Sunday)

## Steps

1. **Headline stats** — weekly PnL, win rate, avg win / avg loss, expectancy, max drawdown, Sharpe (daily returns).
2. **Strategy attribution** — per-strategy contribution; rank best → worst. Flag any strategy with negative expectancy over trailing 20 trades.
3. **Signal funnel** — generated → filtered → approved → executed → profitable. Where is the biggest drop-off?
4. **Alpha score calibration** — bucket confidence into deciles; plot realized win rate per bucket. If top decile isn't the highest win rate, the model is miscalibrated.
5. **Exit-trigger attribution** — which trigger types produced the best outcomes? Trailing stop usually wins; if stop-loss dominates, entries are too early.
6. **Regime review** — invoke `macro-regime-detector`; compare to last week. Any transition means strategy weights need revisiting.
7. **Agent cost + cache** — weekly Claude spend, per-agent breakdown, cache hit rate.
8. **Backlog** — open TODOs in code, failing tests (`pytest tests/`), lint findings (`ruff check src/ tests/`).

## Output

Markdown report saved to `docs/reports/YYYY-WW.md`. One paragraph of "what I'd change" at the end — don't change it yet, just note.
