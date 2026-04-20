# Signal Review (Pre-Approval)

Invoked when a pending signal needs a second look before I hit [BUY & Auto-Sell] / [Manual BUY] / [Ignore].

## Inputs
- Signal ID or symbol (ask if not provided).

## Steps

1. **Pull the signal** from the pending queue (SQLAlchemy, `pending_signals` table). Report: symbol, direction, entry/target/stop, confidence, signal_alignment, market_confirmation, liquidity_score, risk_penalty, horizon, expires_at.
2. **Recompute the alpha score** from stored features using the formula in `CLAUDE.md`. Flag any drift from the stored `confidence`.
3. **Verify filters** (confidence ≥ 0.65, market_confirmation ≥ 0.6, liquidity_score ≥ 0.6, risk_penalty ≤ 0.4). Any fail → recommend Ignore.
4. **Guardrail simulation** — would executing this order still satisfy all 4 risk guardrails given current open positions and deployed capital?
5. **Technical second opinion** — run the `technical-analyst` skill on the current weekly chart; compare its trend/SR read to the signal direction.
6. **Counter-signals** — scan recent Sentinel agent output for this symbol; any unresolved counter-signal downgrades confidence.
7. **News sanity** — `market-news-analyst` for last 24h on this symbol; headline risk?
8. **Position sizing** — invoke `position-sizer` with entry/stop/capital caps; report share count and % risk.

## Output

Recommendation (`BUY & Auto-Sell` / `Manual BUY` / `Ignore`) + 3-line rationale + the exact exit trigger set the auto-sell manager would create.
