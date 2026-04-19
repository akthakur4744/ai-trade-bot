"""Shared data models used across the application."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Sentiment(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class Strength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"


class SignalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ExitReason(str, Enum):
    STOP_LOSS = "stop_loss"
    TARGET = "target"
    TIME_BASED = "time_based"
    CONFIDENCE_DECAY = "confidence_decay"
    STRUCTURE_BREAK = "structure_break"
    MANUAL = "manual"
    KILL_SWITCH = "kill_switch"
    GTT_STOP_LOSS = "gtt_stop_loss"
    GTT_TARGET = "gtt_target"


class GTTStatus(str, Enum):
    """Status of a GTT order on Zerodha."""
    PENDING = "pending"       # Not yet placed (paper mode or pre-placement)
    ACTIVE = "active"         # Placed on exchange
    TRIGGERED = "triggered"   # One leg executed
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    UPDATING = "updating"     # Cancel+create in progress (gap state)


class MarketRegime(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    RANGE_BOUND = "range_bound"
    CHOPPY = "choppy"


class Horizon(str, Enum):
    SHORT_TERM = "Short Term (1-3 days)"
    MEDIUM_TERM = "Medium Term (4-10 days)"


# --- Signal Models ---


class ConfidenceBreakdown(BaseModel):
    news_strength: float = 0.0
    signal_alignment: float = 0.0
    market_confirmation: float = 0.0
    liquidity_score: float = 0.0
    risk_penalty: float = 0.0


class StrategySignal(BaseModel):
    """Raw signal from a strategy engine."""

    symbol: str
    exchange: str = "NSE"
    direction: Direction
    strategy_name: str
    entry_price: float
    stop_loss: float
    target_price: Optional[float] = None
    confidence_inputs: ConfidenceBreakdown = ConfidenceBreakdown()
    time_horizon: str = "intraday"
    metadata: dict = Field(default_factory=dict)


class ScoredSignal(BaseModel):
    """Signal after scoring, filtering, and ranking."""

    symbol: str
    exchange: str = "NSE"
    direction: Direction
    sentiment: Sentiment
    confidence: float
    strength: Strength
    final_score: float
    confidence_breakdown: ConfidenceBreakdown
    strategy_name: str
    key_drivers: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    summary: str = ""
    time_horizon: str = "intraday"
    regime: Optional[MarketRegime] = None
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_price: Optional[float] = None

    @property
    def display_horizon(self) -> str:
        mapping = {
            "intraday": Horizon.SHORT_TERM,
            "swing": Horizon.MEDIUM_TERM,
            "positional": Horizon.MEDIUM_TERM,
        }
        return mapping.get(self.time_horizon, Horizon.MEDIUM_TERM).value

    @property
    def expected_return_pct(self) -> float | None:
        if not self.target_price or self.entry_price <= 0:
            return None
        if self.direction == Direction.BUY:
            return (self.target_price - self.entry_price) / self.entry_price * 100
        return (self.entry_price - self.target_price) / self.entry_price * 100


# --- Order Models ---


class Order(BaseModel):
    """An order to be placed via the broker."""

    symbol: str
    exchange: str = "NSE"
    direction: Direction
    quantity: int
    price: float  # Expected fill price
    stop_loss: float
    target_price: Optional[float] = None
    order_type: str = "MARKET"
    product: str = "MIS"  # MIS = Intraday, CNC = Delivery
    signal_id: Optional[int] = None
    strategy_name: str = ""


class OrderResult(BaseModel):
    """Result of an order placement."""

    success: bool
    order_id: str = ""
    fill_price: float = 0.0
    fill_quantity: int = 0
    message: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- Position Models ---


class Position(BaseModel):
    """An open position being tracked."""

    symbol: str
    exchange: str = "NSE"
    direction: Direction
    quantity: int
    entry_price: float
    current_price: float = 0.0
    stop_loss: float
    target_price: Optional[float] = None
    order_id: str = ""
    signal_id: Optional[int] = None
    strategy_name: str = ""
    entry_time: datetime = Field(default_factory=datetime.utcnow)
    unrealized_pnl: float = 0.0
    capital_deployed: float = 0.0

    def update_pnl(self, current_price: float) -> None:
        self.current_price = current_price
        if self.direction == Direction.BUY:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity


class ExitSignal(BaseModel):
    """Signal to exit a position."""

    symbol: str
    reason: ExitReason
    urgency: str = "MEDIUM"  # HIGH, MEDIUM, LOW
    message: str = ""


# --- Approval Workflow ---


class TradeAction(str, Enum):
    """User action on a pending signal notification."""
    APPROVE = "approve"
    IGNORE = "ignore"
    AUTO_SELL = "auto_sell"


class PendingSignal(BaseModel):
    """A scored signal awaiting user approval.

    Created when the engine finds a tradeable signal.
    User can: Approve (manual exit), Auto-Sell (AI-managed exit), or Ignore.
    Expires after `expiry_minutes` if no action is taken.
    """

    signal_id: str  # Unique ID for tracking
    signal: ScoredSignal
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expiry_minutes: int = 15  # Auto-expire if no user action
    telegram_message_id: Optional[int] = None  # For button callback routing
    status: SignalStatus = SignalStatus.PENDING
    action: Optional[TradeAction] = None

    @property
    def is_expired(self) -> bool:
        from datetime import timedelta
        return datetime.utcnow() > self.created_at + timedelta(minutes=self.expiry_minutes)


class GTTResult(BaseModel):
    """Result of a GTT order placement/modification on Zerodha."""

    success: bool
    trigger_id: str = ""
    message: str = ""


class AutoSellTrigger(BaseModel):
    """AI-defined exit conditions for a position with auto-sell enabled.

    When the user selects 'Enable Auto-Sell', the system creates these
    trigger conditions. The position monitor checks them continuously
    and auto-exits when any condition is met.

    If GTT is enabled (live mode), an OCO order is also placed on Zerodha
    for exchange-level stop loss + target protection. The software monitor
    handles trailing stop, time, confidence, and structure break exits,
    and updates the GTT stop leg as the trailing stop improves.
    """

    symbol: str
    position_entry_price: float
    position_direction: Direction

    # AI-calculated exit conditions
    stop_loss: float  # Hard stop loss
    target_price: float  # Profit target
    trailing_stop_pct: float = 1.5  # Trailing stop percentage
    max_hold_minutes: int = 90  # Time-based exit
    confidence_floor: float = 0.5  # Exit if confidence drops below
    structure_break_threshold: float = -1.0  # PnL% that triggers structure break check

    # Tracking
    created_at: datetime = Field(default_factory=datetime.utcnow)
    highest_price: float = 0.0  # For trailing stop (BUY positions)
    lowest_price: float = 999999.0  # For trailing stop (SELL positions)
    is_active: bool = True

    # GTT (exchange-level protection)
    gtt_trigger_id: str = ""  # Zerodha GTT trigger ID
    gtt_status: GTTStatus = GTTStatus.PENDING
    gtt_stop_price: float = 0.0  # Current stop price on GTT (may differ from trailing)
    gtt_last_updated: Optional[datetime] = None  # For rate-limiting GTT updates

    # AI rationale
    exit_strategy: str = ""  # Human-readable exit plan
    invalidation_condition: str = ""  # What would make the thesis wrong
