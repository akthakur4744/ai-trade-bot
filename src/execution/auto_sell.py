"""Auto-sell manager — monitors positions with AI-defined exit triggers.

When a user enables Auto-Sell on a signal, the system:
1. Creates exit triggers based on AI analysis (stop, target, time, trailing, confidence)
2. Places a GTT OCO order on Zerodha for exchange-level stop loss + target protection
3. Continuously monitors the position against software triggers (trailing, time, confidence)
4. Updates the GTT stop leg as the trailing stop improves
5. Auto-executes the SELL order when any condition is met
6. Cleans up GTT on exit and notifies the user

Dual protection model:
  - ZERODHA (GTT): Hard stop loss + target (survives app crashes)
  - APP (software): Trailing stop, time, confidence, structure break
"""

from __future__ import annotations

import time as time_mod
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import structlog

from src.models import (
    AutoSellTrigger,
    Direction,
    ExitReason,
    ExitSignal,
    GTTResult,
    GTTStatus,
    ScoredSignal,
)

if TYPE_CHECKING:
    from src.config import AutoSellConfig
    from src.execution.broker import Broker
    from src.storage.database import Database

logger = structlog.get_logger(__name__)


class AutoSellManager:
    """Manages auto-sell triggers for positions and monitors exit conditions.

    Dual protection: GTT on Zerodha (exchange-level) + software monitoring (app-level).

    Usage:
        manager = AutoSellManager(broker=broker, config=config, db=db)
        trigger = manager.create_trigger(signal, quantity=10, last_price=2500.0)
        # ... later, in monitoring loop ...
        exit_signal = manager.check_position(symbol, current_price, volume_ratio, confidence)
    """

    def __init__(
        self,
        broker: Broker | None = None,
        config: AutoSellConfig | None = None,
        db: Database | None = None,
    ) -> None:
        self._broker = broker
        self._config = config
        self._db = db
        self._triggers: Dict[str, AutoSellTrigger] = {}  # symbol -> trigger

        if db:
            self._load_from_db()

    def _load_from_db(self) -> None:
        """Restore active auto-sell triggers from database."""
        assert self._db is not None
        trigger_dicts = self._db.load_auto_sell_triggers()
        for t in trigger_dicts:
            trigger = AutoSellTrigger(
                symbol=t["symbol"],
                position_entry_price=t["position_entry_price"],
                position_direction=Direction(t["position_direction"]),
                stop_loss=t["stop_loss"],
                target_price=t["target_price"],
                trailing_stop_pct=t["trailing_stop_pct"],
                max_hold_minutes=t["max_hold_minutes"],
                confidence_floor=t["confidence_floor"],
                structure_break_threshold=t["structure_break_threshold"],
                created_at=t["created_at"],
                highest_price=t["highest_price"],
                lowest_price=t["lowest_price"],
                is_active=t["is_active"],
                exit_strategy=t.get("exit_strategy", ""),
                invalidation_condition=t.get("invalidation_condition", ""),
                gtt_trigger_id=t.get("gtt_trigger_id", ""),
                gtt_status=GTTStatus(t.get("gtt_status", "pending")),
                gtt_stop_price=t.get("gtt_stop_price", 0.0),
                gtt_last_updated=t.get("gtt_last_updated"),
            )
            self._triggers[trigger.symbol] = trigger

        if trigger_dicts:
            logger.info("auto_sell_triggers_loaded", count=len(trigger_dicts))

    @property
    def active_triggers(self) -> Dict[str, AutoSellTrigger]:
        """Return all active auto-sell triggers."""
        return {s: t for s, t in self._triggers.items() if t.is_active}

    def has_trigger(self, symbol: str) -> bool:
        """Check if a symbol has an active auto-sell trigger."""
        return symbol in self._triggers and self._triggers[symbol].is_active

    def get_trigger(self, symbol: str) -> Optional[AutoSellTrigger]:
        return self._triggers.get(symbol)

    def create_trigger(
        self,
        signal: ScoredSignal,
        quantity: int = 0,
        last_price: float = 0.0,
    ) -> AutoSellTrigger:
        """Create auto-sell trigger from a scored signal.

        Uses the signal's price levels, confidence, and AI analysis
        to define smart exit conditions. If GTT is enabled and a broker
        is available, also places a GTT OCO order on Zerodha.

        Args:
            signal: The scored signal that was approved.
            quantity: Fill quantity (needed for GTT order placement).
            last_price: Current LTP (needed for GTT order placement).
        """
        # Calculate trailing stop based on volatility/confidence
        # Higher confidence = tighter trailing stop (protect gains)
        # Lower confidence = wider trailing stop (give room)
        trailing_pct = max(0.8, 2.5 - (signal.confidence * 1.5))

        # Max hold time scales with time horizon
        horizon_map = {"intraday": 90, "swing": 480, "positional": 1440}
        max_hold = horizon_map.get(signal.time_horizon, 90)

        # Target price — if not set, calculate from entry + risk/reward
        target = signal.target_price
        if not target or target <= 0:
            risk = abs(signal.entry_price - signal.stop_loss)
            if signal.direction == Direction.BUY:
                target = signal.entry_price + (risk * 2.0)  # 2:1 reward/risk
            else:
                target = signal.entry_price - (risk * 2.0)

        # Confidence floor — higher base confidence = lower floor acceptable
        conf_floor = max(0.4, signal.confidence - 0.25)

        # Build exit strategy description
        exit_strategy = _build_exit_strategy(signal, target, max_hold, trailing_pct)
        invalidation = _build_invalidation(signal)

        trigger = AutoSellTrigger(
            symbol=signal.symbol,
            position_entry_price=signal.entry_price,
            position_direction=signal.direction,
            stop_loss=signal.stop_loss,
            target_price=target,
            trailing_stop_pct=trailing_pct,
            max_hold_minutes=max_hold,
            confidence_floor=conf_floor,
            structure_break_threshold=-1.0,
            highest_price=signal.entry_price,
            lowest_price=signal.entry_price,
            exit_strategy=exit_strategy,
            invalidation_condition=invalidation,
        )

        # Place GTT OCO on Zerodha for exchange-level protection
        if self._should_place_gtt() and quantity > 0:
            gtt_result = self._place_gtt_with_retry(
                trigger, quantity, last_price or signal.entry_price
            )
            if gtt_result.success:
                trigger.gtt_trigger_id = gtt_result.trigger_id
                trigger.gtt_status = GTTStatus.ACTIVE
                trigger.gtt_stop_price = signal.stop_loss
                trigger.gtt_last_updated = datetime.utcnow()
            else:
                logger.warning(
                    "gtt_placement_failed_software_only",
                    symbol=signal.symbol,
                    error=gtt_result.message,
                )
                trigger.gtt_status = GTTStatus.REJECTED

        self._triggers[signal.symbol] = trigger

        if self._db:
            self._db.save_auto_sell_trigger(trigger)

        logger.info(
            "auto_sell_trigger_created",
            symbol=signal.symbol,
            stop=trigger.stop_loss,
            target=trigger.target_price,
            trailing_pct=trigger.trailing_stop_pct,
            max_hold_min=trigger.max_hold_minutes,
            conf_floor=trigger.confidence_floor,
            gtt_id=trigger.gtt_trigger_id or "none",
            gtt_status=trigger.gtt_status.value,
        )

        return trigger

    def check_position(
        self,
        symbol: str,
        current_price: float,
        volume_ratio: float = 1.0,
        current_confidence: Optional[float] = None,
    ) -> Optional[ExitSignal]:
        """Check a position against its auto-sell triggers.

        Returns ExitSignal if any condition is met, None otherwise.
        """
        trigger = self._triggers.get(symbol)
        if not trigger or not trigger.is_active:
            return None

        # Update price tracking for trailing stop
        if trigger.position_direction == Direction.BUY:
            trigger.highest_price = max(trigger.highest_price, current_price)
        else:
            trigger.lowest_price = min(trigger.lowest_price, current_price)

        # Check conditions in priority order

        # 1. Hard stop loss
        exit_signal = self._check_stop_loss(trigger, current_price)
        if exit_signal:
            return exit_signal

        # 2. Target hit
        exit_signal = self._check_target(trigger, current_price)
        if exit_signal:
            return exit_signal

        # 3. Trailing stop
        exit_signal = self._check_trailing_stop(trigger, current_price)
        if exit_signal:
            return exit_signal

        # 4. Time-based exit
        exit_signal = self._check_time_exit(trigger)
        if exit_signal:
            return exit_signal

        # 5. Structure break (reversal with volume)
        if volume_ratio > 1.5:
            exit_signal = self._check_structure_break(trigger, current_price, volume_ratio)
            if exit_signal:
                return exit_signal

        # 6. Confidence decay
        if current_confidence is not None:
            exit_signal = self._check_confidence_decay(trigger, current_confidence)
            if exit_signal:
                return exit_signal

        return None

    def check_all(
        self,
        prices: Dict[str, float],
        volume_ratios: Optional[Dict[str, float]] = None,
        confidences: Optional[Dict[str, float]] = None,
    ) -> List[ExitSignal]:
        """Check all active triggers against current market data.

        Returns list of exit signals for positions that should be closed.
        """
        volume_ratios = volume_ratios or {}
        confidences = confidences or {}
        exits = []

        for symbol, trigger in list(self._triggers.items()):
            if not trigger.is_active:
                continue

            price = prices.get(symbol)
            if price is None:
                continue

            signal = self.check_position(
                symbol=symbol,
                current_price=price,
                volume_ratio=volume_ratios.get(symbol, 1.0),
                current_confidence=confidences.get(symbol),
            )
            if signal:
                exits.append(signal)

        # Batch-persist price tracking updates at end of cycle
        if self._db:
            for symbol, trigger in self._triggers.items():
                if trigger.is_active:
                    self._db.update_auto_sell_trigger_prices(
                        symbol, trigger.highest_price, trigger.lowest_price, trigger.is_active
                    )

        return exits

    def deactivate(self, symbol: str) -> None:
        """Deactivate auto-sell trigger and cancel any exchange-level GTT."""
        trigger = self._triggers.get(symbol)
        if not trigger:
            return

        trigger.is_active = False

        # Cancel GTT on Zerodha if active
        if trigger.gtt_trigger_id and trigger.gtt_status == GTTStatus.ACTIVE:
            self._delete_gtt_safe(trigger)

        if self._db:
            self._db.update_auto_sell_trigger_prices(
                symbol, trigger.highest_price, trigger.lowest_price, False
            )
        logger.info("auto_sell_deactivated", symbol=symbol)

    def remove(self, symbol: str) -> None:
        """Remove auto-sell trigger completely (deactivate + delete from DB)."""
        trigger = self._triggers.get(symbol)
        if trigger and trigger.gtt_trigger_id and trigger.gtt_status == GTTStatus.ACTIVE:
            self._delete_gtt_safe(trigger)
        self._triggers.pop(symbol, None)
        if self._db:
            self._db.remove_auto_sell_trigger(symbol)

    def get_status_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all active triggers for dashboard display."""
        summaries = []
        for symbol, trigger in self._triggers.items():
            if not trigger.is_active:
                continue

            elapsed = datetime.utcnow() - trigger.created_at
            remaining_min = max(0, trigger.max_hold_minutes - int(elapsed.total_seconds() / 60))

            summaries.append({
                "symbol": symbol,
                "direction": trigger.position_direction.value,
                "entry": trigger.position_entry_price,
                "stop_loss": trigger.stop_loss,
                "target": trigger.target_price,
                "trailing_pct": trigger.trailing_stop_pct,
                "time_remaining_min": remaining_min,
                "confidence_floor": trigger.confidence_floor,
                "highest_price": trigger.highest_price,
                "lowest_price": trigger.lowest_price,
                "exit_strategy": trigger.exit_strategy,
                "invalidation": trigger.invalidation_condition,
                "gtt_status": trigger.gtt_status.value,
                "gtt_trigger_id": trigger.gtt_trigger_id,
                "gtt_stop_price": trigger.gtt_stop_price,
            })
        return summaries

    # ---- GTT management ----

    def _should_place_gtt(self) -> bool:
        """Check if GTT should be placed (broker available + config enabled)."""
        if not self._broker:
            return False
        if self._config and not self._config.gtt_enabled:
            return False
        return True

    def _place_gtt_with_retry(
        self,
        trigger: AutoSellTrigger,
        quantity: int,
        last_price: float,
    ) -> GTTResult:
        """Place GTT OCO with retry logic."""
        assert self._broker is not None
        max_retries = self._config.gtt_max_retries if self._config else 3

        for attempt in range(max_retries):
            result = self._broker.place_gtt_oco(
                symbol=trigger.symbol,
                exchange="NSE",
                direction=trigger.position_direction.value,
                quantity=quantity,
                last_price=last_price,
                stop_loss=trigger.stop_loss,
                target=trigger.target_price,
            )
            if result.success:
                return result

            logger.warning(
                "gtt_placement_retry",
                symbol=trigger.symbol,
                attempt=attempt + 1,
                error=result.message,
            )
            if attempt < max_retries - 1:
                time_mod.sleep(2 ** attempt)  # Exponential backoff

        return GTTResult(
            success=False,
            message=f"GTT placement failed after {max_retries} retries",
        )

    def update_gtt_trailing_stop(
        self,
        symbol: str,
        new_stop: float,
        quantity: int,
        last_price: float,
    ) -> bool:
        """Update the GTT stop leg if trailing stop has improved meaningfully.

        Only updates if:
          1. New stop is better by >= gtt_update_threshold_pct
          2. Enough time has passed since last update (cooldown)

        Returns True if GTT was updated.
        """
        trigger = self._triggers.get(symbol)
        if not trigger or not trigger.is_active:
            return False
        if not trigger.gtt_trigger_id or trigger.gtt_status != GTTStatus.ACTIVE:
            return False
        if not self._broker:
            return False

        # Check threshold: only update if meaningful improvement
        threshold_pct = self._config.gtt_update_threshold_pct if self._config else 0.5
        if trigger.gtt_stop_price > 0:
            improvement_pct = abs(new_stop - trigger.gtt_stop_price) / trigger.gtt_stop_price * 100
            if improvement_pct < threshold_pct:
                return False

        # Check cooldown
        cooldown_sec = self._config.gtt_update_cooldown_sec if self._config else 60
        if trigger.gtt_last_updated:
            elapsed = (datetime.utcnow() - trigger.gtt_last_updated).total_seconds()
            if elapsed < cooldown_sec:
                return False

        # Update GTT via broker
        trigger.gtt_status = GTTStatus.UPDATING
        result = self._broker.modify_gtt(
            trigger_id=trigger.gtt_trigger_id,
            symbol=symbol,
            exchange="NSE",
            direction=trigger.position_direction.value,
            quantity=quantity,
            last_price=last_price,
            stop_loss=new_stop,
            target=trigger.target_price,
        )

        if result.success:
            trigger.gtt_trigger_id = result.trigger_id
            trigger.gtt_status = GTTStatus.ACTIVE
            trigger.gtt_stop_price = new_stop
            trigger.gtt_last_updated = datetime.utcnow()
            if self._db:
                self._db.save_auto_sell_trigger(trigger)
            logger.info(
                "gtt_trailing_updated",
                symbol=symbol,
                new_stop=new_stop,
                old_stop=trigger.gtt_stop_price,
            )
            return True
        else:
            # Restore to active — old GTT may still be valid
            trigger.gtt_status = GTTStatus.ACTIVE
            logger.error(
                "gtt_trailing_update_failed",
                symbol=symbol,
                error=result.message,
            )
            return False

    def check_gtt_status(self, symbol: str) -> Optional[ExitSignal]:
        """Poll Zerodha for GTT status changes (triggered, rejected, expired).

        Returns ExitSignal if GTT was triggered by the exchange.
        """
        trigger = self._triggers.get(symbol)
        if not trigger or not trigger.is_active or not trigger.gtt_trigger_id:
            return None
        if not self._broker:
            return None

        status = self._broker.get_gtt_status(trigger.gtt_trigger_id)
        gtt_status = status.get("status", "unknown")

        if gtt_status == "triggered":
            trigger.gtt_status = GTTStatus.TRIGGERED
            # Determine which leg triggered (stop or target)
            orders = status.get("orders", [])
            reason = ExitReason.GTT_STOP_LOSS
            message = "GTT stop loss triggered by exchange"
            if orders:
                # First order with status=complete is the triggered leg
                for order in orders:
                    if order.get("result", {}).get("status") == "complete":
                        price = order.get("result", {}).get("average_price", 0)
                        if price >= trigger.target_price:
                            reason = ExitReason.GTT_TARGET
                            message = f"GTT target triggered at {price:.2f}"
                        else:
                            message = f"GTT stop loss triggered at {price:.2f}"
                        break

            return ExitSignal(
                symbol=symbol,
                reason=reason,
                urgency="HIGH",
                message=message,
            )

        elif gtt_status in ("rejected", "expired", "cancelled", "deleted"):
            trigger.gtt_status = GTTStatus(gtt_status)
            logger.warning(
                "gtt_no_longer_active",
                symbol=symbol,
                status=gtt_status,
            )
            # GTT is gone — software monitor continues as sole protection

        return None

    def reconcile_on_startup(self) -> List[str]:
        """Reconcile GTT state on app restart.

        Returns list of symbols with missing GTT protection (need re-placement).
        """
        unprotected = []
        for symbol, trigger in self._triggers.items():
            if not trigger.is_active:
                continue
            if not trigger.gtt_trigger_id:
                unprotected.append(symbol)
                continue
            if not self._broker:
                continue

            # Check if GTT is still active on exchange
            status = self._broker.get_gtt_status(trigger.gtt_trigger_id)
            gtt_status = status.get("status", "unknown")

            if gtt_status == "active":
                trigger.gtt_status = GTTStatus.ACTIVE
            elif gtt_status == "triggered":
                trigger.gtt_status = GTTStatus.TRIGGERED
                logger.info("gtt_triggered_during_downtime", symbol=symbol)
            else:
                # GTT expired/cancelled/rejected during downtime — unprotected
                trigger.gtt_status = GTTStatus(gtt_status) if gtt_status in GTTStatus.__members__.values() else GTTStatus.EXPIRED
                trigger.gtt_trigger_id = ""
                unprotected.append(symbol)
                logger.warning(
                    "gtt_lost_during_downtime",
                    symbol=symbol,
                    status=gtt_status,
                )

        return unprotected

    def _delete_gtt_safe(self, trigger: AutoSellTrigger) -> None:
        """Delete GTT from Zerodha, logging but not raising on failure."""
        if not self._broker or not trigger.gtt_trigger_id:
            return
        try:
            self._broker.delete_gtt(trigger.gtt_trigger_id)
            trigger.gtt_status = GTTStatus.CANCELLED
            logger.info("gtt_cancelled", symbol=trigger.symbol, trigger_id=trigger.gtt_trigger_id)
        except Exception as e:
            logger.error("gtt_cancel_failed", symbol=trigger.symbol, error=str(e))

    # ---- Private exit checks ----

    def _check_stop_loss(
        self, trigger: AutoSellTrigger, current_price: float
    ) -> Optional[ExitSignal]:
        if trigger.position_direction == Direction.BUY:
            if current_price <= trigger.stop_loss:
                self._deactivate_trigger(trigger)
                return ExitSignal(
                    symbol=trigger.symbol,
                    reason=ExitReason.STOP_LOSS,
                    urgency="HIGH",
                    message=(
                        f"Auto-Sell: Stop loss hit at {current_price:.2f} "
                        f"(stop: {trigger.stop_loss:.2f})"
                    ),
                )
        else:
            if current_price >= trigger.stop_loss:
                self._deactivate_trigger(trigger)
                return ExitSignal(
                    symbol=trigger.symbol,
                    reason=ExitReason.STOP_LOSS,
                    urgency="HIGH",
                    message=(
                        f"Auto-Sell: Stop loss hit at {current_price:.2f} "
                        f"(stop: {trigger.stop_loss:.2f})"
                    ),
                )
        return None

    def _check_target(
        self, trigger: AutoSellTrigger, current_price: float
    ) -> Optional[ExitSignal]:
        if trigger.position_direction == Direction.BUY:
            if current_price >= trigger.target_price:
                self._deactivate_trigger(trigger)
                return ExitSignal(
                    symbol=trigger.symbol,
                    reason=ExitReason.TARGET,
                    urgency="LOW",
                    message=(
                        f"Auto-Sell: Target reached at {current_price:.2f} "
                        f"(target: {trigger.target_price:.2f})"
                    ),
                )
        else:
            if current_price <= trigger.target_price:
                self._deactivate_trigger(trigger)
                return ExitSignal(
                    symbol=trigger.symbol,
                    reason=ExitReason.TARGET,
                    urgency="LOW",
                    message=(
                        f"Auto-Sell: Target reached at {current_price:.2f} "
                        f"(target: {trigger.target_price:.2f})"
                    ),
                )
        return None

    def _check_trailing_stop(
        self, trigger: AutoSellTrigger, current_price: float
    ) -> Optional[ExitSignal]:
        """Check trailing stop — protects gains by moving stop up with price."""
        if trigger.position_direction == Direction.BUY:
            trailing_stop = trigger.highest_price * (1 - trigger.trailing_stop_pct / 100)
            # Only trigger if we've moved above entry (protecting gains, not cutting losses early)
            if current_price <= trailing_stop and trigger.highest_price > trigger.position_entry_price:
                self._deactivate_trigger(trigger)
                gain_from_peak = (trigger.highest_price - current_price) / trigger.highest_price * 100
                return ExitSignal(
                    symbol=trigger.symbol,
                    reason=ExitReason.STRUCTURE_BREAK,
                    urgency="MEDIUM",
                    message=(
                        f"Auto-Sell: Trailing stop hit. Price dropped {gain_from_peak:.1f}% from "
                        f"peak {trigger.highest_price:.2f} to {current_price:.2f}"
                    ),
                )
        else:
            trailing_stop = trigger.lowest_price * (1 + trigger.trailing_stop_pct / 100)
            if current_price >= trailing_stop and trigger.lowest_price < trigger.position_entry_price:
                self._deactivate_trigger(trigger)
                drop_from_low = (current_price - trigger.lowest_price) / trigger.lowest_price * 100
                return ExitSignal(
                    symbol=trigger.symbol,
                    reason=ExitReason.STRUCTURE_BREAK,
                    urgency="MEDIUM",
                    message=(
                        f"Auto-Sell: Trailing stop hit. Price rose {drop_from_low:.1f}% from "
                        f"low {trigger.lowest_price:.2f} to {current_price:.2f}"
                    ),
                )
        return None

    def _check_time_exit(self, trigger: AutoSellTrigger) -> Optional[ExitSignal]:
        elapsed = datetime.utcnow() - trigger.created_at
        elapsed_min = int(elapsed.total_seconds() / 60)

        if elapsed_min >= trigger.max_hold_minutes:
            self._deactivate_trigger(trigger)
            return ExitSignal(
                symbol=trigger.symbol,
                reason=ExitReason.TIME_BASED,
                urgency="MEDIUM",
                message=(
                    f"Auto-Sell: Holding window expired ({elapsed_min} min, "
                    f"max: {trigger.max_hold_minutes} min)"
                ),
            )
        return None

    def _check_structure_break(
        self, trigger: AutoSellTrigger, current_price: float, volume_ratio: float
    ) -> Optional[ExitSignal]:
        if trigger.position_direction == Direction.BUY:
            pnl_pct = (current_price - trigger.position_entry_price) / trigger.position_entry_price * 100
        else:
            pnl_pct = (trigger.position_entry_price - current_price) / trigger.position_entry_price * 100

        if pnl_pct < trigger.structure_break_threshold:
            self._deactivate_trigger(trigger)
            return ExitSignal(
                symbol=trigger.symbol,
                reason=ExitReason.STRUCTURE_BREAK,
                urgency="HIGH",
                message=(
                    f"Auto-Sell: Price reversal with {volume_ratio:.1f}x volume, "
                    f"PnL: {pnl_pct:+.1f}%"
                ),
            )
        return None

    def _check_confidence_decay(
        self, trigger: AutoSellTrigger, current_confidence: float
    ) -> Optional[ExitSignal]:
        if current_confidence < trigger.confidence_floor:
            self._deactivate_trigger(trigger)
            return ExitSignal(
                symbol=trigger.symbol,
                reason=ExitReason.CONFIDENCE_DECAY,
                urgency="MEDIUM",
                message=(
                    f"Auto-Sell: Confidence decayed to {current_confidence:.2f} "
                    f"(floor: {trigger.confidence_floor:.2f})"
                ),
            )
        return None

    def _deactivate_trigger(self, trigger: AutoSellTrigger) -> None:
        trigger.is_active = False
        if self._db:
            self._db.update_auto_sell_trigger_prices(
                trigger.symbol, trigger.highest_price, trigger.lowest_price, False
            )


# ---- Helper functions ----


def _build_exit_strategy(
    signal: ScoredSignal, target: float, max_hold: int, trailing_pct: float
) -> str:
    """Build human-readable exit strategy description."""
    direction = "sell" if signal.direction == Direction.BUY else "cover"
    parts = [
        f"Auto-{direction} when:",
        f"  - Target: {target:.2f} ({_pct_diff(signal.entry_price, target):+.1f}%)",
        f"  - Stop Loss: {signal.stop_loss:.2f} ({_pct_diff(signal.entry_price, signal.stop_loss):+.1f}%)",
        f"  - Trailing Stop: {trailing_pct:.1f}% from peak",
        f"  - Max Hold: {max_hold} minutes",
        f"  - Confidence drops below {max(0.4, signal.confidence - 0.25):.2f}",
    ]
    return "\n".join(parts)


def _build_invalidation(signal: ScoredSignal) -> str:
    """Build invalidation condition from signal risks."""
    if signal.risks:
        return f"Thesis invalid if: {'; '.join(signal.risks[:2])}"
    if signal.direction == Direction.BUY:
        return f"Thesis invalid if price sustains below {signal.stop_loss:.2f}"
    return f"Thesis invalid if price sustains above {signal.stop_loss:.2f}"


def _pct_diff(base: float, target: float) -> float:
    """Calculate percentage difference."""
    if base == 0:
        return 0.0
    return (target - base) / base * 100
