"""
h004_autocorrelation_reversion.py - Negative Serial Correlation Mean Reversion.

Hypothesis ID: H004_AUTOCORRELATION_MEAN_REVERSION
Family: STATISTICAL_MICROSTRUCTURE
Microstructural Rationale:
On short binary horizons (M1 to M5), periods of high negative first-order return
autocorrelation (rho_1 < -0.15) indicate microstructure bid-ask bounce and inventory
balancing. Under negative autocorrelation, extreme return z-score excursions exhibit
a high conditional probability of immediate mean-reverting reversal.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.indicators import (
    compute_return_autocorrelation,
)
from iq_regime_adaptive.feature_engine.signal_router import MarketSignal
from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis


class H004AutocorrelationReversion(BaseHypothesis):
    """
    H004: Autocorrelation Mean Reversion (Negative Serial Correlation + Return Z-Score Exhaustion).
    """

    def __init__(
        self,
        window: int = 30,
        rho_threshold: float = -0.15,
        z_threshold: float = 1.65,
        default_horizon_bars: int = 1,
        default_payout_hurdle: float = 0.75,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = {
            "window": window,
            "rho_threshold": rho_threshold,
            "z_threshold": z_threshold,
        }
        if parameters:
            params.update(parameters)
        super().__init__(
            hypothesis_id="H004_AUTOCORRELATION_MEAN_REVERSION",
            family="STATISTICAL_MICROSTRUCTURE",
            name="Autocorrelation Mean Reversion",
            description="Exploits negative return autocorrelation for statistical reversal on extreme excursions.",
            default_horizon_bars=default_horizon_bars,
            default_payout_hurdle=default_payout_hurdle,
            parameters=params,
        )

    def generate_signals(self, df: pd.DataFrame, payout: float = 0.85) -> pd.Series:
        self.validate_df(df)
        n = len(df)
        signals = pd.Series(MarketSignal.NO_TRADE.value, index=df.index, name="signal")

        if payout < self.default_payout_hurdle:
            return signals

        close = df["close"]
        p = self.parameters
        w = p["window"]
        rho_thresh = p["rho_threshold"]
        z_thresh = p["z_threshold"]

        if n < w + 5:
            return signals

        # 1. Log returns
        returns = np.log(close / close.shift(1).replace(0, np.nan)).fillna(0.0)

        # 2. Rolling lag-1 autocorrelation
        rho_1, _ = compute_return_autocorrelation(close, window=w, lag=1)

        # 3. Rolling Return Z-Score
        ret_mean = returns.rolling(window=w, min_periods=max(5, w // 2)).mean()
        ret_std = returns.rolling(window=w, min_periods=max(5, w // 2)).std().replace(0, np.nan)
        z_score = (returns - ret_mean) / ret_std

        # Mean reversion condition:
        # Negative serial correlation present
        is_anti_persistent = rho_1 <= rho_thresh

        # CALL: Sharp downward excursion with negative autocorrelation -> expect bounce up
        call_cond = is_anti_persistent & (z_score <= -z_thresh)

        # PUT: Sharp upward excursion with negative autocorrelation -> expect pullback down
        put_cond = is_anti_persistent & (z_score >= z_thresh)

        signals[call_cond] = MarketSignal.CALL.value
        signals[put_cond] = MarketSignal.PUT.value
        signals[call_cond & put_cond] = MarketSignal.NO_TRADE.value

        return signals
