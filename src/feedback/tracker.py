"""Feedback tracker — records outcomes vs predictions for continuous improvement.

After each trade closes, records:
- Direction correctness (did price move in predicted direction?)
- PnL vs expected (target hit vs actual exit)
- Time to profit / max adverse excursion
- Strategy-level and agent-level accuracy
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

import structlog

if TYPE_CHECKING:
    from src.storage.database import Database

logger = structlog.get_logger(__name__)


@dataclass
class TradeOutcome:
    """Captured outcome of a single completed trade."""

    symbol: str
    strategy_name: str
    direction: str  # BUY or SELL
    entry_price: float
    exit_price: float
    stop_loss: float
    target_price: Optional[float]
    entry_time: datetime
    exit_time: datetime
    exit_reason: str
    quantity: int
    pnl: float
    pnl_pct: float

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0

    @property
    def hit_target(self) -> bool:
        return self.exit_reason == "target"

    @property
    def hit_stop(self) -> bool:
        return self.exit_reason == "stop_loss"

    @property
    def holding_minutes(self) -> float:
        return (self.exit_time - self.entry_time).total_seconds() / 60.0

    @property
    def risk_reward_actual(self) -> Optional[float]:
        """Actual R:R achieved. Positive = favorable."""
        risk = abs(self.entry_price - self.stop_loss)
        if risk == 0:
            return None
        reward = abs(self.exit_price - self.entry_price)
        return round(reward / risk, 2) if self.is_winner else round(-reward / risk, 2)


@dataclass
class StrategyStats:
    """Aggregate stats for a single strategy."""

    total_trades: int = 0
    winners: int = 0
    losers: int = 0
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    target_hits: int = 0
    stop_hits: int = 0
    total_holding_minutes: float = 0.0

    @property
    def win_rate(self) -> float:
        return self.winners / self.total_trades if self.total_trades > 0 else 0.0

    @property
    def profit_factor(self) -> float:
        return self.gross_profit / abs(self.gross_loss) if self.gross_loss != 0 else float("inf")

    @property
    def avg_pnl(self) -> float:
        return self.total_pnl / self.total_trades if self.total_trades > 0 else 0.0

    @property
    def avg_holding_minutes(self) -> float:
        return self.total_holding_minutes / self.total_trades if self.total_trades > 0 else 0.0

    @property
    def expectancy(self) -> float:
        """Expected PnL per trade = (win_rate * avg_win) - (loss_rate * avg_loss)."""
        if self.total_trades == 0:
            return 0.0
        avg_win = self.gross_profit / self.winners if self.winners > 0 else 0.0
        avg_loss = abs(self.gross_loss) / self.losers if self.losers > 0 else 0.0
        return (self.win_rate * avg_win) - ((1 - self.win_rate) * avg_loss)


class FeedbackTracker:
    """Tracks trade outcomes and computes strategy-level performance metrics."""

    def __init__(self, db: Database | None = None) -> None:
        self._db = db
        self._outcomes: List[TradeOutcome] = []
        self._strategy_stats: Dict[str, StrategyStats] = {}

        if db:
            self._load_from_trades()

    def _load_from_trades(self) -> None:
        """Reconstruct outcomes and stats from completed trades in DB."""
        assert self._db is not None
        trade_dicts = self._db.load_completed_trades()
        for t in trade_dicts:
            outcome = TradeOutcome(
                symbol=t["symbol"],
                strategy_name=t["strategy_name"],
                direction=t["direction"],
                entry_price=t["entry_price"],
                exit_price=t["exit_price"],
                stop_loss=t["stop_loss"],
                target_price=t["target_price"],
                entry_time=t["entry_time"],
                exit_time=t["exit_time"],
                exit_reason=t["exit_reason"],
                quantity=t["quantity"],
                pnl=t["pnl"],
                pnl_pct=t["pnl_pct"],
            )
            self.record(outcome)

        if trade_dicts:
            logger.info("feedback_tracker_loaded", trades=len(trade_dicts))

    @property
    def outcomes(self) -> List[TradeOutcome]:
        return self._outcomes

    @property
    def strategy_stats(self) -> Dict[str, StrategyStats]:
        return self._strategy_stats

    def record(self, outcome: TradeOutcome) -> None:
        """Record a completed trade outcome."""
        self._outcomes.append(outcome)

        stats = self._strategy_stats.setdefault(
            outcome.strategy_name, StrategyStats()
        )
        stats.total_trades += 1
        stats.total_pnl += outcome.pnl
        stats.total_holding_minutes += outcome.holding_minutes

        if outcome.is_winner:
            stats.winners += 1
            stats.gross_profit += outcome.pnl
            stats.max_win = max(stats.max_win, outcome.pnl)
        else:
            stats.losers += 1
            stats.gross_loss += outcome.pnl  # negative
            stats.max_loss = min(stats.max_loss, outcome.pnl)

        if outcome.hit_target:
            stats.target_hits += 1
        if outcome.hit_stop:
            stats.stop_hits += 1

        logger.info(
            "trade_recorded",
            symbol=outcome.symbol,
            strategy=outcome.strategy_name,
            pnl=outcome.pnl,
            winner=outcome.is_winner,
        )

    def get_overall_stats(self) -> Dict[str, float]:
        """Compute aggregate stats across all strategies."""
        if not self._outcomes:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
            }

        total = len(self._outcomes)
        winners = sum(1 for o in self._outcomes if o.is_winner)
        total_pnl = sum(o.pnl for o in self._outcomes)
        gross_profit = sum(o.pnl for o in self._outcomes if o.pnl > 0)
        gross_loss = sum(o.pnl for o in self._outcomes if o.pnl < 0)

        return {
            "total_trades": total,
            "win_rate": round(winners / total, 4),
            "total_pnl": round(total_pnl, 2),
            "profit_factor": round(
                gross_profit / abs(gross_loss) if gross_loss != 0 else float("inf"), 2
            ),
            "expectancy": round(total_pnl / total, 2),
            "avg_holding_min": round(
                sum(o.holding_minutes for o in self._outcomes) / total, 1
            ),
        }

    def get_strategy_report(self) -> Dict[str, Dict[str, float]]:
        """Get per-strategy performance breakdown."""
        report = {}
        for name, stats in self._strategy_stats.items():
            report[name] = {
                "total_trades": stats.total_trades,
                "win_rate": round(stats.win_rate, 4),
                "total_pnl": round(stats.total_pnl, 2),
                "profit_factor": round(stats.profit_factor, 2),
                "expectancy": round(stats.expectancy, 2),
                "avg_holding_min": round(stats.avg_holding_minutes, 1),
                "target_hit_rate": round(
                    stats.target_hits / stats.total_trades if stats.total_trades > 0 else 0, 4
                ),
                "max_win": round(stats.max_win, 2),
                "max_loss": round(stats.max_loss, 2),
            }
        return report
