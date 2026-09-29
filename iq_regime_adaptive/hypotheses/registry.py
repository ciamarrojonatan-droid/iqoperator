"""
registry.py - Discovery and Factory Registry for Hypotheses H001 to H008.

Supports lookups by short ID ("H001") or canonical full ID ("H001_RANGE_MEAN_REVERSION").
"""

from __future__ import annotations

from typing import Dict, List, Type, Any, Optional

from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis
from iq_regime_adaptive.hypotheses.h001_range_mean_reversion import H001RangeMeanReversion
from iq_regime_adaptive.hypotheses.h002_trend_pullback import H002TrendPullback
from iq_regime_adaptive.hypotheses.h003_volatility_expansion import H003VolatilityExpansion
from iq_regime_adaptive.hypotheses.h004_autocorrelation_reversion import H004AutocorrelationReversion
from iq_regime_adaptive.hypotheses.h005_mtf_trend_alignment import H005MTFTrendAlignment
from iq_regime_adaptive.hypotheses.h006_payout_filtered_edge import H006PayoutFilteredEdge
from iq_regime_adaptive.hypotheses.h007_squeeze_breakout import H007SqueezeBreakout
from iq_regime_adaptive.hypotheses.h008_regime_adaptive_router import H008RegimeAdaptiveRouter


HYPOTHESIS_REGISTRY: Dict[str, Type[BaseHypothesis]] = {
    "H001": H001RangeMeanReversion,
    "H001_RANGE_MEAN_REVERSION": H001RangeMeanReversion,
    "H002": H002TrendPullback,
    "H002_TREND_PULLBACK": H002TrendPullback,
    "H003": H003VolatilityExpansion,
    "H003_VOLATILITY_EXPANSION_BREAKOUT": H003VolatilityExpansion,
    "H004": H004AutocorrelationReversion,
    "H004_AUTOCORRELATION_MEAN_REVERSION": H004AutocorrelationReversion,
    "H005": H005MTFTrendAlignment,
    "H005_MTF_TREND_ALIGNMENT": H005MTFTrendAlignment,
    "H006": H006PayoutFilteredEdge,
    "H006_PAYOUT_FILTERED_DYNAMIC_EDGE": H006PayoutFilteredEdge,
    "H007": H007SqueezeBreakout,
    "H007_VOLATILITY_CONTRACTION_SQUEEZE": H007SqueezeBreakout,
    "H008": H008RegimeAdaptiveRouter,
    "H008_REGIME_ADAPTIVE_ENSEMBLE_ROUTER": H008RegimeAdaptiveRouter,
}

CANONICAL_IDS = [
    "H001_RANGE_MEAN_REVERSION",
    "H002_TREND_PULLBACK",
    "H003_VOLATILITY_EXPANSION_BREAKOUT",
    "H004_AUTOCORRELATION_MEAN_REVERSION",
    "H005_MTF_TREND_ALIGNMENT",
    "H006_PAYOUT_FILTERED_DYNAMIC_EDGE",
    "H007_VOLATILITY_CONTRACTION_SQUEEZE",
    "H008_REGIME_ADAPTIVE_ENSEMBLE_ROUTER",
]


def list_hypotheses(canonical_only: bool = True) -> List[str]:
    """Returns list of registered hypothesis identifiers."""
    if canonical_only:
        return list(CANONICAL_IDS)
    return list(HYPOTHESIS_REGISTRY.keys())


def get_hypothesis(hypothesis_id: str, **kwargs) -> BaseHypothesis:
    """
    Instantiates a registered hypothesis by short or full ID.

    Args:
        hypothesis_id: e.g. "H001" or "H001_RANGE_MEAN_REVERSION"
        **kwargs: Parameters passed to constructor.

    Raises:
        KeyError: If identifier is not in the registry.
    """
    key = hypothesis_id.strip().upper()
    if key not in HYPOTHESIS_REGISTRY:
        valid = ", ".join(CANONICAL_IDS)
        raise KeyError(f"Unknown hypothesis ID '{hypothesis_id}'. Valid IDs: {valid}")
    cls = HYPOTHESIS_REGISTRY[key]
    return cls(**kwargs)


def get_all_hypotheses(**kwargs) -> Dict[str, BaseHypothesis]:
    """
    Instantiates all 8 canonical hypotheses.

    Returns:
        Dict mapping canonical hypothesis ID to instance.
    """
    instances = {}
    for canon_id in CANONICAL_IDS:
        instances[canon_id] = get_hypothesis(canon_id, **kwargs)
    return instances
