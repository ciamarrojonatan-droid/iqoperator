"""
iq_regime_adaptive.hypotheses - Empirical Hypotheses H001 to H008 for Binary Options.

Hypotheses:
- H001: Range Mean Reversion (Bollinger Touch + RSI + Wick Rejection)
- H002: Trend Pullback (EMA Alignment + Dynamic Retest)
- H003: Volatility Expansion Breakout (Bandwidth Surge + Range Expansion)
- H004: Autocorrelation Mean Reversion (Negative Serial Correlation + Return Z-Score)
- H005: Multi-Timeframe Trend Alignment (Macro Anchor + Micro Pullback)
- H006: Payout-Filtered Dynamic Edge (Payout >= 0.80 + EV_WLB Hurdle)
- H007: Volatility Contraction Squeeze Breakout (Bollinger inside Keltner Release)
- H008: Regime-Adaptive Meta-Router (5-Tier Classification + Strict Chaos Veto)
"""

from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis
from iq_regime_adaptive.hypotheses.h001_range_mean_reversion import H001RangeMeanReversion
from iq_regime_adaptive.hypotheses.h002_trend_pullback import H002TrendPullback
from iq_regime_adaptive.hypotheses.h003_volatility_expansion import H003VolatilityExpansion
from iq_regime_adaptive.hypotheses.h004_autocorrelation_reversion import H004AutocorrelationReversion
from iq_regime_adaptive.hypotheses.h005_mtf_trend_alignment import H005MTFTrendAlignment
from iq_regime_adaptive.hypotheses.h006_payout_filtered_edge import H006PayoutFilteredEdge
from iq_regime_adaptive.hypotheses.h007_squeeze_breakout import H007SqueezeBreakout
from iq_regime_adaptive.hypotheses.h008_regime_adaptive_router import H008RegimeAdaptiveRouter
from iq_regime_adaptive.hypotheses.registry import (
    HYPOTHESIS_REGISTRY,
    CANONICAL_IDS,
    list_hypotheses,
    get_hypothesis,
    get_all_hypotheses,
)

__all__ = [
    "BaseHypothesis",
    "H001RangeMeanReversion",
    "H002TrendPullback",
    "H003VolatilityExpansion",
    "H004AutocorrelationReversion",
    "H005MTFTrendAlignment",
    "H006PayoutFilteredEdge",
    "H007SqueezeBreakout",
    "H008RegimeAdaptiveRouter",
    "HYPOTHESIS_REGISTRY",
    "CANONICAL_IDS",
    "list_hypotheses",
    "get_hypothesis",
    "get_all_hypotheses",
]
