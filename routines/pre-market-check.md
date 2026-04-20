# Pre-Market Check (08:55 – 09:15 IST)

Run before every trading session. Goal: catch auth/config/regime issues before the engine arms.

## Steps

1. **Kite auth**
   - Read `~/.insight_alpha/kite_token.json`; confirm `access_token` present and `generated_at` is today.
   - If missing/stale, run `python scripts/kite_auto_login.py --headed` and tail `~/.insight_alpha/auto_login.log`.
2. **Config sanity**
   - Load `config/paper.yaml` (or `live.yaml`) via `src/config.py`; report `execution.mode`, capital caps, `max_open_positions`.
   - Flag any value that drifted from guardrails in `CLAUDE.md` (10k/trade, 30k deployed, 1k daily loss, 3 positions).
3. **Watchlist**
   - Print `config/watchlist.yaml` symbol count; warn if any symbol failed last LTP fetch (check recent structlog entries).
4. **Regime**
   - Invoke the `macro-regime-detector` skill. If regime = bear, confirm bullish-confidence cap (0.6) is active in config.
5. **Overnight news**
   - Invoke `market-news-analyst` for the last 16h on watchlist symbols; surface anything with impact ≥ high.
6. **Open positions & GTTs**
   - Query the DB: open positions, active triggers, GTT OCO status. Any position without exchange GTT protection is a red flag — run `gtt-reconcile.md`.

## Output

One-screen summary: ✅ / ⚠️ / ❌ per step, with exact commands to fix any ❌.
