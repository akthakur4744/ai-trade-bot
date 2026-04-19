"""Tests for auto-sell manager — trigger creation, monitoring, and exit conditions."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.execution.auto_sell import AutoSellManager, _build_exit_strategy, _pct_diff
from src.models import (
    AutoSellTrigger,
    ConfidenceBreakdown,
    Direction,
    ExitReason,
    MarketRegime,
    ScoredSignal,
    Sentiment,
    Strength,
)


def _make_signal(**overrides) -> ScoredSignal:
    defaults = dict(
        symbol="RELIANCE",
        direction=Direction.BUY,
        sentiment=Sentiment.BULLISH,
        confidence=0.78,
        strength=Strength.STRONG,
        final_score=0.82,
        confidence_breakdown=ConfidenceBreakdown(
            news_strength=0.7,
            signal_alignment=0.8,
            market_confirmation=0.9,
        ),
        strategy_name="momentum",
        key_drivers=["Earnings beat", "Volume spike"],
        risks=["Global headwinds"],
        summary="Strong momentum play",
        entry_price=2500.0,
        stop_loss=2450.0,
        target_price=2600.0,
        time_horizon="intraday",
        regime=MarketRegime.BULL,
    )
    defaults.update(overrides)
    return ScoredSignal(**defaults)


class TestAutoSellManager:
    def test_create_trigger(self):
        manager = AutoSellManager()
        signal = _make_signal()
        trigger = manager.create_trigger(signal)

        assert trigger.symbol == "RELIANCE"
        assert trigger.stop_loss == 2450.0
        assert trigger.target_price == 2600.0
        assert trigger.max_hold_minutes == 90  # intraday
        assert trigger.is_active is True
        assert trigger.position_direction == Direction.BUY
        assert manager.has_trigger("RELIANCE")

    def test_create_trigger_no_target(self):
        """When no target, calculates from risk/reward 2:1."""
        manager = AutoSellManager()
        signal = _make_signal(target_price=None)
        trigger = manager.create_trigger(signal)

        risk = abs(2500 - 2450)  # 50
        expected_target = 2500 + (risk * 2.0)  # 2600
        assert trigger.target_price == expected_target

    def test_create_trigger_swing_horizon(self):
        manager = AutoSellManager()
        signal = _make_signal(time_horizon="swing")
        trigger = manager.create_trigger(signal)
        assert trigger.max_hold_minutes == 480

    def test_trailing_stop_scales_with_confidence(self):
        manager = AutoSellManager()

        # Higher confidence => tighter trailing stop
        high_conf = _make_signal(confidence=0.9)
        trigger_high = manager.create_trigger(high_conf)

        manager2 = AutoSellManager()
        low_conf = _make_signal(confidence=0.5, symbol="INFY")
        trigger_low = manager2.create_trigger(low_conf)

        assert trigger_high.trailing_stop_pct < trigger_low.trailing_stop_pct

    def test_no_trigger(self):
        manager = AutoSellManager()
        assert not manager.has_trigger("RELIANCE")
        assert manager.get_trigger("RELIANCE") is None

    def test_deactivate(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())
        manager.deactivate("RELIANCE")
        assert not manager.has_trigger("RELIANCE")

    def test_remove(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())
        manager.remove("RELIANCE")
        assert manager.get_trigger("RELIANCE") is None

    def test_active_triggers(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())
        manager.create_trigger(_make_signal(symbol="INFY"))
        assert len(manager.active_triggers) == 2

        manager.deactivate("RELIANCE")
        assert len(manager.active_triggers) == 1


class TestStopLoss:
    def test_buy_stop_loss_hit(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())
        exit_signal = manager.check_position("RELIANCE", current_price=2440.0)
        assert exit_signal is not None
        assert exit_signal.reason == ExitReason.STOP_LOSS
        assert exit_signal.urgency == "HIGH"

    def test_buy_stop_loss_not_hit(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())
        exit_signal = manager.check_position("RELIANCE", current_price=2500.0)
        assert exit_signal is None

    def test_sell_stop_loss_hit(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal(
            direction=Direction.SELL,
            entry_price=2500.0,
            stop_loss=2550.0,
            target_price=2400.0,
        ))
        exit_signal = manager.check_position("RELIANCE", current_price=2560.0)
        assert exit_signal is not None
        assert exit_signal.reason == ExitReason.STOP_LOSS


class TestTarget:
    def test_buy_target_hit(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())
        exit_signal = manager.check_position("RELIANCE", current_price=2610.0)
        assert exit_signal is not None
        assert exit_signal.reason == ExitReason.TARGET

    def test_sell_target_hit(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal(
            direction=Direction.SELL,
            entry_price=2500.0,
            stop_loss=2550.0,
            target_price=2400.0,
        ))
        exit_signal = manager.check_position("RELIANCE", current_price=2390.0)
        assert exit_signal is not None
        assert exit_signal.reason == ExitReason.TARGET


class TestTrailingStop:
    def test_trailing_stop_buy(self):
        manager = AutoSellManager()
        trigger = manager.create_trigger(_make_signal())

        # Price rises to 2580 (above entry)
        exit_signal = manager.check_position("RELIANCE", current_price=2580.0)
        assert exit_signal is None
        assert trigger.highest_price == 2580.0

        # Price drops enough to trigger trailing stop
        trailing_level = 2580.0 * (1 - trigger.trailing_stop_pct / 100)
        exit_signal = manager.check_position("RELIANCE", current_price=trailing_level - 1)
        assert exit_signal is not None
        assert exit_signal.reason == ExitReason.STRUCTURE_BREAK
        assert "Trailing stop" in exit_signal.message

    def test_trailing_stop_not_triggered_below_entry(self):
        """Trailing stop only triggers when price was above entry (protecting gains)."""
        manager = AutoSellManager()
        trigger = manager.create_trigger(_make_signal())

        # Price never goes above entry, just drops — trailing stop should NOT trigger
        # (hard stop-loss handles that case)
        trigger.highest_price = 2500.0  # Reset to entry
        exit_signal = manager.check_position("RELIANCE", current_price=2490.0)
        # Should not trigger trailing (highest_price == entry_price)
        # But may trigger stop loss
        if exit_signal:
            assert exit_signal.reason != ExitReason.STRUCTURE_BREAK or "Trailing" not in exit_signal.message


class TestTimeExit:
    def test_time_exit_triggered(self):
        manager = AutoSellManager()
        trigger = manager.create_trigger(_make_signal())

        # Fake the created_at to 100 minutes ago
        trigger.created_at = datetime.utcnow() - timedelta(minutes=100)

        exit_signal = manager.check_position("RELIANCE", current_price=2500.0)
        assert exit_signal is not None
        assert exit_signal.reason == ExitReason.TIME_BASED

    def test_time_exit_not_triggered(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())
        exit_signal = manager.check_position("RELIANCE", current_price=2500.0)
        assert exit_signal is None  # Just created, not expired


class TestStructureBreak:
    def test_structure_break_with_volume(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())

        # Price down >1% with high volume
        exit_signal = manager.check_position(
            "RELIANCE", current_price=2470.0, volume_ratio=2.0
        )
        assert exit_signal is not None
        assert exit_signal.reason == ExitReason.STRUCTURE_BREAK

    def test_no_structure_break_low_volume(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())

        # Price down but volume is normal
        exit_signal = manager.check_position(
            "RELIANCE", current_price=2470.0, volume_ratio=1.0
        )
        # Should not trigger structure break (might trigger stop loss though)
        if exit_signal:
            assert exit_signal.reason != ExitReason.STRUCTURE_BREAK


class TestConfidenceDecay:
    def test_confidence_decay_triggered(self):
        manager = AutoSellManager()
        trigger = manager.create_trigger(_make_signal())

        exit_signal = manager.check_position(
            "RELIANCE", current_price=2500.0, current_confidence=0.3
        )
        assert exit_signal is not None
        assert exit_signal.reason == ExitReason.CONFIDENCE_DECAY

    def test_confidence_decay_not_triggered(self):
        manager = AutoSellManager()
        trigger = manager.create_trigger(_make_signal())

        exit_signal = manager.check_position(
            "RELIANCE", current_price=2500.0, current_confidence=0.7
        )
        assert exit_signal is None


class TestCheckAll:
    def test_check_all_multiple_exits(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal(symbol="RELIANCE"))
        manager.create_trigger(_make_signal(symbol="INFY", entry_price=1500, stop_loss=1470, target_price=1550))

        exits = manager.check_all(
            prices={"RELIANCE": 2440.0, "INFY": 1460.0},  # Both hit stop
        )
        assert len(exits) == 2

    def test_check_all_no_exits(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())
        exits = manager.check_all(prices={"RELIANCE": 2500.0})
        assert len(exits) == 0

    def test_check_all_skips_missing_prices(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())
        exits = manager.check_all(prices={})
        assert len(exits) == 0


class TestStatusSummary:
    def test_summary_format(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())
        summaries = manager.get_status_summary()
        assert len(summaries) == 1
        s = summaries[0]
        assert s["symbol"] == "RELIANCE"
        assert s["stop_loss"] == 2450.0
        assert s["target"] == 2600.0
        assert "time_remaining_min" in s
        assert "exit_strategy" in s

    def test_summary_excludes_inactive(self):
        manager = AutoSellManager()
        manager.create_trigger(_make_signal())
        manager.deactivate("RELIANCE")
        summaries = manager.get_status_summary()
        assert len(summaries) == 0


class TestHelpers:
    def test_pct_diff(self):
        assert _pct_diff(100, 110) == 10.0
        assert _pct_diff(100, 90) == -10.0
        assert _pct_diff(0, 100) == 0.0

    def test_build_exit_strategy(self):
        signal = _make_signal()
        text = _build_exit_strategy(signal, 2600.0, 90, 1.5)
        assert "Target" in text
        assert "Stop Loss" in text
        assert "2600" in text
