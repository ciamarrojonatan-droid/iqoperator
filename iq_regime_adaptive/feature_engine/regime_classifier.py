"""
regime_classifier.py - 5-Tier Deterministic Hierarchical Market Regime Classifier.

Stratifies market dynamics into four mutually exclusive statistical regimes:
1. TREND - Directional drift (ADX >= 25, persistent memory VR > 1 or rho_1 > 0).
2. RANGE - Bounded oscillations (ADX < 20, mean-reverting memory VR < 1 or rho_1 < 0).
3. EXPANSION - Squeeze breakout (BBW surge from low percentile, elevated NRV).
4. CHAOS - Volatility shock, extreme bar, conflicting momentum, or indeterminate fallback.

Strict Invariant:
Regime CHAOS unconditionally sets allow_trade = False (Strict NO-TRADE VETO).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from scipy.stats import kurtosis

from iq_regime_adaptive.feature_engine.indicators import (
    compute_atr,
    compute_natr,
    compute_bollinger_bandwidth,
    compute_bbw_zscore,
    compute_bbw_percentile,
    compute_normalized_realized_volatility,
    compute_vol_shock,
    compute_adx,
    compute_return_autocorrelation,
    compute_variance_ratio,
    compute_ema,
    compute_bollinger_bands,
    compute_donchian_channels,
)


class MarketRegime(str, Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    EXPANSION = "EXPANSION"
    CHAOS = "CHAOS"


@dataclass(frozen=True)
class RegimeOutput:
    """Detailed output for point-in-time regime classification."""
    regime: MarketRegime
    allow_trade: bool
    recommended_strategy: str
    tier_triggered: int
    reason: str
    metrics: Dict[str, float]


class RegimeClassifier:
    """
    5-Tier Hierarchical Decision Tree Classifier.
    """

    def __init__(
        self,
        min_candles: int = 50,
        adx_period: int = 14,
        adx_trend_thresh: float = 25.0,
        adx_range_thresh: float = 20.0,
        di_diff_trend_thresh: float = 12.0,
        di_diff_range_thresh: float = 12.0,
        vr_lag: int = 4,
        nrv_chaos_thresh: float = 3.0,
        vol_shock_chaos_thresh: float = 3.5,
        giant_bar_atr_mult: float = 3.5,
        kurtosis_chaos_thresh: float = 8.0,
    ):
        self.min_candles = min_candles
        self.adx_period = adx_period
        self.adx_trend_thresh = adx_trend_thresh
        self.adx_range_thresh = adx_range_thresh
        self.di_diff_trend_thresh = di_diff_trend_thresh
        self.di_diff_range_thresh = di_diff_range_thresh
        self.vr_lag = vr_lag
        self.nrv_chaos_thresh = nrv_chaos_thresh
        self.vol_shock_chaos_thresh = vol_shock_chaos_thresh
        self.giant_bar_atr_mult = giant_bar_atr_mult
        self.kurtosis_chaos_thresh = kurtosis_chaos_thresh

    def classify_latest(self, df: pd.DataFrame) -> RegimeOutput:
        """
        Evaluates the 5-Tier Decision Tree on the latest closed candle of df.
        """
        n = len(df)
        if n < self.min_candles:
            return RegimeOutput(
                regime=MarketRegime.CHAOS,
                allow_trade=False,
                recommended_strategy="NONE",
                tier_triggered=1,
                reason=f"Insufficient candles: {n} < {self.min_candles}",
                metrics={"candle_count": float(n)},
            )

        if df[["open", "high", "low", "close"]].isna().any().any():
            return RegimeOutput(
                regime=MarketRegime.CHAOS,
                allow_trade=False,
                recommended_strategy="NONE",
                tier_triggered=1,
                reason="Corrupted data: NaN or missing values detected in candle window",
                metrics={"candle_count": float(n)},
            )

        close = df["close"]
        high = df["high"]
        low = df["low"]
        open_p = df["open"]

        # Compute Core Indicators
        atr_14 = compute_atr(high, low, close, period=self.adx_period)
        natr = compute_natr(high, low, close, period=self.adx_period)
        bbw = compute_bollinger_bandwidth(close, period=20)
        bbw_z = compute_bbw_zscore(bbw, lookback=50)
        bbw_pct = compute_bbw_percentile(bbw, lookback=50)
        nrv = compute_normalized_realized_volatility(close, short_window=12, long_window=120)
        vol_shock = compute_vol_shock(close, fast_period=5, slow_period=50)
        adx, plus_di, minus_di, di_spread = compute_adx(high, low, close, period=self.adx_period)
        rho_1, t_rho = compute_return_autocorrelation(close, window=40)
        
        # Lo-MacKinlay Variance Ratio over last 60 bars
        log_close = np.log(close.values[-61:])
        vr_q, z_vr = compute_variance_ratio(log_close, q=self.vr_lag)

        # EMAs and Bands
        ema_20 = compute_ema(close, span=20)
        ema_50 = compute_ema(close, span=50)
        middle_bb, upper_bb, lower_bb = compute_bollinger_bands(close, period=20)
        dc_up, dc_low, _ = compute_donchian_channels(high, low, period=20)

        # Latest values
        curr_close = float(close.iloc[-1])
        curr_high = float(high.iloc[-1])
        curr_low = float(low.iloc[-1])
        curr_open = float(open_p.iloc[-1])

        curr_atr = float(atr_14.iloc[-1]) if not np.isnan(atr_14.iloc[-1]) else 0.0001
        curr_natr = float(natr.iloc[-1])
        curr_bbw = float(bbw.iloc[-1])
        curr_bbw_z = float(bbw_z.iloc[-1]) if not np.isnan(bbw_z.iloc[-1]) else 0.0
        curr_bbw_pct = float(bbw_pct.iloc[-1]) if not np.isnan(bbw_pct.iloc[-1]) else 0.5
        curr_nrv = float(nrv.iloc[-1]) if not np.isnan(nrv.iloc[-1]) else 0.0
        curr_vol_shock = float(vol_shock.iloc[-1]) if not np.isnan(vol_shock.iloc[-1]) else 1.0
        curr_adx = float(adx.iloc[-1]) if not np.isnan(adx.iloc[-1]) else 0.0
        curr_plus_di = float(plus_di.iloc[-1]) if not np.isnan(plus_di.iloc[-1]) else 0.0
        curr_minus_di = float(minus_di.iloc[-1]) if not np.isnan(minus_di.iloc[-1]) else 0.0
        curr_di_diff = abs(curr_plus_di - curr_minus_di)
        curr_rho_1 = float(rho_1.iloc[-1]) if not np.isnan(rho_1.iloc[-1]) else 0.0

        curr_ema_20 = float(ema_20.iloc[-1])
        curr_ema_50 = float(ema_50.iloc[-1])
        curr_mid_bb = float(middle_bb.iloc[-1])
        std_20 = (float(upper_bb.iloc[-1]) - curr_mid_bb) / 2.0

        # Bar morphology
        bar_range = curr_high - curr_low
        is_giant_bar = bar_range > (self.giant_bar_atr_mult * curr_atr)

        # Excess Kurtosis over last 30 log returns
        recent_ret = np.diff(np.log(close.values[-31:]))
        curr_kurt = float(kurtosis(recent_ret, fisher=True)) if len(recent_ret) >= 30 else 0.0
        if np.isnan(curr_kurt):
            curr_kurt = 0.0

        # NATR extreme threshold (historical 98th percentile or high multiple)
        natr_p98 = float(natr.dropna().quantile(0.98)) if len(natr.dropna()) >= 50 else curr_natr * 1.5

        # Pack metrics dictionary
        metrics = {
            "adx": curr_adx,
            "plus_di": curr_plus_di,
            "minus_di": curr_minus_di,
            "di_diff": curr_di_diff,
            "bbw": curr_bbw,
            "bbw_z": curr_bbw_z,
            "bbw_pct": curr_bbw_pct,
            "nrv": curr_nrv,
            "vol_shock": curr_vol_shock,
            "rho_1": curr_rho_1,
            "vr_4": 0.0 if np.isnan(vr_q) else vr_q,
            "z_vr": 0.0 if np.isnan(z_vr) else z_vr,
            "natr": curr_natr,
            "kurtosis": curr_kurt,
            "bar_range": bar_range,
            "atr_14": curr_atr,
        }
        metrics = {k: (0.0 if np.isnan(v) else float(v)) for k, v in metrics.items()}

        # =========================================================================
        # TIER 1: CHAOS GUARD (STRICT VETO)
        # =========================================================================
        chaos_reasons = []
        if curr_nrv > self.nrv_chaos_thresh:
            chaos_reasons.append(f"NRV surge ({curr_nrv:.2f} > {self.nrv_chaos_thresh})")
        if curr_vol_shock > self.vol_shock_chaos_thresh:
            chaos_reasons.append(f"Vol shock ({curr_vol_shock:.2f} > {self.vol_shock_chaos_thresh})")
        if curr_natr > natr_p98 and curr_natr > 0.15:
            chaos_reasons.append(f"Extreme NATR ({curr_natr:.3f} > {natr_p98:.3f})")
        if is_giant_bar:
            chaos_reasons.append(f"Giant candle range ({bar_range:.5f} > {self.giant_bar_atr_mult}*ATR)")
        if curr_adx >= 35.0 and curr_di_diff <= 4.0:
            chaos_reasons.append(f"ADX/DI contradiction whipsaw (ADX={curr_adx:.1f}, DI_diff={curr_di_diff:.1f})")
        if (curr_rho_1 <= -0.60 or vr_q <= 0.10) and bar_range > 0:
            chaos_reasons.append(f"Extreme oscillating whipsaw (rho_1={curr_rho_1:.2f}, VR={vr_q:.2f})")
        if curr_kurt > self.kurtosis_chaos_thresh:
            chaos_reasons.append(f"Fat-tail excess kurtosis ({curr_kurt:.1f} > {self.kurtosis_chaos_thresh})")

        if chaos_reasons:
            return RegimeOutput(
                regime=MarketRegime.CHAOS,
                allow_trade=False,
                recommended_strategy="NONE",
                tier_triggered=1,
                reason=" | ".join(chaos_reasons),
                metrics=metrics,
            )

        # =========================================================================
        # TIER 2: EXPANSION REGIME (VOLATILITY BREAKOUT)
        # =========================================================================
        # Prior compression in last 5 bars
        valid_bbw_pct = bbw_pct.dropna()
        if len(valid_bbw_pct) >= 6:
            recent_prior_bbw_pct = valid_bbw_pct.iloc[-6:-1]
            min_prior_pct = float(recent_prior_bbw_pct.min())
            min_prior_bbw = float(bbw.iloc[-6:-1].min())
        else:
            min_prior_pct = 0.5
            min_prior_bbw = curr_bbw

        is_squeeze_release = (curr_bbw >= 1.40 * min_prior_bbw) and (curr_bbw_z >= 1.0)
        is_elevated_nrv = (curr_nrv >= 1.2) and (curr_nrv <= 3.0)

        # Directional breakout
        prev_dc_up = float(dc_up.iloc[-2]) if len(dc_up) >= 2 else curr_high
        prev_dc_low = float(dc_low.iloc[-2]) if len(dc_low) >= 2 else curr_low
        closed_outside_dc = (curr_close > prev_dc_up) or (curr_close < prev_dc_low)
        strong_di = curr_di_diff >= 15.0

        if (min_prior_pct <= 0.25) and is_squeeze_release and is_elevated_nrv and (closed_outside_dc or strong_di):
            return RegimeOutput(
                regime=MarketRegime.EXPANSION,
                allow_trade=True,
                recommended_strategy="VOLATILITY_BREAKOUT",
                tier_triggered=2,
                reason=f"Volatility squeeze release (BBW_Z={curr_bbw_z:.2f}, prior_pct={min_prior_pct:.2f})",
                metrics=metrics,
            )

        # =========================================================================
        # TIER 3: TREND REGIME (DIRECTIONAL DRIFT)
        # =========================================================================
        strong_adx = (curr_adx >= self.adx_trend_thresh) and (curr_di_diff >= self.di_diff_trend_thresh)
        trend_memory = (vr_q >= 1.05) or (curr_rho_1 >= 0.05)

        # Moving average alignment
        bullish_ma = (curr_ema_20 > curr_ema_50) and (curr_plus_di > curr_minus_di)
        bearish_ma = (curr_ema_20 < curr_ema_50) and (curr_minus_di > curr_plus_di)
        ma_aligned = bullish_ma or bearish_ma
        controlled_vol = (-0.5 <= curr_bbw_z <= 2.0)

        if strong_adx and trend_memory and ma_aligned and controlled_vol:
            bias = "Bullish" if bullish_ma else "Bearish"
            return RegimeOutput(
                regime=MarketRegime.TREND,
                allow_trade=True,
                recommended_strategy="TREND_PULLBACK",
                tier_triggered=3,
                reason=f"{bias} Trend confirmed (ADX={curr_adx:.1f}, VR={vr_q:.2f}, rho_1={curr_rho_1:.2f})",
                metrics=metrics,
            )

        # =========================================================================
        # TIER 4: RANGE REGIME (MEAN REVERSION)
        # =========================================================================
        absence_trend = (curr_adx < self.adx_range_thresh) and (curr_di_diff < self.di_diff_range_thresh)
        mean_reverting_memory = (curr_rho_1 <= -0.05) or (vr_q <= 0.95)
        non_whipsaw = (curr_rho_1 > -0.60) and (vr_q > 0.10)
        contained_vol = (curr_bbw_z <= 0.50) and (curr_nrv < 1.0)
        in_envelope = abs(curr_close - curr_mid_bb) <= (2.5 * std_20 + 1e-8)

        if absence_trend and mean_reverting_memory and non_whipsaw and contained_vol and in_envelope:
            return RegimeOutput(
                regime=MarketRegime.RANGE,
                allow_trade=True,
                recommended_strategy="MEAN_REVERSION",
                tier_triggered=4,
                reason=f"Stationary Range confirmed (ADX={curr_adx:.1f}, VR={vr_q:.2f}, rho_1={curr_rho_1:.2f})",
                metrics=metrics,
            )

        # =========================================================================
        # TIER 5: FALLBACK / INDETERMINATE STATE (CHAOS / NO TRADE)
        # =========================================================================
        return RegimeOutput(
            regime=MarketRegime.CHAOS,
            allow_trade=False,
            recommended_strategy="NONE",
            tier_triggered=5,
            reason="Indeterminate statistical state (failed Range, Trend, and Expansion criteria)",
            metrics=metrics,
        )

    def classify_series(self, df: pd.DataFrame) -> pd.Series:
        """
        Computes rolling market regime across all bars of df.
        Returns categorical pd.Series with values ['TREND', 'RANGE', 'EXPANSION', 'CHAOS'].
        """
        n = len(df)
        regimes = [MarketRegime.CHAOS.value] * n

        # We can evaluate starting from min_candles
        for i in range(self.min_candles, n + 1):
            sub_df = df.iloc[max(0, i - 120):i]
            output = self.classify_latest(sub_df)
            regimes[i - 1] = output.regime.value

        return pd.Series(regimes, index=df.index, name="regime", dtype="category")


def classify_market_regime(df: pd.DataFrame) -> RegimeOutput:
    """Convenience functional interface for point-in-time regime classification."""
    classifier = RegimeClassifier()
    return classifier.classify_latest(df)


def classify_regime(df: pd.DataFrame) -> pd.Series:
    """
    Interface contract function matching PROJECT.md:
    classify_regime(df: pd.DataFrame) -> pd.Series
    Returns Series with values in ['TREND', 'RANGE', 'EXPANSION', 'CHAOS'].
    """
    classifier = RegimeClassifier()
    return classifier.classify_series(df)
