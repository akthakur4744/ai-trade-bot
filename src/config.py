"""Configuration loader with pydantic validation and YAML merging."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


# --- Sub-models ---


class PaperConfig(BaseModel):
    slippage_bps: int = 5
    fill_delay_ms: int = 100


class LiveConfig(BaseModel):
    order_type: str = "MARKET"
    exchange: str = "NSE"
    product: str = "MIS"


class AutoSellConfig(BaseModel):
    """Configuration for the auto-sell exit system."""
    gtt_enabled: bool = True  # Place GTT OCO on Zerodha for exchange-level protection
    gtt_update_threshold_pct: float = 0.5  # Only update GTT if trailing SL improves by this %
    gtt_update_cooldown_sec: int = 60  # Min seconds between GTT updates
    gtt_max_retries: int = 3  # Retries for GTT placement failures


class ExecutionConfig(BaseModel):
    mode: Literal["paper", "live"] = "paper"
    paper: PaperConfig = PaperConfig()
    live: LiveConfig = LiveConfig()
    auto_sell: AutoSellConfig = AutoSellConfig()


class RiskConfig(BaseModel):
    max_capital_per_trade: float = 10000
    max_daily_loss: float = 1000
    max_open_positions: int = 3
    max_capital_deployed: float = 30000
    per_trade_risk_pct: float = 0.02
    position_sizing_method: Literal["fixed_pct", "atr", "kelly"] = "fixed_pct"


class MarketConfig(BaseModel):
    open_time: str = "09:15"
    close_time: str = "15:30"
    timezone: str = "Asia/Kolkata"
    scan_interval_minutes: int = 15


class DataConfig(BaseModel):
    candle_intervals: list[str] = ["5minute", "15minute", "day"]
    lookback_days: int = 60
    rate_limit_per_sec: int = 3


class RSIConfig(BaseModel):
    period: int = 14
    overbought: int = 70
    oversold: int = 30


class EMAConfig(BaseModel):
    short: int = 20
    medium: int = 50
    long: int = 200


class ATRConfig(BaseModel):
    period: int = 14


class MACDConfig(BaseModel):
    fast: int = 12
    slow: int = 26
    signal: int = 9


class BollingerConfig(BaseModel):
    period: int = 20
    std_dev: float = 2.0


class VWAPConfig(BaseModel):
    session_reset: bool = True


class ADXConfig(BaseModel):
    period: int = 14
    trend_threshold: int = 25


class IndicatorsConfig(BaseModel):
    rsi: RSIConfig = RSIConfig()
    ema: EMAConfig = EMAConfig()
    atr: ATRConfig = ATRConfig()
    macd: MACDConfig = MACDConfig()
    bollinger: BollingerConfig = BollingerConfig()
    vwap: VWAPConfig = VWAPConfig()
    adx: ADXConfig = ADXConfig()


class ScoringWeights(BaseModel):
    news_strength: float = 0.25
    signal_alignment: float = 0.30
    market_confirmation: float = 0.25
    liquidity_score: float = 0.10
    risk_penalty: float = 0.20


class FilterConfig(BaseModel):
    min_confidence: float = 0.65
    min_market_confirmation: float = 0.6
    min_liquidity_score: float = 0.6
    max_risk_penalty: float = 0.4


class RankingWeights(BaseModel):
    confidence: float = 0.4
    signal_alignment: float = 0.3
    market_confirmation: float = 0.2
    news_strength: float = 0.1


class ScoringConfig(BaseModel):
    weights: ScoringWeights = ScoringWeights()
    filters: FilterConfig = FilterConfig()
    ranking: RankingWeights = RankingWeights()
    sentiment_decay_pct: float = 0.15
    sentiment_decay_interval_min: int = 30
    macro_guard_max_bullish: float = 0.6


class AgentConfig(BaseModel):
    model: str = "claude-sonnet-4-20250514"
    max_retries: int = 5
    timeout_seconds: int = 30
    max_tokens: int = 2048


class NotificationsConfig(BaseModel):
    enabled: bool = True
    channels: list[str] = ["telegram"]


class StrategyToggle(BaseModel):
    enabled: bool = False


class StrategiesConfig(BaseModel):
    mean_reversion: StrategyToggle = StrategyToggle(enabled=True)
    momentum: StrategyToggle = StrategyToggle(enabled=True)
    bollinger_squeeze: StrategyToggle = StrategyToggle(enabled=True)
    golden_cross: StrategyToggle = StrategyToggle(enabled=True)
    vwap_reversion: StrategyToggle = StrategyToggle(enabled=True)
    fundamental_technical: StrategyToggle = StrategyToggle(enabled=False)
    pairs_trading: StrategyToggle = StrategyToggle(enabled=False)
    seasonal: StrategyToggle = StrategyToggle(enabled=False)


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///insight_alpha.db"

    @field_validator("url", mode="before")
    @classmethod
    def _expand_env(cls, v: str) -> str:
        """Expand ${VAR} tokens from environment.

        If the token remains unexpanded (env var not set), fall back to a
        local SQLite file so offline dev still works. Production deploys must
        set the env var — callers should surface this via logging.
        """
        if not isinstance(v, str):
            return v
        expanded = os.path.expandvars(v)
        if "${" in expanded:
            mode = os.getenv("EXECUTION_MODE", "paper")
            return f"sqlite:///insight_alpha_{mode}.db"
        return expanded


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "json"


class WatchlistSymbol(BaseModel):
    symbol: str
    exchange: str = "NSE"
    sector: str = ""


class WatchlistConfig(BaseModel):
    symbols: list[WatchlistSymbol] = []


# --- Root config ---


class AppConfig(BaseModel):
    execution: ExecutionConfig = ExecutionConfig()
    risk: RiskConfig = RiskConfig()
    market: MarketConfig = MarketConfig()
    data: DataConfig = DataConfig()
    indicators: IndicatorsConfig = IndicatorsConfig()
    scoring: ScoringConfig = ScoringConfig()
    agents: AgentConfig = AgentConfig()
    notifications: NotificationsConfig = NotificationsConfig()
    strategies: StrategiesConfig = StrategiesConfig()
    database: DatabaseConfig = DatabaseConfig()
    logging: LoggingConfig = LoggingConfig()
    watchlist: WatchlistConfig = WatchlistConfig()


# --- Loader ---

CONFIG_DIR = Path(__file__).parent.parent / "config"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base dict."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(mode: str | None = None, config_dir: Path | None = None) -> AppConfig:
    """Load config by merging default.yaml + mode overlay + env vars.

    Args:
        mode: "paper" or "live". If None, reads from EXECUTION_MODE env var or defaults to "paper".
        config_dir: Override config directory path.
    """
    config_dir = config_dir or CONFIG_DIR

    # Load default config
    default_path = config_dir / "default.yaml"
    if default_path.exists():
        with open(default_path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # Determine mode
    mode = mode or os.getenv("EXECUTION_MODE", "paper")

    # Merge mode overlay
    overlay_path = config_dir / f"{mode}.yaml"
    if overlay_path.exists():
        with open(overlay_path) as f:
            overlay = yaml.safe_load(f) or {}
        data = _deep_merge(data, overlay)

    # Load watchlist
    watchlist_path = config_dir / "watchlist.yaml"
    if watchlist_path.exists():
        with open(watchlist_path) as f:
            watchlist_data = yaml.safe_load(f) or {}
        data["watchlist"] = watchlist_data

    # Apply env var overrides for secrets (not stored in YAML)
    # These are accessed via os.getenv() at usage sites, not in config

    return AppConfig(**data)
