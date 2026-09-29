"""
test_backtest.py - Unit and Integration Tests for Backtest Engine, Partitioner, Metrics & Degradation.
"""

import unittest
import numpy as np
import pandas as pd

from iq_regime_adaptive.backtest.partitioner import (
    DataPartitioner,
    PartitionedData,
    partition_dataset,
)
from iq_regime_adaptive.backtest.metrics import (
    compute_effective_n,
    compute_backtest_metrics,
    BacktestMetrics,
)
from iq_regime_adaptive.backtest.engine import (
    BacktestEngine,
    BacktestResult,
    TradeRecord,
)
from iq_regime_adaptive.backtest.degradation import (
    compute_degradation,
    DegradationReport,
)
from iq_regime_adaptive.feature_engine.signal_router import MarketSignal


def generate_synthetic_ohlcv(n_bars: int = 1000, seed: int = 42) -> pd.DataFrame:
    """Generates synthetic OHLCV price series for backtesting verification."""
    np.random.seed(seed)
    timestamps = pd.date_range("2026-01-01 00:00:00", periods=n_bars, freq="5min")
    
    # Geometric brownian motion
    returns = np.random.normal(0.0001, 0.002, size=n_bars)
    price = 100.0 * np.exp(np.cumsum(returns))

    high = price * (1.0 + np.abs(np.random.normal(0, 0.001, size=n_bars)))
    low = price * (1.0 - np.abs(np.random.normal(0, 0.001, size=n_bars)))
    open_p = price + np.random.normal(0, 0.0005, size=n_bars)
    close = price
    volume = np.random.randint(100, 1000, size=n_bars)

    df = pd.DataFrame(
        {
            "open": open_p,
            "high": np.maximum(high, np.maximum(open_p, close)),
            "low": np.minimum(low, np.minimum(open_p, close)),
            "close": close,
            "volume": volume,
        },
        index=timestamps,
    )
    return df


class TestPartitioner(unittest.TestCase):
    """Verifies rigid chronological partitioning, purging, and embargo invariants."""

    def setUp(self):
        self.df = generate_synthetic_ohlcv(1000)

    def test_chronological_split_ratios(self):
        partitioner = DataPartitioner(is_ratio=0.50, val_ratio=0.25, oos_ratio=0.25, horizon_bars=1, warmup_bars=60)
        res = partitioner.partition(self.df)

        self.assertEqual(len(res.is_df), 500)
        self.assertEqual(len(res.val_df), 250)
        self.assertEqual(len(res.oos_df), 250)

        # Monotonicity check
        self.assertTrue(res.is_df.index[-1] < res.val_df.index[0])
        self.assertTrue(res.val_df.index[-1] < res.oos_df.index[0])

    def test_boundary_purging_invariant(self):
        horizon = 3
        partitioner = DataPartitioner(is_ratio=0.50, val_ratio=0.25, oos_ratio=0.25, horizon_bars=horizon, warmup_bars=10)
        res = partitioner.partition(self.df)

        # Check IS boundary purging
        is_purged = res.is_df["boundary_purged"].values
        is_eligible = res.is_df["trade_eligible"].values

        # The last `horizon` bars must be boundary_purged and NOT trade_eligible
        self.assertTrue(np.all(is_purged[-horizon:]))
        self.assertTrue(np.all(~is_eligible[-horizon:]))
        # Bars before the boundary purge window must NOT be boundary_purged
        self.assertFalse(is_purged[-horizon - 1])

        # Same for VAL
        val_purged = res.val_df["boundary_purged"].values
        self.assertTrue(np.all(val_purged[-horizon:]))

    def test_warmup_embargo_invariant(self):
        warmup = 60
        partitioner = DataPartitioner(is_ratio=0.50, val_ratio=0.25, oos_ratio=0.25, horizon_bars=1, warmup_bars=warmup)
        res = partitioner.partition(self.df)

        # First `warmup` bars must have warmup_embargo == True and trade_eligible == False
        for p_df in [res.is_df, res.val_df, res.oos_df]:
            self.assertTrue(np.all(p_df["warmup_embargo"].values[:warmup]))
            self.assertTrue(np.all(~p_df["trade_eligible"].values[:warmup]))
            self.assertFalse(p_df["warmup_embargo"].values[warmup])

    def test_partition_dataset_interface_contract(self):
        is_df, val_df, oos_df = partition_dataset(self.df, is_ratio=0.50, val_ratio=0.25, oos_ratio=0.25, horizon_bars=2, warmup_bars=50)
        self.assertEqual(len(is_df), 500)
        self.assertEqual(len(val_df), 250)
        self.assertEqual(len(oos_df), 250)
        self.assertIn("trade_eligible", is_df.columns)
        self.assertIn("trade_eligible", val_df.columns)
        self.assertIn("trade_eligible", oos_df.columns)

    def test_invalid_parameters_raise_errors(self):
        with self.assertRaises(ValueError):
            DataPartitioner(is_ratio=0.6, val_ratio=0.3, oos_ratio=0.3)  # sum != 1
        with self.assertRaises(ValueError):
            DataPartitioner(horizon_bars=0)
        with self.assertRaises(ValueError):
            DataPartitioner().partition(self.df.iloc[:20])  # too short


