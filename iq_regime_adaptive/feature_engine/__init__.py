"""
feature_engine package for iq_regime_adaptive.
"""

from iq_regime_adaptive.feature_engine.indicators import (
    compute_atr,
    compute_natr,
    compute_atr_ratio,
    compute_bollinger_bands,
    compute_bollinger_bandwidth,
    compute_bbw_zscore,
    compute_bbw_percentile,
    compute_normalized_realized_volatility,
    compute_parkinson_volatility,
    compute_vol_shock,
    compute_adx,
    compute_return_autocorrelation,
    compute_variance_ratio,
    compute_rolling_variance_ratio,
    compute_rsi,
    compute_stochastic,
    compute_donchian_channels,
    compute_ema,
    compute_candle_morphology,
)
from iq_regime_adaptive.feature_engine.regime_classifier import (
    MarketRegime,
    RegimeOutput,
    RegimeClassifier,
    classify_market_regime,
    classify_regime,
)
from iq_regime_adaptive.feature_engine.signal_router import (
    MarketSignal,
    SignalDecision,
    SignalRouter,
    route_signal,
)

__all__ = [
    "compute_atr",
    "compute_natr",
    "compute_atr_ratio",
    "compute_bollinger_bands",
    "compute_bollinger_bandwidth",
    "compute_bbw_zscore",
    "compute_bbw_percentile",
    "compute_normalized_realized_volatility",
    "compute_parkinson_volatility",
    "compute_vol_shock",
    "compute_adx",
    "compute_return_autocorrelation",
    "compute_variance_ratio",
    "compute_rolling_variance_ratio",
    "compute_rsi",
    "compute_stochastic",
    "compute_donchian_channels",
    "compute_ema",
    "compute_candle_morphology",
    "MarketRegime",
    "RegimeOutput",
    "RegimeClassifier",
    "classify_market_regime",
    "classify_regime",
    "MarketSignal",
    "SignalDecision",
    "SignalRouter",
    "route_signal",
]
