"""Orchestrator Agent — deterministic alpha scoring + Claude summary generation.

Input: Strategy signals + Researcher output + Sentinel output + market context
Output: ScoredSignals with confidence, final_score, human-readable summary

KEY DESIGN: The alpha score is computed deterministically in Python (not LLM).
Claude is used ONLY for generating the human-readable summary and exit guidance.
This ensures reproducibility, auditability, and testability.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from src.agents.base_agent import BaseAgent
from src.config import AgentConfig, ScoringConfig
from src.models import (
    ConfidenceBreakdown,
    Direction,
    MarketRegime,
    ScoredSignal,
    Sentiment,
    Strength,
    StrategySignal,
)

logger = structlog.get_logger(__name__)

ORCHESTRATOR_SYSTEM_PROMPT = """You are a trading decision summariser for Indian equity markets.

You receive a pre-computed trading signal with all scores already calculated.
Your ONLY job is to produce a concise, actionable summary for a human trader.

OUTPUT FORMAT (strict JSON):
{
    "summary": "One-sentence trading thesis explaining the signal",
    "exit_guidance": "When and how to exit this position",
    "key_risk": "The single biggest risk to this trade"
}

RULES:
- Be concise — traders need quick reads
- Reference specific numbers (price, stop, target)
- Mention the strategy and key driver
- Exit guidance should include both time and price triggers
"""


class OrchestratorAgent(BaseAgent):
    """Merges signals with agent analysis, computes deterministic alpha scores,
    and uses Claude only for human-readable summaries."""

    def __init__(self, config: AgentConfig, scoring_config: ScoringConfig) -> None:
        super().__init__(config, system_prompt=ORCHESTRATOR_SYSTEM_PROMPT)
        self._scoring = scoring_config

    def score_signals(
        self,
        strategy_signals: List[StrategySignal],
        researcher_output: Dict[str, Any],
        sentinel_output: Dict[str, Any],
        market_context: Dict[str, Any],
        regime: Optional[MarketRegime] = None,
    ) -> List[ScoredSignal]:
        """Score a batch of strategy signals and produce ranked ScoredSignals.

        Args:
            strategy_signals: Raw signals from strategy engines.
            researcher_output: Output from ResearcherAgent.
            sentinel_output: Output from SentinelAgent.
            market_context: Current macro snapshot.
            regime: Current market regime (if detected).

        Returns:
            List of ScoredSignals with confidence scores and summaries.
        """
        scored = []
        for signal in strategy_signals:
            scored_signal = self._score_single(
                signal, researcher_output, sentinel_output, market_context, regime
            )
            if scored_signal is not None:
                scored.append(scored_signal)

        # Sort by final_score descending
        scored.sort(key=lambda s: s.final_score, reverse=True)
        return scored

    def _score_single(
        self,
        signal: StrategySignal,
        researcher_output: Dict[str, Any],
        sentinel_output: Dict[str, Any],
        market_context: Dict[str, Any],
        regime: Optional[MarketRegime],
    ) -> Optional[ScoredSignal]:
        """Compute deterministic alpha score for a single signal."""
        # Build confidence breakdown from all sources
        breakdown = self._build_confidence(
            signal, researcher_output, sentinel_output, market_context
        )

        # Compute alpha confidence score (deterministic formula)
        confidence = self._compute_confidence(breakdown)

        # Apply regime guard
        if regime == MarketRegime.BEAR and signal.direction == Direction.BUY:
            confidence = min(confidence, self._scoring.macro_guard_max_bullish)
        elif regime == MarketRegime.BULL and signal.direction == Direction.SELL:
            confidence = min(confidence, self._scoring.macro_guard_max_bullish)

        # Determine sentiment from researcher
        sentiment = self._extract_sentiment(researcher_output, signal.direction)

        # Determine strength tier
        strength = self._classify_strength(confidence)

        # Compute final ranking score
        final_score = self._compute_final_score(breakdown, confidence)

        # Get Claude summary (non-critical — fallback to template if it fails)
        summary_data = self._generate_summary(signal, breakdown, confidence, sentiment)

        return ScoredSignal(
            symbol=signal.symbol,
            exchange=signal.exchange,
            direction=signal.direction,
            sentiment=sentiment,
            confidence=round(confidence, 4),
            strength=strength,
            final_score=round(final_score, 4),
            confidence_breakdown=breakdown,
            strategy_name=signal.strategy_name,
            key_drivers=researcher_output.get("key_drivers", []),
            risks=sentinel_output.get("counter_arguments", []),
            summary=summary_data.get("summary", ""),
            time_horizon=signal.time_horizon,
            regime=regime,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target_price=signal.target_price,
        )

    def _build_confidence(
        self,
        signal: StrategySignal,
        researcher_output: Dict[str, Any],
        sentinel_output: Dict[str, Any],
        market_context: Dict[str, Any],
    ) -> ConfidenceBreakdown:
        """Merge inputs from all sources into a single ConfidenceBreakdown."""
        # News strength from Researcher (NS)
        news_strength = float(researcher_output.get("news_strength", 0.0))

        # Signal alignment from strategy (SA) — how aligned is the technical signal
        signal_alignment = signal.confidence_inputs.signal_alignment

        # Market confirmation (MC) — combine strategy's MC with macro context
        strategy_mc = signal.confidence_inputs.market_confirmation
        is_risk_off = market_context.get("is_risk_off", False)
        market_direction = market_context.get("market_direction", "neutral")

        # Penalise if trading against the market
        direction_aligned = (
            (signal.direction == Direction.BUY and market_direction == "bullish")
            or (signal.direction == Direction.SELL and market_direction == "bearish")
            or market_direction == "neutral"
        )
        macro_bonus = 0.1 if direction_aligned else -0.15
        risk_off_penalty = -0.2 if is_risk_off else 0.0

        market_confirmation = max(
            0.0, min(1.0, strategy_mc + macro_bonus + risk_off_penalty)
        )

        # Liquidity score from strategy (LS)
        liquidity_score = signal.confidence_inputs.liquidity_score

        # Risk penalty from Sentinel (RP)
        risk_penalty = float(sentinel_output.get("risk_penalty", 0.5))

        return ConfidenceBreakdown(
            news_strength=round(max(0.0, min(1.0, news_strength)), 4),
            signal_alignment=round(max(0.0, min(1.0, signal_alignment)), 4),
            market_confirmation=round(market_confirmation, 4),
            liquidity_score=round(max(0.0, min(1.0, liquidity_score)), 4),
            risk_penalty=round(max(0.0, min(1.0, risk_penalty)), 4),
        )

    def _compute_confidence(self, breakdown: ConfidenceBreakdown) -> float:
        """PRD formula: (NS*0.25) + (SA*0.30) + (MC*0.25) + (LS*0.10) - (RP*0.20)"""
        w = self._scoring.weights
        raw = (
            breakdown.news_strength * w.news_strength
            + breakdown.signal_alignment * w.signal_alignment
            + breakdown.market_confirmation * w.market_confirmation
            + breakdown.liquidity_score * w.liquidity_score
            - breakdown.risk_penalty * w.risk_penalty
        )
        return max(0.0, min(1.0, raw))

    def _compute_final_score(
        self, breakdown: ConfidenceBreakdown, confidence: float
    ) -> float:
        """Ranking score: (conf*0.4) + (SA*0.3) + (MC*0.2) + (NS*0.1)"""
        r = self._scoring.ranking
        return (
            confidence * r.confidence
            + breakdown.signal_alignment * r.signal_alignment
            + breakdown.market_confirmation * r.market_confirmation
            + breakdown.news_strength * r.news_strength
        )

    @staticmethod
    def _extract_sentiment(
        researcher_output: Dict[str, Any], direction: Direction
    ) -> Sentiment:
        """Get sentiment from researcher, falling back to direction."""
        raw = str(researcher_output.get("sentiment", "")).upper()
        if raw in ("BULLISH", "BEARISH", "NEUTRAL"):
            return Sentiment(raw)
        # Fall back: BUY → BULLISH, SELL → BEARISH
        return Sentiment.BULLISH if direction == Direction.BUY else Sentiment.BEARISH

    @staticmethod
    def _classify_strength(confidence: float) -> Strength:
        if confidence >= 0.75:
            return Strength.STRONG
        elif confidence >= 0.55:
            return Strength.MODERATE
        return Strength.WEAK

    def _generate_summary(
        self,
        signal: StrategySignal,
        breakdown: ConfidenceBreakdown,
        confidence: float,
        sentiment: Sentiment,
    ) -> Dict[str, str]:
        """Use Claude to generate a human-readable summary. Non-critical."""
        prompt = f"""Summarise this trading signal:

Symbol: {signal.symbol}
Direction: {signal.direction.value}
Strategy: {signal.strategy_name}
Entry: {signal.entry_price}, Stop: {signal.stop_loss}, Target: {signal.target_price}
Sentiment: {sentiment.value}
Confidence: {confidence:.2f}
Signal Alignment: {breakdown.signal_alignment:.2f}
Market Confirmation: {breakdown.market_confirmation:.2f}
Risk Penalty: {breakdown.risk_penalty:.2f}
Time Horizon: {signal.time_horizon}
Metadata: {signal.metadata}

Respond with the JSON format specified in your instructions."""

        result = self.call(prompt, expect_json=True)
        if "error" in result or "parse_error" in result:
            # Non-critical — return template summary
            return {
                "summary": (
                    f"{signal.direction.value} {signal.symbol} via {signal.strategy_name} "
                    f"(confidence: {confidence:.2f})"
                ),
                "exit_guidance": (
                    f"Stop at {signal.stop_loss}, target at {signal.target_price}"
                ),
                "key_risk": "See sentinel analysis for risks",
            }
        return result
