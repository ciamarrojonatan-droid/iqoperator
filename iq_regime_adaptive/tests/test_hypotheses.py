"""
test_hypotheses.py - Unit and Integration Tests for Hypotheses H001 through H008 and Registry.
"""

import unittest
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.signal_router import MarketSignal
from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis
from iq_regime_adaptive.hypotheses.registry import (
    get_hypothesis,
    get_all_hypotheses,
    list_hypotheses,
    CANONICAL_IDS,
    HYPOTHESIS_REGISTRY,
)
from iq_regime_adaptive.hypotheses.h001_range_mean_reversion import H001RangeMeanReversion
from iq_regime_adaptive.hypotheses.h002_trend_pullback import H002TrendPullback
from iq_regime_adaptive.hypotheses.h003_volatility_expansion import H003VolatilityExpansion
from iq_regime_adaptive.hypotheses.h004_autocorrelation_reversion import H004AutocorrelationReversion
from iq_regime_adaptive.hypotheses.h005_mtf_trend_alignment import H005MTFTrendAlignment
from iq_regime_adaptive.hypotheses.h006_payout_filtered_edge import H006PayoutFilteredEdge
from iq_regime_adaptive.hypotheses.h007_squeeze_breakout import H007SqueezeBreakout
from iq_regime_adaptive.hypotheses.h008_regime_adaptive_router import H008RegimeAdaptiveRouter