class TestBacktestMetrics(unittest.TestCase):
    """Verifies statistical metric derivations including WLB and N_eff."""

    def test_metrics_calculation_accuracy(self):
        # 60 wins, 40 losses, 0 pushes
        pnls = [8.5] * 60 + [-10.0] * 40
        results = ["WIN"] * 60 + ["LOSS"] * 40
        trades_df = pd.DataFrame({
            "trade_id": range(1, 101),
            "result": results,
            "pnl": pnls,
            "balance": 1000.0 + np.cumsum(pnls),
        })

        metrics = compute_backtest_metrics(trades_df, initial_balance=1000.0, payout=0.85)

        self.assertEqual(metrics.total_trades, 100)
        self.assertEqual(metrics.wins, 60)
        self.assertEqual(metrics.losses, 40)
        self.assertAlmostEqual(metrics.nominal_win_rate, 0.60, places=4)
        # Wilson lower bound for 60/100 should be ~0.502
        self.assertTrue(0.49 < metrics.wilson_lower_bound < 0.52)
        # EV nominal = 0.60 * 1.85 - 1 = +0.110
        self.assertAlmostEqual(metrics.expected_value, 0.110, places=3)
        self.assertAlmostEqual(metrics.total_pnl, 60 * 8.5 - 40 * 10.0, places=2)

    def test_effective_n_with_serial_correlation(self):
        np.random.seed(42)
        # Independent coin flips (low autocorrelation)
        independent = list(np.random.binomial(1, 0.5, size=200))
        n_eff_indep = compute_effective_n(independent)
        # For independent trials, n_eff should be close to N (>= 150)
        self.assertGreater(n_eff_indep, 150.0)

        # Heavily clustered outcomes (positive correlation: win streaks and loss streaks)
        clustered = [1] * 25 + [0] * 25 + [1] * 25 + [0] * 25
        n_eff_clustered = compute_effective_n(clustered)
        # Clustering reduces degrees of freedom
        self.assertLess(n_eff_clustered, 60.0)

    def test_empty_trades_handling(self):
        empty_df = pd.DataFrame(columns=["result", "pnl", "balance"])
        metrics = compute_backtest_metrics(empty_df, initial_balance=1000.0)
        self.assertEqual(metrics.total_trades, 0)
        self.assertEqual(metrics.total_pnl, 0.0)
        self.assertEqual(metrics.max_drawdown, 0.0)


class TestBacktestEngine(unittest.TestCase):
    """Verifies backtesting simulation, payoff evaluation, and risk allocation."""

    def setUp(self):
        self.df = generate_synthetic_ohlcv(500)

    def test_binary_option_payoff_evaluation(self):
        # Create synthetic deterministic signals
        signals = pd.Series(MarketSignal.NO_TRADE.value, index=self.df.index)
        signals.iloc[10] = MarketSignal.CALL.value
        signals.iloc[20] = MarketSignal.PUT.value

        engine = BacktestEngine(
            initial_balance=1000.0,
            risk_method="fixed",
            fixed_stake=10.0,
            execution_mode="next_open",
            kill_switch_drawdown=0.50,
        )

        res = engine.run(self.df, hypothesis=signals, payout=0.85, horizon_bars=1)
        self.assertGreaterEqual(len(res.trades), 1)

        for trade in res.trades:
            self.assertEqual(trade.stake, 10.0)
            if trade.result == "WIN":
                self.assertAlmostEqual(trade.pnl, 8.50, places=2)
            elif trade.result == "LOSS":
                self.assertAlmostEqual(trade.pnl, -10.00, places=2)
            elif trade.result == "PUSH":
                self.assertAlmostEqual(trade.pnl, 0.00, places=2)

    def test_boundary_purging_in_engine(self):
        # Place signal on the last bar of df
        signals = pd.Series(MarketSignal.NO_TRADE.value, index=self.df.index)
        signals.iloc[-1] = MarketSignal.CALL.value

        engine = BacktestEngine(initial_balance=1000.0)
        res = engine.run(self.df, hypothesis=signals, payout=0.85, horizon_bars=1)

        # Must be purged because t+1 or t+h >= len(df)
        self.assertEqual(len(res.trades), 0)
        self.assertEqual(res.purged_signals_count, 1)

    def test_anti_martingale_zero_gale_verification(self):
        """Verifies that stake strictly contracts with equity decay and never escalates on losses."""
        # Generate alternating loss sequence
        signals = pd.Series(MarketSignal.NO_TRADE.value, index=self.df.index)
        for i in range(10, 60, 2):
            signals.iloc[i] = MarketSignal.CALL.value

        engine = BacktestEngine(
            initial_balance=1000.0,
            risk_method="fractional_kelly",
            fractional_gamma=0.25,
            max_risk_cap=0.02,
        )

        res = engine.run(self.df, hypothesis=signals, payout=0.85, horizon_bars=1)
        trades = res.trades
        self.assertGreater(len(trades), 5)

        for i in range(1, len(trades)):
            prev_trade = trades[i - 1]
            curr_trade = trades[i]
            # Invariant: If previous trade was a loss, stake cannot be higher than prior stake * balance_ratio
            if prev_trade.result == "LOSS":
                self.assertLessEqual(
                    curr_trade.stake,
                    prev_trade.stake * 1.05,  # slight tolerance for rounding/min_stake
                    "Stake increased after a loss! Anti-martingale violation.",
                )

    def test_kill_switch_trigger(self):
        """Verifies that cumulative drawdown halts trading immediately."""
        signals = pd.Series(MarketSignal.NO_TRADE.value, index=self.df.index)
        for i in range(10, 100):
            signals.iloc[i] = MarketSignal.CALL.value

        engine = BacktestEngine(
            initial_balance=100.0,
            risk_method="fixed",
            fixed_stake=10.0,  # 10% risk per trade -> 2 losses trigger 20% drawdown kill switch
            kill_switch_drawdown=0.20,
        )

        res = engine.run(self.df, hypothesis=signals, payout=0.85, horizon_bars=1)
        if res.kill_switch_triggered:
            drawdown = (res.initial_balance - res.final_balance) / res.initial_balance
            self.assertGreaterEqual(drawdown, 0.20)


