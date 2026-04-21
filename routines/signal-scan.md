# Routine: Signal Scan

**Schedule:** hourly during market hours (cron: `0 4-10 * * 1-5` UTC = 09:30–15:30 IST).
**Ideal cadence:** 5 min — but cloud Routines floor is 1 hour. The engine's
internal `scan_interval_minutes` is still honored within each run.

## Purpose

Run the full analysis pipeline once: fetch data → compute indicators → run
strategies → run AI agents → score → filter → enqueue pending signals. For
each qualifying signal, write a row to `pending_signal_state` and post a
Telegram approval card.

## Preconditions

- `is_market_open(now)` — else exit 0.
- `get_active_session(db)` returns a live Kite session — else Telegram alert
  "Session not active, please log in" and exit 0.
- Risk guardrails met (daily loss floor, max positions, etc.).

## Behavior

Exactly the signal-generation path of `src/main.py::Engine.run_once()`
extracted so we don't spin the APScheduler loop. No execution here —
execution happens only when the user taps Approve in Telegram, handled by
the `telegram-poll` routine.

## Implementation entrypoint

```python
# routines/impl/signal_scan.py
from src.config import load_config
from src.storage.database import Database
from src.data.kite_session import get_active_session
from src.utils.market_calendar import is_market_open

def main() -> int:
    if not is_market_open():
        return 0
    cfg = load_config()
    db = Database(cfg.database.url)
    with db.get_session() as s:
        if not get_active_session(s):
            # heartbeat routine will alert; stay silent here to avoid spam
            return 0
    # import Engine lazily — cold-start cost matters for 5-min cadence
    from src.main import Engine
    engine = Engine(cfg, db)
    engine.run_scan_only()  # to be added: the scan half of run_once()
    return 0
```

Requires extracting the scan half of `Engine.run_once` into a dedicated
`run_scan_only()` method that does NOT execute orders.
