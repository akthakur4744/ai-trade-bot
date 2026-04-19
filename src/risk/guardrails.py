"""Pre-trade risk validation — all 4 checks must pass before any order placement.

Never bypass these guardrails. If any check fails, the order is rejected.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from src.config import RiskConfig
from src.models import Order

logger = structlog.get_logger(__name__)


@dataclass
class GuardrailResult:
    """Result of risk validation."""

    passed: bool
    reason: str = ""

    @staticmethod
    def ok() -> GuardrailResult:
        return GuardrailResult(passed=True)

    @staticmethod
    def blocked(reason: str) -> GuardrailResult:
        return GuardrailResult(passed=False, reason=reason)


def check_trade_capital(order: Order, config: RiskConfig) -> GuardrailResult:
    """Check 1: Order size <= max_capital_per_trade."""
    order_value = order.quantity * order.price
    if order_value > config.max_capital_per_trade:
        return GuardrailResult.blocked(
            f"Order value {order_value:.0f} INR exceeds max_capital_per_trade "
            f"{config.max_capital_per_trade:.0f} INR"
        )
    return GuardrailResult.ok()


def check_portfolio_exposure(
    order: Order, current_deployed: float, config: RiskConfig
) -> GuardrailResult:
    """Check 2: Total deployed capital <= max_capital_deployed."""
    order_value = order.quantity * order.price
    total = current_deployed + order_value
    if total > config.max_capital_deployed:
        return GuardrailResult.blocked(
            f"Total deployment {total:.0f} INR would exceed max_capital_deployed "
            f"{config.max_capital_deployed:.0f} INR (current: {current_deployed:.0f})"
        )
    return GuardrailResult.ok()


def check_daily_loss(realized_pnl_today: float, config: RiskConfig) -> GuardrailResult:
    """Check 3: Realized PnL > -max_daily_loss (kill switch territory)."""
    if realized_pnl_today <= -config.max_daily_loss:
        return GuardrailResult.blocked(
            f"Daily loss {realized_pnl_today:.0f} INR has reached max_daily_loss "
            f"-{config.max_daily_loss:.0f} INR — trading halted for the day"
        )
    return GuardrailResult.ok()


def check_position_limit(open_positions: int, config: RiskConfig) -> GuardrailResult:
    """Check 4: Open positions < max_open_positions."""
    if open_positions >= config.max_open_positions:
        return GuardrailResult.blocked(
            f"Open positions {open_positions} has reached max_open_positions "
            f"{config.max_open_positions}"
        )
    return GuardrailResult.ok()


def validate_order(
    order: Order,
    current_deployed: float,
    realized_pnl_today: float,
    open_positions: int,
    config: RiskConfig,
) -> GuardrailResult:
    """Run all 4 pre-trade risk checks. ALL must pass.

    Args:
        order: The order to validate.
        current_deployed: Total capital currently deployed in open positions.
        realized_pnl_today: Realized PnL for today (negative = loss).
        open_positions: Number of currently open positions.
        config: Risk configuration.

    Returns:
        GuardrailResult with passed=True if all checks pass,
        or passed=False with the first failure reason.
    """
    checks = [
        ("trade_capital", lambda: check_trade_capital(order, config)),
        ("portfolio_exposure", lambda: check_portfolio_exposure(order, current_deployed, config)),
        ("daily_loss", lambda: check_daily_loss(realized_pnl_today, config)),
        ("position_limit", lambda: check_position_limit(open_positions, config)),
    ]

    for check_name, check_fn in checks:
        result = check_fn()
        if not result.passed:
            logger.warning(
                "guardrail_blocked",
                check=check_name,
                reason=result.reason,
                symbol=order.symbol,
            )
            return result

    logger.info("guardrail_passed", symbol=order.symbol, quantity=order.quantity)
    return GuardrailResult.ok()
