"""Market regime detector using Hidden Markov Models (HMM).

Classifies market into 4 states:
- BULL: Strong uptrend, low volatility
- BEAR: Strong downtrend, elevated volatility
- RANGE_BOUND: Sideways movement, low volatility
- CHOPPY: High volatility, no clear trend

Features used:
- Rolling returns (20-day)
- Realized volatility (20-day)
- VIX level
- Market breadth (advance/decline ratio)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import structlog
from hmmlearn.hmm import GaussianHMM

from src.models import MarketRegime

logger = structlog.get_logger(__name__)

# Number of hidden states
N_STATES = 4

# Feature computation windows
RETURN_WINDOW = 20
VOLATILITY_WINDOW = 20

# Minimum training samples
MIN_TRAINING_SAMPLES = 100


class RegimeDetector:
    """HMM-based market regime classifier.

    Train on historical Nifty 50 data, then predict current regime
    from a rolling window of features.
    """

    def __init__(self, n_states: int = N_STATES) -> None:
        self._n_states = n_states
        self._model: Optional[GaussianHMM] = None
        self._state_map: dict[int, MarketRegime] = {}
        self._is_trained = False

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    def train(self, nifty_daily: pd.DataFrame, vix_series: Optional[pd.Series] = None) -> bool:
        """Train HMM on historical daily data.

        Args:
            nifty_daily: DataFrame with 'close' column (Nifty 50 daily prices).
            vix_series: Optional India VIX daily series (aligned index with nifty_daily).

        Returns:
            True if training succeeded.
        """
        features = self._compute_features(nifty_daily, vix_series)
        if features is None or len(features) < MIN_TRAINING_SAMPLES:
            logger.warning(
                "regime_insufficient_data",
                samples=0 if features is None else len(features),
                required=MIN_TRAINING_SAMPLES,
            )
            return False

        try:
            self._model = GaussianHMM(
                n_components=self._n_states,
                covariance_type="full",
                n_iter=200,
                random_state=42,
            )
            self._model.fit(features)

            # Map HMM states to regime labels based on state characteristics
            self._state_map = self._label_states(features)
            self._is_trained = True

            logger.info(
                "regime_trained",
                samples=len(features),
                states=self._n_states,
                state_map={v.value: k for k, v in self._state_map.items()},
            )
            return True

        except Exception as e:
            logger.error("regime_training_failed", error=str(e))
            return False

    def predict(
        self,
        nifty_daily: pd.DataFrame,
        vix_series: Optional[pd.Series] = None,
    ) -> MarketRegime:
        """Predict current market regime from recent data.

        Args:
            nifty_daily: Recent daily data (at least RETURN_WINDOW + VOLATILITY_WINDOW bars).
            vix_series: Optional VIX series.

        Returns:
            Current MarketRegime. Defaults to RANGE_BOUND if not trained or data insufficient.
        """
        if not self._is_trained or self._model is None:
            logger.warning("regime_not_trained")
            return MarketRegime.RANGE_BOUND

        features = self._compute_features(nifty_daily, vix_series)
        if features is None or len(features) == 0:
            return MarketRegime.RANGE_BOUND

        try:
            # Predict state for the most recent observation
            states = self._model.predict(features)
            current_state = int(states[-1])
            regime = self._state_map.get(current_state, MarketRegime.RANGE_BOUND)

            logger.info(
                "regime_predicted",
                state=current_state,
                regime=regime.value,
            )
            return regime

        except Exception as e:
            logger.error("regime_prediction_failed", error=str(e))
            return MarketRegime.RANGE_BOUND

    def predict_probabilities(
        self,
        nifty_daily: pd.DataFrame,
        vix_series: Optional[pd.Series] = None,
    ) -> dict[str, float]:
        """Get probability distribution over regimes.

        Returns:
            Dict mapping regime name to probability.
        """
        if not self._is_trained or self._model is None:
            return {r.value: 0.25 for r in MarketRegime}

        features = self._compute_features(nifty_daily, vix_series)
        if features is None or len(features) == 0:
            return {r.value: 0.25 for r in MarketRegime}

        try:
            posteriors = self._model.predict_proba(features)
            last_probs = posteriors[-1]

            result = {}
            for state_idx, prob in enumerate(last_probs):
                regime = self._state_map.get(state_idx, MarketRegime.RANGE_BOUND)
                result[regime.value] = result.get(regime.value, 0.0) + round(float(prob), 4)
            return result

        except Exception as e:
            logger.error("regime_proba_failed", error=str(e))
            return {r.value: 0.25 for r in MarketRegime}

    def _compute_features(
        self,
        nifty_daily: pd.DataFrame,
        vix_series: Optional[pd.Series],
    ) -> Optional[np.ndarray]:
        """Compute feature matrix from price data."""
        if "close" not in nifty_daily.columns:
            logger.warning("regime_missing_close_column")
            return None

        close = nifty_daily["close"].astype(float)
        if len(close) < RETURN_WINDOW + VOLATILITY_WINDOW:
            return None

        # Feature 1: Rolling returns (20-day log returns annualised)
        log_returns = np.log(close / close.shift(1))
        rolling_return = log_returns.rolling(RETURN_WINDOW).mean() * 252

        # Feature 2: Realized volatility (20-day rolling std annualised)
        rolling_vol = log_returns.rolling(VOLATILITY_WINDOW).std() * np.sqrt(252)

        # Feature 3: VIX or volatility proxy
        if vix_series is not None and len(vix_series) == len(close):
            vix_feature = vix_series.astype(float)
        else:
            # Use rolling vol as VIX proxy
            vix_feature = rolling_vol

        # Combine and drop NaNs
        feature_df = pd.DataFrame(
            {
                "return": rolling_return,
                "volatility": rolling_vol,
                "vix": vix_feature,
            }
        ).dropna()

        if len(feature_df) == 0:
            return None

        return feature_df.values

    def _label_states(self, features: np.ndarray) -> dict[int, MarketRegime]:
        """Map HMM state indices to MarketRegime labels.

        Strategy: predict all training data, compute mean return and vol
        for each state, then classify based on characteristics:
        - Highest return, low vol → BULL
        - Lowest return, high vol → BEAR
        - Low vol, near-zero return → RANGE_BOUND
        - High vol, near-zero return → CHOPPY
        """
        states = self._model.predict(features)

        state_stats = {}
        for state in range(self._n_states):
            mask = states == state
            if mask.sum() == 0:
                state_stats[state] = {"return": 0.0, "vol": 1.0}
                continue
            state_features = features[mask]
            state_stats[state] = {
                "return": float(np.mean(state_features[:, 0])),
                "vol": float(np.mean(state_features[:, 1])),
            }

        # Sort states by return
        by_return = sorted(state_stats.keys(), key=lambda s: state_stats[s]["return"])
        # Sort by volatility
        by_vol = sorted(state_stats.keys(), key=lambda s: state_stats[s]["vol"])

        mapping: dict[int, MarketRegime] = {}
        assigned = set()

        # Highest return → BULL
        bull_state = by_return[-1]
        mapping[bull_state] = MarketRegime.BULL
        assigned.add(bull_state)

        # Lowest return → BEAR
        bear_state = by_return[0]
        if bear_state not in assigned:
            mapping[bear_state] = MarketRegime.BEAR
            assigned.add(bear_state)

        # Highest vol among remaining → CHOPPY
        for state in reversed(by_vol):
            if state not in assigned:
                mapping[state] = MarketRegime.CHOPPY
                assigned.add(state)
                break

        # Remaining → RANGE_BOUND
        for state in range(self._n_states):
            if state not in assigned:
                mapping[state] = MarketRegime.RANGE_BOUND

        return mapping
