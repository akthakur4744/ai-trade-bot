"""Combined Fly.io entrypoint: auto-sell tick loop + HTTP trigger API.

The auto-sell loop runs in a daemon thread (same logic as auto_sell_tick.py).
FastAPI/uvicorn runs on port 8080 in the main thread and handles trigger
requests from CCR routines. When uvicorn exits (SIGTERM from Fly.io), the
daemon thread terminates with it.
"""
from __future__ import annotations

import sys
import threading

import structlog
import uvicorn

from workers.auto_sell_tick import run_loop
from workers.trigger_api import app

logger = structlog.get_logger(__name__)

_stop = threading.Event()


def main() -> int:
    t = threading.Thread(
        target=run_loop, args=(_stop,), daemon=True, name="auto-sell-tick"
    )
    t.start()
    logger.info("auto_sell_thread_started")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
    _stop.set()  # Signal loop to stop on next wakeup.
    return 0


if __name__ == "__main__":
    sys.exit(main())
