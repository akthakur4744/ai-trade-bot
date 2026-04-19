"""Portfolio state tracker — open positions, deployed capital, daily PnL."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

import structlog

from src.models import Direction, ExitReason, Position

if TYPE_CHECKING:
    from src.storage.database import Database

logger = structlog.get_logger(__name__)


class Portfolio:
    """Tracks open positions, deployed capital, and realized PnL.

    When a Database reference is provided, state is persisted on every
    mutation and restored on startup.
    """

    def __init__(self, db: Database | None = None) -> None:
        self._db = db
        self._positions: dict[str, Position] = {}  # symbol -> Position
        self._realized_pnl_today: float = 0.0
        self._total_realized_pnl: float = 0.0
        self._trade_count_today: int = 0
        self._winning_trades_today: int = 0
        self._losing_trades_today: int = 0
        self._current_date: date = date.today()

        if db:
            self._load_from_db()

    def _load_from_db(self) -> None:
        """Restore portfolio state from database on startup."""
        assert self._db is not None

        # Load open positions, cross-check against trades table
        position_dicts = self._db.load_positions()
        for p in position_dicts:
            # Skip if the trade has already been closed in the trades table
            if p.get("order_id") and not self._db.has_open_trade(p["order_id"]):
                self._db.remove_position(p["symbol"])
                logger.info("stale_position_removed", symbol=p["symbol"])
                continue

            position = Position(
                symbol=p["symbol"],
                exchange=p.get("exchange", "NSE"),
                direction=Direction(p["direction"]),
                quantity=p["quantity"],
                entry_price=p["entry_price"],
                current_price=p.get("current_price", 0.0),
                stop_loss=p.get("stop_loss", 0.0),
                target_price=p.get("target_price"),
                order_id=p.get("order_id", ""),
                signal_id=p.get("signal_id"),
                strategy_name=p.get("strategy_name", ""),
                entry_time=p.get("entry_time", datetime.utcnow()),
                capital_deployed=p.get("capital_deployed", 0.0),
            )
            self._positions[position.symbol] = position

        # Load portfolio counters from app_state
        counters = self._db.load_app_state("portfolio_counters")
        if counters:
            saved_date = counters.get("current_date", "")
            if saved_date == str(date.today()):
                # Same day — restore daily counters
                self._realized_pnl_today = counters.get("realized_pnl_today", 0.0)
                self._trade_count_today = counters.get("trade_count_today", 0)
                self._winning_trades_today = counters.get("winning_trades_today", 0)
                self._losing_trades_today = counters.get("losing_trades_today", 0)
            else:
                # Different day — reconstruct today's counters from trades
                pnl, count, wins, losses = self._db.get_today_realized_pnl()
                self._realized_pnl_today = pnl
                self._trade_count_today = count
                self._winning_trades_today = wins
                self._losing_trades_today = losses

            self._total_realized_pnl = counters.get("total_realized_pnl", 0.0)
        else:
            # First run after adding persistence — reconstruct from trades
            self._total_realized_pnl = self._db.get_total_realized_pnl()
            pnl, count, wins, losses = self._db.get_today_realized_pnl()
            self._realized_pnl_today = pnl
            self._trade_count_today = count
            self._winning_trades_today = wins
            self._losing_trades_today = losses

        logger.info(
            "portfolio_loaded_from_db",
            positions=len(self._positions),
            total_pnl=round(self._total_realized_pnl, 2),
            today_pnl=round(self._realized_pnl_today, 2),
        )

    def _save_counters(self) -> None:
        """Persist portfolio counters to DB."""
        if not self._db:
            return
        self._db.save_app_state("portfolio_counters", {
            "realized_pnl_today": self._realized_pnl_today,
            "total_realized_pnl": self._total_realized_pnl,
            "trade_count_today": self._trade_count_today,
            "winning_trades_today": self._winning_trades_today,
            "losing_trades_today": self._losing_trades_today,
            "current_date": str(self._current_date),
        })

    def _check_day_reset(self) -> None:
        """Reset daily counters if the date has changed."""
        today = date.today()
        if today != self._current_date:
            logger.info(
                "portfolio_day_reset",
                old_date=str(self._current_date),
                new_date=str(today),
                prev_pnl=self._realized_pnl_today,
            )
            self._realized_pnl_today = 0.0
            self._trade_count_today = 0
            self._winning_trades_today = 0
            self._losing_trades_today = 0
            self._current_date = today
            self._save_counters()

    @property
    def open_positions(self) -> dict[str, Position]:
        return dict(self._positions)

    @property
    def open_position_count(self) -> int:
        return len(self._positions)

    @property
    def deployed_capital(self) -> float:
        """Total capital currently deployed in open positions."""
        return sum(p.capital_deployed for p in self._positions.values())

    @property
    def realized_pnl_today(self) -> float:
        self._check_day_reset()
        return self._realized_pnl_today

    @property
    def total_realized_pnl(self) -> float:
        return self._total_realized_pnl

    @property
    def trade_count_today(self) -> int:
        self._check_day_reset()
        return self._trade_count_today

    @property
    def unrealized_pnl(self) -> float:
        """Total unrealized PnL across all open positions."""
        return sum(p.unrealized_pnl for p in self._positions.values())

    def add_position(self, position: Position) -> None:
        """Add a new open position after order fill."""
        if position.symbol in self._positions:
            logger.warning("duplicate_position", symbol=position.symbol)
            return

        position.capital_deployed = position.entry_price * position.quantity
        self._positions[position.symbol] = position

        if self._db:
            self._db.save_position(position)

        logger.info(
            "position_opened",
            symbol=position.symbol,
            direction=position.direction,
            quantity=position.quantity,
            entry_price=position.entry_price,
            capital=position.capital_deployed,
        )

    def close_position(
        self, symbol: str, exit_price: float, reason: ExitReason
    ) -> float:
        """Close a position and record realized PnL.

        Returns:
            Realized PnL for this trade.
        """
        self._check_day_reset()

        if symbol not in self._positions:
            logger.warning("close_nonexistent_position", symbol=symbol)
            return 0.0

        position = self._positions.pop(symbol)

        if position.direction == Direction.BUY:
            pnl = (exit_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - exit_price) * position.quantity

        self._realized_pnl_today += pnl
        self._total_realized_pnl += pnl
        self._trade_count_today += 1

        if pnl >= 0:
            self._winning_trades_today += 1
        else:
            self._losing_trades_today += 1

        if self._db:
            self._db.remove_position(symbol)
            self._save_counters()

        logger.info(
            "position_closed",
            symbol=symbol,
            exit_price=exit_price,
            pnl=round(pnl, 2),
            reason=reason,
            daily_pnl=round(self._realized_pnl_today, 2),
        )
        return pnl

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update current prices and unrealized PnL for open positions."""
        for symbol, price in prices.items():
            if symbol in self._positions:
                self._positions[symbol].update_pnl(price)

    def get_position(self, symbol: str) -> Position | None:
        return self._positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        return symbol in self._positions

    def get_daily_stats(self) -> dict:
        """Get today's trading statistics."""
        self._check_day_reset()
        return {
            "date": str(self._current_date),
            "trade_count": self._trade_count_today,
            "winning_trades": self._winning_trades_today,
            "losing_trades": self._losing_trades_today,
            "realized_pnl": round(self._realized_pnl_today, 2),
            "open_positions": self.open_position_count,
            "deployed_capital": round(self.deployed_capital, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
        }
