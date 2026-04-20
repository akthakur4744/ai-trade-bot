# New Strategy Checklist

Scaffold + validate before adding a new subclass to `src/strategies/`.

## Design

1. **Thesis in one sentence** — what edge, why it exists, why it hasn't been arbitraged away.
2. **Regime scope** — which regime(s) it's supposed to work in. If "all", be suspicious.
3. **Entry rule** — expressible in indicators that already exist in `src/indicators/`? If not, add a pure function there first.
4. **Exit rule** — define all 6 trigger types (hard stop, target, trailing, time, confidence decay, structure break). Any missing → justify.
5. **Expected holding period** → maps to signal `horizon` (Short 1-3d / Medium 4-10d).

## Implementation

6. Subclass `Strategy` ABC; implement `scan()` and `check_exit()`. Full type hints. structlog, not print.
7. Unit tests in `tests/unit/strategies/test_<name>.py`: entry trigger, exit trigger, no-signal, edge cases (empty df, NaN).
8. Integration test in `tests/integration/`: run against a known fixture, assert expected signal count.

## Validation

9. Run `routines/strategy-backtest.md`.
10. Paper-trade for ≥ 20 trades before any live allocation.
11. Wire into `config/strategies/<name>.yaml` with conservative initial weight.

## Output

Pull request with: code, tests, backtest artifacts, thesis doc in `docs/strategies/<name>.md`.
