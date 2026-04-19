"""Performance reporter — computes Sharpe, max drawdown, win rate, profit factor.

Generates daily and weekly reports from trade history.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import structlog

from src.feedback.tracker import TradeOutcome

logger = structlog.get_logger(__name__)

# Trading days per year (Indian markets)
TRADING_DAYS_YEAR = 252


@dataclass
class PerformanceReport:
    """Comprehensive performance metrics."""

    period: str  # "daily", "weekly", "monthly", "all"
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # Trade stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # PnL
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    avg_pnl_per_trade: float = 0.0

    # Risk metrics
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0

    # Quality metrics
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    reward_risk_ratio: float = 0.0

    # Time metrics
    avg_holding_minutes: float = 0.0
    avg_winner_holding: float = 0.0
    avg_loser_holding: float = 0.0


class Reporter:
    """Generates performance reports from trade outcomes."""

    def __init__(self, initial_capital: float = 100000.0) -> None:
        self._initial_capital = initial_capital

    def generate(
        self,
        outcomes: List[TradeOutcome],
        period: str = "all",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> PerformanceReport:
        """Generate a performance report for the given period.

        Args:
            outcomes: List of completed trade outcomes.
            period: Label for the report period.
            start_date: Filter trades after this date.
            end_date: Filter trades before this date.

        Returns:
            PerformanceReport with all metrics computed.
        """
        # Filter by date range
        filtered = outcomes
        if start_date:
            filtered = [o for o in filtered if o.exit_time.date() >= start_date]
        if end_date:
            filtered = [o for o in filtered if o.exit_time.date() <= end_date]

        report = PerformanceReport(
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        if not filtered:
            return report

        # Basic counts
        report.total_trades = len(filtered)
        report.winning_trades = sum(1 for o in filtered if o.is_winner)
        report.losing_trades = report.total_trades - report.winning_trades

        # PnL
        pnls = [o.pnl for o in filtered]
        report.total_pnl = round(sum(pnls), 2)
        report.gross_profit = round(sum(p for p in pnls if p > 0), 2)
        report.gross_loss = round(sum(p for p in pnls if p < 0), 2)
        report.avg_pnl_per_trade = round(report.total_pnl / report.total_trades, 2)

        # Win rate
        report.win_rate = round(report.winning_trades / report.total_trades, 4)

        # Profit factor
        if report.gross_loss != 0:
            report.profit_factor = round(
                report.gross_profit / abs(report.gross_loss), 2
            )
        else:
            report.profit_factor = float("inf") if report.gross_profit > 0 else 0.0

        # Average win/loss
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        report.avg_win = round(sum(wins) / len(wins), 2) if wins else 0.0
        report.avg_loss = round(sum(losses) / len(losses), 2) if losses else 0.0

        # Reward/Risk ratio
        if report.avg_loss != 0:
            report.reward_risk_ratio = round(
                abs(report.avg_win / report.avg_loss), 2
            )

        # Expectancy
        report.expectancy = round(
            (report.win_rate * report.avg_win)
            + ((1 - report.win_rate) * report.avg_loss),
            2,
        )

        # Sharpe ratio
        report.sharpe_ratio = self._compute_sharpe(pnls)

        # Max drawdown
        report.max_drawdown, report.max_drawdown_pct = self._compute_max_drawdown(
            pnls
        )

        # Time metrics
        holdings = [o.holding_minutes for o in filtered]
        report.avg_holding_minutes = round(sum(holdings) / len(holdings), 1)

        winner_holdings = [o.holding_minutes for o in filtered if o.is_winner]
        loser_holdings = [o.holding_minutes for o in filtered if not o.is_winner]
        report.avg_winner_holding = (
            round(sum(winner_holdings) / len(winner_holdings), 1) if winner_holdings else 0.0
        )
        report.avg_loser_holding = (
            round(sum(loser_holdings) / len(loser_holdings), 1) if loser_holdings else 0.0
        )

        return report

    def _compute_sharpe(self, pnls: List[float], risk_free_rate: float = 0.06) -> float:
        """Compute annualized Sharpe ratio from trade PnLs.

        Uses per-trade returns relative to initial capital.
        """
        if len(pnls) < 2:
            return 0.0

        returns = np.array(pnls) / self._initial_capital
        mean_return = float(np.mean(returns))
        std_return = float(np.std(returns, ddof=1))

        if std_return == 0:
            return 0.0

        # Annualize: assume average 1 trade per day
        daily_rf = risk_free_rate / TRADING_DAYS_YEAR
        sharpe = (mean_return - daily_rf) / std_return
        annualized = sharpe * math.sqrt(TRADING_DAYS_YEAR)
        return round(annualized, 2)

    def _compute_max_drawdown(self, pnls: List[float]) -> tuple[float, float]:
        """Compute max drawdown in absolute INR and percentage terms."""
        if not pnls:
            return 0.0, 0.0

        equity_curve = [self._initial_capital]
        for pnl in pnls:
            equity_curve.append(equity_curve[-1] + pnl)

        peak = equity_curve[0]
        max_dd = 0.0

        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd

        max_dd_pct = (max_dd / self._initial_capital) * 100 if self._initial_capital > 0 else 0.0
        return round(max_dd, 2), round(max_dd_pct, 2)

    def daily_report(
        self, outcomes: List[TradeOutcome], target_date: date
    ) -> PerformanceReport:
        """Generate report for a single day."""
        return self.generate(
            outcomes, period="daily", start_date=target_date, end_date=target_date
        )

    def weekly_report(
        self, outcomes: List[TradeOutcome], week_end: date
    ) -> PerformanceReport:
        """Generate report for the week ending on the given date."""
        week_start = week_end - timedelta(days=6)
        return self.generate(
            outcomes, period="weekly", start_date=week_start, end_date=week_end
        )
