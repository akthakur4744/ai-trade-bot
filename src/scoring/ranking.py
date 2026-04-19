"""Final score ranking — select top N signals from scored candidates."""

from __future__ import annotations

from typing import List

from src.config import RankingWeights
from src.models import ScoredSignal


def rank_signals(
    signals: List[ScoredSignal],
    top_n: int = 5,
) -> List[ScoredSignal]:
    """Sort signals by final_score descending and return top N.

    Args:
        signals: Pre-scored signals.
        top_n: Maximum number of signals to return.

    Returns:
        Top N signals sorted by final_score.
    """
    return sorted(signals, key=lambda s: s.final_score, reverse=True)[:top_n]


def compute_ranking_score(
    confidence: float,
    signal_alignment: float,
    market_confirmation: float,
    news_strength: float,
    weights: RankingWeights,
) -> float:
    """Compute weighted ranking score.

    Args:
        confidence: Alpha confidence (0-1).
        signal_alignment: SA component (0-1).
        market_confirmation: MC component (0-1).
        news_strength: NS component (0-1).
        weights: Ranking weights from config.

    Returns:
        Weighted ranking score.
    """
    return (
        confidence * weights.confidence
        + signal_alignment * weights.signal_alignment
        + market_confirmation * weights.market_confirmation
        + news_strength * weights.news_strength
    )
