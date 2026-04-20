# Strategy Backtest Workflow

"Beat the idea to death before you fund it." Invokes the `backtest-expert` skill.

## Inputs
- Strategy name (from `src/strategies/`)
- Period (default `2y`)
- Parameter grid (optional)

## Steps

1. **Baseline run** — `python scripts/backtest_cli.py --strategy <name> --period <period>`; capture equity curve, trade list, stats.
2. **Sanity checks** — look-ahead bias (any `.shift(-n)`?), survivorship bias (delisted symbols?), cost model (slippage + brokerage realistic for Zerodha?).
3. **Parameter robustness** — sweep ±50% on each param; plot Sharpe surface. A single sharp peak = overfit.
4. **Walk-forward** — rolling 12-month train / 3-month test. Out-of-sample Sharpe should be ≥ 50% of in-sample.
5. **Regime breakdown** — stats by regime (bull / bear / chop). Strategy must not depend on a single regime unless declared.
6. **Cost sensitivity** — 2x slippage, does expectancy survive?
7. **Monte Carlo** — shuffle trade order 10k times; report 5th percentile max DD.
8. **Invoke `backtest-expert` skill** with the artifacts for a structured review.

## Output

Pass/fail verdict + the single weakest result. Only ship a strategy to paper if all 7 checks pass.
