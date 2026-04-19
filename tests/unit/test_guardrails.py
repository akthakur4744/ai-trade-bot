"""Tests for pre-trade risk guardrails."""

import pytest

from src.config import RiskConfig
from src.models import Direction, Order
from src.risk.guardrails import (
    check_daily_loss,
    check_portfolio_exposure,
    check_position_limit,
    check_trade_capital,
    validate_order,
)


@pytest.fixture
def config():
    return RiskConfig(
        max_capital_per_trade=10000,
        max_daily_loss=1000,
        max_open_positions=3,
        max_capital_deployed=30000,
    )


@pytest.fixture
def order():
    return Order(
        symbol="RELIANCE",
        direction=Direction.BUY,
        quantity=4,
        price=2500.0,  # 4 * 2500 = 10000
        stop_loss=2400.0,
    )


class TestTradeCapital:
    def test_within_limit(self, config):
        order = Order(symbol="TCS", direction=Direction.BUY, quantity=2, price=3000, stop_loss=2900)
        result = check_trade_capital(order, config)
        assert result.passed

    def test_at_limit(self, config):
        order = Order(symbol="TCS", direction=Direction.BUY, quantity=4, price=2500, stop_loss=2400)
        result = check_trade_capital(order, config)
        assert result.passed  # 4 * 2500 = 10000 = limit

    def test_exceeds_limit(self, config):
        order = Order(symbol="TCS", direction=Direction.BUY, quantity=5, price=2500, stop_loss=2400)
        result = check_trade_capital(order, config)
        assert not result.passed
        assert "max_capital_per_trade" in result.reason


class TestPortfolioExposure:
    def test_within_limit(self, order, config):
        result = check_portfolio_exposure(order, current_deployed=15000, config=config)
        assert result.passed

    def test_exceeds_limit(self, order, config):
        result = check_portfolio_exposure(order, current_deployed=25000, config=config)
        assert not result.passed
        assert "max_capital_deployed" in result.reason


class TestDailyLoss:
    def test_no_loss(self, config):
        result = check_daily_loss(realized_pnl_today=500, config=config)
        assert result.passed

    def test_within_limit(self, config):
        result = check_daily_loss(realized_pnl_today=-500, config=config)
        assert result.passed

    def test_at_limit(self, config):
        result = check_daily_loss(realized_pnl_today=-1000, config=config)
        assert not result.passed

    def test_exceeds_limit(self, config):
        result = check_daily_loss(realized_pnl_today=-1500, config=config)
        assert not result.passed
        assert "max_daily_loss" in result.reason


class TestPositionLimit:
    def test_within_limit(self, config):
        result = check_position_limit(open_positions=2, config=config)
        assert result.passed

    def test_at_limit(self, config):
        result = check_position_limit(open_positions=3, config=config)
        assert not result.passed

    def test_zero_positions(self, config):
        result = check_position_limit(open_positions=0, config=config)
        assert result.passed


class TestValidateOrder:
    def test_all_pass(self, order, config):
        result = validate_order(
            order=order,
            current_deployed=10000,
            realized_pnl_today=0,
            open_positions=1,
            config=config,
        )
        assert result.passed

    def test_first_failure_returned(self, order, config):
        """When multiple checks fail, the first failure reason is returned."""
        result = validate_order(
            order=order,
            current_deployed=25000,  # Fails exposure
            realized_pnl_today=-1500,  # Also fails daily loss
            open_positions=5,  # Also fails position limit
            config=config,
        )
        assert not result.passed
        # Trade capital check passes (10000 <= 10000), exposure check fails next
        assert "max_capital_deployed" in result.reason
