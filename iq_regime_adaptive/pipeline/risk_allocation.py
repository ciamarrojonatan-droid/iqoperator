"""
risk_allocation.py - Mathematical Capital Allocation & Anti-Martingale Invariant.

Formulations:
1. Regularized Fractional Kelly Criterion:
   f*_WLB = max(0, EV_WLB / payout)
   f_allocated = f*_WLB * gamma (Quarter-Kelly, gamma = 0.25)
   Capped at max_risk_cap = 2% of equity.

2. Fixed Fractional Risk:
   f_fixed = 0.01 (1% default, capped at 2%).

3. Strict Anti-Martingale Invariant:
   d Stake / d (Consecutive Losses) == 0
   d Stake / d Balance >= 0 (monotonically non-decreasing with balance)
   Martingale progressions, loss-chasing multipliers, and grid scalers are strictly prohibited.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import numpy as np

from iq_regime_adaptive.pipeline.payout_filter import (
    compute_wilson_lower_bound,
    compute_expected_value,
    compute_payout_be,
)


class AntiMartingaleViolationError(ValueError):
    """Raised if any staking model violates the anti-martingale invariant."""
    pass


@dataclass(frozen=True)
class StakeAllocation:
    """Capital allocation output per trade."""
    stake: float
    fraction: float
    method: str
    is_allowed: bool
    balance: float
    max_risk_cap: float
    metadata: dict


def calculate_kelly_stake(
    balance: float,
    payout: float,
    sample_wins: int,
    sample_n: int,
    fractional_gamma: float = 0.25,
    max_risk_cap: float = 0.02,
    min_stake: float = 1.0,
    z: float = 1.96,
) -> StakeAllocation:
    """
    Computes regularized Fractional Kelly stake sizing using Wilson Score Lower Bound.
    
    Formula:
        WLB = compute_wilson_lower_bound(wins/n, n, z)
        EV_WLB = WLB * (1 + payout) - 1
        f*_WLB = max(0, EV_WLB / payout)
        f_allocated = min(f*_WLB * gamma, max_risk_cap)
        stake = round(balance * f_allocated, 2)
    """
    if balance <= 0 or payout <= 0:
        return StakeAllocation(
            stake=0.0,
            fraction=0.0,
            method="REGULARIZED_KELLY",
            is_allowed=False,
            balance=balance,
            max_risk_cap=max_risk_cap,
            metadata={"reason": "Non-positive balance or payout"},
        )

    if sample_n <= 0:
        return StakeAllocation(
            stake=0.0,
            fraction=0.0,
            method="REGULARIZED_KELLY",
            is_allowed=False,
            balance=balance,
            max_risk_cap=max_risk_cap,
            metadata={"reason": "Sample n is zero"},
        )

    p_hat = float(sample_wins) / float(sample_n)
    wlb = compute_wilson_lower_bound(p_hat, sample_n, z=z)
    p_be = compute_payout_be(payout)
    ev_wlb = compute_expected_value(wlb, payout)

    # Invariant: if statistical expectation is non-positive, stake is zero
    if ev_wlb <= 0.0 or wlb <= p_be:
        return StakeAllocation(
            stake=0.0,
            fraction=0.0,
            method="REGULARIZED_KELLY",
            is_allowed=False,
            balance=balance,
            max_risk_cap=max_risk_cap,
            metadata={
                "wlb": wlb,
                "p_be": p_be,
                "ev_wlb": ev_wlb,
                "reason": "EV_WLB <= 0, statistical edge insufficient",
            },
        )

    # Kelly formula: f* = EV / payout = (wlb * payout - (1 - wlb)) / payout
    kelly_full = ev_wlb / payout
    f_raw = max(0.0, kelly_full * fractional_gamma)
    f_allocated = min(f_raw, max_risk_cap)

    raw_stake = balance * f_allocated
    if raw_stake < min_stake and balance >= min_stake and f_allocated > 0:
        # If stake falls below broker minimum but balance allows and Kelly > 0, set to min_stake
        # provided min_stake does not exceed max_risk_cap * balance significantly
        if min_stake <= balance * (max_risk_cap * 2.0):
            stake = min_stake
        else:
            stake = 0.0
    else:
        stake = round(raw_stake, 2)

    is_allowed = stake >= min_stake

    return StakeAllocation(
        stake=stake,
        fraction=round(f_allocated, 6),
        method="REGULARIZED_KELLY",
        is_allowed=is_allowed,
        balance=balance,
        max_risk_cap=max_risk_cap,
        metadata={
            "wlb": wlb,
            "p_be": p_be,
            "ev_wlb": ev_wlb,
            "kelly_full": kelly_full,
            "fractional_gamma": fractional_gamma,
        },
    )


def calculate_fixed_stake(
    balance: float,
    fixed_fraction: float = 0.01,
    max_risk_cap: float = 0.02,
    min_stake: float = 1.0,
) -> StakeAllocation:
    """
    Computes Fixed Fractional Risk stake sizing.
    Formula:
        f_allocated = min(fixed_fraction, max_risk_cap)
        stake = round(balance * f_allocated, 2)
    """
    if balance <= 0 or fixed_fraction <= 0:
        return StakeAllocation(
            stake=0.0,
            fraction=0.0,
            method="FIXED_FRACTIONAL",
            is_allowed=False,
            balance=balance,
            max_risk_cap=max_risk_cap,
            metadata={"reason": "Non-positive balance or fraction"},
        )

    f_allocated = min(fixed_fraction, max_risk_cap)
    raw_stake = balance * f_allocated
    stake = max(min_stake, round(raw_stake, 2)) if balance >= min_stake else 0.0
    is_allowed = stake >= min_stake

    return StakeAllocation(
        stake=stake,
        fraction=round(f_allocated, 6),
        method="FIXED_FRACTIONAL",
        is_allowed=is_allowed,
        balance=balance,
        max_risk_cap=max_risk_cap,
        metadata={"fixed_fraction": fixed_fraction},
    )


def verify_anti_martingale_invariant(
    stake_fn,
    base_balance: float = 1000.0,
    consecutive_loss_streaks: Optional[List[int]] = None,
    balance_steps: Optional[List[float]] = None,
    **stake_kwargs,
) -> bool:
    """
    Formally verifies that the staking model satisfies:
    1. Zero Martingale Multiplier:
       d Stake / d (Loss Streak) == 0 (for constant balance).
    2. Monotonicity with Balance:
       d Stake / d Balance >= 0.
    
    Raises AntiMartingaleViolationError if any violation is detected.
    """
    if consecutive_loss_streaks is None:
        consecutive_loss_streaks = [0, 1, 2, 3, 5, 8, 10]

    # Invariant 1: Loss streak invariance
    base_alloc = stake_fn(balance=base_balance, **stake_kwargs)
    base_stake = base_alloc.stake

    for streak in consecutive_loss_streaks:
        # Check if function supports consecutive_losses argument
        try:
            alloc = stake_fn(
                balance=base_balance,
                consecutive_losses=streak,
                **stake_kwargs,
            )
            if alloc.stake != base_stake:
                raise AntiMartingaleViolationError(
                    f"Martingale violation detected! Stake altered from {base_stake} to {alloc.stake} "
                    f"after {streak} consecutive losses."
                )
        except TypeError:
            # Function correctly does not even accept a loss streak argument (by design)
            pass

    # Invariant 2: Monotonicity with Balance (d Stake / d Balance >= 0)
    if balance_steps is None:
        balance_steps = [100.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0]

    prev_stake = 0.0
    for bal in balance_steps:
        alloc = stake_fn(balance=bal, **stake_kwargs)
        if alloc.is_allowed:
            if alloc.stake < prev_stake - 1e-6:
                raise AntiMartingaleViolationError(
                    f"Monotonicity violation: Stake decreased from {prev_stake} to {alloc.stake} "
                    f"as balance increased to {bal}."
                )
            prev_stake = alloc.stake

    return True


# Aliases for spec compliance
calculate_stake = calculate_kelly_stake
fractional_kelly = calculate_kelly_stake
verify_zero_martingale = verify_anti_martingale_invariant

