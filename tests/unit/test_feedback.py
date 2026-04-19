"""Tests for feedback tracker and reporter."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.feedback.reporter import Reporter
from src.feedback.tracker import FeedbackTracker, TradeOutcome


def _make_outcome(
    pnl: float = 100.0,
    strategy: str = "momentum",
    exit_reason: str = "target",
    minutes_ago: int = 30,
    symbol: str = "RELIANCE",
) -> TradeOutcome:
    now = datetime(2024, 6, 15, 14, 0, 0)
    return TradeOutcome(
        symbol=symbol,
        strategy_name=strategy,
        direction="BUY",
        entry_price=2500.0,
        exit_price=2500.0 + (pnl / 10),
        stop_loss=2450.0,
        target_price=2550.0,
        entry_time=now - timedelta(minutes=minutes_ago),
        exit_time=now,
        exit_reason=exit_reason,
        quantity=10,
        pnl=pnl,
        pnl_pct=round(pnl / 25000 * 100, 2),
    )


# ---- TradeOutcome Tests ----


class TestTradeOutcome:
    def test_is_winner(self):
        assert _make_outcome(100).is_winner is True
        assert _make_outcome(-50).is_winner is False

    def test_hit_target(self):
        assert _make_outcome(exit_reason="target").hit_target is True
        assert _make_outcome(exit_reason="stop_loss").hit_target is False

    def test_hit_stop(self):
        assert _make_outcome(exit_reason="stop_loss").hit_stop is True

    def test_holding_minutes(self):
        outcome = _make_outcome(minutes_ago=45)
        assert outcome.holding_minutes == 45.0

    def test_risk_reward_winner(self):
        outcome = _make_outcome(100)
        rr = outcome.risk_reward_actual
        assert rr is not None
        assert rr > 0

    def test_risk_reward_loser(self):
        outcome = _make_outcome(-100)
        rr = outcome.risk_reward_actual
        assert rr is not None
        assert rr < 0


# ---- FeedbackTracker Tests ----


class TestFeedbackTracker:
    def test_record_single(self):
        tracker = FeedbackTracker()
        tracker.record(_make_outcome(100))
        assert len(tracker.outcomes) == 1
        assert "momentum" in tracker.strategy_stats

    def test_record_multiple_strategies(self):
        tracker = FeedbackTracker()
        tracker.record(_make_outcome(100, strategy="momentum"))
        tracker.record(_make_outcome(-50, strategy="mean_reversion"))
        tracker.record(_make_outcome(200, strategy="momentum"))
        assert tracker.strategy_stats["momentum"].total_trades == 2
        assert tracker.strategy_stats["mean_reversion"].total_trades == 1

    def test_strategy_stats_win_rate(self):
        tracker = FeedbackTracker()
        tracker.record(_make_outcome(100, strategy="s1"))
        tracker.record(_make_outcome(50, strategy="s1"))
        tracker.record(_make_outcome(-30, strategy="s1"))
        stats = tracker.strategy_stats["s1"]
        assert stats.win_rate == pytest.approx(2 / 3, abs=0.01)

    def test_strategy_stats_profit_factor(self):
        tracker = FeedbackTracker()
        tracker.record(_make_outcome(200, strategy="s1"))
        tracker.record(_make_outcome(-100, strategy="s1"))
        stats = tracker.strategy_stats["s1"]
        assert stats.profit_factor == 2.0

    def test_strategy_stats_expectancy(self):
        tracker = FeedbackTracker()
        tracker.record(_make_outcome(300, strategy="s1"))
        tracker.record(_make_outcome(-100, strategy="s1"))
        stats = tracker.strategy_stats["s1"]
        assert stats.expectancy > 0

    def test_get_overall_stats(self):
        tracker = FeedbackTracker()
        tracker.record(_make_outcome(100))
        tracker.record(_make_outcome(-50))
        tracker.record(_make_outcome(200))
        overall = tracker.get_overall_stats()
        assert overall["total_trades"] == 3
        assert overall["win_rate"] == pytest.approx(2 / 3, abs=0.01)
        assert overall["total_pnl"] == 250.0

    def test_overall_stats_empty(self):
        tracker = FeedbackTracker()
        overall = tracker.get_overall_stats()
        assert overall["total_trades"] == 0

    def test_strategy_report(self):
        tracker = FeedbackTracker()
        tracker.record(_make_outcome(100, strategy="s1"))
        tracker.record(_make_outcome(-40, strategy="s2"))
        report = tracker.get_strategy_report()
        assert "s1" in report
        assert "s2" in report
        assert report["s1"]["win_rate"] == 1.0
        assert report["s2"]["win_rate"] == 0.0


# ---- Reporter Tests ----


class TestReporter:
    def test_empty_report(self):
        reporter = Reporter()
        report = reporter.generate([])
        assert report.total_trades == 0
        assert report.sharpe_ratio == 0.0

    def test_basic_report(self):
        reporter = Reporter(initial_capital=100000)
        outcomes = [
            _make_outcome(500),
            _make_outcome(-200),
            _make_outcome(300),
            _make_outcome(100),
        ]
        report = reporter.generate(outcomes)
        assert report.total_trades == 4
        assert report.winning_trades == 3
        assert report.total_pnl == 700.0
        assert report.win_rate == 0.75

    def test_profit_factor(self):
        reporter = Reporter()
        outcomes = [_make_outcome(300), _make_outcome(-100)]
        report = reporter.generate(outcomes)
        assert report.profit_factor == 3.0

    def test_max_drawdown(self):
        reporter = Reporter(initial_capital=100000)
        outcomes = [
            _make_outcome(-500),
            _make_outcome(-300),
            _make_outcome(1000),
        ]
        report = reporter.generate(outcomes)
        assert report.max_drawdown == 800.0  # Peak 100k, trough 99200
        assert report.max_drawdown_pct == 0.8

    def test_sharpe_ratio_positive(self):
        reporter = Reporter(initial_capital=100000)
        outcomes = [_make_outcome(500) for _ in range(20)]
        report = reporter.generate(outcomes)
        assert report.sharpe_ratio > 0

    def test_date_filtering(self):
        reporter = Reporter()
        from datetime import date

        o1 = _make_outcome(100)
        o2 = _make_outcome(200)
        # Both have exit_time on 2024-06-15
        report = reporter.generate(
            [o1, o2], start_date=date(2024, 6, 15), end_date=date(2024, 6, 15)
        )
        assert report.total_trades == 2

        # Filter to different date
        report2 = reporter.generate(
            [o1, o2], start_date=date(2024, 6, 16)
        )
        assert report2.total_trades == 0

    def test_daily_report(self):
        reporter = Reporter()
        from datetime import date

        outcomes = [_make_outcome(100), _make_outcome(-50)]
        report = reporter.daily_report(outcomes, date(2024, 6, 15))
        assert report.period == "daily"
        assert report.total_trades == 2

    def test_weekly_report(self):
        reporter = Reporter()
        from datetime import date

        outcomes = [_make_outcome(100)]
        report = reporter.weekly_report(outcomes, date(2024, 6, 15))
        assert report.period == "weekly"

    def test_holding_time_metrics(self):
        reporter = Reporter()
        outcomes = [
            _make_outcome(100, minutes_ago=60),  # winner, 60 min
            _make_outcome(-50, minutes_ago=20),   # loser, 20 min
        ]
        report = reporter.generate(outcomes)
        assert report.avg_holding_minutes == 40.0
        assert report.avg_winner_holding == 60.0
        assert report.avg_loser_holding == 20.0

    def test_reward_risk_ratio(self):
        reporter = Reporter()
        outcomes = [
            _make_outcome(200),
            _make_outcome(-100),
        ]
        report = reporter.generate(outcomes)
        assert report.reward_risk_ratio == 2.0
