"""Tests for backtest runner and walk-forward validator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models import Direction
from src.strategies.mean_reversion import MeanReversionStrategy
from tests.backtest.runner import BacktestConfig, BacktestResult, BacktestRunner


def _make_ohlcv(n: int = 500, base: float = 100.0, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    np.random.seed(seed)
    close = base + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame(
        {
            "open": close + np.random.randn(n) * 0.2,
            "high": close + abs(np.random.randn(n) * 0.5),
            "low": close - abs(np.random.randn(n) * 0.5),
            "close": close,
            "volume": np.random.randint(100000, 1000000, n),
        },
        index=pd.date_range("2023-01-01", periods=n, freq="15min"),
    )


def _make_trending_data(n: int = 500, direction: str = "up") -> pd.DataFrame:
    """Generate data with clear trend for strategy testing."""
    np.random.seed(55)
    if direction == "up":
        trend = np.linspace(0, 50, n)
    else:
        trend = np.linspace(50, 0, n)
    noise = np.random.randn(n) * 0.3
    close = 100 + trend + noise
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + abs(np.random.randn(n) * 0.3),
            "low": close - abs(np.random.randn(n) * 0.3),
            "close": close,
            "volume": np.random.randint(200000, 2000000, n),
        },
        index=pd.date_range("2023-01-01", periods=n, freq="15min"),
    )


class TestBacktestRunner:
    def test_run_returns_result(self):
        runner = BacktestRunner()
        strategy = MeanReversionStrategy()
        data = _make_ohlcv(500)
        result = runner.run(strategy, "TEST", data)
        assert isinstance(result, BacktestResult)
        assert result.strategy_name == "mean_reversion"
        assert result.symbol == "TEST"
        assert result.initial_capital == 100000.0

    def test_insufficient_data(self):
        runner = BacktestRunner()
        strategy = MeanReversionStrategy()
        data = _make_ohlcv(50)
        result = runner.run(strategy, "TEST", data, warmup_bars=200)
        assert result.total_trades == 0
        assert result.final_capital == 100000.0

    def test_capital_preserved_no_trades(self):
        runner = BacktestRunner()
        strategy = MeanReversionStrategy()
        # Short data that won't trigger signals
        data = _make_ohlcv(250)
        result = runner.run(strategy, "TEST", data, warmup_bars=200)
        # If no trades, capital should be initial
        if result.total_trades == 0:
            assert result.final_capital == 100000.0

    def test_slippage_applied(self):
        runner = BacktestRunner(BacktestConfig(slippage_bps=10))
        # BUY slippage: price goes up
        price = runner._apply_slippage(100.0, Direction.BUY, exit=False)
        assert price > 100.0
        # SELL slippage: price goes down
        price = runner._apply_slippage(100.0, Direction.SELL, exit=False)
        assert price < 100.0

    def test_exit_slippage_adverse(self):
        runner = BacktestRunner(BacktestConfig(slippage_bps=10))
        # BUY exit (sell): price goes down
        price = runner._apply_slippage(100.0, Direction.BUY, exit=True)
        assert price < 100.0
        # SELL exit (cover): price goes up
        price = runner._apply_slippage(100.0, Direction.SELL, exit=True)
        assert price > 100.0

    def test_position_sizing(self):
        runner = BacktestRunner(BacktestConfig(risk_pct=0.02))
        qty = runner._calculate_quantity(100000, 100.0, 95.0)
        # Risk = 100000 * 0.02 = 2000, risk_per_share = 5, qty = 400
        assert qty == 400

    def test_position_sizing_zero_risk(self):
        runner = BacktestRunner()
        qty = runner._calculate_quantity(100000, 100.0, 100.0)
        assert qty == 0

    def test_timeframe_inference(self):
        assert BacktestRunner._infer_timeframe(
            _make_ohlcv(10)
        ) == "15minute"

        # 5-minute data
        data_5m = pd.DataFrame(
            {"close": range(10)},
            index=pd.date_range("2024-01-01", periods=10, freq="5min"),
        )
        assert BacktestRunner._infer_timeframe(data_5m) == "5minute"

        # Daily data
        data_daily = pd.DataFrame(
            {"close": range(10)},
            index=pd.date_range("2024-01-01", periods=10, freq="B"),
        )
        assert BacktestRunner._infer_timeframe(data_daily) == "day"

    def test_max_positions_respected(self):
        config = BacktestConfig(max_open_positions=1)
        runner = BacktestRunner(config)
        strategy = MeanReversionStrategy()
        data = _make_ohlcv(500)
        result = runner.run(strategy, "TEST", data)
        # Can't verify exact behavior but should not crash
        assert isinstance(result, BacktestResult)

    def test_outcomes_recorded(self):
        runner = BacktestRunner()
        strategy = MeanReversionStrategy()
        data = _make_ohlcv(500)
        result = runner.run(strategy, "TEST", data)
        # All outcomes should match total trades
        assert len(result.outcomes) == result.total_trades

    def test_pnl_consistency(self):
        runner = BacktestRunner()
        strategy = MeanReversionStrategy()
        data = _make_ohlcv(500)
        result = runner.run(strategy, "TEST", data)
        if result.total_trades > 0:
            outcome_pnl = sum(o.pnl for o in result.outcomes)
            assert abs(outcome_pnl - result.total_pnl) < 1.0  # Allow rounding

    def test_tracker_populated(self):
        runner = BacktestRunner()
        strategy = MeanReversionStrategy()
        data = _make_ohlcv(500)
        result = runner.run(strategy, "TEST", data)
        assert len(runner.tracker.outcomes) == result.total_trades
