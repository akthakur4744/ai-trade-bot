#!/usr/bin/env python3
"""CLI for backtesting strategies on historical data.

Usage:
    python scripts/backtest_cli.py --strategy mean_reversion --symbol RELIANCE --data data/RELIANCE_15min.csv
    python scripts/backtest_cli.py --strategy momentum --symbol TCS --data data/TCS_15min.csv --walk-forward
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.bollinger_squeeze import BollingerSqueezeStrategy
from src.strategies.golden_cross import GoldenCrossStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.vwap_reversion import VWAPReversionStrategy
from tests.backtest.runner import BacktestConfig, BacktestRunner
from tests.backtest.walk_forward import WalkForwardValidator

STRATEGIES = {
    "mean_reversion": MeanReversionStrategy,
    "momentum": MomentumStrategy,
    "bollinger_squeeze": BollingerSqueezeStrategy,
    "golden_cross": GoldenCrossStrategy,
    "vwap_reversion": VWAPReversionStrategy,
}


def load_csv(path: str) -> pd.DataFrame:
    """Load OHLCV CSV with datetime index."""
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")
    return df.sort_index()


def print_result(result):
    """Pretty-print backtest results."""
    print(f"\n{'='*60}")
    print(f"  Backtest: {result.strategy_name} on {result.symbol}")
    print(f"  Period: {result.period_start:%Y-%m-%d} to {result.period_end:%Y-%m-%d}")
    print(f"{'='*60}")
    print(f"  Initial Capital:  ₹{result.initial_capital:>12,.2f}")
    print(f"  Final Capital:    ₹{result.final_capital:>12,.2f}")
    print(f"  Total PnL:        ₹{result.total_pnl:>12,.2f}")
    print(f"  {'─'*40}")
    print(f"  Total Trades:     {result.total_trades:>8d}")
    print(f"  Winners:          {result.winning_trades:>8d}")
    print(f"  Losers:           {result.losing_trades:>8d}")
    print(f"  Win Rate:         {result.win_rate:>8.1%}")
    print(f"  Profit Factor:    {result.profit_factor:>8.2f}")
    print(f"  Max Drawdown:     ₹{result.max_drawdown:>10,.2f} ({result.max_drawdown_pct:.1f}%)")
    print(f"{'='*60}\n")


def print_walk_forward(wf_result):
    """Pretty-print walk-forward validation results."""
    print(f"\n{'='*60}")
    print(f"  Walk-Forward: {wf_result.strategy_name} on {wf_result.symbol}")
    print(f"  Windows: {len(wf_result.windows)}")
    print(f"{'='*60}")
    print(f"  In-Sample Avg PnL:      ₹{wf_result.in_sample_avg_pnl:>10,.2f}")
    print(f"  Out-of-Sample Avg PnL:  ₹{wf_result.out_of_sample_avg_pnl:>10,.2f}")
    print(f"  IS Win Rate:            {wf_result.in_sample_win_rate:>8.1%}")
    print(f"  OOS Win Rate:           {wf_result.out_of_sample_win_rate:>8.1%}")
    print(f"  Consistency Ratio:      {wf_result.consistency_ratio:>8.2f}")
    print(f"  Overfitting Flag:       {'YES' if wf_result.overfitting_flag else 'NO':>8s}")

    if wf_result.overfitting_flag:
        print(f"\n  ⚠ WARNING: Strategy shows signs of overfitting!")
        print(f"    In-sample performance does not hold out-of-sample.")

    print(f"\n  Per-Window Results:")
    for i, w in enumerate(wf_result.windows):
        is_pnl = w.train_result.total_pnl if w.train_result else 0
        oos_pnl = w.test_result.total_pnl if w.test_result else 0
        is_trades = w.train_result.total_trades if w.train_result else 0
        oos_trades = w.test_result.total_trades if w.test_result else 0
        print(
            f"    Window {i+1}: "
            f"IS ₹{is_pnl:>8,.0f} ({is_trades}t) | "
            f"OOS ₹{oos_pnl:>8,.0f} ({oos_trades}t)"
        )

    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Backtest trading strategies")
    parser.add_argument(
        "--strategy",
        required=True,
        choices=list(STRATEGIES.keys()),
        help="Strategy to backtest",
    )
    parser.add_argument("--symbol", required=True, help="Symbol name")
    parser.add_argument("--data", required=True, help="Path to OHLCV CSV file")
    parser.add_argument(
        "--capital", type=float, default=100000, help="Initial capital (INR)"
    )
    parser.add_argument(
        "--max-per-trade", type=float, default=10000, help="Max capital per trade"
    )
    parser.add_argument(
        "--warmup", type=int, default=200, help="Warmup bars to skip"
    )
    parser.add_argument(
        "--walk-forward", action="store_true", help="Run walk-forward validation"
    )
    parser.add_argument(
        "--train-months", type=int, default=6, help="Walk-forward train window (months)"
    )
    parser.add_argument(
        "--test-months", type=int, default=1, help="Walk-forward test window (months)"
    )

    args = parser.parse_args()

    # Load data
    print(f"Loading data from {args.data}...")
    data = load_csv(args.data)
    print(f"Loaded {len(data)} bars from {data.index[0]:%Y-%m-%d} to {data.index[-1]:%Y-%m-%d}")

    # Create strategy
    strategy = STRATEGIES[args.strategy]()

    config = BacktestConfig(
        initial_capital=args.capital,
        max_capital_per_trade=args.max_per_trade,
    )

    if args.walk_forward:
        validator = WalkForwardValidator(
            train_months=args.train_months,
            test_months=args.test_months,
            backtest_config=config,
        )
        result = validator.validate(
            strategy, args.symbol, data, warmup_bars=args.warmup
        )
        print_walk_forward(result)
    else:
        runner = BacktestRunner(config)
        result = runner.run(strategy, args.symbol, data, warmup_bars=args.warmup)
        print_result(result)


if __name__ == "__main__":
    main()
