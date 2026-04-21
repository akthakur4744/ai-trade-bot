# Routine: Auto-Sell Tick

**Schedule:** every 1 min during market hours (**NOT cloud Routines** — runs
on the always-on Fly.io worker; cloud Routines floor is 1 h).

## Purpose

Evaluate auto-sell exit conditions for every active position and fire a
market sell when any trigger hits. GTT OCO is the exchange-level backstop;
this routine handles the software-only triggers:

- Trailing stop (% from peak)
- Time-based exit
- Structure break (reversal + volume spike)
- Confidence decay

## Preconditions

- Active Kite session (`get_active_session`); else exit 0 silently — the
  GTT OCO sitting on-exchange still protects the position.
- `is_market_open()`; else exit 0.

## Behavior

Reuses `src/execution/auto_sell_manager.AutoSellManager`. Iterates active
rows from `auto_sell_trigger_state`; for each, calls `check_exit(position,
ltp, confidence)`; if an exit fires, places a market SELL via
`LiveBroker` (live) or `PaperBroker` (paper).

## Rate-limit budget

Kite allows 10 req/s. One tick across N open positions:
- 1 × LTP batch call (all symbols)
- up to N × GTT update calls (for trailing-stop improvements)

With `max_open_positions = 3`, this is comfortably under the limit.

## Fly.io worker skeleton

```
flyctl launch --name insight-alpha-autosell --image python:3.11-slim
# Single process: while True: run_tick(); sleep(60)
```

See `fly.toml` and `worker/run_autosell.py` (to be added in deploy PR).

## Missed-tick alerting

The `heartbeat` routine checks `app_state[last_autosell_tick_ts]` — if older
than 2 × cadence, Telegram alert fires. Positions are still protected by
GTT OCO during outages.
