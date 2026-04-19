"""Auto-exit monitor — watches open positions for exit triggers.

Three exit types:
1. Time-based: holding window expired
2. Structure-based: price reversal with volume confirmation
3. Confidence-decay: re-scored confidence dropped below threshold
Also: stop-loss and target hit detection.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import structlog

from src.models import Direction, ExitReason, ExitSignal, Position

logger = structlog.get_logger(__name__)


class AutoExitMonitor:
    """Monitors open positions and emits exit signals when conditions are met."""

    def __init__(
        self,
        max_hold_minutes: int = 90,
        stop_loss_enabled: bool = True,
        target_enabled: bool = True,
        confidence_threshold: float = 0.5,
    ) -> None:
        self._max_hold_minutes = max_hold_minutes
        self._stop_loss_enabled = stop_loss_enabled
        self._target_enabled = target_enabled
        self._confidence_threshold = confidence_threshold

    def check_position(
        self,
        position: Position,
        current_price: float,
        current_confidence: float | None = None,
        volume_ratio: float | None = None,
    ) -> ExitSignal | None:
        """Check a single position against all exit conditions.

        Args:
            position: The open position to check.
            current_price: Current market price.
            current_confidence: Re-scored confidence (if available).
            volume_ratio: Current volume / average volume.

        Returns:
            ExitSignal if any exit condition is met, None otherwise.
        """
        # 1. Stop-loss hit
        if self._stop_loss_enabled:
            signal = self._check_stop_loss(position, current_price)
            if signal:
                return signal

        # 2. Target hit
        if self._target_enabled:
            signal = self._check_target(position, current_price)
            if signal:
                return signal

        # 3. Time-based exit
        signal = self._check_time_exit(position)
        if signal:
            return signal

        # 4. Structure break (reversal + volume)
        if volume_ratio is not None:
            signal = self._check_structure_break(position, current_price, volume_ratio)
            if signal:
                return signal

        # 5. Confidence decay
        if current_confidence is not None:
            signal = self._check_confidence_decay(position, current_confidence)
            if signal:
                return signal

        return None

    def check_all_positions(
        self,
        positions: dict[str, Position],
        prices: dict[str, float],
        confidences: dict[str, float] | None = None,
        volume_ratios: dict[str, float] | None = None,
    ) -> list[ExitSignal]:
        """Check all open positions for exit conditions.

        Returns:
            List of exit signals for positions that should be closed.
        """
        confidences = confidences or {}
        volume_ratios = volume_ratios or {}
        signals = []

        for symbol, position in positions.items():
            current_price = prices.get(symbol)
            if current_price is None:
                continue

            signal = self.check_position(
                position=position,
                current_price=current_price,
                current_confidence=confidences.get(symbol),
                volume_ratio=volume_ratios.get(symbol),
            )
            if signal:
                signals.append(signal)

        return signals

    def _check_stop_loss(self, position: Position, current_price: float) -> ExitSignal | None:
        if position.stop_loss <= 0:
            return None

        triggered = (
            (position.direction == Direction.BUY and current_price <= position.stop_loss)
            or (position.direction == Direction.SELL and current_price >= position.stop_loss)
        )

        if triggered:
            logger.warning(
                "stop_loss_hit",
                symbol=position.symbol,
                stop_loss=position.stop_loss,
                current_price=current_price,
            )
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.STOP_LOSS,
                urgency="HIGH",
                message=f"Stop loss hit at {current_price} (stop: {position.stop_loss})",
            )
        return None

    def _check_target(self, position: Position, current_price: float) -> ExitSignal | None:
        if not position.target_price or position.target_price <= 0:
            return None

        triggered = (
            (position.direction == Direction.BUY and current_price >= position.target_price)
            or (position.direction == Direction.SELL and current_price <= position.target_price)
        )

        if triggered:
            logger.info(
                "target_hit",
                symbol=position.symbol,
                target=position.target_price,
                current_price=current_price,
            )
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.TARGET,
                urgency="MEDIUM",
                message=f"Target hit at {current_price} (target: {position.target_price})",
            )
        return None

    def _check_time_exit(self, position: Position) -> ExitSignal | None:
        elapsed = datetime.utcnow() - position.entry_time
        if elapsed > timedelta(minutes=self._max_hold_minutes):
            logger.info(
                "time_exit",
                symbol=position.symbol,
                held_minutes=int(elapsed.total_seconds() / 60),
                max_minutes=self._max_hold_minutes,
            )
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.TIME_BASED,
                urgency="MEDIUM",
                message=f"Holding window expired ({int(elapsed.total_seconds() / 60)} min)",
            )
        return None

    def _check_structure_break(
        self, position: Position, current_price: float, volume_ratio: float
    ) -> ExitSignal | None:
        """Detect price reversal with above-average volume."""
        if volume_ratio < 1.5:
            return None

        if position.direction == Direction.BUY:
            # Price dropped below entry with high volume = structure break
            pnl_pct = (current_price - position.entry_price) / position.entry_price
            if pnl_pct < -0.01:  # >1% loss with high volume
                return ExitSignal(
                    symbol=position.symbol,
                    reason=ExitReason.STRUCTURE_BREAK,
                    urgency="HIGH",
                    message=f"Reversal with volume ({volume_ratio:.1f}x avg), PnL: {pnl_pct:.1%}",
                )
        else:
            pnl_pct = (position.entry_price - current_price) / position.entry_price
            if pnl_pct < -0.01:
                return ExitSignal(
                    symbol=position.symbol,
                    reason=ExitReason.STRUCTURE_BREAK,
                    urgency="HIGH",
                    message=f"Reversal with volume ({volume_ratio:.1f}x avg), PnL: {pnl_pct:.1%}",
                )
        return None

    def _check_confidence_decay(
        self, position: Position, current_confidence: float
    ) -> ExitSignal | None:
        if current_confidence < self._confidence_threshold:
            return ExitSignal(
                symbol=position.symbol,
                reason=ExitReason.CONFIDENCE_DECAY,
                urgency="MEDIUM",
                message=f"Confidence decayed to {current_confidence:.2f} (threshold: {self._confidence_threshold})",
            )
        return None
