# Routine: Heartbeat

**Schedule:** hourly during market window (cron: `30 3-10 * * 1-5` UTC).

## Purpose

Watchdog that alerts if any critical trigger has stopped firing:

- `last_autosell_tick_ts` > 2 min stale → "⚠️ Auto-sell worker silent"
- `last_signal_scan_ts`   > 2 × scan cadence stale → "⚠️ Signal-scan missed"
- Kite session stale / missing during market hours → "⚠️ No Kite session"
- Two consecutive routine failures (tracked in `app_state`) → alert

## Data contract

Every trigger updates a well-known `app_state` key on success:

| Key                         | Writer                      |
|-----------------------------|-----------------------------|
| `last_autosell_tick_ts`     | `auto-sell-tick`            |
| `last_signal_scan_ts`       | `signal-scan`               |
| `last_telegram_poll_ts`     | `telegram-poll`             |
| `last_heartbeat_ts`         | `heartbeat` (self)          |

Values are ISO-8601 UTC timestamps.

## Behavior

Read each key, compare to `now - threshold`, emit one consolidated Telegram
alert per run (not one per stale check). If everything's green, stay silent.

## Failure-amplification guard

Don't alert during the first 10 min after market open — the first scan/tick
hasn't fired yet.
