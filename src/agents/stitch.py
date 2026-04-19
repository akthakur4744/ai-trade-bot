"""Stitch Agent — cross-timeframe consensus, dedup, and final ranking.

Input: List of ScoredSignals from Orchestrator
Output: Final ranked list after consensus checks and dedup

The Stitch agent ensures:
1. Multi-timeframe consensus (same symbol across strategies must agree)
2. Confidence variance check (divergent scores → reject)
3. Sector dedup (max 1-2 signals per sector)
4. Final top-N selection
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

import structlog

from src.config import ScoringConfig
from src.models import Direction, ScoredSignal, Sentiment

logger = structlog.get_logger(__name__)

# Max confidence variance allowed between strategies for the same symbol
MAX_CONFIDENCE_VARIANCE = 0.15

# Max signals per sector
MAX_PER_SECTOR = 2

# Max total output signals
MAX_OUTPUT_SIGNALS = 5


class StitchAgent:
    """Cross-timeframe consensus and final signal ranking.

    This is a deterministic agent — no LLM calls needed.
    All logic is rule-based for reproducibility and speed.
    """

    def __init__(self, scoring_config: ScoringConfig) -> None:
        self._scoring = scoring_config

    def finalize(
        self,
        scored_signals: List[ScoredSignal],
        sector_map: Optional[Dict[str, str]] = None,
        max_signals: int = MAX_OUTPUT_SIGNALS,
    ) -> List[ScoredSignal]:
        """Apply consensus checks, dedup, and produce final ranked output.

        Args:
            scored_signals: Scored signals from OrchestratorAgent.
            sector_map: symbol → sector mapping for dedup.
            max_signals: Maximum output signals.

        Returns:
            Final ranked list of actionable signals.
        """
        if not scored_signals:
            return []

        sector_map = sector_map or {}

        # Step 1: Group by symbol for consensus check
        by_symbol = self._group_by_symbol(scored_signals)

        # Step 2: Apply consensus — resolve conflicts per symbol
        consensus_signals = self._apply_consensus(by_symbol)

        # Step 3: Sector dedup
        deduped = self._sector_dedup(consensus_signals, sector_map)

        # Step 4: Final sort by final_score and take top N
        deduped.sort(key=lambda s: s.final_score, reverse=True)
        result = deduped[:max_signals]

        logger.info(
            "stitch_finalized",
            input_count=len(scored_signals),
            after_consensus=len(consensus_signals),
            after_dedup=len(deduped),
            output_count=len(result),
        )
        return result

    @staticmethod
    def _group_by_symbol(
        signals: List[ScoredSignal],
    ) -> Dict[str, List[ScoredSignal]]:
        grouped: Dict[str, List[ScoredSignal]] = defaultdict(list)
        for sig in signals:
            grouped[sig.symbol].append(sig)
        return dict(grouped)

    def _apply_consensus(
        self, by_symbol: Dict[str, List[ScoredSignal]]
    ) -> List[ScoredSignal]:
        """For each symbol, check if multiple strategies agree."""
        result = []

        for symbol, signals in by_symbol.items():
            if len(signals) == 1:
                result.append(signals[0])
                continue

            # Check direction consensus
            directions = [s.direction for s in signals]
            buy_count = directions.count(Direction.BUY)
            sell_count = directions.count(Direction.SELL)

            if buy_count > 0 and sell_count > 0:
                # Conflicting directions — take the majority, or skip if tied
                if buy_count == sell_count:
                    logger.info(
                        "stitch_direction_conflict_skip",
                        symbol=symbol,
                        buy=buy_count,
                        sell=sell_count,
                    )
                    continue
                # Keep only the majority direction
                majority = Direction.BUY if buy_count > sell_count else Direction.SELL
                signals = [s for s in signals if s.direction == majority]

            # Check confidence variance
            confidences = [s.confidence for s in signals]
            conf_range = max(confidences) - min(confidences)
            if conf_range > MAX_CONFIDENCE_VARIANCE:
                logger.info(
                    "stitch_high_confidence_variance",
                    symbol=symbol,
                    variance=round(conf_range, 4),
                    threshold=MAX_CONFIDENCE_VARIANCE,
                )
                # Take the most conservative (lowest confidence) to be safe
                signals.sort(key=lambda s: s.confidence)
                result.append(signals[0])
                continue

            # Multi-strategy agreement — boost confidence of the best signal
            best = max(signals, key=lambda s: s.final_score)

            # Agreement bonus: multiple strategies confirming = higher conviction
            agreement_count = len(signals)
            if agreement_count >= 3:
                bonus_desc = "3+ strategy agreement"
            elif agreement_count == 2:
                bonus_desc = "2-strategy agreement"
            else:
                bonus_desc = None

            if bonus_desc:
                # Create a new signal with boosted score (don't mutate)
                boosted_score = min(1.0, best.final_score * (1 + 0.05 * agreement_count))
                best = best.model_copy(
                    update={
                        "final_score": round(boosted_score, 4),
                        "summary": f"[{agreement_count} strategies agree] {best.summary}",
                    }
                )

            result.append(best)

        return result

    @staticmethod
    def _sector_dedup(
        signals: List[ScoredSignal],
        sector_map: Dict[str, str],
    ) -> List[ScoredSignal]:
        """Limit signals per sector to avoid concentration risk."""
        # Sort by final_score descending so we keep the best per sector
        signals.sort(key=lambda s: s.final_score, reverse=True)

        sector_counts: Dict[str, int] = defaultdict(int)
        result = []

        for sig in signals:
            sector = sector_map.get(sig.symbol, "unknown")
            if sector_counts[sector] >= MAX_PER_SECTOR:
                logger.info(
                    "stitch_sector_dedup_skip",
                    symbol=sig.symbol,
                    sector=sector,
                    count=sector_counts[sector],
                )
                continue
            sector_counts[sector] += 1
            result.append(sig)

        return result
