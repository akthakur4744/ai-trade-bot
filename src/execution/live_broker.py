"""Live broker — real order execution via Zerodha Kite Connect API."""

from __future__ import annotations

from datetime import datetime

import structlog
from kiteconnect import KiteConnect

from src.execution.broker import Broker
from src.models import Direction, GTTResult, Order, OrderResult, Position

logger = structlog.get_logger(__name__)


class LiveBroker(Broker):
    """Executes real orders via Kite Connect.

    This broker calls actual Kite APIs — only use after thorough
    paper trading validation.
    """

    def __init__(self, kite: KiteConnect) -> None:
        self._kite = kite

    def place_order(self, order: Order) -> OrderResult:
        """Place a real order via Kite Connect."""
        try:
            transaction_type = (
                self._kite.TRANSACTION_TYPE_BUY
                if order.direction == Direction.BUY
                else self._kite.TRANSACTION_TYPE_SELL
            )

            order_id = self._kite.place_order(
                variety=self._kite.VARIETY_REGULAR,
                exchange=order.exchange,
                tradingsymbol=order.symbol,
                transaction_type=transaction_type,
                quantity=order.quantity,
                order_type=self._kite.ORDER_TYPE_MARKET
                if order.order_type == "MARKET"
                else self._kite.ORDER_TYPE_LIMIT,
                product=self._kite.PRODUCT_MIS
                if order.product == "MIS"
                else self._kite.PRODUCT_CNC,
                price=order.price if order.order_type == "LIMIT" else None,
            )

            logger.info(
                "live_order_placed",
                order_id=order_id,
                symbol=order.symbol,
                direction=order.direction,
                quantity=order.quantity,
            )

            # Fetch fill details
            order_history = self._kite.order_history(order_id)
            last_update = order_history[-1] if order_history else {}

            fill_price = last_update.get("average_price", order.price)
            fill_qty = last_update.get("filled_quantity", 0)
            status = last_update.get("status", "UNKNOWN")

            return OrderResult(
                success=status in ("COMPLETE", "TRADED"),
                order_id=str(order_id),
                fill_price=fill_price,
                fill_quantity=fill_qty,
                message=f"Kite order {order_id}: {status}",
                timestamp=datetime.utcnow(),
            )

        except Exception as e:
            logger.error("live_order_failed", symbol=order.symbol, error=str(e))
            return OrderResult(
                success=False,
                message=f"Order failed: {e}",
            )

    def get_positions(self) -> list[Position]:
        """Fetch open positions from Kite."""
        try:
            positions = self._kite.positions()
            result = []
            for pos in positions.get("net", []):
                if pos["quantity"] != 0:
                    result.append(
                        Position(
                            symbol=pos["tradingsymbol"],
                            exchange=pos["exchange"],
                            direction=Direction.BUY if pos["quantity"] > 0 else Direction.SELL,
                            quantity=abs(pos["quantity"]),
                            entry_price=pos["average_price"],
                            current_price=pos["last_price"],
                            unrealized_pnl=pos["pnl"],
                            capital_deployed=abs(pos["quantity"]) * pos["average_price"],
                        )
                    )
            return result
        except Exception as e:
            logger.error("live_positions_error", error=str(e))
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order via Kite."""
        try:
            self._kite.cancel_order(
                variety=self._kite.VARIETY_REGULAR,
                order_id=order_id,
            )
            logger.info("live_order_cancelled", order_id=order_id)
            return True
        except Exception as e:
            logger.error("live_cancel_failed", order_id=order_id, error=str(e))
            return False

    def get_order_status(self, order_id: str) -> dict:
        """Get order status from Kite."""
        try:
            history = self._kite.order_history(order_id)
            if history:
                last = history[-1]
                return {
                    "order_id": order_id,
                    "status": last.get("status"),
                    "fill_price": last.get("average_price"),
                    "filled_quantity": last.get("filled_quantity"),
                }
        except Exception as e:
            logger.error("live_status_error", order_id=order_id, error=str(e))
        return {"order_id": order_id, "status": "ERROR"}

    # ---- GTT (Good Till Triggered) ----

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
        """Place a GTT OCO order on Zerodha.

        For a BUY position: sell at stop_loss (LIMIT at stop_loss) or target (LIMIT at target).
        trigger_values = [stop_loss, target] for BUY position exit.
        """
        try:
            # Exit direction is opposite of position direction
            exit_type = (
                self._kite.TRANSACTION_TYPE_SELL
                if direction == "BUY"
                else self._kite.TRANSACTION_TYPE_BUY
            )
            kite_product = (
                self._kite.PRODUCT_MIS if product == "MIS" else self._kite.PRODUCT_CNC
            )

            # OCO: two trigger values, two orders
            # For BUY position: trigger[0]=stop (below), trigger[1]=target (above)
            # For SELL position: trigger[0]=target (below), trigger[1]=stop (above)
            if direction == "BUY":
                trigger_values = [stop_loss, target]
            else:
                trigger_values = [target, stop_loss]

            orders = [
                {
                    "transaction_type": exit_type,
                    "quantity": quantity,
                    "order_type": self._kite.ORDER_TYPE_LIMIT,
                    "product": kite_product,
                    "price": trigger_values[0],
                },
                {
                    "transaction_type": exit_type,
                    "quantity": quantity,
                    "order_type": self._kite.ORDER_TYPE_LIMIT,
                    "product": kite_product,
                    "price": trigger_values[1],
                },
            ]

            trigger_id = self._kite.place_gtt(
                trigger_type=self._kite.GTT_TYPE_OCO,
                tradingsymbol=symbol,
                exchange=exchange,
                trigger_values=trigger_values,
                last_price=last_price,
                orders=orders,
            )

            logger.info(
                "gtt_oco_placed",
                trigger_id=trigger_id,
                symbol=symbol,
                stop_loss=stop_loss,
                target=target,
                quantity=quantity,
            )
            return GTTResult(
                success=True,
                trigger_id=str(trigger_id),
                message=f"GTT OCO placed: SL={stop_loss}, Target={target}",
            )

        except Exception as e:
            logger.error("gtt_place_failed", symbol=symbol, error=str(e))
            return GTTResult(success=False, message=f"GTT placement failed: {e}")

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
        """Modify an existing GTT order on Zerodha."""
        try:
            exit_type = (
                self._kite.TRANSACTION_TYPE_SELL
                if direction == "BUY"
                else self._kite.TRANSACTION_TYPE_BUY
            )
            kite_product = (
                self._kite.PRODUCT_MIS if product == "MIS" else self._kite.PRODUCT_CNC
            )

            if direction == "BUY":
                trigger_values = [stop_loss, target]
            else:
                trigger_values = [target, stop_loss]

            orders = [
                {
                    "transaction_type": exit_type,
                    "quantity": quantity,
                    "order_type": self._kite.ORDER_TYPE_LIMIT,
                    "product": kite_product,
                    "price": trigger_values[0],
                },
                {
                    "transaction_type": exit_type,
                    "quantity": quantity,
                    "order_type": self._kite.ORDER_TYPE_LIMIT,
                    "product": kite_product,
                    "price": trigger_values[1],
                },
            ]

            new_trigger_id = self._kite.modify_gtt(
                trigger_id=trigger_id,
                trigger_type=self._kite.GTT_TYPE_OCO,
                tradingsymbol=symbol,
                exchange=exchange,
                trigger_values=trigger_values,
                last_price=last_price,
                orders=orders,
            )

            logger.info(
                "gtt_modified",
                old_trigger_id=trigger_id,
                new_trigger_id=new_trigger_id,
                symbol=symbol,
                stop_loss=stop_loss,
            )
            return GTTResult(
                success=True,
                trigger_id=str(new_trigger_id),
                message=f"GTT modified: new SL={stop_loss}",
            )

        except Exception as e:
            logger.error(
                "gtt_modify_failed",
                trigger_id=trigger_id,
                symbol=symbol,
                error=str(e),
            )
            return GTTResult(success=False, message=f"GTT modify failed: {e}")

    def delete_gtt(self, trigger_id: str) -> bool:
        """Delete/cancel a GTT order on Zerodha."""
        try:
            self._kite.delete_gtt(trigger_id=trigger_id)
            logger.info("gtt_deleted", trigger_id=trigger_id)
            return True
        except Exception as e:
            logger.error("gtt_delete_failed", trigger_id=trigger_id, error=str(e))
            return False

    def get_gtt_status(self, trigger_id: str) -> dict:
        """Get GTT order status from Zerodha."""
        try:
            gtt = self._kite.get_gtt(trigger_id=trigger_id)
            return {
                "trigger_id": str(trigger_id),
                "status": gtt.get("status", "unknown"),
                "condition": gtt.get("condition", {}),
                "orders": gtt.get("orders", []),
                "updated_at": gtt.get("updated_at"),
            }
        except Exception as e:
            logger.error("gtt_status_failed", trigger_id=trigger_id, error=str(e))
            return {"trigger_id": str(trigger_id), "status": "error"}
