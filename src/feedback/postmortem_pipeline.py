"""Postmortem pipeline — glues PostmortemAgent → pending-update DB → Telegram approval → MemoryWriter.

TradingEngine only needs to call:
    pipeline.enqueue_postmortem_for_closed_trade(order_id)

and
    pipeline.handle_memory_callback(pending_id, action)

from the Telegram callback route. Everything else is private.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import structlog
from sqlalchemy import func

from src.feedback.memory_writer import MemoryWriter
from src.feedback.postmortem_agent import MemoryUpdateDraft, PostmortemAgent
from src.feedback.tracker import TradeOutcome
from src.notifications.telegram import TelegramNotifier
from src.storage.database import Database
from src.storage.models import Trade as TradeRecord

logger = structlog.get_logger(__name__)

EXPIRY_MINUTES = 60


class PostmortemPipeline:
    def __init__(
        self,
        agent: PostmortemAgent,
        writer: MemoryWriter,
        telegram: TelegramNotifier,
        db: Database,
    ) -> None:
        self._agent = agent
        self._writer = writer
        self._telegram = telegram
        self._db = db

    # ---- Public API ----

    def enqueue_postmortem_for_closed_trade(self, order_id: str) -> Optional[int]:
        """Look up the closed trade by order_id, draft a postmortem, persist + notify.

        Returns pending_memory_update id, or None if skipped/failed.
        """
        trade_row = self._load_trade(order_id)
        if not trade_row:
            logger.warning("postmortem_skip_no_trade", order_id=order_id)
            return None

        if trade_row["exit_price"] is None:
            logger.warning("postmortem_skip_not_closed", order_id=order_id)
            return None

        try:
            outcome = self._to_outcome(trade_row)
        except Exception as e:
            logger.error("postmortem_outcome_build_failed", order_id=order_id, error=str(e))
            return None

        recurrence_count, recurrence_hint = self._recurrence(trade_row)

        draft = self._agent.draft(
            outcome=outcome,
            trade_id=trade_row["id"],
            recurrence_count=recurrence_count,
            recurrence_hint=recurrence_hint,
        )
        if not draft:
            logger.warning("postmortem_draft_none", trade_id=trade_row["id"])
            return None

        pending_id = self._db.save_pending_memory_update(
            source="postmortem",
            trade_id=trade_row["id"],
            title=draft.headline or f"Postmortem {outcome.symbol}",
            draft=draft.to_dict(),
            expires_at=datetime.utcnow() + timedelta(minutes=EXPIRY_MINUTES),
        )
        if not pending_id:
            return None

        if self._telegram.is_configured:
            summary = self._build_summary(draft)
            msg_id = self._telegram.send_memory_update_for_approval(
                pending_id=pending_id,
                headline=draft.headline or outcome.symbol,
                summary=summary,
                has_mistakes=bool(draft.mistakes_entry),
                has_learnings=draft.touches_learnings,
                has_strategy=draft.touches_strategy,
            )
            if msg_id:
                self._db.set_pending_memory_message_id(pending_id, msg_id)

        logger.info(
            "postmortem_enqueued",
            pending_id=pending_id,
            trade_id=trade_row["id"],
            symbol=outcome.symbol,
        )
        return pending_id

    def handle_memory_callback(self, pending_id: int, action: str) -> None:
        """Process a Telegram memory_update callback."""
        pending = self._db.load_pending_memory_update(pending_id)
        if not pending:
            logger.warning("memory_callback_no_pending", pending_id=pending_id)
            return

        if pending["status"] != "pending":
            logger.info(
                "memory_callback_already_resolved",
                pending_id=pending_id,
                status=pending["status"],
            )
            return

        msg_id = pending.get("telegram_message_id") or 0

        if action == "reject":
            self._db.update_pending_memory_status(pending_id, "rejected")
            if msg_id and self._telegram.is_configured:
                self._telegram.update_memory_message(msg_id, "Rejected, no changes made.")
            logger.info("memory_update_rejected", pending_id=pending_id)
            return

        if action != "approve":
            logger.warning("memory_callback_unknown_action", action=action)
            return

        # Apply
        draft = pending["draft"]
        if pending["source"] == "postmortem":
            trade_id = pending.get("trade_id") or 0
            symbol = self._lookup_symbol_for_trade(trade_id) or "UNKNOWN"
            ok, result = self._writer.apply_postmortem(
                draft=draft, trade_id=trade_id, symbol=symbol
            )
        elif pending["source"] == "weekly_review":
            week = draft.get("week_ending") or datetime.utcnow().strftime("%Y-%m-%d")
            ok, result = self._writer.apply_weekly_review(draft=draft, week_ending=week)
        else:
            logger.warning("memory_callback_unknown_source", source=pending["source"])
            return

        if ok:
            self._db.update_pending_memory_status(pending_id, "approved", commit_sha=result)
            if msg_id and self._telegram.is_configured:
                short_sha = result[:8] if result else ""
                self._telegram.update_memory_message(msg_id, f"Committed {short_sha}")
        else:
            self._db.update_pending_memory_status(pending_id, "failed")
            if msg_id and self._telegram.is_configured:
                self._telegram.update_memory_message(msg_id, f"Apply failed: {result}")

    def sweep_expired(self) -> int:
        """Mark stale pending rows as expired and update their Telegram messages."""
        expired = self._db.expire_stale_pending_memory_updates()
        for row in expired:
            msg_id = row.get("telegram_message_id") or 0
            if msg_id and self._telegram.is_configured:
                self._telegram.update_memory_message(msg_id, "Expired, no changes made.")
        if expired:
            logger.info("memory_updates_expired", count=len(expired))
        return len(expired)

    # ---- Internals ----

    def _load_trade(self, order_id: str) -> Optional[dict]:
        session = self._db.get_session()
        try:
            row = session.query(TradeRecord).filter_by(order_id=order_id).first()
            if not row:
                return None
            return {
                "id": row.id,
                "symbol": row.symbol,
                "strategy_name": row.strategy_name or "unknown",
                "direction": row.direction,
                "entry_price": row.entry_price,
                "exit_price": row.exit_price,
                "stop_loss": row.stop_loss or 0.0,
                "target_price": row.target_price,
                "entry_time": row.created_at,
                "exit_time": row.exit_at or row.created_at,
                "exit_reason": row.exit_reason or "manual",
                "quantity": row.quantity,
                "pnl": row.pnl or 0.0,
                "pnl_pct": row.pnl_pct or 0.0,
            }
        finally:
            session.close()

    def _lookup_symbol_for_trade(self, trade_id: int) -> Optional[str]:
        if not trade_id:
            return None
        session = self._db.get_session()
        try:
            row = session.query(TradeRecord).filter_by(id=trade_id).first()
            return row.symbol if row else None
        finally:
            session.close()

    def _recurrence(self, trade_row: dict) -> tuple[int, str]:
        """Count prior closed trades on the same symbol + exit_reason (rough recurrence signal)."""
        session = self._db.get_session()
        try:
            count = (
                session.query(func.count(TradeRecord.id))
                .filter(
                    TradeRecord.symbol == trade_row["symbol"],
                    TradeRecord.exit_reason == trade_row["exit_reason"],
                    TradeRecord.id != trade_row["id"],
                    TradeRecord.exit_price.isnot(None),
                )
                .scalar()
            )
            count = int(count or 0)
            hint = (
                f"{count} prior closed trade(s) on {trade_row['symbol']} with exit_reason={trade_row['exit_reason']}"
                if count
                else ""
            )
            return count, hint
        finally:
            session.close()

    @staticmethod
    def _to_outcome(row: dict) -> TradeOutcome:
        return TradeOutcome(
            symbol=row["symbol"],
            strategy_name=row["strategy_name"],
            direction=row["direction"],
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            stop_loss=row["stop_loss"],
            target_price=row["target_price"],
            entry_time=row["entry_time"],
            exit_time=row["exit_time"],
            exit_reason=row["exit_reason"],
            quantity=row["quantity"],
            pnl=row["pnl"],
            pnl_pct=row["pnl_pct"],
        )

    @staticmethod
    def _build_summary(draft: MemoryUpdateDraft) -> str:
        parts: list[str] = []
        if draft.mistakes_entry:
            parts.append("[MISTAKES.md]\n" + _truncate(draft.mistakes_entry, 500))
        if draft.learnings_entry:
            parts.append("[LEARNINGS.md]\n" + _truncate(draft.learnings_entry, 400))
        if draft.strategy_patch:
            parts.append("[TRADING-STRATEGY.md]\n" + _truncate(draft.strategy_patch, 300))
        if draft.config_suggestion:
            parts.append(f"[config suggestion] {draft.config_suggestion}")
        return "\n\n".join(parts) if parts else "(empty draft)"


def _truncate(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "\u2026"
