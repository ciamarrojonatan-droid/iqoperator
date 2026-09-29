"""
test_pipeline.py - Unit Tests for Ingestion, Payout Filtering, and Risk Allocation.
"""

import unittest
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

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


class TestDataLoader(unittest.TestCase):
    """Test suite for CSV ingestion, schema validation, and timestamp normalization."""

    def test_normalize_timestamps_all_formats(self):
        # 1. Epoch seconds
        s_sec = pd.Series([1782123600, 1782123900])
        dt_sec = normalize_timestamps(s_sec)
        self.assertEqual(str(dt_sec.iloc[0].tz), "UTC")
        self.assertEqual(dt_sec.iloc[0].year, 2026)

        # 2. Epoch milliseconds
        s_ms = pd.Series([1716485400000, 1716486300000])
        dt_ms = normalize_timestamps(s_ms)
        self.assertEqual(str(dt_ms.iloc[0].tz), "UTC")
        self.assertEqual(dt_ms.iloc[0].year, 2024)

        # 3. ISO format strings
        s_iso = pd.Series(["2026-06-22 10:20:00", "2026-06-22 10:25:00"])
        dt_iso = normalize_timestamps(s_iso)
        self.assertEqual(str(dt_iso.iloc[0].tz), "UTC")
        self.assertEqual(dt_iso.iloc[0].year, 2026)

    def test_validate_ohlcv_invariants(self):
        # Valid DataFrame
        df_valid = pd.DataFrame({
            "time": [1000, 1060],
            "open": [1.1000, 1.1010],
            "high": [1.1050, 1.1060],
            "low": [1.0950, 1.0980],
            "close": [1.1010, 1.1020],
        })
        res = validate_ohlcv(df_valid)
        self.assertIn("volume", res.columns)
        self.assertEqual(res["volume"].iloc[0], 0.0)

        # Invalid: High < Low
        df_invalid_hl = df_valid.copy()
        df_invalid_hl.loc[0, "high"] = 1.0900 # lower than low 1.0950
        with self.assertRaises(DataValidationError):
            validate_ohlcv(df_invalid_hl)

        # Invalid: Non-positive price
        df_invalid_price = df_valid.copy()
        df_invalid_price.loc[0, "close"] = -1.1000
        with self.assertRaises(DataValidationError):
            validate_ohlcv(df_invalid_price)

        # Invalid: Missing column
        df_missing = df_valid.drop(columns=["close"])
        with self.assertRaises(DataValidationError):
            validate_ohlcv(df_missing)

    def test_load_real_eurusd_csv(self):
        csv_path = Path("data/EURUSD_M5_iq.csv")
        if csv_path.exists():
            df = load_csv(csv_path)
            self.assertEqual(len(df), 20000)
            self.assertTrue(df["time"].is_monotonic_increasing, "Data must be sorted chronologically")
            self.assertTrue((df["high"] >= df["low"]).all(), "High must be >= Low")
            self.assertTrue((df["close"] > 0).all(), "Close must be positive")

    def test_load_csv_with_date_filtering(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("time,open,high,low,close\n")
            f.write("1782123600,1.10,1.15,1.05,1.12\n") # 2026-06-22 10:20:00
            f.write("1782123900,1.12,1.16,1.08,1.14\n") # 2026-06-22 10:25:00
            f.write("1782124200,1.14,1.17,1.10,1.15\n") # 2026-06-22 10:30:00
            temp_path = f.name

        try:
            # Filter starting at 10:25
            df_filtered = load_csv(temp_path, start_time="2026-06-22 10:25:00+00:00")
            self.assertEqual(len(df_filtered), 2)
            self.assertEqual(df_filtered["close"].iloc[0], 1.14)
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestPayoutFilter(unittest.TestCase):
    """Test suite for P_BE, Wilson Lower Bound, and conservative EV gate."""

    def test_payout_breakeven_math(self):
        # 85% payout -> 1 / 1.85 ~ 0.54054
        self.assertAlmostEqual(compute_payout_be(0.85), 1.0 / 1.85, places=5)
        # 70% payout -> 1 / 1.70 ~ 0.58824
        self.assertAlmostEqual(compute_payout_be(0.70), 1.0 / 1.70, places=5)
        # 80% payout -> 1 / 1.80 ~ 0.55556
        self.assertAlmostEqual(compute_payout_be(0.80), 1.0 / 1.80, places=5)
        # Degenerate payout <= 0
        self.assertEqual(compute_payout_be(0.0), 1.0)
        self.assertEqual(compute_payout_be(-0.5), 1.0)

    def test_wilson_lower_bound_properties(self):
        # Edge case: n = 0
        self.assertEqual(compute_wilson_lower_bound(0.70, 0), 0.0)

        # Invariant: As n -> infinity, WLB converges to p_hat
        wlb_large = compute_wilson_lower_bound(0.60, 10000000)
        self.assertAlmostEqual(wlb_large, 0.60, places=3)

        # Invariant: WLB is strictly less than p_hat for finite n
        wlb_finite = compute_wilson_lower_bound(0.60, 100)
        self.assertLess(wlb_finite, 0.60)

        # Exact check for Table 2 from research spec:
        # n = 10, w = 7 -> p_hat = 0.70 -> WLB ~ 0.3968
        wlb_10 = compute_wilson_lower_bound(0.70, 10, z=1.96)
        self.assertAlmostEqual(wlb_10, 0.3968, places=3)

        # n = 100, w = 65 -> p_hat = 0.65 -> WLB ~ 0.5525
        wlb_100 = compute_wilson_lower_bound(0.65, 100, z=1.96)
        self.assertAlmostEqual(wlb_100, 0.5525, places=3)

    def test_execution_gate_law_of_small_numbers_rejection(self):
        # 7 wins in 10 trades at 85% payout:
        # Nominal win rate is 70% (well above P_BE=54.05%), but sample is tiny.
        # WLB is 39.68% -> EV_WLB = -0.2660 < 0 -> MUST BE REJECTED!
        decision_small = evaluate_trade_gate(sample_wins=7, sample_n=10, payout=0.85)
        self.assertFalse(decision_small.allow_trade)
        self.assertLess(decision_small.ev_wlb, 0.0)
        self.assertLess(decision_small.wlb, decision_small.p_be)
        self.assertIsNotNone(decision_small.rejection_reason)

    def test_execution_gate_large_sample_acceptance(self):
        # 65 wins in 100 trades at 85% payout:
        # WLB is 55.25% > P_BE (54.05%) -> EV_WLB = +0.0222 > 0 -> MUST BE ACCEPTED!
        decision_100 = evaluate_trade_gate(sample_wins=65, sample_n=100, payout=0.85)
        self.assertTrue(decision_100.allow_trade)
        self.assertGreater(decision_100.ev_wlb, 0.0)
        self.assertGreater(decision_100.wlb, decision_100.p_be)
        self.assertIsNone(decision_100.rejection_reason)

        # 180 wins in 300 trades at 85% payout (60% win rate):
        # WLB is 54.36% > P_BE (54.05%) -> EV_WLB = +0.0057 > 0 -> ACCEPTED!
        decision_300 = evaluate_trade_gate(sample_wins=180, sample_n=300, payout=0.85)
        self.assertTrue(decision_300.allow_trade)
        self.assertGreater(decision_300.ev_wlb, 0.0)


class TestRiskAllocation(unittest.TestCase):
    """Test suite for Kelly staking, fixed sizing, and strict zero-martingale invariant."""

    def test_kelly_stake_sizing_positive_edge(self):
        # Balance = 1000, payout = 0.85, 65 wins in 100 trades
        alloc = calculate_kelly_stake(
            balance=1000.0,
            payout=0.85,
            sample_wins=65,
            sample_n=100,
            fractional_gamma=0.25,
            max_risk_cap=0.02,
        )
        self.assertTrue(alloc.is_allowed)
        self.assertGreater(alloc.stake, 1.0)
        self.assertLessEqual(alloc.stake, 1000.0 * 0.02) # Must obey 2% cap

    def test_kelly_stake_sizing_negative_or_insufficient_edge(self):
        # Small sample (7 wins / 10 trades) has EV_WLB < 0 -> stake must be 0
        alloc = calculate_kelly_stake(
            balance=1000.0,
            payout=0.85,
            sample_wins=7,
            sample_n=10,
        )
        self.assertFalse(alloc.is_allowed)
        self.assertEqual(alloc.stake, 0.0)

    def test_fixed_stake_sizing(self):
        alloc = calculate_fixed_stake(balance=1000.0, fixed_fraction=0.01)
        self.assertTrue(alloc.is_allowed)
        self.assertEqual(alloc.stake, 10.0)

        # Test cap at 2%
        alloc_capped = calculate_fixed_stake(balance=1000.0, fixed_fraction=0.05, max_risk_cap=0.02)
        self.assertEqual(alloc_capped.stake, 20.0)

    def test_anti_martingale_invariant_verification(self):
        # 1. Kelly Staking must pass anti-martingale verification
        passed_kelly = verify_anti_martingale_invariant(
            calculate_kelly_stake,
            base_balance=1000.0,
            payout=0.85,
            sample_wins=180,
            sample_n=300,
        )
        self.assertTrue(passed_kelly)

        # 2. Fixed Staking must pass anti-martingale verification
        passed_fixed = verify_anti_martingale_invariant(
            calculate_fixed_stake,
            base_balance=1000.0,
            fixed_fraction=0.01,
        )
        self.assertTrue(passed_fixed)

    def test_martingale_detection_catches_cheating(self):
        # Negative control: define a fraudulent martingale staking function
        def fraudulent_martingale_stake(balance: float, consecutive_losses: int = 0, **kwargs):
            # Doubles stake on consecutive losses
            base_stake = 10.0
            stake = base_stake * (2.0 ** consecutive_losses)
            return StakeAllocation(
                stake=stake,
                fraction=stake / balance,
                method="FRAUDULENT_MARTINGALE",
                is_allowed=True,
                balance=balance,
                max_risk_cap=1.0,
                metadata={},
            )

        with self.assertRaises(AntiMartingaleViolationError):
            verify_anti_martingale_invariant(
                fraudulent_martingale_stake,
                base_balance=1000.0,
                consecutive_loss_streaks=[0, 1, 2, 3],
            )


if __name__ == "__main__":
    unittest.main()
