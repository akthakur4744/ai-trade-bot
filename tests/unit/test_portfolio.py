"""Tests for portfolio state tracking."""

import pytest

from src.models import Direction, ExitReason, Position
from src.risk.portfolio import Portfolio


@pytest.fixture
def portfolio():
    return Portfolio()


@pytest.fixture
def sample_position():
    return Position(
        symbol="RELIANCE",
        direction=Direction.BUY,
        quantity=10,
        entry_price=2500.0,
        stop_loss=2400.0,
    )


class TestPortfolio:
    def test_add_position(self, portfolio, sample_position):
        portfolio.add_position(sample_position)
        assert portfolio.open_position_count == 1
        assert portfolio.deployed_capital == 25000.0  # 10 * 2500
        assert portfolio.has_position("RELIANCE")

    def test_close_position_profit(self, portfolio, sample_position):
        portfolio.add_position(sample_position)
        pnl = portfolio.close_position("RELIANCE", exit_price=2600.0, reason=ExitReason.TARGET)
        assert pnl == 1000.0  # (2600 - 2500) * 10
        assert portfolio.open_position_count == 0
        assert portfolio.realized_pnl_today == 1000.0

    def test_close_position_loss(self, portfolio, sample_position):
        portfolio.add_position(sample_position)
        pnl = portfolio.close_position("RELIANCE", exit_price=2400.0, reason=ExitReason.STOP_LOSS)
        assert pnl == -1000.0
        assert portfolio.realized_pnl_today == -1000.0

    def test_close_nonexistent(self, portfolio):
        pnl = portfolio.close_position("FAKE", exit_price=100, reason=ExitReason.MANUAL)
        assert pnl == 0.0

    def test_multiple_positions(self, portfolio):
        p1 = Position(symbol="TCS", direction=Direction.BUY, quantity=5, entry_price=3000, stop_loss=2900)
        p2 = Position(symbol="INFY", direction=Direction.BUY, quantity=10, entry_price=1500, stop_loss=1450)
        portfolio.add_position(p1)
        portfolio.add_position(p2)
        assert portfolio.open_position_count == 2
        assert portfolio.deployed_capital == 30000.0  # 15000 + 15000

    def test_update_prices(self, portfolio, sample_position):
        portfolio.add_position(sample_position)
        portfolio.update_prices({"RELIANCE": 2550.0})
        pos = portfolio.get_position("RELIANCE")
        assert pos.current_price == 2550.0
        assert pos.unrealized_pnl == 500.0  # (2550 - 2500) * 10

    def test_daily_stats(self, portfolio, sample_position):
        portfolio.add_position(sample_position)
        portfolio.close_position("RELIANCE", exit_price=2600.0, reason=ExitReason.TARGET)
        stats = portfolio.get_daily_stats()
        assert stats["trade_count"] == 1
        assert stats["winning_trades"] == 1
        assert stats["realized_pnl"] == 1000.0

    def test_sell_direction_pnl(self, portfolio):
        """Short position PnL calculates correctly."""
        pos = Position(
            symbol="TCS", direction=Direction.SELL, quantity=5,
            entry_price=3000, stop_loss=3100,
        )
        portfolio.add_position(pos)
        pnl = portfolio.close_position("TCS", exit_price=2900, reason=ExitReason.TARGET)
        assert pnl == 500.0  # (3000 - 2900) * 5

    def test_duplicate_position_rejected(self, portfolio, sample_position):
        portfolio.add_position(sample_position)
        portfolio.add_position(sample_position)  # Should warn, not add
        assert portfolio.open_position_count == 1
