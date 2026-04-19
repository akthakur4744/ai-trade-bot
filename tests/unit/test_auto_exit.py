"""Tests for auto-exit monitor."""

from datetime import datetime, timedelta

import pytest

from src.execution.auto_exit import AutoExitMonitor
from src.models import Direction, ExitReason, Position


@pytest.fixture
def monitor():
    return AutoExitMonitor(max_hold_minutes=90)


@pytest.fixture
def long_position():
    return Position(
        symbol="RELIANCE",
        direction=Direction.BUY,
        quantity=10,
        entry_price=2500.0,
        stop_loss=2400.0,
        target_price=2700.0,
        entry_time=datetime.utcnow(),
    )


class TestStopLoss:
    def test_stop_hit_long(self, monitor, long_position):
        signal = monitor.check_position(long_position, current_price=2399.0)
        assert signal is not None
        assert signal.reason == ExitReason.STOP_LOSS

    def test_stop_not_hit(self, monitor, long_position):
        signal = monitor.check_position(long_position, current_price=2450.0)
        assert signal is None

    def test_stop_hit_short(self, monitor):
        pos = Position(
            symbol="TCS", direction=Direction.SELL, quantity=5,
            entry_price=3000, stop_loss=3100, entry_time=datetime.utcnow(),
        )
        signal = monitor.check_position(pos, current_price=3101.0)
        assert signal is not None
        assert signal.reason == ExitReason.STOP_LOSS


class TestTarget:
    def test_target_hit(self, monitor, long_position):
        signal = monitor.check_position(long_position, current_price=2700.0)
        assert signal is not None
        assert signal.reason == ExitReason.TARGET

    def test_target_not_hit(self, monitor, long_position):
        signal = monitor.check_position(long_position, current_price=2600.0)
        assert signal is None


class TestTimeExit:
    def test_expired(self, monitor):
        pos = Position(
            symbol="TCS", direction=Direction.BUY, quantity=5,
            entry_price=3000, stop_loss=2900,
            entry_time=datetime.utcnow() - timedelta(minutes=100),
        )
        signal = monitor.check_position(pos, current_price=3050.0)
        assert signal is not None
        assert signal.reason == ExitReason.TIME_BASED

    def test_not_expired(self, monitor, long_position):
        signal = monitor.check_position(long_position, current_price=2550.0)
        assert signal is None


class TestConfidenceDecay:
    def test_decay_triggers_exit(self, monitor, long_position):
        signal = monitor.check_position(
            long_position, current_price=2550.0, current_confidence=0.3
        )
        assert signal is not None
        assert signal.reason == ExitReason.CONFIDENCE_DECAY

    def test_healthy_confidence(self, monitor, long_position):
        signal = monitor.check_position(
            long_position, current_price=2550.0, current_confidence=0.7
        )
        assert signal is None


class TestStructureBreak:
    def test_reversal_with_volume(self, monitor, long_position):
        signal = monitor.check_position(
            long_position, current_price=2470.0, volume_ratio=2.0
        )
        assert signal is not None
        assert signal.reason == ExitReason.STRUCTURE_BREAK

    def test_no_reversal_low_volume(self, monitor, long_position):
        signal = monitor.check_position(
            long_position, current_price=2470.0, volume_ratio=1.0
        )
        assert signal is None


class TestPriorityOrder:
    def test_stop_loss_before_time(self, monitor):
        """Stop loss has higher priority than time-based exit."""
        pos = Position(
            symbol="TCS", direction=Direction.BUY, quantity=5,
            entry_price=3000, stop_loss=2900, target_price=3200,
            entry_time=datetime.utcnow() - timedelta(minutes=100),
        )
        signal = monitor.check_position(pos, current_price=2899.0)
        assert signal.reason == ExitReason.STOP_LOSS
