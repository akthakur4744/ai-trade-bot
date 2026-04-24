"""HTTP trigger API for heavy CCR-delegated operations.

POST /trigger/scan  — async: fires engine.run_cycle() in background, returns 200 immediately
POST /trigger/poll  — sync:  processes Telegram callbacks + persists offset

All endpoints require X-Trigger-Token header matching the TRIGGER_API_TOKEN env var.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import structlog
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException

logger = structlog.get_logger(__name__)
_TOKEN = os.environ.get("TRIGGER_API_TOKEN", "")

app = FastAPI()


def _auth(x_trigger_token: str = Header(..., alias="x-trigger-token")) -> None:
    if not _TOKEN or x_trigger_token != _TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


# ── /trigger/scan ─────────────────────────────────────────────────────────────

def _run_scan() -> None:
    from src.config import load_config
    from src.main import TradingEngine
    from src.storage.database import Database
    from src.storage.models import AppState

    cfg = load_config()
    db  = Database(cfg.database.url)
    engine = TradingEngine(cfg)
    try:
        engine.run_cycle()
    except Exception as e:
        logger.error("scan_cycle_error", error=str(e))
    finally:
        try:
            engine._telegram.stop_callback_polling()
        except Exception:
            pass

    now = datetime.now(timezone.utc).isoformat()
    try:
        with db.get_session() as s:
            row = s.query(AppState).filter_by(key="last_signal_scan_ts").first()
            if row:
                row.value = now
            else:
                s.add(AppState(key="last_signal_scan_ts", value=now))
            s.commit()
    except Exception as e:
        logger.warning("scan_heartbeat_failed", error=str(e))

    logger.info("scan_cycle_complete")


@app.post("/trigger/scan", dependencies=[Depends(_auth)])
def trigger_scan(background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(_run_scan)
    logger.info("scan_accepted")
    return {"ok": True, "status": "accepted"}


# ── /trigger/poll ─────────────────────────────────────────────────────────────

@app.post("/trigger/poll", dependencies=[Depends(_auth)])
def trigger_poll() -> dict:
    from src.config import load_config
    from src.feedback.memory_writer import MemoryWriter
    from src.feedback.postmortem_pipeline import PostmortemPipeline
    from src.notifications.telegram import TelegramNotifier
    from src.storage.database import Database
    from src.storage.models import AppState

    OFFSET_KEY    = "telegram_update_offset"
    HEARTBEAT_KEY = "last_telegram_poll_ts"

    cfg = load_config()
    db  = Database(cfg.database.url)
    tg  = TelegramNotifier()

    if not tg.is_configured:
        raise HTTPException(status_code=503, detail="Telegram not configured")

    offset = 0
    with db.get_session() as s:
        row = s.query(AppState).filter_by(key=OFFSET_KEY).first()
        if row:
            try:
                offset = int(row.value)
            except ValueError:
                offset = 0

    memory_pipeline = None
    engine = None

    def handle(action: str, signal_id: str) -> None:
        nonlocal memory_pipeline, engine
        logger.info("telegram_callback", action=action, signal_id=signal_id)

        if action == "memory_update":
            try:
                pending_id_str, sub_action = signal_id.split(":", 1)
                pending_id = int(pending_id_str)
            except (ValueError, AttributeError):
                logger.warning("memory_callback_malformed", signal_id=signal_id)
                return
            if memory_pipeline is None:
                memory_pipeline = PostmortemPipeline(
                    agent=None, writer=MemoryWriter(), telegram=tg, db=db
                )
            memory_pipeline.handle_memory_callback(pending_id, sub_action)
            return

        if action in ("approve", "ignore", "auto_sell"):
            from src.main import TradingEngine
            if engine is None:
                engine = TradingEngine(cfg)
            engine._handle_telegram_callback(action, signal_id)
            return

        logger.warning("telegram_callback_unknown_action", action=action)

    next_offset = tg.process_updates_once(offset, handler=handle)

    if engine is not None:
        try:
            engine._telegram.stop_callback_polling()
        except Exception:
            pass

    now = datetime.now(timezone.utc).isoformat()
    with db.get_session() as s:
        for key, value in [(OFFSET_KEY, str(next_offset)), (HEARTBEAT_KEY, now)]:
            row = s.query(AppState).filter_by(key=key).first()
            if row:
                row.value = value
            else:
                s.add(AppState(key=key, value=value))
        s.commit()

    logger.info("telegram_poll_done", offset_before=offset, offset_after=next_offset)
    return {"ok": True, "offset_before": offset, "offset_after": next_offset}
