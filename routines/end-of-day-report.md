# End-of-Day Report (after 15:30 IST)

## Steps

1. **PnL** — realized + unrealized, per symbol and aggregate. Compare to daily-loss guardrail (1,000 INR floor).
2. **Orders executed today** — count by action (BUY auto-sell, manual BUY, exit); fill quality vs signal entry price.
3. **Signals summary** — generated / approved / ignored / expired (15-min timeout). Approval rate trend vs 7-day avg.
4. **Exit attribution** — for each position closed today, which trigger fired (stop / target / trail / time / confidence / structure)? Was it exchange GTT or software?
5. **Unresolved signals** — any still pending near expiry. Decide now, don't let them rot.
6. **Strategy attribution** — PnL and win rate by strategy (8 strategies in `src/strategies/`).
7. **Agent cost** — Claude API spend today (Researcher / Sentinel / Orchestrator / Stitch), cache hit rate.
8. **Log scan** — errors/warnings from structlog since 08:55.

## Output

Markdown report suitable for pasting into a daily journal. End with "3 things to fix tomorrow" if anything in steps 1-8 flagged red.
