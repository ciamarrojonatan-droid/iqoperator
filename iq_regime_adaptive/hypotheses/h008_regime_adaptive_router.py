"""
h008_regime_adaptive_router.py - Meta-Ensemble Regime-Adaptive Signal Router.

Hypothesis ID: H008_REGIME_ADAPTIVE_ENSEMBLE_ROUTER
Family: META_ENSEMBLE_ROUTER
Microstructural Rationale:
Financial markets switch non-linearly across volatility and trend regimes. Static setups
suffer deep drawdowns during regime mismatch. H008 dynamically classifies market dynamics
into four regimes (TREND, RANGE, EXPANSION, CHAOS), routes signals to matched specialists,
and enforces a non-bypassable NO-TRADE VETO during CHAOS or turbulent volatility shocks.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.regime_classifier import (
    MarketRegime,
    RegimeClassifier,
)
from iq_regime_adaptive.feature_engine.signal_router import MarketSignal
from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis
from iq_regime_adaptive.hypotheses.h001_range_mean_reversion import H001RangeMeanReversion
from iq_regime_adaptive.hypotheses.h002_trend_pullback import H002TrendPullback
from iq_regime_adaptive.hypotheses.h003_volatility_expansion import H003VolatilityExpansion
from iq_regime_adaptive.hypotheses.h004_autocorrelation_reversion import H004AutocorrelationReversion
from iq_regime_adaptive.hypotheses.h005_mtf_trend_alignment import H005MTFTrendAlignment
from iq_regime_adaptive.hypotheses.h007_squeeze_breakout import H007SqueezeBreakout


class H008RegimeAdaptiveRouter(BaseHypothesis):
    """
    H008: Full Regime-Adaptive Meta-Router (5-Tier Classification + Strict Chaos Veto).
    """

    def __init__(
        self,
        classifier: Optional[RegimeClassifier] = None,
        default_horizon_bars: int = 1,
        default_payout_hurdle: float = 0.75,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = {}
        if parameters:
            params.update(parameters)
        super().__init__(
            hypothesis_id="H008_REGIME_ADAPTIVE_ENSEMBLE_ROUTER",
            family="META_ENSEMBLE_ROUTER",
            name="Regime-Adaptive Meta-Router",
            description="Dynamically routes signals across regimes with strict Chaos veto.",
            default_horizon_bars=default_horizon_bars,
            default_payout_hurdle=default_payout_hurdle,
            parameters=params,
        )
        self.classifier = classifier or RegimeClassifier()
        # Sub-hypotheses
        self.h1 = H001RangeMeanReversion()
        self.h2 = H002TrendPullback()
        self.h3 = H003VolatilityExpansion()
        self.h4 = H004AutocorrelationReversion()
        self.h5 = H005MTFTrendAlignment()
        self.h7 = H007SqueezeBreakout()

    def generate_signals(self, df: pd.DataFrame, payout: float = 0.85) -> pd.Series:
        self.validate_df(df)
        n = len(df)
        signals = pd.Series(MarketSignal.NO_TRADE.value, index=df.index, name="signal")

        if payout < self.default_payout_hurdle:
            return signals

        if n < self.classifier.min_candles:
            return signals

        # 1. Compute rolling regime classification series
        regime_series = self.classifier.classify_series(df)

        # 2. Compute candidate signals from specialists
        s1 = self.h1.generate_signals(df, payout=payout)
        s2 = self.h2.generate_signals(df, payout=payout)
        s3 = self.h3.generate_signals(df, payout=payout)
        s4 = self.h4.generate_signals(df, payout=payout)
        s5 = self.h5.generate_signals(df, payout=payout)
        s7 = self.h7.generate_signals(df, payout=payout)

        # 3. Route according to regime (Vectorized)
        
        # Helper mappings
        call = MarketSignal.CALL.value
        put = MarketSignal.PUT.value
        no_trade = MarketSignal.NO_TRADE.value

        def resolve_vec(s_a, s_b):
            cond_conflict = ((s_a == call) & (s_b == put)) | ((s_a == put) & (s_b == call))
            cond_call = (s_a == call) | (s_b == call)
            cond_put = (s_a == put) | (s_b == put)
            return np.where(cond_conflict, no_trade, np.where(cond_call, call, np.where(cond_put, put, no_trade)))

        routed_range = resolve_vec(s1, s4)
        routed_trend = resolve_vec(s2, s5)
        routed_exp = resolve_vec(s3, s7)

        # Apply regimes
        signals_arr = np.full(n, no_trade, dtype=object)
        
        is_range = (regime_series == MarketRegime.RANGE.value)
        is_trend = (regime_series == MarketRegime.TREND.value)
        is_exp = (regime_series == MarketRegime.EXPANSION.value)
        
        signals_arr = np.where(is_range, routed_range, signals_arr)
        signals_arr = np.where(is_trend, routed_trend, signals_arr)
        signals_arr = np.where(is_exp, routed_exp, signals_arr)
        
        signals[:] = signals_arr

        return signals
