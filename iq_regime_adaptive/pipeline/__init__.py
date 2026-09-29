"""
pipeline package for iq_regime_adaptive.
"""

from iq_regime_adaptive.pipeline.data_loader import (
    DataLoader,
    load_csv,
    normalize_timestamps,
    validate_ohlcv,
    DataValidationError,
)
from iq_regime_adaptive.pipeline.payout_filter import (
    compute_payout_be,
    compute_wilson_lower_bound,
    compute_expected_value,
    evaluate_trade_gate,
    evaluate_payout_gate,
    TradeGateDecision,
)
from iq_regime_adaptive.pipeline.risk_allocation import (
    calculate_kelly_stake,
    calculate_fixed_stake,
    verify_anti_martingale_invariant,
    StakeAllocation,
    AntiMartingaleViolationError,
)

__all__ = [
    "DataLoader",
    "load_csv",
    "normalize_timestamps",
    "validate_ohlcv",
    "DataValidationError",
    "compute_payout_be",
    "compute_wilson_lower_bound",
    "compute_expected_value",
    "evaluate_trade_gate",
    "evaluate_payout_gate",
    "TradeGateDecision",
    "calculate_kelly_stake",
    "calculate_fixed_stake",
    "verify_anti_martingale_invariant",
    "StakeAllocation",
    "AntiMartingaleViolationError",
]