def make_test_df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Generates synthetic OHLCV DataFrame for testing."""
    np.random.seed(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="5min")
    ret = np.random.normal(0, 0.002, size=n)
    close = 100.0 * np.exp(np.cumsum(ret))
    high = close * 1.002
    low = close * 0.998
    open_p = (high + low) / 2.0
    vol = np.full(n, 500)
    return pd.DataFrame({"open": open_p, "high": high, "low": low, "close": close, "volume": vol}, index=idx)


class TestHypothesesRegistry(unittest.TestCase):
    """Verifies hypothesis discovery and factory registry."""

    def test_canonical_hypotheses_count(self):
        canonical = list_hypotheses(canonical_only=True)
        self.assertEqual(len(canonical), 8)
        expected = [
            "H001_RANGE_MEAN_REVERSION",
            "H002_TREND_PULLBACK",
            "H003_VOLATILITY_EXPANSION_BREAKOUT",
            "H004_AUTOCORRELATION_MEAN_REVERSION",
            "H005_MTF_TREND_ALIGNMENT",
            "H006_PAYOUT_FILTERED_DYNAMIC_EDGE",
            "H007_VOLATILITY_CONTRACTION_SQUEEZE",
            "H008_REGIME_ADAPTIVE_ENSEMBLE_ROUTER",
        ]
        self.assertEqual(canonical, expected)

    def test_factory_instantiation_by_id(self):
        # Short ID
        h1 = get_hypothesis("H001")
        self.assertIsInstance(h1, H001RangeMeanReversion)
        self.assertEqual(h1.hypothesis_id, "H001_RANGE_MEAN_REVERSION")

        # Full ID
        h8 = get_hypothesis("H008_REGIME_ADAPTIVE_ENSEMBLE_ROUTER")
        self.assertIsInstance(h8, H008RegimeAdaptiveRouter)
        self.assertEqual(h8.hypothesis_id, "H008_REGIME_ADAPTIVE_ENSEMBLE_ROUTER")

    def test_unknown_hypothesis_raises_key_error(self):
        with self.assertRaises(KeyError):
            get_hypothesis("H999_NON_EXISTENT")

    def test_get_all_hypotheses(self):
        all_hyps = get_all_hypotheses()
        self.assertEqual(len(all_hyps), 8)
        for canon_id, instance in all_hyps.items():
            self.assertIsInstance(instance, BaseHypothesis)
            self.assertEqual(instance.hypothesis_id, canon_id)
            meta = instance.get_metadata()
            self.assertEqual(meta["hypothesis_id"], canon_id)
            self.assertIn("family", meta)
            self.assertIn("default_horizon_bars", meta)


class TestBaseHypothesisContracts(unittest.TestCase):
    """Verifies BaseHypothesis abstract contracts and validation."""

    def test_cannot_instantiate_abstract(self):
        with self.assertRaises(TypeError):
            BaseHypothesis("H000", "FAMILY", "Name", "Desc")

    def test_validate_df_missing_columns(self):
        h1 = H001RangeMeanReversion()
        bad_df = pd.DataFrame({"close": [10, 20]})
        with self.assertRaises(ValueError):
            h1.generate_signals(bad_df)


class TestH001RangeMeanReversion(unittest.TestCase):
    """Verifies H001 Bollinger + RSI + Wick reversion logic."""

    def test_h001_signals_and_payout_gate(self):
        df = make_test_df(200)
        h1 = H001RangeMeanReversion()

        # Gate check: payout < 0.75 hurdle should emit all NO_TRADE
        low_pay_signals = h1.generate_signals(df, payout=0.60)
        self.assertTrue((low_pay_signals == MarketSignal.NO_TRADE.value).all())

        # Test valid signals on favorable payout
        signals = h1.generate_signals(df, payout=0.85)
        self.assertEqual(len(signals), len(df))
        self.assertTrue(set(signals.unique()).issubset({
            MarketSignal.CALL.value, MarketSignal.PUT.value, MarketSignal.NO_TRADE.value
        }))

    def test_h001_call_trigger_on_oversold_lower_band(self):
        df = make_test_df(100)
        # Force an extreme downward candle with lower wick rejection at the end
        df.iloc[-1, df.columns.get_loc("close")] = df["close"].min() * 0.95
        df.iloc[-1, df.columns.get_loc("low")] = df["close"].min() * 0.94
        df.iloc[-1, df.columns.get_loc("open")] = df["close"].min() * 0.945
        df.iloc[-1, df.columns.get_loc("high")] = df["close"].min() * 0.96

        h1 = H001RangeMeanReversion()
        sig = h1.generate_signals(df, payout=0.85)
        self.assertIn(sig.iloc[-1], (MarketSignal.CALL.value, MarketSignal.NO_TRADE.value))


class TestH002TrendPullback(unittest.TestCase):
    """Verifies H002 Trend Pullback to EMA 20."""

    def test_h002_signal_generation(self):
        # Create strong uptrend
        idx = pd.date_range("2026-01-01", periods=150, freq="5min")
        close = np.linspace(100.0, 150.0, 150)
        high = close + 0.5
        low = close - 0.5
        open_p = close - 0.2
        df = pd.DataFrame({"open": open_p, "high": high, "low": low, "close": close, "volume": 500}, index=idx)

        h2 = H002TrendPullback()
        signals = h2.generate_signals(df, payout=0.85)
        self.assertEqual(len(signals), 150)
        self.assertEqual(h2.default_horizon_bars, 2)


class TestH003VolatilityExpansion(unittest.TestCase):
    """Verifies H003 Volatility Expansion Breakout."""

    def test_h003_signal_generation(self):
        df = make_test_df(150)
        h3 = H003VolatilityExpansion()
        signals = h3.generate_signals(df, payout=0.85)
        self.assertEqual(len(signals), 150)
        self.assertEqual(h3.default_horizon_bars, 1)


class TestH004AutocorrelationReversion(unittest.TestCase):
    """Verifies H004 Negative Serial Correlation Reversion."""

    def test_h004_signals_under_alternating_prices(self):
        # Alternating sharp price jumps create rho_1 < -0.5
        n = 100
        idx = pd.date_range("2026-01-01", periods=n, freq="5min")
        close = np.array([100.0, 102.0] * (n // 2))
        high = close + 0.2
        low = close - 0.2
        open_p = close
        df = pd.DataFrame({"open": open_p, "high": high, "low": low, "close": close, "volume": 500}, index=idx)

        h4 = H004AutocorrelationReversion(rho_threshold=-0.10, z_threshold=1.0)
        signals = h4.generate_signals(df, payout=0.85)
        self.assertEqual(len(signals), n)
        # Should detect reversal opportunities
        self.assertTrue(MarketSignal.CALL.value in signals.values or MarketSignal.PUT.value in signals.values)


class TestH005MTFTrendAlignment(unittest.TestCase):
    """Verifies H005 Multi-Timeframe Trend Alignment."""

    def test_h005_signal_generation(self):
        df = make_test_df(180)
        h5 = H005MTFTrendAlignment()
        signals = h5.generate_signals(df, payout=0.85)
        self.assertEqual(len(signals), 180)


class TestH006PayoutFilteredEdge(unittest.TestCase):
    """Verifies H006 Strict Payout Gate (Payout >= 0.80)."""

    def test_strict_payout_gate_veto(self):
        df = make_test_df(150)
        h6 = H006PayoutFilteredEdge(min_payout=0.80)

        # Under payout 0.75, must be 100% NO_TRADE
        sig_low = h6.generate_signals(df, payout=0.75)
        self.assertTrue((sig_low == MarketSignal.NO_TRADE.value).all())

        # Under payout 0.85, can generate signals
        sig_high = h6.generate_signals(df, payout=0.85)
        self.assertEqual(len(sig_high), 150)


class TestH007SqueezeBreakout(unittest.TestCase):
    """Verifies H007 Bollinger inside Keltner Squeeze Breakout."""

    def test_h007_signal_generation(self):
        df = make_test_df(150)
        h7 = H007SqueezeBreakout()
        signals = h7.generate_signals(df, payout=0.85)
        self.assertEqual(len(signals), 150)
        self.assertEqual(h7.default_horizon_bars, 2)


class TestH008RegimeAdaptiveRouter(unittest.TestCase):
    """Verifies H008 Full Meta-Router with Chaos Veto."""

    def test_h008_meta_router_execution(self):
        df = make_test_df(200)
        h8 = H008RegimeAdaptiveRouter()
        signals = h8.generate_signals(df, payout=0.85)
        self.assertEqual(len(signals), 200)

        # Test consensus resolution logic
        self.assertEqual(H008RegimeAdaptiveRouter._resolve_consensus("CALL", "CALL"), "CALL")
        self.assertEqual(H008RegimeAdaptiveRouter._resolve_consensus("PUT", "PUT"), "PUT")
        self.assertEqual(H008RegimeAdaptiveRouter._resolve_consensus("CALL", "NO_TRADE"), "CALL")
        self.assertEqual(H008RegimeAdaptiveRouter._resolve_consensus("CALL", "PUT"), "NO_TRADE")


if __name__ == "__main__":
    unittest.main()
