# Per-Trade Postmortem

Run on every closed position — win or loss. Feeds the `signal-postmortem` skill and, over time, the alpha-score weights.

## Inputs
- Position ID or (symbol, entry_date).

## Steps

1. **Reconstruct the signal** — pull the original pending-signal row: features, confidence, horizon, rationale.
2. **Reconstruct the exit** — which trigger fired, at what price, after how many bars. Was the exit exchange-side (GTT) or software?
3. **Outcome classification** — one of: true positive, false positive, missed target (exited early), stop hit (thesis invalidated), time exit (thesis never played out), structure break.
4. **Feature drift** — did `confidence`, `market_confirmation`, or sentiment decay meaningfully between entry and exit? Plot the trajectory.
5. **Regime match** — was the regime at entry the regime the strategy is supposed to work in? (Cross-reference strategy metadata.)
6. **Invoke `signal-postmortem` skill** with the reconstructed record.
7. **Lesson** — one sentence. Add to `docs/trade_journal.md` (create if missing).

## Output

Row appended to postmortem store + one-line lesson + suggested weight nudge (if any) for the scoring model. Do not change weights automatically — just recommend.
