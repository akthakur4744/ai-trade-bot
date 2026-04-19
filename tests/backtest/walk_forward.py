"""Walk-forward validation — rolling window out-of-sample testing.

Splits data into rolling train/test windows to detect overfitting.
If a strategy performs well in-sample but poorly out-of-sample,
it's likely overfit.

Default: 6-month train, 1-month test, sliding by 1 month.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, List, Optional, Type

import pandas as pd
import structlog

from src.strategies.base import Strategy
from tests.backtest.runner import BacktestConfig, BacktestResult, BacktestRunner

logger = structlog.get_logger(__name__)


@dataclass
class WalkForwardWindow:
    """A single train/test window."""

    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_result: Optional[BacktestResult] = None
    test_result: Optional[BacktestResult] = None


@dataclass
class WalkForwardResult:
    """Complete walk-forward analysis output."""

    strategy_name: str
    symbol: str
    windows: List[WalkForwardWindow] = field(default_factory=list)
    in_sample_avg_pnl: float = 0.0
    out_of_sample_avg_pnl: float = 0.0
    in_sample_win_rate: float = 0.0
    out_of_sample_win_rate: float = 0.0
    consistency_ratio: float = 0.0  # OOS avg / IS avg — closer to 1.0 = less overfit
    overfitting_flag: bool = False


class WalkForwardValidator:
    """Rolling window out-of-sample validation.

    For each window:
    1. Backtest on train period (in-sample)
    2. Backtest on test period (out-of-sample)
    3. Compare IS vs OOS performance
    """

    def __init__(
        self,
        train_months: int = 6,
        test_months: int = 1,
        step_months: int = 1,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> None:
        self._train_months = train_months
        self._test_months = test_months
        self._step_months = step_months
        self._bt_config = backtest_config or BacktestConfig()

    def validate(
        self,
        strategy: Strategy,
        symbol: str,
        data: pd.DataFrame,
        strategy_config: Optional[dict] = None,
        warmup_bars: int = 200,
    ) -> WalkForwardResult:
        """Run walk-forward validation.

        Args:
            strategy: Strategy to validate.
            symbol: Symbol being tested.
            data: Full OHLCV DataFrame with DatetimeIndex.
            strategy_config: Strategy params.
            warmup_bars: Bars for indicator warmup.

        Returns:
            WalkForwardResult with per-window and aggregate metrics.
        """
        strategy_config = strategy_config or {}
        windows = self._generate_windows(data)

        if not windows:
            logger.warning("walk_forward_no_windows", data_len=len(data))
            return WalkForwardResult(strategy_name=strategy.name, symbol=symbol)

        for window in windows:
            runner = BacktestRunner(self._bt_config)

            # In-sample (train)
            train_data = data[window.train_start : window.train_end]
            if len(train_data) > warmup_bars:
                window.train_result = runner.run(
                    strategy, symbol, train_data, strategy_config, warmup_bars
                )

            # Out-of-sample (test)
            test_data = data[window.test_start : window.test_end]
            if len(test_data) > warmup_bars:
                window.test_result = runner.run(
                    strategy, symbol, test_data, strategy_config, warmup_bars
                )

        return self._build_result(strategy.name, symbol, windows)

    def _generate_windows(self, data: pd.DataFrame) -> List[WalkForwardWindow]:
        """Generate rolling train/test windows."""
        if len(data) == 0:
            return []

        start = data.index[0]
        end = data.index[-1]

        train_delta = pd.DateOffset(months=self._train_months)
        test_delta = pd.DateOffset(months=self._test_months)
        step_delta = pd.DateOffset(months=self._step_months)

        windows = []
        cursor = start

        while True:
            train_start = cursor
            train_end = cursor + train_delta
            test_start = train_end
            test_end = test_start + test_delta

            if test_end > end:
                break

            windows.append(
                WalkForwardWindow(
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )

            cursor += step_delta

        return windows

    @staticmethod
    def _build_result(
        strategy_name: str,
        symbol: str,
        windows: List[WalkForwardWindow],
    ) -> WalkForwardResult:
        result = WalkForwardResult(
            strategy_name=strategy_name,
            symbol=symbol,
            windows=windows,
        )

        # Compute averages
        is_pnls = []
        oos_pnls = []
        is_win_rates = []
        oos_win_rates = []

        for w in windows:
            if w.train_result and w.train_result.total_trades > 0:
                is_pnls.append(w.train_result.total_pnl)
                is_win_rates.append(w.train_result.win_rate)
            if w.test_result and w.test_result.total_trades > 0:
                oos_pnls.append(w.test_result.total_pnl)
                oos_win_rates.append(w.test_result.win_rate)

        if is_pnls:
            result.in_sample_avg_pnl = round(sum(is_pnls) / len(is_pnls), 2)
        if oos_pnls:
            result.out_of_sample_avg_pnl = round(sum(oos_pnls) / len(oos_pnls), 2)
        if is_win_rates:
            result.in_sample_win_rate = round(sum(is_win_rates) / len(is_win_rates), 4)
        if oos_win_rates:
            result.out_of_sample_win_rate = round(
                sum(oos_win_rates) / len(oos_win_rates), 4
            )

        # Consistency ratio: OOS / IS (closer to 1.0 = better)
        if result.in_sample_avg_pnl != 0:
            result.consistency_ratio = round(
                result.out_of_sample_avg_pnl / result.in_sample_avg_pnl, 2
            )

        # Flag overfitting if OOS performance is significantly worse
        if result.in_sample_avg_pnl > 0 and result.out_of_sample_avg_pnl <= 0:
            result.overfitting_flag = True
        elif result.in_sample_win_rate > 0.7 and result.out_of_sample_win_rate < 0.4:
            result.overfitting_flag = True

        return result
