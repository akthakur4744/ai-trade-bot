# Pre-Market Check (09:00 IST)

**Schedule:** daily (cron: `30 3 * * 1-5` UTC).

Run before every trading session. Goal: catch auth/config/regime issues
before the engine arms.

## Steps

1. **Kite session**
   - Read `kite_access_token` from Neon `app_state`. Confirm
     `kite_session_expires_at` is in the future.
   - If stale/missing, Telegram alert "session not active" and exit 0 —
     the `morning-login-prompt` routine will (or already did) re-post the
     login link.
2. **Config sanity**
   - Load `config/paper.yaml` (or `live.yaml`) via `src/config.py`; report
     `execution.mode`, capital caps, `max_open_positions`.
   - Flag any value that drifted from guardrails in `CLAUDE.md` (10k/trade,
     30k deployed, 1k daily loss, 3 positions).
3. **Watchlist** — read `config/watchlist.yaml` symbol count; warn if any
   symbol failed last LTP fetch (check structlog entries in Neon `app_state`
   if we persist them, else skip).
4. **Regime** — invoke the `macro-regime-detector` skill. If regime = bear,
   confirm bullish-confidence cap (0.6) is active in config.
5. **Overnight news** — invoke `market-news-analyst` for the last 16h on
   watchlist symbols; surface anything with impact ≥ high.
6. **Open positions & GTTs** — query Neon: open positions, active triggers,
   GTT OCO status. Any position without exchange GTT protection is a red
   flag — run `gtt-reconcile.md`.

## Output

One-screen summary to Telegram: ✅ / ⚠️ / ❌ per step, with exact commands
to fix any ❌.
