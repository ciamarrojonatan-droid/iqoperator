"""
test_adversarial_payout_risk.py - Empirical Adversarial Stress Test Suite.

Target Modules:
- iq_regime_adaptive/pipeline/payout_filter.py
- iq_regime_adaptive/pipeline/risk_allocation.py

Objectives:
1. Adversarial matrix stress-test for Wilson Lower Bound and EV Execution Gate:
   - N in {1, 2, 5, 10, 50, 100, 1_000_000}
   - Nominal win rate p in {0.0, 0.50, 0.55, 0.60, 0.99, 1.0}
   - Payout b in {0.01, 0.50, 0.80, 0.85, 0.95, 2.0}
   - Verify Law of Small Numbers rejection: e.g. 8/10 (80%) rejected under typical broker payouts.
2. Adversarial stress-test for Anti-Martingale Capital Allocation:
   - Simulate a 50-trade streak of consecutive losses.
   - Verify stake invariant: Stake_{t+1} <= Stake_t strictly holds after every loss.
   - Verify balance remains positive and never enters catastrophic drawdown or margin call.
   - Contrast against Classical Martingale blowup oracle.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure package root is in sys.path for direct script execution
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import unittest
from typing import List, Dict, Any, Tuple
import numpy as np

from iq_regime_adaptive.pipeline.payout_filter import (
    compute_payout_be,
    compute_wilson_lower_bound,
    compute_expected_value,
    evaluate_trade_gate,
    TradeGateDecision,
)
from iq_regime_adaptive.pipeline.risk_allocation import (
    calculate_kelly_stake,
    calculate_fixed_stake,
    verify_anti_martingale_invariant,
    StakeAllocation,
    AntiMartingaleViolationError,
)


class TestWilsonAndEVGateAdversarialMatrix(unittest.TestCase):
    """
    Stress-testing Wilson Lower Bound and EV Gate across boundary conditions.
    Matrix: 7 N values x 6 nominal win rates x 6 payouts = 252 scenarios.
    """

    def setUp(self):
        self.n_values = [1, 2, 5, 10, 50, 100, 1_000_000]
        self.p_values = [0.0, 0.50, 0.55, 0.60, 0.99, 1.0]
        self.b_values = [0.01, 0.50, 0.80, 0.85, 0.95, 2.0]

    def test_full_252_matrix_invariants(self):
        """
        Verify mathematical invariants across all 252 boundary scenarios:
        1. 0.0 <= WLB <= 1.0
        2. WLB <= p_hat + 1e-12 (lower bound never exceeds empirical mean)
        3. Mathematical equivalence: allow_trade == (EV_WLB > 0) == (WLB > P_BE)
        4. Rejection reason integrity: None iff allow_trade is True
        """
        evaluated_count = 0
        accepted_count = 0
        rejected_count = 0

        for n in self.n_values:
            for p in self.p_values:
                wins = int(round(p * n))
                p_hat = float(wins) / float(n)

                for b in self.b_values:
                    decision = evaluate_trade_gate(sample_wins=wins, sample_n=n, payout=b)
                    evaluated_count += 1

                    # 1. Bounds check
                    self.assertGreaterEqual(decision.wlb, 0.0, f"WLB < 0 for N={n}, p={p}, b={b}")
                    self.assertLessEqual(decision.wlb, 1.0, f"WLB > 1 for N={n}, p={p}, b={b}")

                    # 2. Lower bound property
                    self.assertLessEqual(
                        decision.wlb,
                        p_hat + 1e-12,
                        f"WLB ({decision.wlb}) > p_hat ({p_hat}) for N={n}, p={p}",
                    )

                    # 3. Equivalence invariant: allow_trade <==> EV_WLB > 0 <==> WLB > P_BE
                    p_be_exact = compute_payout_be(b)
                    ev_exact = decision.wlb * (1.0 + b) - 1.0

                    self.assertAlmostEqual(decision.p_be, p_be_exact, places=6)
                    self.assertAlmostEqual(decision.ev_wlb, ev_exact, places=6)

                    expected_allow = (decision.ev_wlb > 0.0) and (decision.wlb > decision.p_be)
                    self.assertEqual(
                        decision.allow_trade,
                        expected_allow,
                        f"Gate mismatch at N={n}, p={p}, b={b}: allowed={decision.allow_trade}, EV={decision.ev_wlb}, P_BE={decision.p_be}",
                    )

                    # 4. Reason consistency
                    if decision.allow_trade:
                        accepted_count += 1
                        self.assertIsNone(decision.rejection_reason)
                    else:
                        rejected_count += 1
                        self.assertIsNotNone(decision.rejection_reason)

        self.assertEqual(evaluated_count, 252)
        print(f"[Matrix Stress Test] Evaluated 252 scenarios: {accepted_count} Accepted, {rejected_count} Rejected.")

    def test_law_of_small_numbers_rejections(self):
        """
        Adversarially verify that small sample sizes with apparently stellar nominal
        win rates are strictly rejected under typical broker payouts (80%, 85%, 95%).
        """
        typical_payouts = [0.80, 0.85, 0.95]

        # Case 1: 8 wins in 10 trades (80% nominal win rate)
        # Broker payouts: P_BE in [51.28%, 55.56%].
        # WLB(8/10) ~ 0.4902. Since 0.4902 < P_BE, MUST BE REJECTED.
        for b in typical_payouts:
            dec = evaluate_trade_gate(sample_wins=8, sample_n=10, payout=b)
            self.assertFalse(
                dec.allow_trade,
                f"FAILED: 8/10 (80% win rate) was erroneously accepted at payout {b}!",
            )
            self.assertLess(dec.wlb, dec.p_be)
            self.assertLess(dec.ev_wlb, 0.0)

        # Case 2: 1 win in 1 trade (100% nominal win rate)
        # WLB(1/1) = 1 / (1 + 3.8416) ~ 0.2065 < P_BE. MUST BE REJECTED.
        for b in typical_payouts:
            dec = evaluate_trade_gate(sample_wins=1, sample_n=1, payout=b)
            self.assertFalse(
                dec.allow_trade,
                f"FAILED: 1/1 (100% win rate) was erroneously accepted at payout {b}!",
            )
            self.assertLess(dec.wlb, dec.p_be)

        # Case 3: 2 wins in 2 trades (100% nominal win rate)
        # WLB(2/2) = 2 / (2 + 3.8416) ~ 0.3424 < P_BE. MUST BE REJECTED.
        for b in typical_payouts:
            dec = evaluate_trade_gate(sample_wins=2, sample_n=2, payout=b)
            self.assertFalse(
                dec.allow_trade,
                f"FAILED: 2/2 (100% win rate) was erroneously accepted at payout {b}!",
            )
            self.assertLess(dec.wlb, dec.p_be)

        # Case 4: 4 wins in 5 trades (80% nominal win rate)
        # WLB(4/5) ~ 0.3755 < P_BE. MUST BE REJECTED.
        for b in typical_payouts:
            dec = evaluate_trade_gate(sample_wins=4, sample_n=5, payout=b)
            self.assertFalse(
                dec.allow_trade,
                f"FAILED: 4/5 (80% win rate) was erroneously accepted at payout {b}!",
            )

        # Case 5: 6 wins in 10 trades (60% nominal win rate)
        # WLB(6/10) ~ 0.3127 < P_BE. MUST BE REJECTED.
        for b in typical_payouts:
            dec = evaluate_trade_gate(sample_wins=6, sample_n=10, payout=b)
            self.assertFalse(dec.allow_trade)

        # Case 6: 28 wins in 50 trades (56% nominal win rate)
        # At payout 0.85, P_BE = 54.05%. WLB(28/50) ~ 0.4221 < 54.05%. REJECTED.
        dec_50 = evaluate_trade_gate(sample_wins=28, sample_n=50, payout=0.85)
        self.assertFalse(dec_50.allow_trade)

    def test_asymptotic_convergence_large_n(self):
        """
        Verify that for N = 1,000,000, WLB converges to p_hat within 0.002.
        """
        for p in self.p_values:
            wins = int(p * 1_000_000)
            wlb = compute_wilson_lower_bound(p, 1_000_000, z=1.96)
            diff = abs(wlb - p)
            self.assertLessEqual(
                diff,
                0.002,
                f"Asymptotic convergence failed: N=1M, p={p}, wlb={wlb}, diff={diff}",
            )

    def test_extreme_and_degenerate_inputs(self):
        """
        Adversarial inputs: N=0, negative payout, zero payout, zero wins.
        """
        # N = 0
        dec_0 = evaluate_trade_gate(sample_wins=0, sample_n=0, payout=0.85)
        self.assertFalse(dec_0.allow_trade)
        self.assertEqual(dec_0.wlb, 0.0)
        self.assertIn("n=0", dec_0.rejection_reason)

        # Payout <= 0
        dec_neg_payout = evaluate_trade_gate(sample_wins=100, sample_n=100, payout=-0.5)
        self.assertFalse(dec_neg_payout.allow_trade)
        self.assertEqual(dec_neg_payout.p_be, 1.0)

        dec_zero_payout = evaluate_trade_gate(sample_wins=100, sample_n=100, payout=0.0)
        self.assertFalse(dec_zero_payout.allow_trade)
        self.assertEqual(dec_zero_payout.p_be, 1.0)


class TestAntiMartingaleCapitalAllocationStress(unittest.TestCase):
    """
    Stress-testing Anti-Martingale Capital Allocation under extreme loss streaks:
    - 50 consecutive losses.
    - Multiple initial balance levels ($10 to $100,000).
    - Fixed fractional and Regularized Kelly staking.
    - Verification of stake non-increase invariant: Stake_{t+1} <= Stake_t.
    - Verification of balance solvency: Balance > 0, no catastrophic drawdown.
    - Classical Martingale blowup comparison.
    """

    def test_50_consecutive_losses_fixed_fractional(self):
        """
        Simulate 50 consecutive losses with Fixed Fractional Staking (1% and 2%).
        Invariants:
        1. Stake_{t+1} <= Stake_t strictly holds at every step.
        2. Balance strictly remains positive (Balance > 0).
        3. Drawdown is bounded: exactly 1 - (1 - f)^t.
        """
        test_balances = [10.0, 50.0, 100.0, 1000.0, 10000.0, 100000.0]
        fractions = [0.01, 0.02]

        for init_balance in test_balances:
            for f in fractions:
                balance = init_balance
                prev_stake = float("inf")
                stake_history = []
                balance_history = [balance]

                for t in range(1, 51):
                    alloc = calculate_fixed_stake(
                        balance=balance,
                        fixed_fraction=f,
                        max_risk_cap=0.02,
                        min_stake=1.0,
                    )

                    curr_stake = alloc.stake

                    # Invariant 1: Stake strictly never increases after a loss!
                    # Floating point safety buffer 1e-9
                    self.assertLessEqual(
                        curr_stake,
                        prev_stake + 1e-9,
                        f"STAKE INCREASE VIOLATION at step {t}: Stake increased from {prev_stake} to {curr_stake} (Balance={balance})",
                    )

                    if not alloc.is_allowed or curr_stake <= 0.0:
                        # Staking model halted trading (e.g. balance below min stake)
                        break

                    # Invariant 2: Trade stake does not exceed balance
                    self.assertLessEqual(
                        curr_stake,
                        balance,
                        f"Solvency violation at step {t}: Stake {curr_stake} > Balance {balance}",
                    )

                    # Simulate loss: balance decreases by stake
                    balance -= curr_stake
                    balance = round(balance, 2)

                    # Invariant 3: Balance remains strictly non-negative
                    self.assertGreaterEqual(
                        balance,
                        0.0,
                        f"Bankruptcy violation at step {t}: Balance became negative ({balance})",
                    )

                    prev_stake = curr_stake
                    stake_history.append(curr_stake)
                    balance_history.append(balance)

                # For large initial balances ($1000+), verify drawdown matches theoretical decay
                if init_balance >= 1000.0:
                    self.assertEqual(len(stake_history), 50)
                    self.assertGreater(balance, 0.0)
                    drawdown = (init_balance - balance) / init_balance
                    # For f=0.01: (1-0.01)^50 = 0.6050 -> DD ~ 39.5%
                    # For f=0.02: (1-0.02)^50 = 0.3642 -> DD ~ 63.6%
                    if f == 0.01:
                        self.assertAlmostEqual(drawdown, 0.395, delta=0.02)
                    elif f == 0.02:
                        self.assertAlmostEqual(drawdown, 0.636, delta=0.02)

    def test_50_consecutive_losses_regularized_kelly_fixed_edge(self):
        """
        Simulate 50 consecutive losses with Regularized Kelly Staking (fixed sample edge).
        Validates capital preservation under balance decline.
        """
        init_balance = 1000.0
        balance = init_balance
        prev_stake = float("inf")
        stake_history = []

        # Known statistical edge: 180 wins / 300 trades at payout 0.85
        # WLB ~ 54.36% > P_BE (54.05%) -> Kelly produces positive fraction
        for t in range(1, 51):
            alloc = calculate_kelly_stake(
                balance=balance,
                payout=0.85,
                sample_wins=180,
                sample_n=300,
                fractional_gamma=0.25,
                max_risk_cap=0.02,
                min_stake=1.0,
            )

            curr_stake = alloc.stake

            # Invariant: Stake strictly never increases after loss
            self.assertLessEqual(
                curr_stake,
                prev_stake + 1e-9,
                f"Kelly Stake increased at step {t}: {prev_stake} -> {curr_stake}",
            )

            if not alloc.is_allowed or curr_stake <= 0.0:
                # Trading safely halted
                break

            balance -= curr_stake
            balance = round(balance, 2)
            self.assertGreaterEqual(balance, 0.0)

            prev_stake = curr_stake
            stake_history.append(curr_stake)

        self.assertGreater(balance, 0.0)
        print(f"[Kelly Fixed-Edge 50-Loss] Initial: ${init_balance:.2f} -> Final: ${balance:.2f} ({len(stake_history)} trades executed).")

    def test_50_consecutive_losses_regularized_kelly_dynamic_edge(self):
        """
        Simulate 50 consecutive losses where sample edge updates live in real time.
        Each loss adds 1 trade to sample_n with 0 added wins.
        Invariant:
        As sample edge degrades, EV_WLB drops and Kelly automatically vetoes trades (stake = 0),
        preserving account capital from further losses!
        """
        init_balance = 1000.0
        balance = init_balance
        prev_stake = float("inf")
        trades_executed = 0

        # Start with moderate edge: 65 wins / 100 trades (65%) at 0.85 payout
        current_wins = 65
        current_n = 100

        for t in range(1, 51):
            alloc = calculate_kelly_stake(
                balance=balance,
                payout=0.85,
                sample_wins=current_wins,
                sample_n=current_n,
                fractional_gamma=0.25,
                max_risk_cap=0.02,
                min_stake=1.0,
            )

            curr_stake = alloc.stake

            if not alloc.is_allowed or curr_stake <= 0.0:
                # Edge degraded below break-even! System vetoes further trading.
                break

            self.assertLessEqual(curr_stake, prev_stake + 1e-9)
            balance -= curr_stake
            balance = round(balance, 2)
            prev_stake = curr_stake
            trades_executed += 1

            # Update sample with current loss
            current_n += 1

        # Because edge degrades, Kelly must halt trading well before 50 losses!
        self.assertLess(
            trades_executed,
            15,
            f"Expected Kelly to shut down quickly on consecutive losses, but ran {trades_executed} trades!",
        )
        self.assertGreater(balance, 800.0, "Capital preservation failed during loss streak!")
        print(f"[Kelly Dynamic-Edge 50-Loss] Circuit breaker activated after {trades_executed} losses! Balance preserved at ${balance:.2f}.")

    def test_classical_martingale_vs_anti_martingale_comparative(self):
        """
        Adversarially contrast Anti-Martingale against Classical Martingale:
        With Balance = $1,000 and Base Stake = $10:
        - Martingale doubles stake on each loss: 10, 20, 40, 80, 160, 320, 640...
          Total loss at step 7 = $1,270 > $1,000 -> Total Ruin / Margin Call at trade 7!
        - Anti-Martingale (1% Fixed or Kelly):
          At step 7, balance is ~$932.07 (only 6.8% drawdown).
          At step 50, balance is ~$605.01 (zero ruin, strictly solvent).
        """
        init_balance = 1000.0
        base_stake = 10.0

        # 1. Classical Martingale Simulation
        mg_balance = init_balance
        mg_stake = base_stake
        mg_bankrupt_step = None

        for t in range(1, 51):
            if mg_stake > mg_balance:
                mg_bankrupt_step = t
                break
            mg_balance -= mg_stake
            mg_stake *= 2.0

        self.assertIsNotNone(mg_bankrupt_step)
        self.assertEqual(
            mg_bankrupt_step,
            7,
            f"Classical Martingale was expected to go bankrupt at trade 7, but did at {mg_bankrupt_step}",
        )

        # 2. Anti-Martingale Fixed 1% Simulation
        am_balance = init_balance
        for t in range(1, 51):
            alloc = calculate_fixed_stake(balance=am_balance, fixed_fraction=0.01)
            self.assertTrue(alloc.is_allowed)
            am_balance -= alloc.stake

        self.assertGreater(am_balance, 600.0)
        print(
            f"[Comparative Oracle] Classical Martingale suffered total ruin at Trade {mg_bankrupt_step}. "
            f"Anti-Martingale survived 50 losses with ${am_balance:.2f} remaining."
        )


if __name__ == "__main__":
    unittest.main()
