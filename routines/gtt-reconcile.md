# GTT Reconciliation

Every auto-sell position must have a live GTT OCO (stop + target) on the exchange. The app runs reconciliation on startup; this routine runs it on demand.

## Steps

1. **Local state** — query `triggers` table: all active auto-sell positions and their expected stop/target legs.
2. **Exchange state** — fetch GTTs from Kite GTT API (paper mode: in-memory store).
3. **Diff:**
   - **Orphan position** (local trigger, no exchange GTT) → re-place immediately. Root cause? (Startup race? Network fail? GTT rejected?)
   - **Orphan GTT** (exchange GTT, no local trigger) → position was closed but GTT wasn't cancelled; cancel now.
   - **Price drift** — local trail stop says X, exchange stop leg says Y. Only update if improvement ≥ 0.5% and cooldown ≥ 60s elapsed (per `CLAUDE.md` rate-limit rules).
4. **Log every action** via structlog with `event=gtt_reconcile` and the diff reason.

## Output

Diff table + actions taken (or proposed, if dry-run). Never silently modify exchange GTTs — always log the before/after.
