"""Tests for AI agents — Orchestrator scoring logic and Stitch consensus.

Note: These tests mock the Claude API to test deterministic logic only.
Integration tests with real API calls belong in tests/integration/.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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


# ---- Orchestrator Tests ----


def _make_orchestrator():
    """Create OrchestratorAgent with mocked Claude client."""
    with patch("src.agents.base_agent.anthropic.Anthropic"):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from src.agents.orchestrator import OrchestratorAgent

            agent = OrchestratorAgent(
                config=AgentConfig(),
                scoring_config=ScoringConfig(),
            )
    return agent


def _make_strategy_signal(
    symbol: str = "RELIANCE",
    direction: Direction = Direction.BUY,
    sa: float = 0.8,
    mc: float = 0.7,
    ls: float = 0.6,
) -> StrategySignal:
    return StrategySignal(
        symbol=symbol,
        direction=direction,
        strategy_name="test_strategy",
        entry_price=2500.0,
        stop_loss=2450.0,
        target_price=2600.0,
        confidence_inputs=ConfidenceBreakdown(
            signal_alignment=sa,
            market_confirmation=mc,
            liquidity_score=ls,
        ),
    )


def _make_researcher_output(
    sentiment: str = "BULLISH",
    news_strength: float = 0.7,
) -> dict:
    return {
        "sentiment": sentiment,
        "news_strength": news_strength,
        "key_drivers": ["Earnings beat", "Volume spike"],
        "entities": [{"symbol": "RELIANCE", "sector": "Energy"}],
    }


def _make_sentinel_output(risk_penalty: float = 0.2) -> dict:
    return {
        "risk_penalty": risk_penalty,
        "counter_arguments": ["Global markets weak"],
        "conflicting_signals": [],
        "recommendation": "PROCEED",
    }


def _make_market_context(
    direction: str = "bullish",
    is_risk_off: bool = False,
) -> dict:
    return {
        "nifty_price": 22000,
        "nifty_change_pct": 0.5,
        "india_vix": 14,
        "market_direction": direction,
        "is_risk_off": is_risk_off,
    }


class TestOrchestratorScoring:
    def test_build_confidence(self):
        agent = _make_orchestrator()
        signal = _make_strategy_signal()
        researcher = _make_researcher_output()
        sentinel = _make_sentinel_output()
        market = _make_market_context()

        breakdown = agent._build_confidence(signal, researcher, sentinel, market)

        assert breakdown.news_strength == 0.7
        assert breakdown.signal_alignment == 0.8
        assert breakdown.liquidity_score == 0.6
        assert breakdown.risk_penalty == 0.2
        # MC = 0.7 (strategy) + 0.1 (direction aligned) = 0.8
        assert breakdown.market_confirmation == 0.8

    def test_build_confidence_risk_off(self):
        agent = _make_orchestrator()
        signal = _make_strategy_signal()
        researcher = _make_researcher_output()
        sentinel = _make_sentinel_output()
        market = _make_market_context(is_risk_off=True)

        breakdown = agent._build_confidence(signal, researcher, sentinel, market)
        # MC = 0.7 + 0.1 (aligned) - 0.2 (risk_off) = 0.6
        assert breakdown.market_confirmation == 0.6

    def test_build_confidence_against_market(self):
        agent = _make_orchestrator()
        signal = _make_strategy_signal(direction=Direction.SELL)
        researcher = _make_researcher_output()
        sentinel = _make_sentinel_output()
        market = _make_market_context(direction="bullish")

        breakdown = agent._build_confidence(signal, researcher, sentinel, market)
        # Selling in bullish market: MC = 0.7 - 0.15 = 0.55
        assert breakdown.market_confirmation == 0.55

    def test_compute_confidence_formula(self):
        agent = _make_orchestrator()
        breakdown = ConfidenceBreakdown(
            news_strength=0.7,
            signal_alignment=0.8,
            market_confirmation=0.8,
            liquidity_score=0.6,
            risk_penalty=0.2,
        )
        conf = agent._compute_confidence(breakdown)
        # (0.7*0.25) + (0.8*0.30) + (0.8*0.25) + (0.6*0.10) - (0.2*0.20)
        # = 0.175 + 0.24 + 0.20 + 0.06 - 0.04 = 0.635
        assert abs(conf - 0.635) < 0.001

    def test_extract_sentiment_from_researcher(self):
        from src.agents.orchestrator import OrchestratorAgent

        assert OrchestratorAgent._extract_sentiment(
            {"sentiment": "BEARISH"}, Direction.BUY
        ) == Sentiment.BEARISH

    def test_extract_sentiment_fallback(self):
        from src.agents.orchestrator import OrchestratorAgent

        assert OrchestratorAgent._extract_sentiment(
            {"sentiment": "invalid"}, Direction.BUY
        ) == Sentiment.BULLISH
        assert OrchestratorAgent._extract_sentiment(
            {}, Direction.SELL
        ) == Sentiment.BEARISH

    def test_classify_strength(self):
        from src.agents.orchestrator import OrchestratorAgent

        assert OrchestratorAgent._classify_strength(0.8) == Strength.STRONG
        assert OrchestratorAgent._classify_strength(0.6) == Strength.MODERATE
        assert OrchestratorAgent._classify_strength(0.3) == Strength.WEAK

    def test_regime_guard_bear_caps_buy(self):
        agent = _make_orchestrator()
        signal = _make_strategy_signal(direction=Direction.BUY, sa=1.0, mc=1.0, ls=1.0)
        researcher = _make_researcher_output(news_strength=1.0)
        sentinel = _make_sentinel_output(risk_penalty=0.0)
        market = _make_market_context()

        # Mock the Claude call for summary
        agent.call = MagicMock(return_value={
            "summary": "Test", "exit_guidance": "Test", "key_risk": "Test"
        })

        scored = agent._score_single(
            signal, researcher, sentinel, market, regime=MarketRegime.BEAR
        )
        # Bear regime caps BUY confidence at 0.6
        assert scored.confidence <= 0.6

    def test_score_signals_returns_sorted(self):
        agent = _make_orchestrator()
        agent.call = MagicMock(return_value={
            "summary": "Test", "exit_guidance": "Test", "key_risk": "Test"
        })

        signals = [
            _make_strategy_signal("A", sa=0.5, mc=0.5, ls=0.5),
            _make_strategy_signal("B", sa=0.9, mc=0.9, ls=0.9),
        ]
        researcher = _make_researcher_output()
        sentinel = _make_sentinel_output()
        market = _make_market_context()

        scored = agent.score_signals(signals, researcher, sentinel, market)
        assert len(scored) == 2
        assert scored[0].symbol == "B"  # Higher score first
        assert scored[0].final_score >= scored[1].final_score


# ---- Stitch Tests ----


def _make_scored_signal(
    symbol: str,
    direction: Direction = Direction.BUY,
    confidence: float = 0.7,
    final_score: float = 0.7,
    strategy: str = "test",
) -> ScoredSignal:
    return ScoredSignal(
        symbol=symbol,
        direction=direction,
        sentiment=Sentiment.BULLISH if direction == Direction.BUY else Sentiment.BEARISH,
        confidence=confidence,
        strength=Strength.MODERATE,
        final_score=final_score,
        confidence_breakdown=ConfidenceBreakdown(),
        strategy_name=strategy,
    )


class TestStitchConsensus:
    def _make_stitch(self):
        from src.agents.stitch import StitchAgent

        return StitchAgent(ScoringConfig())

    def test_single_signal_passes_through(self):
        stitch = self._make_stitch()
        signals = [_make_scored_signal("RELIANCE")]
        result = stitch.finalize(signals)
        assert len(result) == 1
        assert result[0].symbol == "RELIANCE"

    def test_empty_input(self):
        stitch = self._make_stitch()
        assert stitch.finalize([]) == []

    def test_direction_conflict_skips_tied(self):
        stitch = self._make_stitch()
        signals = [
            _make_scored_signal("RELIANCE", Direction.BUY, strategy="s1"),
            _make_scored_signal("RELIANCE", Direction.SELL, strategy="s2"),
        ]
        result = stitch.finalize(signals)
        assert len(result) == 0  # Tied conflict → skip

    def test_direction_conflict_majority_wins(self):
        stitch = self._make_stitch()
        signals = [
            _make_scored_signal("RELIANCE", Direction.BUY, strategy="s1"),
            _make_scored_signal("RELIANCE", Direction.BUY, strategy="s2"),
            _make_scored_signal("RELIANCE", Direction.SELL, strategy="s3"),
        ]
        result = stitch.finalize(signals)
        assert len(result) == 1
        assert result[0].direction == Direction.BUY

    def test_high_confidence_variance_takes_conservative(self):
        stitch = self._make_stitch()
        signals = [
            _make_scored_signal("RELIANCE", confidence=0.9, final_score=0.9, strategy="s1"),
            _make_scored_signal("RELIANCE", confidence=0.5, final_score=0.5, strategy="s2"),
        ]
        result = stitch.finalize(signals)
        assert len(result) == 1
        # Variance = 0.4 > 0.15 threshold → takes lowest confidence
        assert result[0].confidence == 0.5

    def test_multi_strategy_agreement_boosts(self):
        stitch = self._make_stitch()
        signals = [
            _make_scored_signal("RELIANCE", confidence=0.7, final_score=0.7, strategy="s1"),
            _make_scored_signal("RELIANCE", confidence=0.75, final_score=0.75, strategy="s2"),
        ]
        result = stitch.finalize(signals)
        assert len(result) == 1
        # Best score 0.75 boosted by agreement
        assert result[0].final_score > 0.75

    def test_sector_dedup(self):
        stitch = self._make_stitch()
        signals = [
            _make_scored_signal("RELIANCE", final_score=0.9),
            _make_scored_signal("BPCL", final_score=0.8),
            _make_scored_signal("IOC", final_score=0.7),  # 3rd energy → should be dropped
        ]
        sector_map = {"RELIANCE": "Energy", "BPCL": "Energy", "IOC": "Energy"}
        result = stitch.finalize(signals, sector_map=sector_map)
        assert len(result) == 2
        symbols = {s.symbol for s in result}
        assert "IOC" not in symbols

    def test_max_output_signals(self):
        stitch = self._make_stitch()
        signals = [_make_scored_signal(f"S{i}", final_score=0.1 * i) for i in range(10)]
        sector_map = {f"S{i}": f"Sector{i}" for i in range(10)}
        result = stitch.finalize(signals, sector_map=sector_map, max_signals=3)
        assert len(result) == 3

    def test_sorted_by_final_score(self):
        stitch = self._make_stitch()
        signals = [
            _make_scored_signal("A", final_score=0.5),
            _make_scored_signal("B", final_score=0.9),
            _make_scored_signal("C", final_score=0.7),
        ]
        sector_map = {"A": "S1", "B": "S2", "C": "S3"}
        result = stitch.finalize(signals, sector_map=sector_map)
        assert result[0].symbol == "B"
        assert result[-1].symbol == "A"

    def test_different_symbols_no_conflict(self):
        stitch = self._make_stitch()
        signals = [
            _make_scored_signal("RELIANCE", final_score=0.8),
            _make_scored_signal("TCS", final_score=0.7),
            _make_scored_signal("INFY", final_score=0.6),
        ]
        sector_map = {"RELIANCE": "Energy", "TCS": "IT", "INFY": "IT2"}
        result = stitch.finalize(signals, sector_map=sector_map)
        assert len(result) == 3
