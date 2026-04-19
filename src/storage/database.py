"""Database setup, session management, and persistence methods."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from src.storage.models import (
    AppState,
    AutoSellTriggerState,
    Base,
    PendingMemoryUpdate,
    PendingSignalState,
    PositionState,
    Signal,
    Trade,
)

logger = structlog.get_logger(__name__)


class Database:
    """Manages SQLAlchemy engine and sessions."""

    def __init__(self, url: str = "sqlite:///insight_alpha.db") -> None:
        self.engine = create_engine(url, echo=False)
        self._session_factory = sessionmaker(bind=self.engine)

        # Enable WAL mode for SQLite concurrent read/write safety
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _set_wal_mode(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()

    def create_tables(self) -> None:
        """Create all tables if they don't exist, and migrate schema."""
        Base.metadata.create_all(self.engine)
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        """Add missing columns to existing tables (lightweight migration)."""
        inspector = inspect(self.engine)

        if "auto_sell_trigger_state" in inspector.get_table_names():
            existing = {
                col["name"] for col in inspector.get_columns("auto_sell_trigger_state")
            }
            migrations = {
                "gtt_trigger_id": "VARCHAR(50) DEFAULT ''",
                "gtt_status": "VARCHAR(20) DEFAULT 'pending'",
                "gtt_stop_price": "FLOAT DEFAULT 0.0",
                "gtt_last_updated": "DATETIME",
            }
            with self.engine.begin() as conn:
                for col_name, col_type in migrations.items():
                    if col_name not in existing:
                        conn.execute(text(
                            f"ALTER TABLE auto_sell_trigger_state "
                            f"ADD COLUMN {col_name} {col_type}"
                        ))
                        logger.info(
                            "schema_migration",
                            table="auto_sell_trigger_state",
                            column=col_name,
                        )

    def get_session(self) -> Session:
        """Create a new database session."""
        return self._session_factory()

    # ---- Position State ----

    def save_position(self, position: Any) -> None:
        """Upsert an open position by symbol."""
        session = self._session_factory()
        try:
            row = session.query(PositionState).filter_by(
                symbol=position.symbol
            ).first()
            direction_val = (
                position.direction.value
                if hasattr(position.direction, "value")
                else position.direction
            )
            if row:
                row.direction = direction_val
                row.quantity = position.quantity
                row.entry_price = position.entry_price
                row.current_price = position.current_price
                row.stop_loss = position.stop_loss
                row.target_price = position.target_price
                row.order_id = position.order_id
                row.signal_id = position.signal_id
                row.strategy_name = position.strategy_name
                row.entry_time = position.entry_time
                row.capital_deployed = position.capital_deployed
                row.updated_at = datetime.utcnow()
            else:
                row = PositionState(
                    symbol=position.symbol,
                    exchange=getattr(position, "exchange", "NSE"),
                    direction=direction_val,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    current_price=position.current_price,
                    stop_loss=position.stop_loss,
                    target_price=position.target_price,
                    order_id=position.order_id,
                    signal_id=position.signal_id,
                    strategy_name=position.strategy_name,
                    entry_time=position.entry_time,
                    capital_deployed=position.capital_deployed,
                )
                session.add(row)
            session.commit()
        except Exception as e:
            logger.error("save_position_error", symbol=position.symbol, error=str(e))
            session.rollback()
        finally:
            session.close()

    def remove_position(self, symbol: str) -> None:
        """Delete a position row by symbol."""
        session = self._session_factory()
        try:
            session.query(PositionState).filter_by(symbol=symbol).delete()
            session.commit()
        except Exception as e:
            logger.error("remove_position_error", symbol=symbol, error=str(e))
            session.rollback()
        finally:
            session.close()

    def load_positions(self) -> list[dict]:
        """Load all persisted positions as dicts."""
        session = self._session_factory()
        try:
            rows = session.query(PositionState).all()
            positions = []
            for r in rows:
                positions.append({
                    "symbol": r.symbol,
                    "exchange": r.exchange,
                    "direction": r.direction,
                    "quantity": r.quantity,
                    "entry_price": r.entry_price,
                    "current_price": r.current_price or 0.0,
                    "stop_loss": r.stop_loss,
                    "target_price": r.target_price,
                    "order_id": r.order_id or "",
                    "signal_id": r.signal_id,
                    "strategy_name": r.strategy_name or "",
                    "entry_time": r.entry_time,
                    "capital_deployed": r.capital_deployed or 0.0,
                })
            return positions
        except Exception as e:
            logger.error("load_positions_error", error=str(e))
            return []
        finally:
            session.close()

    # ---- Auto-Sell Trigger State ----

    def save_auto_sell_trigger(self, trigger: Any) -> None:
        """Upsert an auto-sell trigger by symbol."""
        session = self._session_factory()
        try:
            row = (
                session.query(AutoSellTriggerState)
                .filter_by(symbol=trigger.symbol)
                .first()
            )
            direction = (
                trigger.position_direction.value
                if hasattr(trigger.position_direction, "value")
                else trigger.position_direction
            )
            gtt_status = (
                trigger.gtt_status.value
                if hasattr(trigger.gtt_status, "value")
                else trigger.gtt_status
            )
            if row:
                row.position_entry_price = trigger.position_entry_price
                row.position_direction = direction
                row.stop_loss = trigger.stop_loss
                row.target_price = trigger.target_price
                row.trailing_stop_pct = trigger.trailing_stop_pct
                row.max_hold_minutes = trigger.max_hold_minutes
                row.confidence_floor = trigger.confidence_floor
                row.structure_break_threshold = trigger.structure_break_threshold
                row.created_at = trigger.created_at
                row.highest_price = trigger.highest_price
                row.lowest_price = trigger.lowest_price
                row.is_active = trigger.is_active
                row.exit_strategy = trigger.exit_strategy
                row.invalidation_condition = trigger.invalidation_condition
                row.gtt_trigger_id = trigger.gtt_trigger_id
                row.gtt_status = gtt_status
                row.gtt_stop_price = trigger.gtt_stop_price
                row.gtt_last_updated = trigger.gtt_last_updated
                row.updated_at = datetime.utcnow()
            else:
                row = AutoSellTriggerState(
                    symbol=trigger.symbol,
                    position_entry_price=trigger.position_entry_price,
                    position_direction=direction,
                    stop_loss=trigger.stop_loss,
                    target_price=trigger.target_price,
                    trailing_stop_pct=trigger.trailing_stop_pct,
                    max_hold_minutes=trigger.max_hold_minutes,
                    confidence_floor=trigger.confidence_floor,
                    structure_break_threshold=trigger.structure_break_threshold,
                    created_at=trigger.created_at,
                    highest_price=trigger.highest_price,
                    lowest_price=trigger.lowest_price,
                    is_active=trigger.is_active,
                    exit_strategy=trigger.exit_strategy,
                    invalidation_condition=trigger.invalidation_condition,
                    gtt_trigger_id=trigger.gtt_trigger_id,
                    gtt_status=gtt_status,
                    gtt_stop_price=trigger.gtt_stop_price,
                    gtt_last_updated=trigger.gtt_last_updated,
                )
                session.add(row)
            session.commit()
        except Exception as e:
            logger.error("save_auto_sell_trigger_error", symbol=trigger.symbol, error=str(e))
            session.rollback()
        finally:
            session.close()

    def remove_auto_sell_trigger(self, symbol: str) -> None:
        """Delete an auto-sell trigger by symbol."""
        session = self._session_factory()
        try:
            session.query(AutoSellTriggerState).filter_by(symbol=symbol).delete()
            session.commit()
        except Exception as e:
            logger.error("remove_auto_sell_trigger_error", symbol=symbol, error=str(e))
            session.rollback()
        finally:
            session.close()

    def load_auto_sell_triggers(self) -> list[dict]:
        """Load all active auto-sell triggers as dicts."""
        session = self._session_factory()
        try:
            rows = session.query(AutoSellTriggerState).filter_by(is_active=True).all()
            triggers = []
            for r in rows:
                triggers.append({
                    "symbol": r.symbol,
                    "position_entry_price": r.position_entry_price,
                    "position_direction": r.position_direction,
                    "stop_loss": r.stop_loss,
                    "target_price": r.target_price,
                    "trailing_stop_pct": r.trailing_stop_pct,
                    "max_hold_minutes": r.max_hold_minutes,
                    "confidence_floor": r.confidence_floor,
                    "structure_break_threshold": r.structure_break_threshold,
                    "created_at": r.created_at,
                    "highest_price": r.highest_price,
                    "lowest_price": r.lowest_price,
                    "is_active": r.is_active,
                    "exit_strategy": r.exit_strategy or "",
                    "invalidation_condition": r.invalidation_condition or "",
                    "gtt_trigger_id": r.gtt_trigger_id or "",
                    "gtt_status": r.gtt_status or "pending",
                    "gtt_stop_price": r.gtt_stop_price or 0.0,
                    "gtt_last_updated": r.gtt_last_updated,
                })
            return triggers
        except Exception as e:
            logger.error("load_auto_sell_triggers_error", error=str(e))
            return []
        finally:
            session.close()

    def update_auto_sell_trigger_prices(
        self, symbol: str, highest: float, lowest: float, is_active: bool
    ) -> None:
        """Lightweight update for price tracking during monitoring."""
        session = self._session_factory()
        try:
            row = session.query(AutoSellTriggerState).filter_by(symbol=symbol).first()
            if row:
                row.highest_price = highest
                row.lowest_price = lowest
                row.is_active = is_active
                row.updated_at = datetime.utcnow()
                session.commit()
        except Exception as e:
            logger.error("update_trigger_prices_error", symbol=symbol, error=str(e))
            session.rollback()
        finally:
            session.close()

    # ---- Pending Signal State ----

    def save_pending_signal(self, pending: Any) -> None:
        """Upsert a pending signal by signal_id."""
        session = self._session_factory()
        try:
            signal_json = pending.signal.model_dump_json()
            status_val = (
                pending.status.value
                if hasattr(pending.status, "value")
                else pending.status
            )
            action_val = (
                pending.action.value
                if pending.action and hasattr(pending.action, "value")
                else pending.action
            )
            row = (
                session.query(PendingSignalState)
                .filter_by(signal_id=pending.signal_id)
                .first()
            )
            if row:
                row.signal_json = signal_json
                row.status = status_val
                row.action = action_val
                row.telegram_message_id = pending.telegram_message_id
            else:
                row = PendingSignalState(
                    signal_id=pending.signal_id,
                    signal_json=signal_json,
                    created_at=pending.created_at,
                    expiry_minutes=pending.expiry_minutes,
                    telegram_message_id=pending.telegram_message_id,
                    status=status_val,
                    action=action_val,
                )
                session.add(row)
            session.commit()
        except Exception as e:
            logger.error("save_pending_signal_error", signal_id=pending.signal_id, error=str(e))
            session.rollback()
        finally:
            session.close()

    def update_pending_signal_status(
        self, signal_id: str, status: str, action: str | None = None
    ) -> None:
        """Update a pending signal's status after user action."""
        session = self._session_factory()
        try:
            row = session.query(PendingSignalState).filter_by(signal_id=signal_id).first()
            if row:
                row.status = status
                row.action = action
                session.commit()
        except Exception as e:
            logger.error("update_pending_signal_error", signal_id=signal_id, error=str(e))
            session.rollback()
        finally:
            session.close()

    def load_pending_signals(self) -> list[dict]:
        """Load all pending signals (status='pending') as dicts."""
        session = self._session_factory()
        try:
            rows = session.query(PendingSignalState).filter_by(status="pending").all()
            signals = []
            for r in rows:
                signals.append({
                    "signal_id": r.signal_id,
                    "signal_json": r.signal_json,
                    "created_at": r.created_at,
                    "expiry_minutes": r.expiry_minutes,
                    "telegram_message_id": r.telegram_message_id,
                    "status": r.status,
                    "action": r.action,
                })
            return signals
        except Exception as e:
            logger.error("load_pending_signals_error", error=str(e))
            return []
        finally:
            session.close()

    def cleanup_old_pending_signals(self) -> None:
        """Delete non-pending signals older than 1 day."""
        session = self._session_factory()
        try:
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(days=1)
            session.query(PendingSignalState).filter(
                PendingSignalState.status != "pending",
                PendingSignalState.created_at < cutoff,
            ).delete(synchronize_session=False)
            session.commit()
        except Exception as e:
            logger.error("cleanup_pending_signals_error", error=str(e))
            session.rollback()
        finally:
            session.close()

    # ---- Pending Memory Updates ----

    def save_pending_memory_update(
        self,
        source: str,
        title: str,
        draft: dict,
        expires_at: datetime,
        trade_id: int | None = None,
    ) -> int:
        """Insert a new pending memory update draft. Returns the row id."""
        session = self._session_factory()
        try:
            row = PendingMemoryUpdate(
                source=source,
                trade_id=trade_id,
                title=title,
                draft_json=json.dumps(draft),
                expires_at=expires_at,
                status="pending",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return int(row.id)
        except Exception as e:
            logger.error("save_pending_memory_update_error", error=str(e))
            session.rollback()
            return 0
        finally:
            session.close()

    def set_pending_memory_message_id(self, pending_id: int, message_id: int) -> None:
        session = self._session_factory()
        try:
            row = session.query(PendingMemoryUpdate).filter_by(id=pending_id).first()
            if row:
                row.telegram_message_id = message_id
                session.commit()
        except Exception as e:
            logger.error("set_pending_memory_message_id_error", error=str(e))
            session.rollback()
        finally:
            session.close()

    def load_pending_memory_update(self, pending_id: int) -> dict | None:
        session = self._session_factory()
        try:
            row = session.query(PendingMemoryUpdate).filter_by(id=pending_id).first()
            if not row:
                return None
            return {
                "id": row.id,
                "source": row.source,
                "trade_id": row.trade_id,
                "title": row.title,
                "draft": json.loads(row.draft_json),
                "created_at": row.created_at,
                "expires_at": row.expires_at,
                "telegram_message_id": row.telegram_message_id,
                "status": row.status,
            }
        except Exception as e:
            logger.error("load_pending_memory_update_error", pending_id=pending_id, error=str(e))
            return None
        finally:
            session.close()

    def load_open_pending_memory_updates(self) -> list[dict]:
        session = self._session_factory()
        try:
            rows = session.query(PendingMemoryUpdate).filter_by(status="pending").all()
            return [
                {
                    "id": r.id,
                    "source": r.source,
                    "trade_id": r.trade_id,
                    "title": r.title,
                    "draft": json.loads(r.draft_json),
                    "created_at": r.created_at,
                    "expires_at": r.expires_at,
                    "telegram_message_id": r.telegram_message_id,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("load_open_pending_memory_updates_error", error=str(e))
            return []
        finally:
            session.close()

    def update_pending_memory_status(
        self,
        pending_id: int,
        status: str,
        commit_sha: str | None = None,
    ) -> None:
        session = self._session_factory()
        try:
            row = session.query(PendingMemoryUpdate).filter_by(id=pending_id).first()
            if row:
                row.status = status
                if status in ("approved", "failed"):
                    row.applied_at = datetime.utcnow()
                if commit_sha:
                    row.commit_sha = commit_sha
                session.commit()
        except Exception as e:
            logger.error("update_pending_memory_status_error", error=str(e))
            session.rollback()
        finally:
            session.close()

    def expire_stale_pending_memory_updates(self) -> list[dict]:
        """Mark pending rows past expires_at as expired. Returns the expired rows."""
        session = self._session_factory()
        expired: list[dict] = []
        try:
            now = datetime.utcnow()
            rows = (
                session.query(PendingMemoryUpdate)
                .filter(
                    PendingMemoryUpdate.status == "pending",
                    PendingMemoryUpdate.expires_at < now,
                )
                .all()
            )
            for r in rows:
                r.status = "expired"
                expired.append({
                    "id": r.id,
                    "title": r.title,
                    "telegram_message_id": r.telegram_message_id,
                })
            session.commit()
        except Exception as e:
            logger.error("expire_pending_memory_error", error=str(e))
            session.rollback()
        finally:
            session.close()
        return expired

    # ---- App State (key-value) ----

    def save_app_state(self, key: str, value: dict) -> None:
        """Upsert a key-value pair in app_state."""
        session = self._session_factory()
        try:
            row = session.query(AppState).filter_by(key=key).first()
            json_value = json.dumps(value)
            if row:
                row.value = json_value
                row.updated_at = datetime.utcnow()
            else:
                row = AppState(key=key, value=json_value)
                session.add(row)
            session.commit()
        except Exception as e:
            logger.error("save_app_state_error", key=key, error=str(e))
            session.rollback()
        finally:
            session.close()

    def load_app_state(self, key: str) -> dict | None:
        """Load a key-value pair from app_state."""
        session = self._session_factory()
        try:
            row = session.query(AppState).filter_by(key=key).first()
            if row:
                return json.loads(row.value)
            return None
        except Exception as e:
            logger.error("load_app_state_error", key=key, error=str(e))
            return None
        finally:
            session.close()

    # ---- Dashboard Data (from existing tables) ----

    def load_recent_signals(self, limit: int = 50) -> list[dict]:
        """Load recent signals from the signals table for dashboard."""
        session = self._session_factory()
        try:
            rows = session.query(Signal).order_by(Signal.created_at.desc()).limit(limit).all()
            return [
                {
                    "time": r.created_at.strftime("%H:%M:%S") if r.created_at else "",
                    "symbol": r.symbol,
                    "direction": r.sentiment,
                    "strategy": r.strategy_name or "",
                    "confidence": r.confidence,
                    "score": r.final_score or 0,
                    "entry": 0,
                    "stop": 0,
                    "target": 0,
                    "status": r.status,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("load_recent_signals_error", error=str(e))
            return []
        finally:
            session.close()

    def load_recent_trades(self, limit: int = 50) -> list[dict]:
        """Load recent trades from the trades table for dashboard."""
        session = self._session_factory()
        try:
            rows = session.query(Trade).order_by(Trade.created_at.desc()).limit(limit).all()
            return [
                {
                    "time": r.created_at.strftime("%H:%M:%S") if r.created_at else "",
                    "symbol": r.symbol,
                    "direction": r.direction,
                    "quantity": r.quantity,
                    "entry_price": r.entry_price,
                    "exit_price": r.exit_price,
                    "pnl": r.pnl,
                    "pnl_pct": r.pnl_pct,
                    "exit_reason": r.exit_reason or "",
                    "strategy": r.strategy_name or "",
                    "execution_mode": r.execution_mode or "",
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("load_recent_trades_error", error=str(e))
            return []
        finally:
            session.close()

    def load_completed_trades(self) -> list[dict]:
        """Load all completed trades (with exit_price) for FeedbackTracker reconstruction."""
        session = self._session_factory()
        try:
            rows = (
                session.query(Trade)
                .filter(Trade.exit_price.isnot(None))
                .order_by(Trade.created_at.asc())
                .all()
            )
            return [
                {
                    "symbol": r.symbol,
                    "strategy_name": r.strategy_name or "",
                    "direction": r.direction,
                    "entry_price": r.entry_price,
                    "exit_price": r.exit_price,
                    "stop_loss": r.stop_loss or 0.0,
                    "target_price": r.target_price,
                    "entry_time": r.created_at,
                    "exit_time": r.exit_at or r.created_at,
                    "exit_reason": r.exit_reason or "manual",
                    "quantity": r.quantity,
                    "pnl": r.pnl or 0.0,
                    "pnl_pct": r.pnl_pct or 0.0,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("load_completed_trades_error", error=str(e))
            return []
        finally:
            session.close()

    def get_total_realized_pnl(self) -> float:
        """Sum all realized PnL from trades table (fallback for first run)."""
        session = self._session_factory()
        try:
            from sqlalchemy import func
            result = session.query(func.coalesce(func.sum(Trade.pnl), 0.0)).filter(
                Trade.exit_price.isnot(None)
            ).scalar()
            return float(result)
        except Exception as e:
            logger.error("get_total_pnl_error", error=str(e))
            return 0.0
        finally:
            session.close()

    def get_today_realized_pnl(self) -> tuple[float, int, int, int]:
        """Get today's realized PnL and trade counts from trades table."""
        session = self._session_factory()
        try:
            from datetime import date
            today_start = datetime.combine(date.today(), datetime.min.time())
            rows = (
                session.query(Trade)
                .filter(Trade.exit_price.isnot(None), Trade.exit_at >= today_start)
                .all()
            )
            pnl = sum(r.pnl or 0.0 for r in rows)
            wins = sum(1 for r in rows if (r.pnl or 0) > 0)
            losses = sum(1 for r in rows if (r.pnl or 0) < 0)
            return pnl, len(rows), wins, losses
        except Exception as e:
            logger.error("get_today_pnl_error", error=str(e))
            return 0.0, 0, 0, 0
        finally:
            session.close()

    def has_open_trade(self, order_id: str) -> bool:
        """Check if a trade with the given order_id has been closed (has exit_price)."""
        session = self._session_factory()
        try:
            trade = session.query(Trade).filter_by(order_id=order_id).first()
            if trade and trade.exit_price is not None:
                return False  # Trade is closed
            return True  # Trade is open or not found
        except Exception as e:
            logger.error("has_open_trade_error", order_id=order_id, error=str(e))
            return True
        finally:
            session.close()
