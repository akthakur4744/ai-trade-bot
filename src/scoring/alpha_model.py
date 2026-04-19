"""Alpha model — deterministic confidence formula implementation.

The confidence score is the core metric for signal quality.
Formula: (NS * w_ns) + (SA * w_sa) + (MC * w_mc) + (LS * w_ls) - (RP * w_rp)

All inputs are clamped to [0, 1]. Output is clamped to [0, 1].
"""

from __future__ import annotations

from src.config import ScoringWeights
from src.models import ConfidenceBreakdown


def compute_confidence(
    breakdown: ConfidenceBreakdown,
    weights: ScoringWeights,
) -> float:
    """Compute alpha confidence score from breakdown components.

    Args:
        breakdown: Component scores (each 0-1).
        weights: Weight for each component.

    Returns:
        Confidence score clamped to [0, 1].
    """
    raw = (
        breakdown.news_strength * weights.news_strength
        + breakdown.signal_alignment * weights.signal_alignment
        + breakdown.market_confirmation * weights.market_confirmation
        + breakdown.liquidity_score * weights.liquidity_score
        - breakdown.risk_penalty * weights.risk_penalty
    )
    return max(0.0, min(1.0, raw))


def compute_final_score(
    confidence: float,
    breakdown: ConfidenceBreakdown,
    confidence_weight: float = 0.4,
    sa_weight: float = 0.3,
    mc_weight: float = 0.2,
    ns_weight: float = 0.1,
) -> float:
    """Compute ranking score for signal prioritization.

    Args:
        confidence: Alpha confidence score.
        breakdown: Component scores.
        confidence_weight: Weight for confidence in ranking.
        sa_weight: Weight for signal alignment.
        mc_weight: Weight for market confirmation.
        ns_weight: Weight for news strength.

    Returns:
        Final ranking score.
    """
    return (
        confidence * confidence_weight
        + breakdown.signal_alignment * sa_weight
        + breakdown.market_confirmation * mc_weight
        + breakdown.news_strength * ns_weight
    )
