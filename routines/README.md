# Claude Code Routines

Reusable operational playbooks for the Insight-Alpha trading agent. Each `.md` is a
self-contained prompt — run it by pasting its contents into Claude Code, or reference it
as `@routines/<name>.md`.

Routines are grouped by cadence:

| Cadence     | Routine                          | Purpose                                              |
|-------------|----------------------------------|------------------------------------------------------|
| Daily AM    | `pre-market-check.md`            | Auth, config, regime, watchlist sanity before 09:15  |
| Intraday    | `signal-review.md`               | Review a pending signal before approving             |
| Intraday    | `risk-audit.md`                  | Verify guardrails + open positions mid-session       |
| Daily PM    | `end-of-day-report.md`           | Positions, PnL, triggers, unresolved signals         |
| Per-trade   | `postmortem-trade.md`            | Record outcome, feed signal-postmortem skill         |
| Weekly      | `weekly-performance-review.md`   | Aggregate stats, strategy attribution                |
| Weekly      | `regime-check.md`                | Re-evaluate macro regime, adjust caps                |
| Ad-hoc      | `strategy-backtest.md`           | Full backtest workflow with robustness tests         |
| Ad-hoc      | `new-strategy-checklist.md`      | Scaffold + validate a new `Strategy` subclass        |
| Ad-hoc      | `kite-token-health.md`           | Diagnose auth / token / auto-login issues            |
| Ad-hoc      | `gtt-reconcile.md`               | Verify exchange GTTs match local state               |

Edit freely — these are playbooks, not contracts.
