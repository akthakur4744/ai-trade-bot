"""Sentiment decay — reduces news_strength over time.

News becomes stale. A headline that's 2 hours old should carry less weight
than one from 5 minutes ago. Default: 15% decay every 30 minutes.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def apply_decay(
    news_strength: float,
    news_time: datetime,
    current_time: datetime,
    decay_pct: float = 0.15,
    decay_interval_min: int = 30,
) -> float:
    """Apply time-based decay to news_strength.

    Args:
        news_strength: Original news_strength score (0-1).
        news_time: When the news was published/received.
        current_time: Current timestamp.
        decay_pct: Fraction to decay per interval (0.15 = 15%).
        decay_interval_min: Interval in minutes for each decay step.

    Returns:
        Decayed news_strength, minimum 0.0.
    """
    if news_strength <= 0.0:
        return 0.0

    elapsed = current_time - news_time
    if elapsed <= timedelta(0):
        return news_strength

    elapsed_minutes = elapsed.total_seconds() / 60.0
    intervals = elapsed_minutes / decay_interval_min

    # Exponential decay: strength * (1 - decay_pct) ^ intervals
    decay_factor = (1.0 - decay_pct) ** intervals
    return max(0.0, round(news_strength * decay_factor, 4))


def is_stale(
    news_time: datetime,
    current_time: datetime,
    max_age_minutes: float = 240.0,
) -> bool:
    """Check if news is too old to be useful.

    Args:
        news_time: When the news was published.
        current_time: Current timestamp.
        max_age_minutes: Maximum age before considered stale.

    Returns:
        True if news is stale.
    """
    elapsed = (current_time - news_time).total_seconds() / 60.0
    return elapsed > max_age_minutes
