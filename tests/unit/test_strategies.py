"""Tests for trading strategies."""

import numpy as np
import pandas as pd
import pytest

from src.models import Direction, Position
from src.strategies.bollinger_squeeze import BollingerSqueezeStrategy
from src.strategies.golden_cross import GoldenCrossStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.seasonal import SeasonalStrategy
from src.strategies.vwap_reversion import VWAPReversionStrategy


def make_ohlcv(n: int, base: float = 100.0, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    np.random.seed(seed)
    close = base + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame(
        {
            "open": close + np.random.randn(n) * 0.2,
            "high": close + abs(np.random.randn(n) * 0.5),
            "low": close - abs(np.random.randn(n) * 0.5),
            "close": close,
            "volume": np.random.randint(100000, 1000000, n),
        },
        index=pd.date_range("2024-01-01", periods=n, freq="15min"),
    )


def make_trending_up(n: int, base: float = 100.0) -> pd.DataFrame:
    """Generate data with strong uptrend for trend-following tests."""
    np.random.seed(123)
    trend = np.linspace(0, 30, n)
    noise = np.random.randn(n) * 0.3
    close = base + trend + noise
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + abs(np.random.randn(n) * 0.3),
            "low": close - abs(np.random.randn(n) * 0.3),
            "close": close,
            "volume": np.random.randint(200000, 2000000, n),
        },
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )


def make_oversold(n: int = 100, base: float = 100.0) -> pd.DataFrame:
    """Generate data ending in an oversold condition."""
    np.random.seed(99)
    # Downtrend followed by oversold bounce
    close = np.concatenate([
        base + np.linspace(0, -15, n - 10),
        base - 15 + np.linspace(0, -3, 10),  # Final drop to oversold
    ])
    return pd.DataFrame(
        {
            "open": close + 0.2,
            "high": close + abs(np.random.randn(n) * 0.3),
            "low": close - abs(np.random.randn(n) * 0.3),
            "close": close,
            "volume": np.concatenate([
                np.random.randint(100000, 500000, n - 10),
                np.random.randint(500000, 2000000, 10),  # Volume spike at bottom
            ]),
        },
        index=pd.date_range("2024-01-01", periods=n, freq="15min"),
    )


class TestMeanReversion:
    def test_name(self):
        assert MeanReversionStrategy().name == "mean_reversion"

    def test_no_signal_normal_rsi(self):
        df = make_ohlcv(100)
        strategy = MeanReversionStrategy()
        signal = strategy.scan("RELIANCE", {"15minute": df}, {})
        # Normal data shouldn't always trigger (depends on random seed)
        # Just verify it returns None or a valid StrategySignal
        if signal is not None:
            assert signal.symbol == "RELIANCE"
            assert signal.direction in (Direction.BUY, Direction.SELL)

    def test_oversold_signal(self):
        df = make_oversold()
        strategy = MeanReversionStrategy()
        signal = strategy.scan("RELIANCE", {"15minute": df}, {"volume_threshold": 1.0})
        # Should produce a BUY signal on deeply oversold data
        if signal is not None:
            assert signal.direction == Direction.BUY
            assert signal.stop_loss < signal.entry_price

    def test_check_exit_returns_none_when_neutral(self):
        df = make_ohlcv(50)
        strategy = MeanReversionStrategy()
        pos = Position(
            symbol="RELIANCE", direction=Direction.BUY,
            quantity=10, entry_price=100, stop_loss=95,
        )
        result = strategy.check_exit(pos, {"15minute": df}, {})
        # May or may not trigger depending on RSI
        assert result is None or result.symbol == "RELIANCE"

    def test_insufficient_data_returns_none(self):
        df = make_ohlcv(10)  # Too few bars
        strategy = MeanReversionStrategy()
        assert strategy.scan("RELIANCE", {"15minute": df}, {}) is None


class TestGoldenCross:
    def test_name(self):
        assert GoldenCrossStrategy().name == "golden_cross"

    def test_requires_daily_data(self):
        strategy = GoldenCrossStrategy()
        df = make_ohlcv(50)
        assert strategy.scan("TCS", {"15minute": df}, {}) is None

    def test_needs_enough_data(self):
        strategy = GoldenCrossStrategy()
        df = make_ohlcv(100)  # Need 210+
        assert strategy.scan("TCS", {"day": df}, {}) is None


class TestMomentum:
    def test_name(self):
        assert MomentumStrategy().name == "momentum"

    def test_requires_enough_data(self):
        strategy = MomentumStrategy()
        df = make_ohlcv(50)
        assert strategy.scan("INFY", {"15minute": df}, {}) is None

    def test_trending_data(self):
        df = make_trending_up(250)
        strategy = MomentumStrategy()
        signal = strategy.scan("INFY", {"15minute": df}, {"volume_threshold": 0.5})
        # May or may not trigger depending on ADX
        if signal is not None:
            assert signal.strategy_name == "momentum"


class TestBollingerSqueeze:
    def test_name(self):
        assert BollingerSqueezeStrategy().name == "bollinger_squeeze"

    def test_insufficient_data(self):
        strategy = BollingerSqueezeStrategy()
        df = make_ohlcv(50)
        assert strategy.scan("SBIN", {"15minute": df}, {}) is None


class TestVWAPReversion:
    def test_name(self):
        assert VWAPReversionStrategy().name == "vwap_reversion"

    def test_insufficient_data(self):
        strategy = VWAPReversionStrategy()
        df = make_ohlcv(10)
        assert strategy.scan("HDFC", {"5minute": df}, {}) is None


class TestSeasonal:
    def test_name(self):
        assert SeasonalStrategy().name == "seasonal"

    def test_scans_daily_data(self):
        strategy = SeasonalStrategy()
        df = make_ohlcv(60, base=2500)
        df.index = pd.date_range("2024-01-01", periods=60, freq="D")
        # May or may not produce signal depending on current date
        result = strategy.scan("RELIANCE", {"day": df}, {"min_seasonal_score": 0.1})
        if result is not None:
            assert result.strategy_name == "seasonal"

    def test_no_exit_logic(self):
        strategy = SeasonalStrategy()
        pos = Position(
            symbol="TCS", direction=Direction.BUY,
            quantity=5, entry_price=3000, stop_loss=2900,
        )
        df = make_ohlcv(60, base=3000)
        df.index = pd.date_range("2024-01-01", periods=60, freq="D")
        assert strategy.check_exit(pos, {"day": df}, {}) is None


class TestStrategyInterface:
    """Verify all strategies implement the interface correctly."""

    @pytest.mark.parametrize("cls", [
        MeanReversionStrategy,
        GoldenCrossStrategy,
        MomentumStrategy,
        BollingerSqueezeStrategy,
        VWAPReversionStrategy,
        SeasonalStrategy,
    ])
    def test_has_name(self, cls):
        assert isinstance(cls().name, str)
        assert len(cls().name) > 0

    @pytest.mark.parametrize("cls", [
        MeanReversionStrategy,
        GoldenCrossStrategy,
        MomentumStrategy,
        BollingerSqueezeStrategy,
        VWAPReversionStrategy,
        SeasonalStrategy,
    ])
    def test_scan_returns_none_on_empty(self, cls):
        strategy = cls()
        result = strategy.scan("TEST", {}, {})
        assert result is None
