"""
test_adversarial_m1.py - Adversarial Stress Test Suite for M1 Feature Engine & Data Loader.

Adversarially stress-tests:
1. Extreme volatility flash crash / spike (50x standard deviation).
2. Flatline zero-volatility prices (constant Close).
3. Oscillating alternating whipsaws (sudden, persistent, and ADX/DI contradiction).
4. Massive wick anomalies (giant upper/lower wicks, long-legged doji).
5. Gaps, missing rows, and small sample frames (< 50 bars).
6. NaN propagation and zero division safety.
7. DataLoader schema rejection and corrupted input integrity.
"""

import unittest
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.indicators import (
    compute_true_range,
    compute_atr,
    compute_natr,
    compute_bollinger_bandwidth,
    compute_bbw_zscore,
    compute_normalized_realized_volatility,
    compute_vol_shock,
    compute_adx,
    compute_return_autocorrelation,
    compute_variance_ratio,
    compute_rsi,
    compute_stochastic,
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
from iq_regime_adaptive.pipeline.data_loader import (
    DataLoader,
    load_csv,
    normalize_timestamps,
    validate_ohlcv,
    DataValidationError,
)


class TestAdversarialStressM1(unittest.TestCase):
    """Adversarial stress-test harness for Feature Engine and Data Loader."""

    def setUp(self):
        self.classifier = RegimeClassifier(min_candles=50)
        self.router = SignalRouter(self.classifier)

        # Baseline random walk dataset (n=100)
        np.random.seed(42)
        n = 100
        self.rets = np.random.normal(0, 0.001, n)
        self.prices = 1.1000 * np.exp(np.cumsum(self.rets))
        self.base_df = pd.DataFrame({
            "open": self.prices,
            "high": self.prices * 1.0005,
            "low": self.prices * 0.9995,
            "close": self.prices,
            "volume": 1000.0,
        })

    # =========================================================================
    # 1. Extreme Volatility Flash Crash / Spike (50x Standard Deviation)
    # =========================================================================

    def test_extreme_flash_crash_50x_std(self):
        """Stress test: 50x stddev sudden price collapse on final candle."""
        df = self.base_df.copy()
        std_ret = float(np.std(self.rets))
        crash_close = float(df.loc[98, "close"] * (1.0 - 50.0 * std_ret))
        df.loc[99, "close"] = crash_close
        df.loc[99, "low"] = crash_close * 0.9990
        df.loc[99, "high"] = float(df.loc[98, "close"])
        df.loc[99, "open"] = float(df.loc[98, "close"])

        out = self.classifier.classify_latest(df)
        decision = self.router.route_signal(df, out)

        self.assertEqual(out.regime, MarketRegime.CHAOS, "Flash crash must trigger CHAOS")
        self.assertFalse(out.allow_trade, "Flash crash must forbid trading")
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE, "SignalRouter must output NO_TRADE")
        self.assertFalse(decision.confidence > 0, "Confidence must be 0.0 on CHAOS veto")
        self.assertEqual(out.tier_triggered, 1, "Must be triggered by Tier 1 Chaos Guard")

        # Verify no NaN in returned metrics
        for k, v in out.metrics.items():
            self.assertFalse(np.isnan(v), f"Metric '{k}' contains NaN during flash crash")

    def test_extreme_flash_spike_50x_std(self):
        """Stress test: 50x stddev sudden upward price surge on final candle."""
        df = self.base_df.copy()
        std_ret = float(np.std(self.rets))
        spike_close = float(df.loc[98, "close"] * (1.0 + 50.0 * std_ret))
        df.loc[99, "close"] = spike_close
        df.loc[99, "high"] = spike_close * 1.0010
        df.loc[99, "low"] = float(df.loc[98, "close"])
        df.loc[99, "open"] = float(df.loc[98, "close"])

        out = self.classifier.classify_latest(df)
        decision = self.router.route_signal(df, out)

        self.assertEqual(out.regime, MarketRegime.CHAOS, "Flash spike must trigger CHAOS")
        self.assertFalse(out.allow_trade, "Flash spike must forbid trading")
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE, "SignalRouter must output NO_TRADE")
        self.assertEqual(out.tier_triggered, 1, "Must be triggered by Tier 1 Chaos Guard")

        for k, v in out.metrics.items():
            self.assertFalse(np.isnan(v), f"Metric '{k}' contains NaN during flash spike")

    # =========================================================================
    # 2. Flatline Zero-Volatility Prices (Constant Close)
    # =========================================================================

    def test_flatline_zero_volatility_detection(self):
        """Stress test: 60 bars of perfectly constant OHLC prices (zero volatility)."""
        df_flat = pd.DataFrame({
            "open": [1.1000] * 60,
            "high": [1.1000] * 60,
            "low": [1.1000] * 60,
            "close": [1.1000] * 60,
            "volume": [100.0] * 60,
        })

        out = self.classifier.classify_latest(df_flat)
        decision = self.router.route_signal(df_flat, out)

        # In zero volatility, system must NOT allow trades
        self.assertEqual(out.regime, MarketRegime.CHAOS, "Zero-vol flatline must be classified as CHAOS")
        self.assertFalse(out.allow_trade, "Zero-vol flatline must forbid trading")
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE, "SignalRouter must output NO_TRADE on flatline")

        # Invariant: No NaN propagation escapes unhandled into metrics
        for k, v in out.metrics.items():
            self.assertFalse(np.isnan(v), f"Metric '{k}' in flatline metrics contains unhandled NaN")

    # =========================================================================
    # 3. Oscillating Alternating Whipsaws
    # =========================================================================

    def test_sudden_alternating_whipsaw(self):
        """Stress test: Normal baseline followed by sudden violent alternating swings."""
        prices = list(self.prices[:80])
        for i in range(10):
            p = prices[-1] + (0.0100 if i % 2 == 0 else -0.0100)
            prices.append(p)

        df = pd.DataFrame({
            "open": prices,
            "high": [p + 0.0020 for p in prices],
            "low": [p - 0.0020 for p in prices],
            "close": prices,
            "volume": [100.0] * len(prices),
        })

        out = self.classifier.classify_latest(df)
        decision = self.router.route_signal(df, out)

        self.assertEqual(out.regime, MarketRegime.CHAOS, "Sudden alternating whipsaw must trigger CHAOS")
        self.assertFalse(out.allow_trade, "Sudden alternating whipsaw must forbid trading")
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE)

    def test_persistent_alternating_whipsaw_veto(self):
        """
        Stress test: Persistent alternating whipsaw (ping-pong square wave for 100 bars).
        An oscillating alternating whipsaw is an extreme condition and must not be marked as a safe RANGE.
        """
        whipsaw_prices = [1.1000 if i % 2 == 0 else 1.1100 for i in range(100)]
        df_whip = pd.DataFrame({
            "open": whipsaw_prices,
            "high": [p + 0.0050 for p in whipsaw_prices],
            "low": [p - 0.0050 for p in whipsaw_prices],
            "close": whipsaw_prices,
            "volume": [100.0] * 100,
        })

        out = self.classifier.classify_latest(df_whip)
        decision = self.router.route_signal(df_whip, out)

        # In extreme alternating whipsaw, the system must robustly flag CHAOS
        self.assertEqual(
            out.regime,
            MarketRegime.CHAOS,
            f"Persistent alternating whipsaw flagged as '{out.regime.value}' instead of CHAOS!",
        )
        self.assertFalse(out.allow_trade, "Alternating whipsaw must not allow trading")
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE)

    def test_adx_di_contradiction_whipsaw(self):
        """Stress test: ADX elevated with DI spread collapse (contradiction whipsaw)."""
        # Create a series where ADX >= 35 but plus_di ~= minus_di
        # Trend up for 40 bars then oscillate violently
        prices = [1.0000 + 0.0030 * i for i in range(50)]
        for i in range(20):
            prices.append(prices[-1] + (0.0040 if i % 2 == 0 else -0.0040))

        df = pd.DataFrame({
            "open": prices,
            "high": [p + 0.0020 for p in prices],
            "low": [p - 0.0020 for p in prices],
            "close": prices,
            "volume": [100.0] * len(prices),
        })

        out = self.classifier.classify_latest(df)
        decision = self.router.route_signal(df, out)

        self.assertEqual(out.regime, MarketRegime.CHAOS)
        self.assertFalse(out.allow_trade)
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE)

    # =========================================================================
    # 4. Massive Wick Anomalies
    # =========================================================================

    def test_massive_upper_wick_anomaly(self):
        """Stress test: Giant upper wick pin bar (20x ATR)."""
        df = self.base_df.copy()
        df.loc[99, "high"] = float(df.loc[99, "close"] + 0.0500)  # Massive upper wick

        out = self.classifier.classify_latest(df)
        decision = self.router.route_signal(df, out)

        self.assertEqual(out.regime, MarketRegime.CHAOS, "Giant upper wick anomaly must trigger CHAOS")
        self.assertFalse(out.allow_trade)
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE)
        self.assertEqual(out.tier_triggered, 1)

    def test_massive_lower_wick_anomaly(self):
        """Stress test: Giant lower wick anomaly (20x ATR)."""
        df = self.base_df.copy()
        df.loc[99, "low"] = float(df.loc[99, "close"] - 0.0500)  # Massive lower wick

        out = self.classifier.classify_latest(df)
        decision = self.router.route_signal(df, out)

        self.assertEqual(out.regime, MarketRegime.CHAOS, "Giant lower wick anomaly must trigger CHAOS")
        self.assertFalse(out.allow_trade)
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE)
        self.assertEqual(out.tier_triggered, 1)

    def test_massive_symmetric_doji_wick_anomaly(self):
        """Stress test: Massive symmetric wicks (both upper and lower wicks 15x normal bar)."""
        df = self.base_df.copy()
        c = float(df.loc[99, "close"])
        df.loc[99, "high"] = c + 0.0300
        df.loc[99, "low"] = c - 0.0300
        df.loc[99, "open"] = c

        out = self.classifier.classify_latest(df)
        decision = self.router.route_signal(df, out)

        self.assertEqual(out.regime, MarketRegime.CHAOS)
        self.assertFalse(out.allow_trade)
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE)

    # =========================================================================
    # 5. Gaps, Missing Rows, and Small Sample Frames (< 50 bars)
    # =========================================================================

    def test_small_sample_frames_under_50_bars(self):
        """Stress test: Candle sample sizes < 50 bars (0, 1, 5, 20, 49 bars)."""
        for count in [0, 1, 5, 20, 49]:
            df_small = self.base_df.iloc[:count].copy()
            out = self.classifier.classify_latest(df_small)
            decision = self.router.route_signal(df_small, out)

            self.assertEqual(
                out.regime,
                MarketRegime.CHAOS,
                f"Small frame of {count} bars failed to flag CHAOS",
            )
            self.assertFalse(
                out.allow_trade,
                f"Small frame of {count} bars incorrectly allowed trade",
            )
            self.assertEqual(
                decision.signal,
                MarketSignal.NO_TRADE,
                f"Small frame of {count} bars did not output NO_TRADE",
            )

    def test_classify_series_small_frame(self):
        """Stress test: classify_regime on DataFrame smaller than min_candles."""
        df_small = self.base_df.iloc[:30].copy()
        series = classify_regime(df_small)
        self.assertEqual(len(series), 30)
        self.assertTrue((series == "CHAOS").all(), "All rows under min_candles must be CHAOS")

    def test_gap_jump_anomaly(self):
        """Stress test: 500-pip weekend/overnight price gap jump."""
        prices = [1.1000 + 0.0001 * i for i in range(60)]
        prices.append(1.1500)  # 500-pip gap jump

        df_gap = pd.DataFrame({
            "open": prices,
            "high": [p + 0.0005 for p in prices],
            "low": [p - 0.0005 for p in prices],
            "close": prices,
            "volume": [1000.0] * len(prices),
        })

        out = self.classifier.classify_latest(df_gap)
        decision = self.router.route_signal(df_gap, out)

        self.assertEqual(out.regime, MarketRegime.CHAOS, "500-pip gap jump must trigger CHAOS")
        self.assertFalse(out.allow_trade)
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE)

    # =========================================================================
    # 6. NaN Propagation & Zero Division Safety
    # =========================================================================

    def test_nan_in_candle_data_handling(self):
        """
        Stress test: Passing raw DataFrame containing NaN values into classify_latest.
        Must not crash and must not propagate NaN into out.metrics.
        """
        df_nan = self.base_df.copy()
        df_nan.loc[45, "close"] = np.nan

        out = self.classifier.classify_latest(df_nan)
        decision = self.router.route_signal(df_nan, out)

        self.assertEqual(out.regime, MarketRegime.CHAOS)
        self.assertFalse(out.allow_trade)
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE)

        # Check no NaN values escaped into metrics
        for k, v in out.metrics.items():
            self.assertFalse(
                np.isnan(v),
                f"Metric '{k}' contains unhandled NaN when input contains NaN",
            )

    def test_zero_division_guard_all_indicators(self):
        """Stress test: Ensure core indicators handle all-zero or extreme zero inputs without crashing."""
        zeros = pd.Series(np.zeros(50))
        ones = pd.Series(np.ones(50))

        # True Range & ATR
        tr = compute_true_range(ones, ones, ones)
        self.assertFalse(tr.isna().any())
        atr = compute_atr(ones, ones, ones, period=14)
        self.assertFalse(atr.isna().any())

        # NATR with near-zero close
        natr = compute_natr(ones, ones, pd.Series(np.full(50, 1e-15)), period=14)
        self.assertFalse(natr.isna().any())

        # BBW and BBW Z-Score with zero volatility
        bbw = compute_bollinger_bandwidth(ones, period=20)
        self.assertFalse(bbw.iloc[20:].isna().any())
        bbw_z = compute_bbw_zscore(bbw, lookback=20)
        self.assertFalse(bbw_z.iloc[30:].isna().any(), "bbw_z should be finite and non-NaN after warmup")

        # NRV with constant prices
        nrv = compute_normalized_realized_volatility(ones, short_window=10, long_window=30)
        self.assertFalse(nrv.iloc[30:].isna().any())

        # Vol shock with constant prices
        vol_shock = compute_vol_shock(ones, fast_period=5, slow_period=20)
        self.assertFalse(vol_shock.iloc[20:].isna().any())

        # ADX with flat prices
        adx, pdi, mdi, _ = compute_adx(ones, ones, ones, period=14)
        self.assertFalse(adx.isna().any())

        # Variance ratio with constant array
        vr, z_vr = compute_variance_ratio(np.ones(60), q=4)
        self.assertFalse(np.isnan(vr), "Variance ratio returned NaN on constant array")
        self.assertFalse(np.isnan(z_vr), "VR z-stat returned NaN on constant array")

        # RSI with constant prices
        rsi = compute_rsi(ones, period=14)
        self.assertFalse(rsi.isna().any())

        # Stochastic with flat prices
        stoch_k, stoch_d = compute_stochastic(ones, ones, ones, k_period=14, d_period=3)
        self.assertFalse(stoch_k.iloc[14:].isna().any())

        # Candle morphology with zero range
        morph = compute_candle_morphology(ones, ones, ones, ones)
        self.assertFalse(morph["body_ratio"].isna().any())
        self.assertFalse(morph["upper_wick_ratio"].isna().any())

    # =========================================================================
    # 7. DataLoader Adversarial Schema & Corrupted Ingestion
    # =========================================================================

    def test_dataloader_rejects_inverted_high_low(self):
        """DataLoader must raise DataValidationError when high < low."""
        df = pd.DataFrame({
            "open": [1.1000],
            "high": [1.0900],  # high < low!
            "low": [1.1100],
            "close": [1.1000],
        })
        with self.assertRaises(DataValidationError):
            validate_ohlcv(df)

    def test_dataloader_rejects_high_below_open_or_close(self):
        """DataLoader must raise DataValidationError when high < max(open, close)."""
        df = pd.DataFrame({
            "open": [1.1200],
            "high": [1.1100],  # high < open
            "low": [1.0800],
            "close": [1.1000],
        })
        with self.assertRaises(DataValidationError):
            validate_ohlcv(df)

    def test_dataloader_rejects_low_above_open_or_close(self):
        """DataLoader must raise DataValidationError when low > min(open, close)."""
        df = pd.DataFrame({
            "open": [1.1000],
            "high": [1.1200],
            "low": [1.1050],  # low > open
            "close": [1.1100],
        })
        with self.assertRaises(DataValidationError):
            validate_ohlcv(df)

    def test_dataloader_rejects_non_positive_prices(self):
        """DataLoader must reject zero or negative prices."""
        for bad_price in [0.0, -1.05]:
            df = pd.DataFrame({
                "open": [bad_price],
                "high": [1.1200],
                "low": [1.0800],
                "close": [1.1000],
            })
            with self.assertRaises(DataValidationError):
                validate_ohlcv(df)

    def test_dataloader_rejects_nan_or_string_in_numeric_columns(self):
        """DataLoader must reject NaNs or corrupted strings in price columns."""
        df_corrupt = pd.DataFrame({
            "open": ["CORRUPTED_STRING"],
            "high": [1.1200],
            "low": [1.0800],
            "close": [1.1000],
        })
        with self.assertRaises(DataValidationError):
            validate_ohlcv(df_corrupt)

    def test_dataloader_rejects_negative_volume(self):
        """DataLoader must reject negative volume values."""
        df = pd.DataFrame({
            "open": [1.1000],
            "high": [1.1200],
            "low": [1.0800],
            "close": [1.1000],
            "volume": [-50.0],
        })
        with self.assertRaises(DataValidationError):
            validate_ohlcv(df)

    def test_dataloader_rejects_missing_mandatory_columns(self):
        """DataLoader must reject files missing open, high, low, or close."""
        df = pd.DataFrame({
            "time": ["2026-06-22 10:00:00"],
            "open": [1.1000],
            "high": [1.1200],
            # low missing
            "close": [1.1000],
        })
        with self.assertRaises(DataValidationError):
            validate_ohlcv(df)

    def test_dataloader_empty_csv_rejection(self):
        """DataLoader must raise DataValidationError on empty CSV files."""
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as tf:
            tf.write("")
            tf_path = Path(tf.name)

        try:
            loader = DataLoader()
            with self.assertRaises(DataValidationError):
                loader.load_csv(tf_path)
        finally:
            if tf_path.exists():
                tf_path.unlink()

    def test_dataloader_timestamp_deduplication_and_sorting(self):
        """DataLoader must deduplicate identical timestamps and sort chronologically."""
        csv_content = """time,open,high,low,close,volume
2026-06-22 10:05:00,1.1050,1.1080,1.1040,1.1070,100
2026-06-22 10:00:00,1.1000,1.1050,1.0990,1.1040,150
2026-06-22 10:00:00,1.1000,1.1050,1.0990,1.1040,150
2026-06-22 10:10:00,1.1070,1.1100,1.1060,1.1090,200
"""
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as tf:
            tf.write(csv_content)
            tf_path = Path(tf.name)

        try:
            loader = DataLoader()
            df = loader.load_csv(tf_path)
            self.assertEqual(len(df), 3, "Duplicates must be dropped")
            times = df["time"].tolist()
            self.assertTrue(times[0] < times[1] < times[2], "Timestamps must be strictly chronological")
        finally:
            if tf_path.exists():
                tf_path.unlink()


if __name__ == "__main__":
    unittest.main()
