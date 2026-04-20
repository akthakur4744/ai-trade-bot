# Risk Audit (Intraday Spot-Check)

Run on demand mid-session, or whenever the kill switch trips.

## Steps

1. **Guardrail snapshot** — for each of the 4 guardrails in `CLAUDE.md`, print current value vs cap:
   - largest open order notional
   - total deployed capital
   - realized PnL for the day
   - open position count
2. **Position-level risk** — per open position: entry, LTP, unrealized PnL, distance-to-stop (%), distance-to-target (%), active triggers (stop / target / trail / time / confidence / structure).
3. **GTT coverage** — every auto-sell position must have a live GTT OCO on the exchange. Query `src/execution` GTT manager, diff against exchange. Report orphans either direction.
4. **Trigger freshness** — any trigger whose `last_evaluated_at` is > 5 min stale means the monitor loop is lagging.
5. **Kill switch state** — if engaged, explain *why* (which guardrail fired, which event).
6. **Telegram callback daemon** — confirm the polling thread is alive (check recent structlog heartbeat).

## Output

Traffic-light table + immediate actions. Do not propose config changes unless a guardrail is breached.
