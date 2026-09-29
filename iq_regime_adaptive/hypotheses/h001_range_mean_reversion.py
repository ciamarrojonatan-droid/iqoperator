"""
h001_range_mean_reversion.py - Statistical Mean Reversion in Range Regime.

Hypothesis ID: H001_RANGE_MEAN_REVERSION
Family: STATISTICAL_MEAN_REVERSION
Microstructural Rationale:
In stationary range regimes, price excursions touching or breaching Bollinger Bands (2.0 std)
with concurrent RSI oversold/overbought extremes and rejection wicks reflect temporary
liquidity consumption that reverts toward equilibrium mean over the subsequent 1 bar.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.indicators import (
    compute_adx,
    compute_bollinger_bands,
    compute_bollinger_bandwidth,
    compute_rsi,
)
from iq_regime_adaptive.feature_engine.signal_router import MarketSignal
from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis


class H001RangeMeanReversion(BaseHypothesis):
    """
    H001: Range Mean Reversion (Bollinger Touch + RSI Exhaustion + Wick Rejection).
    """

    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        adx_period: int = 14,
        adx_max: float = 25.0,
        wick_rejection_ratio: float = 0.25,
        default_horizon_bars: int = 1,
        default_payout_hurdle: float = 0.75,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = {
            "bb_period": bb_period,
            "bb_std": bb_std,
            "rsi_period": rsi_period,
            "rsi_oversold": rsi_oversold,
            "rsi_overbought": rsi_overbought,
            "adx_period": adx_period,
            "adx_max": adx_max,
            "wick_rejection_ratio": wick_rejection_ratio,
        }
        if parameters:
            params.update(parameters)
        super().__init__(
            hypothesis_id="H001_RANGE_MEAN_REVERSION",
            family="STATISTICAL_MEAN_REVERSION",
            name="Range Mean Reversion",
            description="Fades 2-sigma Bollinger band penetrations with RSI exhaustion in low-ADX range regimes.",
            default_horizon_bars=default_horizon_bars,
            default_payout_hurdle=default_payout_hurdle,
            parameters=params,
        )

    def generate_signals(self, df: pd.DataFrame, payout: float = 0.85) -> pd.Series:
        self.validate_df(df)
        n = len(df)
        signals = pd.Series(MarketSignal.NO_TRADE.value, index=df.index, name="signal")

        if payout < self.default_payout_hurdle:
            return signals

        close = df["close"]
        high = df["high"]
        low = df["low"]
        open_p = df["open"]

        p = self.parameters
        bb_period = p["bb_period"]
        bb_std = p["bb_std"]
        rsi_period = p["rsi_period"]
        rsi_os = p["rsi_oversold"]
        rsi_ob = p["rsi_overbought"]
        adx_period = p["adx_period"]
        adx_max = p["adx_max"]
        wick_ratio = p["wick_rejection_ratio"]

        min_lookback = max(bb_period, rsi_period, adx_period * 2) + 5
        if n < min_lookback:
            return signals

        # 1. Bollinger Bands
        bb_mid, bb_upper, bb_lower = compute_bollinger_bands(close, period=bb_period, k=bb_std)

        # 2. RSI
        rsi = compute_rsi(close, period=rsi_period)

        # 3. ADX Range Check
        adx, plus_di, minus_di, _ = compute_adx(high, low, close, period=adx_period)

        # 4. Wick Rejections
        candle_range = (high - low).replace(0, np.nan)
        lower_wick = close - low
        upper_wick = high - close
        lower_wick_ratio = lower_wick / candle_range
        upper_wick_ratio = upper_wick / candle_range

        # Entry Conditions:
        # Range Regime: ADX < adx_max
        is_range = (adx < adx_max) | adx.isna()

        # CALL: Close <= Lower Band (or Low breaches Lower Band) + RSI < oversold + lower wick rejection
        call_cond = (
            is_range
            & ((close <= bb_lower) | (low <= bb_lower))
            & (rsi <= rsi_os)
            & (lower_wick_ratio >= wick_ratio)
        )

        # PUT: Close >= Upper Band (or High breaches Upper Band) + RSI > overbought + upper wick rejection
        put_cond = (
            is_range
            & ((close >= bb_upper) | (high >= bb_upper))
            & (rsi >= rsi_ob)
            & (upper_wick_ratio >= wick_ratio)
        )

        signals[call_cond] = MarketSignal.CALL.value
        signals[put_cond] = MarketSignal.PUT.value

        # In case both fire on aberrant wick candle, discard
        signals[call_cond & put_cond] = MarketSignal.NO_TRADE.value

        return signals
