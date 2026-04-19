"""Paper broker — simulated order execution using real market data.

Never calls Kite order APIs. Fetches real LTP for pricing, applies
configurable slippage, and tracks positions locally.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog

from src.config import PaperConfig
from src.data.market_data import MarketDataFetcher
from src.execution.broker import Broker
from src.models import Direction, GTTResult, Order, OrderResult, Position

logger = structlog.get_logger(__name__)


class PaperBroker(Broker):
    """Simulated broker for paper trading.

    Uses real market data (LTP) from Kite for realistic fills,
    but never places actual orders.
    """

    def __init__(
        self,
        market_data: MarketDataFetcher,
        config: PaperConfig,
    ) -> None:
        self._market_data = market_data
        self._config = config
        self._orders: dict[str, dict] = {}  # order_id -> order details

    def place_order(self, order: Order) -> OrderResult:
        """Simulate order execution at current LTP + slippage."""
        instrument = f"{order.exchange}:{order.symbol}"

        # Fetch real LTP
        ltp_data = self._market_data.get_ltp([instrument])
        ltp = ltp_data.get(instrument)

        if ltp is None:
            logger.error("paper_ltp_unavailable", symbol=order.symbol)
            return OrderResult(
                success=False,
                message=f"Could not fetch LTP for {order.symbol}",
            )

        # Apply slippage
        slippage_factor = self._config.slippage_bps / 10000
        if order.direction == Direction.BUY:
            fill_price = ltp * (1 + slippage_factor)
        else:
            fill_price = ltp * (1 - slippage_factor)

        fill_price = round(fill_price, 2)
        order_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"

        # Store order record
        self._orders[order_id] = {
            "order": order,
            "fill_price": fill_price,
            "ltp": ltp,
            "slippage_bps": self._config.slippage_bps,
            "status": "COMPLETE",
            "timestamp": datetime.utcnow(),
        }

        logger.info(
            "paper_order_filled",
            order_id=order_id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=order.quantity,
            ltp=ltp,
            fill_price=fill_price,
            slippage_bps=self._config.slippage_bps,
        )

        return OrderResult(
            success=True,
            order_id=order_id,
            fill_price=fill_price,
            fill_quantity=order.quantity,
            message=f"Paper fill at {fill_price} (LTP: {ltp}, slippage: {self._config.slippage_bps}bps)",
            timestamp=datetime.utcnow(),
        )

    def get_positions(self) -> list[Position]:
        """Paper broker doesn't track positions — Portfolio handles that."""
        return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a paper order (mark as cancelled)."""
        if order_id in self._orders:
            self._orders[order_id]["status"] = "CANCELLED"
            logger.info("paper_order_cancelled", order_id=order_id)
            return True
        return False

    def get_order_status(self, order_id: str) -> dict:
        """Get status of a paper order."""
        if order_id in self._orders:
            record = self._orders[order_id]
            return {
                "order_id": order_id,
                "status": record["status"],
                "fill_price": record["fill_price"],
                "timestamp": record["timestamp"].isoformat(),
            }
        return {"order_id": order_id, "status": "NOT_FOUND"}

    # ---- GTT (simulated in paper mode) ----

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
        """Simulate GTT OCO placement — tracked in-memory."""
        gtt_id = f"PAPER-GTT-{uuid.uuid4().hex[:8].upper()}"
        self._orders[gtt_id] = {
            "type": "gtt_oco",
            "symbol": symbol,
            "direction": direction,
            "quantity": quantity,
            "stop_loss": stop_loss,
            "target": target,
            "status": "active",
            "timestamp": datetime.utcnow(),
        }
        logger.info(
            "paper_gtt_placed",
            gtt_id=gtt_id,
            symbol=symbol,
            stop_loss=stop_loss,
            target=target,
        )
        return GTTResult(
            success=True,
            trigger_id=gtt_id,
            message=f"Paper GTT OCO: SL={stop_loss}, Target={target}",
        )

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
        """Simulate GTT modification."""
        if trigger_id in self._orders:
            self._orders[trigger_id]["stop_loss"] = stop_loss
            self._orders[trigger_id]["target"] = target
            logger.info(
                "paper_gtt_modified",
                trigger_id=trigger_id,
                stop_loss=stop_loss,
            )
            return GTTResult(
                success=True,
                trigger_id=trigger_id,
                message=f"Paper GTT modified: SL={stop_loss}",
            )
        return GTTResult(success=False, message="GTT not found")

    def delete_gtt(self, trigger_id: str) -> bool:
        """Simulate GTT cancellation."""
        if trigger_id in self._orders:
            self._orders[trigger_id]["status"] = "cancelled"
            logger.info("paper_gtt_deleted", trigger_id=trigger_id)
            return True
        return False

    def get_gtt_status(self, trigger_id: str) -> dict:
        """Get simulated GTT status."""
        if trigger_id in self._orders:
            record = self._orders[trigger_id]
            return {
                "trigger_id": trigger_id,
                "status": record.get("status", "active"),
            }
        return {"trigger_id": trigger_id, "status": "not_found"}
