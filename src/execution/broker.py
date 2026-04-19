"""Abstract broker interface — implemented by PaperBroker and LiveBroker."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import GTTResult, Order, OrderResult, Position


class Broker(ABC):
    """Base class for order execution.

    Paper and live brokers implement the same interface so the rest
    of the system is mode-agnostic.
    """

    @abstractmethod
    def place_order(self, order: Order) -> OrderResult:
        """Place an order and return the fill result."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Get all open positions from the broker."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order. Returns True if successful."""

    @abstractmethod
    def get_order_status(self, order_id: str) -> dict:
        """Get current status of an order."""

    # ---- GTT (Good Till Triggered) ----

    @abstractmethod
    def place_gtt_oco(
        self,
        symbol: str,
        exchange: str,
        direction: str,
        quantity: int,
        last_price: float,
        stop_loss: float,
        target: float,
        product: str = "MIS",
    ) -> GTTResult:
        """Place a GTT OCO (One Cancels Other) order with stop loss + target.

        For a BUY position, this places a SELL GTT:
          - Leg 1 (stop): triggers if price drops to stop_loss
          - Leg 2 (target): triggers if price rises to target

        Returns GTTResult with trigger_id on success.
        """

    @abstractmethod
    def modify_gtt(
        self,
        trigger_id: str,
        symbol: str,
        exchange: str,
        direction: str,
        quantity: int,
        last_price: float,
        stop_loss: float,
        target: float,
        product: str = "MIS",
    ) -> GTTResult:
        """Modify an existing GTT order (e.g. to update trailing stop)."""

    @abstractmethod
    def delete_gtt(self, trigger_id: str) -> bool:
        """Cancel/delete a GTT order. Returns True if successful."""

    @abstractmethod
    def get_gtt_status(self, trigger_id: str) -> dict:
        """Get current status of a GTT order.

        Returns dict with at least: {"status": str, "trigger_id": str}
        Status values: active, triggered, cancelled, rejected, expired, deleted
        """
