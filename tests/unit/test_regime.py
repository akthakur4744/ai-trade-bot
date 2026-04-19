"""Tests for HMM-based market regime detector."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models import MarketRegime
from src.regime.detector import RegimeDetector


def _make_daily_data(n: int = 500, seed: int = 42, trend: float = 0.0) -> pd.DataFrame:
    """Generate synthetic daily close prices."""
    np.random.seed(seed)
    returns = np.random.randn(n) * 0.01 + trend
    close = 20000 * np.exp(np.cumsum(returns))
    return pd.DataFrame(
        {"close": close},
        index=pd.date_range("2022-01-01", periods=n, freq="B"),
    )


def _make_bull_data(n: int = 500) -> pd.DataFrame:
    """Strong uptrend data."""
    return _make_daily_data(n, seed=10, trend=0.001)


def _make_bear_data(n: int = 500) -> pd.DataFrame:
    """Strong downtrend data."""
    return _make_daily_data(n, seed=20, trend=-0.001)


class TestRegimeDetector:
    def test_not_trained_returns_default(self):
        detector = RegimeDetector()
        assert not detector.is_trained
        result = detector.predict(_make_daily_data())
        assert result == MarketRegime.RANGE_BOUND

    def test_train_succeeds_with_sufficient_data(self):
        detector = RegimeDetector()
        data = _make_daily_data(500)
        success = detector.train(data)
        assert success is True
        assert detector.is_trained

    def test_train_fails_with_insufficient_data(self):
        detector = RegimeDetector()
        data = _make_daily_data(30)
        success = detector.train(data)
        assert success is False
        assert not detector.is_trained

    def test_predict_after_training(self):
        detector = RegimeDetector()
        data = _make_daily_data(500)
        detector.train(data)
        regime = detector.predict(data)
        assert isinstance(regime, MarketRegime)
        assert regime in list(MarketRegime)

    def test_predict_probabilities(self):
        detector = RegimeDetector()
        data = _make_daily_data(500)
        detector.train(data)
        probs = detector.predict_probabilities(data)
        assert isinstance(probs, dict)
        total = sum(probs.values())
        assert abs(total - 1.0) < 0.01

    def test_predict_probabilities_not_trained(self):
        detector = RegimeDetector()
        probs = detector.predict_probabilities(_make_daily_data())
        # Default: equal probabilities
        assert all(abs(v - 0.25) < 0.01 for v in probs.values())

    def test_train_with_vix(self):
        detector = RegimeDetector()
        data = _make_daily_data(500)
        np.random.seed(99)
        vix = pd.Series(15 + np.random.randn(500) * 3, index=data.index)
        success = detector.train(data, vix_series=vix)
        assert success is True

    def test_predict_with_vix(self):
        detector = RegimeDetector()
        data = _make_daily_data(500)
        np.random.seed(99)
        vix = pd.Series(15 + np.random.randn(500) * 3, index=data.index)
        detector.train(data, vix_series=vix)
        regime = detector.predict(data, vix_series=vix)
        assert isinstance(regime, MarketRegime)

    def test_missing_close_column(self):
        detector = RegimeDetector()
        data = pd.DataFrame({"open": [1, 2, 3]})
        assert detector.train(data) is False

    def test_state_labeling_produces_all_regimes(self):
        detector = RegimeDetector()
        data = _make_daily_data(500)
        detector.train(data)
        assigned = set(detector._state_map.values())
        # All 4 regimes should be assigned to some state
        assert len(assigned) == 4

    def test_predict_empty_data(self):
        detector = RegimeDetector()
        data = _make_daily_data(500)
        detector.train(data)
        empty = pd.DataFrame({"close": []})
        assert detector.predict(empty) == MarketRegime.RANGE_BOUND