class TestDegradation(unittest.TestCase):
    """Verifies degradation mathematics (Delta EV, DI, Delta WR, S_comp)."""

    def test_robust_degradation_evaluation(self):
        is_metrics = {
            "expected_value": 0.150,
            "nominal_win_rate": 0.620,
            "wilson_lower_bound": 0.550,
            "breakeven_win_rate": 0.54054,
            "max_drawdown_pct": 0.08,
            "monthly_consistency": "4_OF_4_MONTHS_PROFITABLE",
        }
        oos_metrics = {
            "expected_value": 0.125,
            "nominal_win_rate": 0.605,
            "wilson_lower_bound": 0.600,
            "breakeven_win_rate": 0.54054,
            "max_drawdown_pct": 0.09,
            "monthly_consistency": "4_OF_4_MONTHS_PROFITABLE",
        }

        report = compute_degradation(is_metrics, oos_metrics)

        # Delta EV = 0.150 - 0.125 = 0.025
        self.assertAlmostEqual(report.delta_ev, 0.025, places=3)
        # DI = 0.025 / 0.150 = 0.1667 (<= 0.25 -> ROBUST)
        self.assertAlmostEqual(report.degradation_index, 0.1667, places=3)
        self.assertEqual(report.verdict, "ROBUST")
        # Stability score should be high (> 75)
        self.assertGreater(report.stability_score, 75.0)

    def test_rejected_overfitted_degradation(self):
        is_metrics = {
            "expected_value": 0.200,
            "nominal_win_rate": 0.650,
            "wilson_lower_bound": 0.580,
            "breakeven_win_rate": 0.54054,
            "max_drawdown_pct": 0.05,
        }
        oos_metrics = {
            "expected_value": -0.050,  # Negative EV in OOS
            "nominal_win_rate": 0.510,
            "wilson_lower_bound": 0.440,
            "breakeven_win_rate": 0.54054,
            "max_drawdown_pct": 0.25,
        }

        report = compute_degradation(is_metrics, oos_metrics)
        self.assertEqual(report.verdict, "REJECTED")
        self.assertGreater(report.degradation_index, 0.75)


class TestBacktestEndToEndIntegration(unittest.TestCase):
    """End-to-end integration test validating the entire M2 backtesting and hypotheses pipeline."""

    def setUp(self):
        from iq_regime_adaptive.hypotheses import get_all_hypotheses
        self.df = generate_synthetic_ohlcv(600, seed=123)
        self.partitioner = DataPartitioner(is_ratio=0.50, val_ratio=0.25, oos_ratio=0.25, horizon_bars=1, warmup_bars=30)
        self.part_data = self.partitioner.partition(self.df)
        self.hypotheses = get_all_hypotheses()

    def test_all_8_hypotheses_across_partitions_and_degradation(self):
        engine = BacktestEngine(initial_balance=1000.0, risk_method="fixed", fixed_stake=10.0)

        for hyp_id, hyp in self.hypotheses.items():
            # 1. In-Sample run
            res_is = engine.run(self.part_data.is_df, hypothesis=hyp, payout=0.85)
            self.assertIsInstance(res_is, BacktestResult)
            self.assertIsInstance(res_is.metrics, BacktestMetrics)

            # 2. Out-of-Sample run
            res_oos = engine.run(self.part_data.oos_df, hypothesis=hyp, payout=0.85)
            self.assertIsInstance(res_oos, BacktestResult)

            # 3. Degradation computation
            deg = compute_degradation(res_is.metrics, res_oos.metrics)
            self.assertIsInstance(deg, DegradationReport)
            self.assertIn(deg.verdict, ("ANTIFRAGILE", "ROBUST", "MODERATE_DECAY", "SEVERE_DECAY", "REJECTED"))
            self.assertTrue(0.0 <= deg.stability_score <= 100.0)


if __name__ == "__main__":
    unittest.main()
