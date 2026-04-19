"""Tests for config loading."""

from pathlib import Path

import pytest

from src.config import AppConfig, load_config


CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class TestConfigLoading:
    def test_load_defaults(self):
        config = load_config(mode="paper", config_dir=CONFIG_DIR)
        assert isinstance(config, AppConfig)
        assert config.execution.mode == "paper"
        assert config.risk.max_capital_per_trade == 10000
        assert config.risk.max_daily_loss == 1000
        assert config.risk.max_open_positions == 3

    def test_paper_overlay(self):
        config = load_config(mode="paper", config_dir=CONFIG_DIR)
        assert config.execution.mode == "paper"
        assert config.logging.level == "DEBUG"  # Paper overrides to DEBUG

    def test_live_overlay(self):
        config = load_config(mode="live", config_dir=CONFIG_DIR)
        assert config.execution.mode == "live"
        assert config.risk.max_capital_per_trade == 5000  # Stricter in live
        assert config.risk.max_daily_loss == 500

    def test_watchlist_loaded(self):
        config = load_config(mode="paper", config_dir=CONFIG_DIR)
        assert len(config.watchlist.symbols) > 0
        symbols = [s.symbol for s in config.watchlist.symbols]
        assert "RELIANCE" in symbols
        assert "TCS" in symbols

    def test_indicator_defaults(self):
        config = load_config(mode="paper", config_dir=CONFIG_DIR)
        assert config.indicators.rsi.period == 14
        assert config.indicators.ema.short == 20
        assert config.indicators.ema.long == 200
        assert config.indicators.macd.fast == 12

    def test_scoring_weights_sum(self):
        config = load_config(mode="paper", config_dir=CONFIG_DIR)
        w = config.scoring.weights
        # Weights before penalty should sum to ~0.9 (penalty is subtracted)
        total = w.news_strength + w.signal_alignment + w.market_confirmation + w.liquidity_score
        assert abs(total - 0.9) < 0.01

    def test_strategies_defaults(self):
        config = load_config(mode="paper", config_dir=CONFIG_DIR)
        assert config.strategies.mean_reversion.enabled is True
        assert config.strategies.pairs_trading.enabled is False
