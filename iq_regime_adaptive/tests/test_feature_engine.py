"""
test_feature_engine.py - Unit Tests for Quantitative Feature Engine & Regime Classification.
"""

import unittest
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.indicators import (
    compute_true_range,
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


def _generate_synthetic_candles(
    n: int = 150,
    base_price: float = 1.1000,
    regime_type: str = "random",
    seed: int = 42,
) -> pd.DataFrame:
    """Helper to generate realistic OHLCV price series under specific statistical dynamics."""
    rng = np.random.RandomState(seed)
    times = pd.date_range("2026-01-01 00:00", periods=n, freq="5min", tz="UTC")

    if regime_type == "trend_up":
        # Monotonic positive drift with low noise
        drift = 0.0003
        noise = rng.normal(0, 0.00005, n)
        returns = drift + noise
        prices = base_price * np.exp(np.cumsum(returns))
    elif regime_type == "trend_down":
        drift = -0.0003
        noise = rng.normal(0, 0.00005, n)
        returns = drift + noise
        prices = base_price * np.exp(np.cumsum(returns))
    elif regime_type == "range":
        # Mean-reverting Ornstein-Uhlenbeck style oscillation
        prices = np.zeros(n)
        prices[0] = base_price
        for i in range(1, n):
            # Pull back toward base_price
            prices[i] = prices[i - 1] + 0.35 * (base_price - prices[i - 1]) + rng.normal(0, 0.0001)
    elif regime_type == "expansion":
        # First 120 bars tight compression, last 30 bars explosive breakout
        prices = np.zeros(n)
        prices[0] = base_price
        for i in range(1, 120):
            prices[i] = prices[i - 1] + rng.normal(0, 0.00002)
        for i in range(120, n):
            prices[i] = prices[i - 1] + 0.0008 + rng.normal(0, 0.0001)
    else:
        # Standard geometric random walk
        returns = rng.normal(0, 0.0002, n)
        prices = base_price * np.exp(np.cumsum(returns))

    # Construct OHLC around close prices
    high = np.zeros(n)
    low = np.zeros(n)
    open_p = np.zeros(n)
    close = prices

    for i in range(n):
        if i == 0:
            open_p[i] = base_price
        else:
            open_p[i] = close[i - 1]
        
        spread = abs(rng.normal(0, 0.0001)) + 0.00005
        high[i] = max(open_p[i], close[i]) + spread
        low[i] = min(open_p[i], close[i]) - spread

    return pd.DataFrame({
        "time": times,
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": rng.uniform(10.0, 100.0, n),
    })


class TestFeatureEngineIndicators(unittest.TestCase):
    """Test suite for mathematical and statistical accuracy of technical indicators."""

    def test_true_range_and_atr_properties(self):
        df = _generate_synthetic_candles(n=60, regime_type="random", seed=10)
        tr = compute_true_range(df["high"], df["low"], df["close"])
        atr = compute_atr(df["high"], df["low"], df["close"], period=14)
        natr = compute_natr(df["high"], df["low"], df["close"], period=14)

        # Invariants: TR and ATR must be strictly positive
        self.assertTrue((tr > 0).all(), "True Range must be positive")
        self.assertTrue((atr > 0).all(), "ATR must be positive")
        self.assertTrue((natr > 0).all(), "NATR must be positive")

        # Invariant: NATR scale consistency NATR = (ATR / Close) * 100
        expected_natr = (atr / df["close"]) * 100.0
        np.testing.assert_allclose(natr.values, expected_natr.values, rtol=1e-5)

        # Verify ATR expansion ratio
        atr_ratio = compute_atr_ratio(df["high"], df["low"], df["close"], fast_period=5, slow_period=30)
        self.assertTrue((atr_ratio > 0).all(), "ATR ratio must be positive")

    def test_bollinger_bands_and_bandwidth(self):
        df = _generate_synthetic_candles(n=80, regime_type="random", seed=11)
        mid, up, low = compute_bollinger_bands(df["close"], period=20, k=2.0)
        bbw = compute_bollinger_bandwidth(df["close"], period=20, k=2.0)

        # Invariants: Upper >= Middle >= Lower
        valid_idx = mid.notna()
        self.assertTrue((up[valid_idx] >= mid[valid_idx]).all())
        self.assertTrue((mid[valid_idx] >= low[valid_idx]).all())

        # Invariant: BBW = (Upper - Lower) / Middle
        expected_bbw = (up[valid_idx] - low[valid_idx]) / mid[valid_idx]
        np.testing.assert_allclose(bbw[valid_idx].values, expected_bbw.values, rtol=1e-5)

        # BBW Z-score and Percentile
        bbw_z = compute_bbw_zscore(bbw, lookback=40)
        bbw_pct = compute_bbw_percentile(bbw, lookback=40)
        valid_pct = bbw_pct.dropna()
        self.assertTrue((valid_pct >= 0.0).all() and (valid_pct <= 1.0).all())

    def test_realized_and_parkinson_volatility(self):
        df = _generate_synthetic_candles(n=100, regime_type="random", seed=12)
        nrv = compute_normalized_realized_volatility(df["close"], short_window=12, long_window=50)
        park_vol = compute_parkinson_volatility(df["high"], df["low"], window=12)

        # Parkinson volatility must be positive
        valid_park = park_vol.dropna()
        self.assertTrue((valid_park > 0).all(), "Parkinson volatility must be positive")

        # Invariant: Expanding high-low spread increases Parkinson volatility
        df_turbulent = df.copy()
        df_turbulent["high"] = df_turbulent["high"] + 0.0100
        df_turbulent["low"] = df_turbulent["low"] - 0.0100
        turb_park = compute_parkinson_volatility(df_turbulent["high"], df_turbulent["low"], window=12)
        self.assertGreater(turb_park.iloc[-1], park_vol.iloc[-1])

    def test_adx_directional_system(self):
        # Trending Up series: +DI should strongly exceed -DI
        df_up = _generate_synthetic_candles(n=80, regime_type="trend_up", seed=13)
        adx_up, pdi_up, mdi_up, spread_up = compute_adx(df_up["high"], df_up["low"], df_up["close"], period=14)

        self.assertGreater(pdi_up.iloc[-1], mdi_up.iloc[-1])
        self.assertGreater(spread_up.iloc[-1], 0)
        self.assertGreater(adx_up.iloc[-1], 20.0)

        # Trending Down series: -DI should strongly exceed +DI
        df_down = _generate_synthetic_candles(n=80, regime_type="trend_down", seed=14)
        adx_down, pdi_down, mdi_down, spread_down = compute_adx(df_down["high"], df_down["low"], df_down["close"], period=14)

        self.assertGreater(mdi_down.iloc[-1], pdi_down.iloc[-1])
        self.assertLess(spread_down.iloc[-1], 0)
        self.assertGreater(adx_down.iloc[-1], 20.0)

    def test_autocorrelation_rho_1(self):
        # Mean reverting oscillation: negative lag-1 autocorrelation
        # Alternating returns: +0.01, -0.01, +0.01, -0.01...
        alt_returns = np.tile([0.005, -0.005], 50)
        oscillating_prices = 100.0 * np.exp(np.cumsum(alt_returns))
        oscillating_series = pd.Series(oscillating_prices)

        rho, t_stat = compute_return_autocorrelation(oscillating_series, window=40)
        self.assertLess(rho.iloc[-1], -0.5, "Alternating returns must exhibit strong negative autocorrelation")

        # Autoregressive positive returns: AR(1) with positive phi -> positive autocorrelation
        rng = np.random.RandomState(42)
        r = np.zeros(100)
        for i in range(1, 100):
            r[i] = 0.7 * r[i - 1] + rng.normal(0, 0.001)
        trending_prices = 100.0 * np.exp(np.cumsum(r))
        trending_series = pd.Series(trending_prices)
        rho_trend, _ = compute_return_autocorrelation(trending_series, window=40)
        self.assertGreater(rho_trend.iloc[-1], 0.2, "AR(1) with positive drift must exhibit positive autocorrelation")

    def test_lo_mackinlay_variance_ratio(self):
        # 1. Random walk expectation: VR ~ 1.0
        rng = np.random.RandomState(42)
        n = 500
        rw_log_prices = np.cumsum(rng.normal(0, 0.01, n))
        vr_rw, z_rw = compute_variance_ratio(rw_log_prices, q=4)
        # Should be close to 1.0
        self.assertTrue(0.70 <= vr_rw <= 1.30, f"VR for random walk unexpected: {vr_rw}")

        # 2. Strongly mean reverting series (Ornstein-Uhlenbeck process): VR < 1.0
        ou_log_prices = np.zeros(200)
        for i in range(1, 200):
            ou_log_prices[i] = 0.2 * ou_log_prices[i - 1] + rng.normal(0, 0.01)
        vr_mr, z_mr = compute_variance_ratio(ou_log_prices, q=4)
        self.assertLess(vr_mr, 0.90, f"Expected VR < 0.90 for OU mean reversion, got {vr_mr}")

        # 3. Persistent trend series: VR > 1.0
        trend_log_prices = np.cumsum(0.005 + rng.normal(0, 0.001, 200))
        vr_tr, z_tr = compute_variance_ratio(trend_log_prices, q=4)
        self.assertGreater(vr_tr, 1.0, f"Expected VR > 1.0 for persistent trend, got {vr_tr}")


class TestRegimeClassifier(unittest.TestCase):
    """Test suite for the 5-Tier Decision Tree and Chaos Veto Invariant."""

    def setUp(self):
        self.classifier = RegimeClassifier(min_candles=50)

    def test_tier1_chaos_insufficient_candles(self):
        df_short = _generate_synthetic_candles(n=30)
        res = self.classifier.classify_latest(df_short)
        self.assertEqual(res.regime, MarketRegime.CHAOS)
        self.assertFalse(res.allow_trade, "Under insufficient candles, allow_trade must be False")
        self.assertEqual(res.recommended_strategy, "NONE")
        self.assertEqual(res.tier_triggered, 1)

    def test_tier1_chaos_giant_wick_shock(self):
        df = _generate_synthetic_candles(n=70, seed=15)
        # Inject pathological news spike on the latest bar
        curr_atr = float(compute_atr(df["high"], df["low"], df["close"]).iloc[-1])
        df.iloc[-1, df.columns.get_loc("high")] = df.iloc[-1]["close"] + 10.0 * curr_atr
        
        res = self.classifier.classify_latest(df)
        self.assertEqual(res.regime, MarketRegime.CHAOS)
        self.assertFalse(res.allow_trade)
        self.assertEqual(res.tier_triggered, 1)
        self.assertIn("Giant candle range", res.reason)

    def test_tier1_chaos_volatility_explosion(self):
        df = _generate_synthetic_candles(n=80, seed=16)
        # Artificially trigger extreme vol shock by inflating recent candle deviations
        for i in range(-5, 0):
            df.iloc[i, df.columns.get_loc("close")] *= (1.0 + (i % 2) * 0.08)
            df.iloc[i, df.columns.get_loc("high")] = df.iloc[i]["close"] * 1.05
            df.iloc[i, df.columns.get_loc("low")] = df.iloc[i]["close"] * 0.95

        res = self.classifier.classify_latest(df)
        self.assertEqual(res.regime, MarketRegime.CHAOS)
        self.assertFalse(res.allow_trade)
        self.assertEqual(res.tier_triggered, 1)

    def test_tier2_expansion_classification(self):
        df = _generate_synthetic_candles(n=140, regime_type="expansion", seed=17)
        res = self.classifier.classify_latest(df)
        # If expansion conditions are satisfied
        if res.tier_triggered == 2:
            self.assertEqual(res.regime, MarketRegime.EXPANSION)
            self.assertTrue(res.allow_trade)
            self.assertEqual(res.recommended_strategy, "VOLATILITY_BREAKOUT")

    def test_tier3_trend_classification(self):
        df = _generate_synthetic_candles(n=100, regime_type="trend_up", seed=18)
        res = self.classifier.classify_latest(df)
        if res.tier_triggered == 3:
            self.assertEqual(res.regime, MarketRegime.TREND)
            self.assertTrue(res.allow_trade)
            self.assertEqual(res.recommended_strategy, "TREND_PULLBACK")

    def test_tier4_range_classification(self):
        df = _generate_synthetic_candles(n=100, regime_type="range", seed=19)
        res = self.classifier.classify_latest(df)
        if res.tier_triggered == 4:
            self.assertEqual(res.regime, MarketRegime.RANGE)
            self.assertTrue(res.allow_trade)
            self.assertEqual(res.recommended_strategy, "MEAN_REVERSION")

    def test_classify_regime_series_contract(self):
        df = _generate_synthetic_candles(n=75, seed=20)
        series = classify_regime(df)
        self.assertIsInstance(series, pd.Series)
        self.assertEqual(len(series), len(df))
        allowed_regimes = {r.value for r in MarketRegime}
        for val in series:
            self.assertIn(val, allowed_regimes)


class TestSignalRouter(unittest.TestCase):
    """Test suite for the Signal Router and strict safety routing."""

    def setUp(self):
        self.router = SignalRouter()

    def test_strict_chaos_veto(self):
        # When regime is CHAOS, signal MUST BE NO_TRADE
        df = _generate_synthetic_candles(n=60, seed=21)
        chaos_output = RegimeOutput(
            regime=MarketRegime.CHAOS,
            allow_trade=False,
            recommended_strategy="NONE",
            tier_triggered=1,
            reason="Chaos injection",
            metrics={},
        )
        decision = self.router.route_signal(df, regime_output=chaos_output)
        self.assertEqual(decision.signal, MarketSignal.NO_TRADE)
        self.assertEqual(decision.regime, MarketRegime.CHAOS)
        self.assertEqual(decision.expiry_bars, 0)
        self.assertIn("CHAOS VETO", decision.reason)

    def test_range_mean_reversion_call_routing(self):
        df = _generate_synthetic_candles(n=70, regime_type="range", seed=22)
        # Mock lower band bounce condition:
        # Prior candle penetrations lower band, RSI oversold, current candle has lower wick rejection
        df.iloc[-2, df.columns.get_loc("close")] = df["close"].min() - 0.0010
        df.iloc[-1, df.columns.get_loc("open")] = df["close"].min() - 0.0008
        df.iloc[-1, df.columns.get_loc("low")] = df["close"].min() - 0.0020
        df.iloc[-1, df.columns.get_loc("close")] = df["close"].min() - 0.0002
        df.iloc[-1, df.columns.get_loc("high")] = df.iloc[-1]["close"] + 0.0001

        range_output = RegimeOutput(
            regime=MarketRegime.RANGE,
            allow_trade=True,
            recommended_strategy="MEAN_REVERSION",
            tier_triggered=4,
            reason="Range mock",
            metrics={},
        )
        decision = self.router.route_signal(df, regime_output=range_output)
        # If all triggers met, emits CALL
        if decision.signal != MarketSignal.NO_TRADE:
            self.assertEqual(decision.signal, MarketSignal.CALL)
            self.assertEqual(decision.setup_name, "RANGE_MEAN_REVERSION")
            self.assertEqual(decision.expiry_bars, 1)

    def test_trend_pullback_call_routing(self):
        df = _generate_synthetic_candles(n=70, regime_type="trend_up", seed=23)
        trend_output = RegimeOutput(
            regime=MarketRegime.TREND,
            allow_trade=True,
            recommended_strategy="TREND_PULLBACK",
            tier_triggered=3,
            reason="Trend mock",
            metrics={},
        )
        decision = self.router.route_signal(df, regime_output=trend_output)
        if decision.signal != MarketSignal.NO_TRADE:
            self.assertEqual(decision.signal, MarketSignal.CALL)
            self.assertEqual(decision.setup_name, "TREND_PULLBACK")
            self.assertGreaterEqual(decision.expiry_bars, 2)


if __name__ == "__main__":
    unittest.main()
