"""Order manager — orchestrates the full execution flow.

Signal -> Kill Switch -> Guardrails -> Position Sizing -> Broker -> Portfolio -> DB
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog

from src.config import AppConfig
from src.execution.broker import Broker
from src.models import (
    Direction,
    ExitReason,
    Order,
    OrderResult,
    Position,
    ScoredSignal,
)
from src.risk.guardrails import validate_order
from src.risk.kill_switch import KillSwitch
from src.risk.portfolio import Portfolio
from src.risk.position_sizing import calculate_position_size
from src.storage.database import Database
from src.storage.models import Trade as TradeRecord

logger = structlog.get_logger(__name__)


class OrderManager:
    """Manages the complete lifecycle from signal to tracked position.

    Responsibilities:
    1. Check kill switch
    2. Calculate position size
    3. Run risk guardrails
    4. Place order via broker
    5. Track position in portfolio
    6. Persist trade to database
    """

    def __init__(
        self,
        broker: Broker,
        portfolio: Portfolio,
        kill_switch: KillSwitch,
        config: AppConfig,
        db: Database,
    ) -> None:
        self._broker = broker
        self._portfolio = portfolio
        self._kill_switch = kill_switch
        self._config = config
        self._db = db

    def execute_signal(
        self,
        signal: ScoredSignal,
        capital: float,
        atr: float = 0.0,
    ) -> Optional[OrderResult]:
        """Execute a scored signal through the full risk pipeline.

        Args:
            signal: The scored and filtered signal to execute.
            capital: Available account capital.
            atr: Current ATR for the symbol (used in ATR-based sizing).

        Returns:
            OrderResult if order was placed, None if blocked.
        """
        # Step 1: Kill switch
        if self._kill_switch.check():
            logger.warning("order_blocked_kill_switch", symbol=signal.symbol)
            return None

        # Step 2: Skip if already holding this symbol
        if self._portfolio.has_position(signal.symbol):
            logger.info("order_skipped_existing_position", symbol=signal.symbol)
            return None

        # Step 3: Calculate position size
        quantity = calculate_position_size(
            method=self._config.risk.position_sizing_method,
            capital=capital,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            config=self._config.risk,
            atr=atr,
        )

        if quantity <= 0:
            logger.warning("order_zero_quantity", symbol=signal.symbol)
            return None

        # Step 4: Build order
        order = Order(
            symbol=signal.symbol,
            exchange=signal.exchange,
            direction=signal.direction,
            quantity=quantity,
            price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target_price=signal.target_price,
            order_type=self._config.execution.live.order_type,
            product=self._config.execution.live.product,
            strategy_name=signal.strategy_name,
        )

        # Step 5: Run guardrails
        guardrail_result = validate_order(
            order=order,
            current_deployed=self._portfolio.deployed_capital,
            realized_pnl_today=self._portfolio.realized_pnl_today,
            open_positions=self._portfolio.open_position_count,
            config=self._config.risk,
        )

        if not guardrail_result.passed:
            logger.warning(
                "order_blocked_guardrail",
                symbol=signal.symbol,
                reason=guardrail_result.reason,
            )
            return None

        # Step 6: Place order
        result = self._broker.place_order(order)

        if not result.success:
            logger.error("order_failed", symbol=signal.symbol, message=result.message)
            return result

        # Step 7: Track position
        position = Position(
            symbol=signal.symbol,
            exchange=signal.exchange,
            direction=signal.direction,
            quantity=result.fill_quantity,
            entry_price=result.fill_price,
            stop_loss=signal.stop_loss,
            target_price=signal.target_price,
            order_id=result.order_id,
            strategy_name=signal.strategy_name,
            entry_time=result.timestamp,
        )
        self._portfolio.add_position(position)

        # Step 8: Persist to DB
        self._persist_trade(order, result, signal)

        return result

    def close_position(
        self,
        symbol: str,
        reason: ExitReason,
        exit_price: float | None = None,
    ) -> Optional[OrderResult]:
        """Close an open position.

        Args:
            symbol: Symbol to close.
            reason: Why the position is being closed.
            exit_price: Override exit price (paper broker fetches LTP if None).
        """
        position = self._portfolio.get_position(symbol)
        if position is None:
            logger.warning("close_no_position", symbol=symbol)
            return None

        # Build exit order (reverse direction)
        exit_direction = Direction.SELL if position.direction == Direction.BUY else Direction.BUY
        exit_order = Order(
            symbol=symbol,
            exchange=position.exchange,
            direction=exit_direction,
            quantity=position.quantity,
            price=exit_price or position.current_price,
            stop_loss=0,
            strategy_name=position.strategy_name,
        )

        result = self._broker.place_order(exit_order)
        if not result.success:
            logger.error("exit_order_failed", symbol=symbol, message=result.message)
            return result

        # Record PnL in portfolio
        pnl = self._portfolio.close_position(symbol, result.fill_price, reason)

        # Update trade record in DB
        self._update_trade_exit(position.order_id, result.fill_price, pnl, reason)

        # Re-check kill switch after closing (in case this trade pushed us over)
        self._kill_switch.check()

        return result

    def _persist_trade(
        self, order: Order, result: OrderResult, signal: ScoredSignal
    ) -> None:
        """Save trade entry to database."""
        try:
            session = self._db.get_session()
            trade = TradeRecord(
                symbol=order.symbol,
                exchange=order.exchange,
                direction=order.direction.value,
                quantity=result.fill_quantity,
                entry_price=result.fill_price,
                stop_loss=order.stop_loss,
                target_price=order.target_price,
                order_id=result.order_id,
                execution_mode=self._config.execution.mode,
                strategy_name=signal.strategy_name,
                position_size_method=self._config.risk.position_sizing_method,
                created_at=result.timestamp,
            )
            session.add(trade)
            session.commit()
            session.close()
        except Exception as e:
            logger.error("trade_persist_error", error=str(e))

    def _update_trade_exit(
        self, order_id: str, exit_price: float, pnl: float, reason: ExitReason
    ) -> None:
        """Update trade record with exit details."""
        try:
            session = self._db.get_session()
            trade = session.query(TradeRecord).filter_by(order_id=order_id).first()
            if trade:
                trade.exit_price = exit_price
                trade.exit_at = datetime.utcnow()
                trade.exit_reason = reason.value
                trade.pnl = round(pnl, 2)
                if trade.entry_price > 0:
                    trade.pnl_pct = round((pnl / (trade.entry_price * trade.quantity)) * 100, 2)
                if trade.created_at:
                    delta = datetime.utcnow() - trade.created_at
                    trade.holding_duration_min = int(delta.total_seconds() / 60)
                session.commit()
            session.close()
        except Exception as e:
            logger.error("trade_exit_persist_error", error=str(e))
