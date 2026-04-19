"""Tests for technical indicators."""

import numpy as np
import pandas as pd
import pytest

from src.indicators.atr import compute_atr
from src.indicators.bollinger import compute_bandwidth, compute_bollinger_bands
from src.indicators.macd import compute_macd, detect_macd_crossover
from src.indicators.moving_averages import compute_ema, compute_sma, detect_crossover
from src.indicators.rsi import compute_rsi
from src.indicators.volume import compute_obv, detect_volume_spike


@pytest.fixture
def sample_df():
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame({
        "open": close + np.random.randn(n) * 0.2,
        "high": close + abs(np.random.randn(n) * 0.5),
        "low": close - abs(np.random.randn(n) * 0.5),
        "close": close,
        "volume": np.random.randint(100000, 1000000, n),
    })


class TestRSI:
    def test_output_range(self, sample_df):
        rsi = compute_rsi(sample_df)
        valid = rsi.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_period_respected(self, sample_df):
        rsi = compute_rsi(sample_df, period=14)
        # First 13 values should be NaN (need 14 periods)
        assert rsi.iloc[:13].isna().all()

    def test_custom_period(self, sample_df):
        rsi_7 = compute_rsi(sample_df, period=7)
        rsi_21 = compute_rsi(sample_df, period=21)
        # Different periods produce different values
        assert not rsi_7.dropna().equals(rsi_21.dropna())


class TestMovingAverages:
    def test_ema_smoothing(self, sample_df):
        ema = compute_ema(sample_df, period=20)
        assert len(ema) == len(sample_df)
        # EMA should be less volatile than raw close
        assert ema.std() < sample_df["close"].std()

    def test_sma_is_simple_average(self, sample_df):
        sma = compute_sma(sample_df, period=5)
        # Check a specific value
        expected = sample_df["close"].iloc[0:5].mean()
        assert abs(sma.iloc[4] - expected) < 1e-10

    def test_crossover_detection(self, sample_df):
        fast = compute_ema(sample_df, period=10)
        slow = compute_ema(sample_df, period=30)
        crossovers = detect_crossover(fast, slow)
        assert set(crossovers.unique()).issubset({-1, 0, 1})


class TestATR:
    def test_positive_values(self, sample_df):
        atr = compute_atr(sample_df)
        valid = atr.dropna()
        assert (valid > 0).all()

    def test_reflects_volatility(self):
        # High volatility data should have higher ATR
        low_vol = pd.DataFrame({
            "open": [100] * 30, "high": [101] * 30,
            "low": [99] * 30, "close": [100] * 30, "volume": [1000] * 30,
        })
        high_vol = pd.DataFrame({
            "open": [100] * 30, "high": [110] * 30,
            "low": [90] * 30, "close": [100] * 30, "volume": [1000] * 30,
        })
        atr_low = compute_atr(low_vol, period=14).iloc[-1]
        atr_high = compute_atr(high_vol, period=14).iloc[-1]
        assert atr_high > atr_low


class TestMACD:
    def test_output_shape(self, sample_df):
        macd_line, signal_line, histogram = compute_macd(sample_df)
        assert len(macd_line) == len(sample_df)
        assert len(signal_line) == len(sample_df)
        assert len(histogram) == len(sample_df)

    def test_histogram_is_difference(self, sample_df):
        macd_line, signal_line, histogram = compute_macd(sample_df)
        diff = macd_line - signal_line
        np.testing.assert_array_almost_equal(histogram.values, diff.values)

    def test_crossover_detection(self, sample_df):
        macd_line, signal_line, _ = compute_macd(sample_df)
        crossovers = detect_macd_crossover(macd_line, signal_line)
        assert set(crossovers.unique()).issubset({-1, 0, 1})


class TestBollinger:
    def test_band_ordering(self, sample_df):
        upper, middle, lower = compute_bollinger_bands(sample_df)
        valid_idx = middle.dropna().index
        assert (upper[valid_idx] >= middle[valid_idx]).all()
        assert (middle[valid_idx] >= lower[valid_idx]).all()

    def test_bandwidth_positive(self, sample_df):
        upper, middle, lower = compute_bollinger_bands(sample_df)
        bw = compute_bandwidth(upper, lower, middle)
        valid = bw.dropna()
        assert (valid >= 0).all()


class TestVolume:
    def test_obv_direction(self):
        df = pd.DataFrame({
            "close": [100, 101, 102, 101, 100],
            "volume": [1000, 1000, 1000, 1000, 1000],
        })
        obv = compute_obv(df)
        # Up days add volume, down days subtract
        assert obv.iloc[1] > obv.iloc[0]  # Price up
        assert obv.iloc[3] < obv.iloc[2]  # Price down

    def test_volume_spike(self, sample_df):
        spikes = detect_volume_spike(sample_df, multiplier=2.0, window=20)
        assert spikes.dtype == bool
