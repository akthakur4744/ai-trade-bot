# Routine: Telegram Poll

**Schedule:** hourly during market window (cron: `0 3-10 * * 1-5` UTC = 08:30–15:30 IST).
Cloud Routines floor is 1 hour; for faster approval latency, the always-on
auto-sell worker can call the same entrypoint every 30s.

## Purpose

Process pending Telegram button callbacks that accumulated since the last run:
- Signal approvals / rejections (`BUY & Auto-Sell`, `Manual BUY`, `Ignore`).
- Memory-update approvals / rejections (open or reject GitHub PR).

Replaces the long-polling daemon thread in `telegram.py::_poll_callbacks` for
remote execution.

## Preconditions

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DATABASE_URL_*`, `GITHUB_PAT` set.
- `app_state` key `telegram_update_offset` tracks the next update_id to fetch.

## Behavior

1. Read `telegram_update_offset` from `app_state` (default 0).
2. Call Telegram `getUpdates` with `offset` + `timeout=0` (short poll — we are
   the one driving the cadence).
3. For each update with a `callback_query`:
   a. If the callback data matches a pending_signal row → dispatch to the
      approval callback handler (reuse `PendingSignalManager.handle_callback`).
   b. If it matches a pending_memory_update row → open (or close) a GitHub PR
      via `src/feedback/memory_writer.py::MemoryWriter.merge_via_pr()`.
4. Update `telegram_update_offset` to `last_update_id + 1`.
5. Exit 0.

## Implementation sketch

Refactor `TelegramNotifier._poll_callbacks` to split out:

```python
def process_updates_once(self, offset: int, handler: Callable[[str, str], None]) -> int:
    """One-shot: fetch updates from `offset`, dispatch, return next offset."""
    url = f"{TELEGRAM_API_BASE.format(token=self._token)}/getUpdates"
    resp = httpx.get(url, params={"offset": offset, "timeout": 0}, timeout=10.0)
    data = resp.json()
    next_offset = offset
    for update in data.get("result", []):
        next_offset = max(next_offset, update["update_id"] + 1)
        if "callback_query" in update:
            self._handle_callback(update["callback_query"], handler)
    return next_offset
```

The existing daemon `_poll_callbacks` becomes a thin loop over
`process_updates_once` for local-dev use.
