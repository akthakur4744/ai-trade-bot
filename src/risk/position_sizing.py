"""Position sizing — determines how many shares to buy based on risk budget.

Three methods:
1. Fixed Percentage: Risk a fixed % of capital per trade
2. ATR-Based: Use volatility (ATR) to set stop distance, then size accordingly
3. Kelly Criterion: Mathematically optimal sizing from win/loss stats
"""

from __future__ import annotations

import math

import structlog

from src.config import RiskConfig

logger = structlog.get_logger(__name__)


def fixed_percentage_size(
    capital: float,
    entry_price: float,
    stop_loss: float,
    risk_pct: float = 0.02,
) -> int:
    """Size position so that hitting stop_loss loses at most risk_pct of capital.

    Formula: quantity = (capital * risk_pct) / |entry_price - stop_loss|

    Args:
        capital: Total account capital.
        entry_price: Expected entry price.
        stop_loss: Stop loss price.
        risk_pct: Max fraction of capital to risk (0.02 = 2%).

    Returns:
        Number of shares (floored to integer, minimum 0).
    """
    risk_per_share = abs(entry_price - stop_loss)
    if risk_per_share <= 0:
        logger.warning("zero_risk_per_share", entry_price=entry_price, stop_loss=stop_loss)
        return 0

    risk_amount = capital * risk_pct
    quantity = math.floor(risk_amount / risk_per_share)
    return max(0, quantity)


def atr_based_size(
    capital: float,
    entry_price: float,
    atr: float,
    atr_multiplier: float = 2.0,
    risk_pct: float = 0.02,
) -> tuple[int, float]:
    """Size position using ATR for stop distance.

    Stop loss = entry_price - (atr * multiplier) for longs.
    Then applies fixed percentage sizing with that stop.

    Args:
        capital: Total account capital.
        entry_price: Expected entry price.
        atr: Current ATR value.
        atr_multiplier: How many ATRs away to place stop.
        risk_pct: Max fraction of capital to risk.

    Returns:
        Tuple of (quantity, implied_stop_loss).
    """
    stop_distance = atr * atr_multiplier
    if stop_distance <= 0:
        return 0, entry_price

    implied_stop = entry_price - stop_distance  # For longs; flip for shorts

    risk_amount = capital * risk_pct
    quantity = math.floor(risk_amount / stop_distance)
    return max(0, quantity), implied_stop


def kelly_criterion_size(
    capital: float,
    entry_price: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    fraction: float = 0.5,
    max_position_pct: float = 0.25,
) -> int:
    """Kelly Criterion position sizing.

    Kelly % = W - (1 - W) / R
    where W = win probability, R = win/loss ratio

    Uses fractional Kelly (default half-Kelly) to reduce risk of ruin.

    Args:
        capital: Total account capital.
        entry_price: Expected entry price.
        win_rate: Historical win probability (0.0-1.0).
        avg_win: Average winning trade amount.
        avg_loss: Average losing trade amount (positive number).
        fraction: Kelly fraction (0.5 = half-Kelly, recommended).
        max_position_pct: Max position as % of capital (safety cap).

    Returns:
        Number of shares.
    """
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0

    win_loss_ratio = avg_win / avg_loss
    kelly_pct = win_rate - ((1 - win_rate) / win_loss_ratio)

    if kelly_pct <= 0:
        logger.info("kelly_negative", kelly_pct=kelly_pct, win_rate=win_rate)
        return 0

    # Apply fractional Kelly and cap
    position_pct = min(kelly_pct * fraction, max_position_pct)
    position_value = capital * position_pct

    if entry_price <= 0:
        return 0

    quantity = math.floor(position_value / entry_price)
    return max(0, quantity)


def calculate_position_size(
    method: str,
    capital: float,
    entry_price: float,
    stop_loss: float,
    config: RiskConfig,
    atr: float = 0.0,
    win_rate: float = 0.0,
    avg_win: float = 0.0,
    avg_loss: float = 0.0,
) -> int:
    """Dispatch to the configured position sizing method.

    Also enforces max_capital_per_trade as a hard cap.
    """
    if method == "atr" and atr > 0:
        quantity, _ = atr_based_size(capital, entry_price, atr, risk_pct=config.per_trade_risk_pct)
    elif method == "kelly" and win_rate > 0:
        quantity = kelly_criterion_size(capital, entry_price, win_rate, avg_win, avg_loss)
    else:
        quantity = fixed_percentage_size(capital, entry_price, stop_loss, config.per_trade_risk_pct)

    # Hard cap: never exceed max_capital_per_trade
    if entry_price > 0:
        max_qty = math.floor(config.max_capital_per_trade / entry_price)
        quantity = min(quantity, max_qty)

    logger.info(
        "position_sized",
        method=method,
        quantity=quantity,
        entry_price=entry_price,
        value=quantity * entry_price,
    )
    return quantity
