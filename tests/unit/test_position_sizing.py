"""Tests for position sizing methods."""

import pytest

from src.config import RiskConfig
from src.risk.position_sizing import (
    atr_based_size,
    calculate_position_size,
    fixed_percentage_size,
    kelly_criterion_size,
)


class TestFixedPercentage:
    def test_basic_calculation(self):
        # 100K capital, 2% risk = 2000 INR risk budget
        # Entry 500, stop 480 = 20 risk per share
        # 2000 / 20 = 100 shares
        qty = fixed_percentage_size(capital=100000, entry_price=500, stop_loss=480, risk_pct=0.02)
        assert qty == 100

    def test_tight_stop(self):
        # Tight stop = more shares
        qty = fixed_percentage_size(capital=100000, entry_price=500, stop_loss=495, risk_pct=0.02)
        assert qty == 400  # 2000 / 5

    def test_wide_stop(self):
        # Wide stop = fewer shares
        qty = fixed_percentage_size(capital=100000, entry_price=500, stop_loss=450, risk_pct=0.02)
        assert qty == 40  # 2000 / 50

    def test_zero_risk_per_share(self):
        qty = fixed_percentage_size(capital=100000, entry_price=500, stop_loss=500, risk_pct=0.02)
        assert qty == 0

    def test_small_capital(self):
        qty = fixed_percentage_size(capital=10000, entry_price=2500, stop_loss=2400, risk_pct=0.02)
        assert qty == 2  # 200 / 100


class TestATRBased:
    def test_basic(self):
        qty, stop = atr_based_size(capital=100000, entry_price=500, atr=10, atr_multiplier=2.0, risk_pct=0.02)
        # Risk budget = 2000, stop distance = 20, qty = 100
        assert qty == 100
        assert stop == 480.0  # 500 - 20

    def test_high_volatility(self):
        qty, stop = atr_based_size(capital=100000, entry_price=500, atr=50, atr_multiplier=2.0, risk_pct=0.02)
        # Stop distance = 100, qty = 20
        assert qty == 20
        assert stop == 400.0

    def test_zero_atr(self):
        qty, stop = atr_based_size(capital=100000, entry_price=500, atr=0, risk_pct=0.02)
        assert qty == 0


class TestKellyCriterion:
    def test_profitable_system(self):
        # 55% win rate, 2:1 win/loss ratio
        # Kelly = 0.55 - (0.45 / 2) = 0.55 - 0.225 = 0.325
        # Half Kelly = 0.1625, position = 16250
        # Shares at 500 = 32
        qty = kelly_criterion_size(
            capital=100000, entry_price=500,
            win_rate=0.55, avg_win=200, avg_loss=100,
            fraction=0.5,
        )
        assert qty == 32

    def test_negative_edge(self):
        # 30% win rate, 1:1 ratio -> Kelly negative
        qty = kelly_criterion_size(
            capital=100000, entry_price=500,
            win_rate=0.30, avg_win=100, avg_loss=100,
        )
        assert qty == 0

    def test_max_position_cap(self):
        # Very high Kelly but capped at 25%
        qty = kelly_criterion_size(
            capital=100000, entry_price=100,
            win_rate=0.80, avg_win=300, avg_loss=50,
            fraction=1.0,
            max_position_pct=0.25,
        )
        max_possible = 100000 * 0.25 / 100  # 250
        assert qty <= max_possible


class TestCalculatePositionSize:
    def test_enforces_max_capital_per_trade(self):
        config = RiskConfig(max_capital_per_trade=5000, per_trade_risk_pct=0.02)
        # Fixed pct would give 100 shares, but 100 * 500 = 50000 > 5000
        qty = calculate_position_size(
            method="fixed_pct",
            capital=100000,
            entry_price=500,
            stop_loss=480,
            config=config,
        )
        # Max qty at 500/share with 5000 cap = 10
        assert qty == 10

    def test_atr_method_dispatch(self):
        config = RiskConfig(max_capital_per_trade=100000, per_trade_risk_pct=0.02)
        qty = calculate_position_size(
            method="atr",
            capital=100000,
            entry_price=500,
            stop_loss=480,
            config=config,
            atr=10,
        )
        assert qty > 0

    def test_falls_back_to_fixed_pct(self):
        config = RiskConfig(max_capital_per_trade=100000, per_trade_risk_pct=0.02)
        # ATR method with atr=0 falls back to fixed_pct
        qty = calculate_position_size(
            method="atr",
            capital=100000,
            entry_price=500,
            stop_loss=480,
            config=config,
            atr=0,
        )
        assert qty == 100
