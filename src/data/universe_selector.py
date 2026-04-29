"""Dynamic stock universe selector.

Scores each candidate in the extended universe using daily candles
and returns the top N to supplement the static core watchlist.

Scoring formula (all components 0-1):
  RSI extreme  40%  abs(rsi-50)/20   — high setup potential at extremes
  Volume spike 30%  min(1, ratio/2)  — 2× avg volume = full score
  ADX strength 20%  (adx-15)/25      — 15→0, 40→1
  EMA align    10%  (align+1)/2      — bullish=1, neutral=0.5, bearish=0

Regime sector boosts (+0.08) applied before ranking.
Sector cap: max 5 per sector in the final selection.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from src.models import MarketRegime

logger = structlog.get_logger(__name__)

_MAX_PER_SECTOR = 5
_SECTOR_BOOST = 0.08

_REGIME_BOOSTED_SECTORS: Dict[MarketRegime, List[str]] = {
    MarketRegime.BULL: ["IT", "Banking", "Finance", "Auto", "Infrastructure"],
    MarketRegime.BEAR: ["Pharma", "Healthcare", "FMCG", "Power", "Energy"],
    MarketRegime.RANGE_BOUND: ["FMCG", "Pharma", "Consumer", "Healthcare"],
    MarketRegime.CHOPPY: [],
}


def _score_symbol(df_day: Any, sector: str, regime: Optional[MarketRegime]) -> float:
    """Compute composite setup score for a single symbol using daily candles."""
    from src.indicators.adx import compute_adx
    from src.indicators.moving_averages import compute_ema_alignment
    from src.indicators.rsi import compute_rsi
    from src.indicators.volume import compute_volume_ratio

    if df_day is None or len(df_day) < 30:
        return 0.0

    try:
        rsi_val = float(compute_rsi(df_day, period=14).iloc[-1])
        rsi_score = min(1.0, abs(rsi_val - 50) / 20) if rsi_val == rsi_val else 0.0

        vol_ratio = float(compute_volume_ratio(df_day).iloc[-1])
        vol_score = min(1.0, vol_ratio / 2.0) if vol_ratio == vol_ratio else 0.0

        adx_val = float(compute_adx(df_day, period=14)[0].iloc[-1])
        adx_score = min(1.0, max(0.0, (adx_val - 15) / 25)) if adx_val == adx_val else 0.0

        align_val = float(compute_ema_alignment(df_day).iloc[-1])
        ema_score = (align_val + 1) / 2  # -1/0/1 → 0/0.5/1.0

        score = (rsi_score * 0.40) + (vol_score * 0.30) + (adx_score * 0.20) + (ema_score * 0.10)

        if regime is not None and sector in _REGIME_BOOSTED_SECTORS.get(regime, []):
            score = min(1.0, score + _SECTOR_BOOST)

        return round(score, 4)

    except Exception as e:
        logger.warning("universe_score_error", sector=sector, error=str(e))
        return 0.0


def select_dynamic_universe(
    instrument_tokens: Dict[str, int],
    extended_candidates: List[Dict[str, str]],
    core_symbols: List[str],
    market_data_fetcher: Any,
    config_data: Any,
    regime: Optional[MarketRegime],
    n: int = 20,
) -> List[str]:
    """Score extended candidates and return top N symbols by composite score.

    Args:
        instrument_tokens: Kite symbol → token map (must include extended universe).
        extended_candidates: List of {"symbol": str, "sector": str} from extended_universe.yaml.
        core_symbols: Already-scanned core 30 (excluded from dynamic selection).
        market_data_fetcher: MarketDataFetcher instance for daily candle fetches.
        config_data: DataConfig (provides lookback_days).
        regime: Current market regime for sector tilts; None = no tilt.
        n: Number of dynamic stocks to select (default 20).

    Returns:
        List of up to n symbols to append to the scan universe.
    """
    core_set = set(core_symbols)
    scored: List[tuple[str, str, float]] = []

    for candidate in extended_candidates:
        symbol = candidate.get("symbol", "")
        sector = candidate.get("sector", "")

        if symbol in core_set:
            continue

        token = instrument_tokens.get(symbol)
        if token is None:
            continue

        try:
            df_day = market_data_fetcher.get_historical_data(
                instrument_token=token,
                interval="day",
                lookback_days=config_data.lookback_days,
            )
            score = _score_symbol(df_day, sector, regime)
            scored.append((symbol, sector, score))
        except Exception as e:
            logger.warning("universe_fetch_error", symbol=symbol, error=str(e))

    scored.sort(key=lambda x: x[2], reverse=True)

    selected: List[str] = []
    sector_counts: Dict[str, int] = {}

    for symbol, sector, _ in scored:
        if len(selected) >= n:
            break
        if sector_counts.get(sector, 0) >= _MAX_PER_SECTOR:
            continue
        selected.append(symbol)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    logger.info(
        "dynamic_universe_selected",
        count=len(selected),
        regime=regime.value if regime else "none",
        top5=selected[:5],
    )
    return selected
