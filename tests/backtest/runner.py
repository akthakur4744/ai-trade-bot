"""Backtest runner — replay historical data through strategy + risk pipeline.

Uses the SAME strategy and risk code as live/paper trading.
No separate backtest logic = no divergence between backtest and production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Type

import pandas as pd
import structlog

from src.feedback.tracker import FeedbackTracker, TradeOutcome
from src.models import Direction, ExitReason, Position, StrategySignal
from src.risk.guardrails import validate_order
from src.risk.position_sizing import fixed_percentage_size
from src.strategies.base import Strategy

logger = structlog.get_logger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    initial_capital: float = 100000.0
    max_capital_per_trade: float = 10000.0
    max_open_positions: int = 3
    max_daily_loss: float = 5000.0
    slippage_bps: float = 5.0
    risk_pct: float = 0.02
    commission_per_trade: float = 20.0  # INR flat


@dataclass
class BacktestPosition:
    """Internal position tracking during backtest."""

    symbol: str
    direction: Direction
    quantity: int
    entry_price: float
    entry_time: datetime
    stop_loss: float
    target_price: Optional[float]
    strategy_name: str
    capital_deployed: float = 0.0


@dataclass
class BacktestResult:
    """Complete backtest output."""

    strategy_name: str
    symbol: str
    period_start: datetime
    period_end: datetime
    initial_capital: float
    final_capital: float
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    outcomes: List[TradeOutcome] = field(default_factory=list)


class BacktestRunner:
    """Replays historical OHLCV data through a strategy engine.

    Walk-forward bar-by-bar simulation:
    1. For each bar, expand the visible window
    2. Run strategy.scan() on visible data
    3. If signal, simulate entry (with slippage)
    4. For open positions, check stop/target/strategy exit
    5. Record outcomes to FeedbackTracker
    """

    def __init__(self, config: Optional[BacktestConfig] = None) -> None:
        self._config = config or BacktestConfig()
        self._tracker = FeedbackTracker()

    @property
    def tracker(self) -> FeedbackTracker:
        return self._tracker

    def run(
        self,
        strategy: Strategy,
        symbol: str,
        data: pd.DataFrame,
        strategy_config: Optional[dict] = None,
        warmup_bars: int = 200,
    ) -> BacktestResult:
        """Run a backtest for a single strategy on a single symbol.

        Args:
            strategy: Strategy instance to test.
            symbol: Symbol being tested.
            data: Full OHLCV DataFrame (must have open/high/low/close/volume).
            strategy_config: Strategy-specific params (passed to scan/check_exit).
            warmup_bars: Bars to skip for indicator warmup.

        Returns:
            BacktestResult with complete performance metrics.
        """
        strategy_config = strategy_config or {}

        if len(data) <= warmup_bars:
            logger.warning(
                "backtest_insufficient_data",
                bars=len(data),
                warmup=warmup_bars,
            )
            return self._empty_result(strategy.name, symbol, data)

        capital = self._config.initial_capital
        positions: Dict[str, BacktestPosition] = {}
        outcomes: List[TradeOutcome] = []
        daily_pnl = 0.0
        current_day: Optional[datetime] = None

        # Determine the timeframe key based on data frequency
        tf_key = self._infer_timeframe(data)

        for i in range(warmup_bars, len(data)):
            bar_time = data.index[i]
            bar = data.iloc[i]

            # Reset daily PnL tracker
            if current_day is None or bar_time.date() != current_day.date():
                daily_pnl = 0.0
                current_day = bar_time

            # Daily loss check
            if daily_pnl < -self._config.max_daily_loss:
                continue

            visible_data = data.iloc[: i + 1]
            data_dict = {tf_key: visible_data}

            # Check exits on open positions
            for sym, pos in list(positions.items()):
                exit_reason = self._check_exit(
                    pos, bar, strategy, data_dict, strategy_config
                )
                if exit_reason is not None:
                    exit_price = self._apply_slippage(
                        float(bar["close"]), pos.direction, exit=True
                    )
                    outcome = self._close_position(pos, exit_price, bar_time, exit_reason)
                    outcomes.append(outcome)
                    self._tracker.record(outcome)
                    capital += outcome.pnl - self._config.commission_per_trade
                    daily_pnl += outcome.pnl
                    del positions[sym]

            # Skip if at max positions
            if len(positions) >= self._config.max_open_positions:
                continue

            # Scan for new signals
            signal = strategy.scan(symbol, data_dict, strategy_config)
            if signal is None:
                continue

            # Skip if already in position for this symbol
            if symbol in positions:
                continue

            # Calculate position size
            entry_price = self._apply_slippage(
                signal.entry_price, signal.direction, exit=False
            )
            quantity = self._calculate_quantity(capital, entry_price, signal.stop_loss)
            if quantity <= 0:
                continue

            # Check capital limits
            order_value = quantity * entry_price
            if order_value > self._config.max_capital_per_trade:
                quantity = int(self._config.max_capital_per_trade / entry_price)
                if quantity <= 0:
                    continue

            positions[symbol] = BacktestPosition(
                symbol=symbol,
                direction=signal.direction,
                quantity=quantity,
                entry_price=entry_price,
                entry_time=bar_time,
                stop_loss=signal.stop_loss,
                target_price=signal.target_price,
                strategy_name=strategy.name,
                capital_deployed=quantity * entry_price,
            )

        # Close any remaining positions at last bar
        last_bar = data.iloc[-1]
        last_time = data.index[-1]
        for sym, pos in list(positions.items()):
            exit_price = float(last_bar["close"])
            outcome = self._close_position(pos, exit_price, last_time, "end_of_data")
            outcomes.append(outcome)
            self._tracker.record(outcome)
            capital += outcome.pnl - self._config.commission_per_trade

        return self._build_result(strategy.name, symbol, data, capital, outcomes)

    def _check_exit(
        self,
        pos: BacktestPosition,
        bar: pd.Series,
        strategy: Strategy,
        data_dict: Dict[str, pd.DataFrame],
        config: dict,
    ) -> Optional[str]:
        """Check all exit conditions for a position."""
        price = float(bar["close"])
        high = float(bar["high"])
        low = float(bar["low"])

        # Stop-loss hit
        if pos.direction == Direction.BUY and low <= pos.stop_loss:
            return "stop_loss"
        if pos.direction == Direction.SELL and high >= pos.stop_loss:
            return "stop_loss"

        # Target hit
        if pos.target_price is not None:
            if pos.direction == Direction.BUY and high >= pos.target_price:
                return "target"
            if pos.direction == Direction.SELL and low <= pos.target_price:
                return "target"

        # Strategy-specific exit
        position_model = Position(
            symbol=pos.symbol,
            direction=pos.direction,
            quantity=pos.quantity,
            entry_price=pos.entry_price,
            stop_loss=pos.stop_loss,
            target_price=pos.target_price,
            strategy_name=pos.strategy_name,
            entry_time=pos.entry_time,
        )
        exit_signal = strategy.check_exit(position_model, data_dict, config)
        if exit_signal is not None:
            return exit_signal.reason.value

        return None

    def _close_position(
        self,
        pos: BacktestPosition,
        exit_price: float,
        exit_time: datetime,
        exit_reason: str,
    ) -> TradeOutcome:
        if pos.direction == Direction.BUY:
            pnl = (exit_price - pos.entry_price) * pos.quantity
        else:
            pnl = (pos.entry_price - exit_price) * pos.quantity

        pnl_pct = (pnl / (pos.entry_price * pos.quantity)) * 100 if pos.entry_price > 0 else 0.0

        return TradeOutcome(
            symbol=pos.symbol,
            strategy_name=pos.strategy_name,
            direction=pos.direction.value,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            stop_loss=pos.stop_loss,
            target_price=pos.target_price,
            entry_time=pos.entry_time,
            exit_time=exit_time,
            exit_reason=exit_reason,
            quantity=pos.quantity,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
        )

    def _apply_slippage(
        self, price: float, direction: Direction, exit: bool
    ) -> float:
        """Apply slippage — adverse price movement on entry/exit."""
        slip = price * (self._config.slippage_bps / 10000)
        if exit:
            # Exit slippage is opposite of entry
            if direction == Direction.BUY:
                return round(price - slip, 2)  # Sell lower
            return round(price + slip, 2)  # Cover higher
        else:
            if direction == Direction.BUY:
                return round(price + slip, 2)  # Buy higher
            return round(price - slip, 2)  # Sell lower

    def _calculate_quantity(
        self, capital: float, entry_price: float, stop_loss: float
    ) -> int:
        """Simple risk-based position sizing."""
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0:
            return 0
        risk_amount = capital * self._config.risk_pct
        return max(1, int(risk_amount / risk_per_share))

    @staticmethod
    def _infer_timeframe(data: pd.DataFrame) -> str:
        """Infer timeframe key from data frequency."""
        if len(data) < 2:
            return "15minute"
        diff = (data.index[1] - data.index[0]).total_seconds()
        if diff <= 60:
            return "minute"
        elif diff <= 300:
            return "5minute"
        elif diff <= 900:
            return "15minute"
        elif diff <= 3600:
            return "60minute"
        return "day"

    def _build_result(
        self,
        strategy_name: str,
        symbol: str,
        data: pd.DataFrame,
        final_capital: float,
        outcomes: List[TradeOutcome],
    ) -> BacktestResult:
        total = len(outcomes)
        winners = sum(1 for o in outcomes if o.is_winner)
        pnls = [o.pnl for o in outcomes]
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = sum(p for p in pnls if p < 0)

        # Max drawdown
        equity = [self._config.initial_capital]
        for pnl in pnls:
            equity.append(equity[-1] + pnl)
        peak = equity[0]
        max_dd = 0.0
        for e in equity:
            if e > peak:
                peak = e
            max_dd = max(max_dd, peak - e)

        return BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            period_start=data.index[0].to_pydatetime(),
            period_end=data.index[-1].to_pydatetime(),
            initial_capital=self._config.initial_capital,
            final_capital=round(final_capital, 2),
            total_trades=total,
            winning_trades=winners,
            losing_trades=total - winners,
            total_pnl=round(sum(pnls), 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_pct=round((max_dd / self._config.initial_capital) * 100, 2),
            win_rate=round(winners / total, 4) if total > 0 else 0.0,
            profit_factor=round(
                gross_profit / abs(gross_loss) if gross_loss != 0 else float("inf"),
                2,
            ),
            outcomes=outcomes,
        )

    def _empty_result(
        self, strategy_name: str, symbol: str, data: pd.DataFrame
    ) -> BacktestResult:
        return BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            period_start=data.index[0].to_pydatetime() if len(data) > 0 else datetime.now(),
            period_end=data.index[-1].to_pydatetime() if len(data) > 0 else datetime.now(),
            initial_capital=self._config.initial_capital,
            final_capital=self._config.initial_capital,
        )
