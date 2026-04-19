"""Strict all-must-pass filters for signal quality gating.

Every filter must pass for a signal to proceed. This is the primary
mechanism for "eliminating bad trades" per the PRD philosophy.
"""

from __future__ import annotations

from typing import List, Tuple

from src.config import FilterConfig
from src.models import ConfidenceBreakdown


def apply_filters(
    confidence: float,
    breakdown: ConfidenceBreakdown,
    config: FilterConfig,
) -> Tuple[bool, List[str]]:
    """Run all-must-pass filters on a signal.

    Args:
        confidence: Computed alpha confidence score.
        breakdown: Component scores.
        config: Filter thresholds.

    Returns:
        (passed, reasons) — True if all filters pass; reasons lists failures.
    """
    failures: List[str] = []

    if confidence < config.min_confidence:
        failures.append(
            f"confidence {confidence:.3f} < min {config.min_confidence}"
        )

    if breakdown.market_confirmation < config.min_market_confirmation:
        failures.append(
            f"market_confirmation {breakdown.market_confirmation:.3f} "
            f"< min {config.min_market_confirmation}"
        )

    if breakdown.liquidity_score < config.min_liquidity_score:
        failures.append(
            f"liquidity_score {breakdown.liquidity_score:.3f} "
            f"< min {config.min_liquidity_score}"
        )

    if breakdown.risk_penalty > config.max_risk_penalty:
        failures.append(
            f"risk_penalty {breakdown.risk_penalty:.3f} "
            f"> max {config.max_risk_penalty}"
        )

    return (len(failures) == 0, failures)
