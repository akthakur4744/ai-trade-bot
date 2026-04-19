"""Tests for scoring pipeline — alpha model, filters, ranking, sentiment decay."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.config import FilterConfig, RankingWeights, ScoringWeights
from src.models import ConfidenceBreakdown, Direction, ScoredSignal, Sentiment, Strength
from src.scoring.alpha_model import compute_confidence, compute_final_score
from src.scoring.filters import apply_filters
from src.scoring.ranking import compute_ranking_score, rank_signals
from src.scoring.sentiment_decay import apply_decay, is_stale


# ---- Alpha Model ----


class TestComputeConfidence:
    def test_default_weights(self):
        breakdown = ConfidenceBreakdown(
            news_strength=0.8,
            signal_alignment=0.9,
            market_confirmation=0.7,
            liquidity_score=0.6,
            risk_penalty=0.2,
        )
        weights = ScoringWeights()
        # (0.8*0.25) + (0.9*0.30) + (0.7*0.25) + (0.6*0.10) - (0.2*0.20)
        # = 0.20 + 0.27 + 0.175 + 0.06 - 0.04 = 0.665
        result = compute_confidence(breakdown, weights)
        assert abs(result - 0.665) < 0.001

    def test_zero_inputs(self):
        breakdown = ConfidenceBreakdown()
        weights = ScoringWeights()
        assert compute_confidence(breakdown, weights) == 0.0

    def test_max_inputs(self):
        breakdown = ConfidenceBreakdown(
            news_strength=1.0,
            signal_alignment=1.0,
            market_confirmation=1.0,
            liquidity_score=1.0,
            risk_penalty=0.0,
        )
        weights = ScoringWeights()
        # 0.25 + 0.30 + 0.25 + 0.10 - 0.0 = 0.90
        result = compute_confidence(breakdown, weights)
        assert abs(result - 0.90) < 0.001

    def test_high_risk_penalty_clamps_to_zero(self):
        breakdown = ConfidenceBreakdown(
            news_strength=0.1,
            signal_alignment=0.1,
            market_confirmation=0.1,
            liquidity_score=0.1,
            risk_penalty=1.0,
        )
        weights = ScoringWeights()
        result = compute_confidence(breakdown, weights)
        assert result == 0.0  # Clamped

    def test_output_clamped_0_1(self):
        breakdown = ConfidenceBreakdown(
            news_strength=1.0,
            signal_alignment=1.0,
            market_confirmation=1.0,
            liquidity_score=1.0,
            risk_penalty=0.0,
        )
        # Use extreme weights that would push above 1.0
        weights = ScoringWeights(
            news_strength=0.5,
            signal_alignment=0.5,
            market_confirmation=0.5,
            liquidity_score=0.5,
            risk_penalty=0.0,
        )
        result = compute_confidence(breakdown, weights)
        assert result == 1.0


class TestComputeFinalScore:
    def test_basic(self):
        breakdown = ConfidenceBreakdown(
            news_strength=0.8,
            signal_alignment=0.9,
            market_confirmation=0.7,
        )
        score = compute_final_score(0.7, breakdown)
        # (0.7*0.4) + (0.9*0.3) + (0.7*0.2) + (0.8*0.1) = 0.28 + 0.27 + 0.14 + 0.08 = 0.77
        assert abs(score - 0.77) < 0.001


# ---- Filters ----


class TestFilters:
    def test_all_pass(self):
        config = FilterConfig()
        breakdown = ConfidenceBreakdown(
            market_confirmation=0.8,
            liquidity_score=0.8,
            risk_penalty=0.2,
        )
        passed, reasons = apply_filters(0.75, breakdown, config)
        assert passed is True
        assert reasons == []

    def test_confidence_fail(self):
        config = FilterConfig()
        breakdown = ConfidenceBreakdown(
            market_confirmation=0.8,
            liquidity_score=0.8,
            risk_penalty=0.2,
        )
        passed, reasons = apply_filters(0.5, breakdown, config)
        assert passed is False
        assert len(reasons) == 1
        assert "confidence" in reasons[0]

    def test_market_confirmation_fail(self):
        config = FilterConfig()
        breakdown = ConfidenceBreakdown(
            market_confirmation=0.3,
            liquidity_score=0.8,
            risk_penalty=0.2,
        )
        passed, reasons = apply_filters(0.75, breakdown, config)
        assert passed is False
        assert any("market_confirmation" in r for r in reasons)

    def test_liquidity_fail(self):
        config = FilterConfig()
        breakdown = ConfidenceBreakdown(
            market_confirmation=0.8,
            liquidity_score=0.3,
            risk_penalty=0.2,
        )
        passed, reasons = apply_filters(0.75, breakdown, config)
        assert passed is False
        assert any("liquidity_score" in r for r in reasons)

    def test_risk_penalty_fail(self):
        config = FilterConfig()
        breakdown = ConfidenceBreakdown(
            market_confirmation=0.8,
            liquidity_score=0.8,
            risk_penalty=0.6,
        )
        passed, reasons = apply_filters(0.75, breakdown, config)
        assert passed is False
        assert any("risk_penalty" in r for r in reasons)

    def test_multiple_failures(self):
        config = FilterConfig()
        breakdown = ConfidenceBreakdown(
            market_confirmation=0.3,
            liquidity_score=0.3,
            risk_penalty=0.6,
        )
        passed, reasons = apply_filters(0.4, breakdown, config)
        assert passed is False
        assert len(reasons) == 4  # All 4 checks fail

    def test_exact_thresholds_pass(self):
        config = FilterConfig()
        breakdown = ConfidenceBreakdown(
            market_confirmation=0.6,
            liquidity_score=0.6,
            risk_penalty=0.4,
        )
        passed, reasons = apply_filters(0.65, breakdown, config)
        assert passed is True


# ---- Ranking ----


def _make_scored(symbol: str, final_score: float) -> ScoredSignal:
    return ScoredSignal(
        symbol=symbol,
        direction=Direction.BUY,
        sentiment=Sentiment.BULLISH,
        confidence=0.7,
        strength=Strength.MODERATE,
        final_score=final_score,
        confidence_breakdown=ConfidenceBreakdown(),
        strategy_name="test",
    )


class TestRanking:
    def test_rank_signals_sorted(self):
        signals = [
            _make_scored("A", 0.5),
            _make_scored("B", 0.9),
            _make_scored("C", 0.7),
        ]
        ranked = rank_signals(signals)
        assert [s.symbol for s in ranked] == ["B", "C", "A"]

    def test_rank_signals_top_n(self):
        signals = [_make_scored(f"S{i}", 0.1 * i) for i in range(10)]
        ranked = rank_signals(signals, top_n=3)
        assert len(ranked) == 3
        assert ranked[0].symbol == "S9"

    def test_rank_signals_empty(self):
        assert rank_signals([]) == []

    def test_compute_ranking_score(self):
        weights = RankingWeights()
        score = compute_ranking_score(0.7, 0.9, 0.8, 0.6, weights)
        # (0.7*0.4) + (0.9*0.3) + (0.8*0.2) + (0.6*0.1) = 0.28+0.27+0.16+0.06 = 0.77
        assert abs(score - 0.77) < 0.001


# ---- Sentiment Decay ----


class TestSentimentDecay:
    def test_no_decay_at_zero_elapsed(self):
        now = datetime(2024, 1, 1, 10, 0, 0)
        result = apply_decay(0.8, now, now)
        assert result == 0.8

    def test_one_interval_decay(self):
        news_time = datetime(2024, 1, 1, 10, 0, 0)
        current = datetime(2024, 1, 1, 10, 30, 0)  # 30 min later
        result = apply_decay(1.0, news_time, current, decay_pct=0.15, decay_interval_min=30)
        # 1.0 * (1 - 0.15)^1 = 0.85
        assert abs(result - 0.85) < 0.001

    def test_two_intervals_decay(self):
        news_time = datetime(2024, 1, 1, 10, 0, 0)
        current = datetime(2024, 1, 1, 11, 0, 0)  # 60 min = 2 intervals
        result = apply_decay(1.0, news_time, current, decay_pct=0.15, decay_interval_min=30)
        # 1.0 * (0.85)^2 = 0.7225
        assert abs(result - 0.7225) < 0.001

    def test_zero_strength_stays_zero(self):
        news_time = datetime(2024, 1, 1, 10, 0, 0)
        current = datetime(2024, 1, 1, 11, 0, 0)
        assert apply_decay(0.0, news_time, current) == 0.0

    def test_future_news_no_decay(self):
        news_time = datetime(2024, 1, 1, 11, 0, 0)
        current = datetime(2024, 1, 1, 10, 0, 0)  # Before news
        result = apply_decay(0.8, news_time, current)
        assert result == 0.8

    def test_heavy_decay_over_long_time(self):
        news_time = datetime(2024, 1, 1, 9, 0, 0)
        current = datetime(2024, 1, 1, 13, 0, 0)  # 4 hours = 8 intervals
        result = apply_decay(1.0, news_time, current)
        # 0.85^8 ≈ 0.2725
        assert result < 0.3
        assert result > 0.2

    def test_is_stale_true(self):
        news_time = datetime(2024, 1, 1, 9, 0, 0)
        current = datetime(2024, 1, 1, 14, 0, 0)  # 5 hours
        assert is_stale(news_time, current, max_age_minutes=240) is True

    def test_is_stale_false(self):
        news_time = datetime(2024, 1, 1, 10, 0, 0)
        current = datetime(2024, 1, 1, 11, 0, 0)  # 1 hour
        assert is_stale(news_time, current, max_age_minutes=240) is False
