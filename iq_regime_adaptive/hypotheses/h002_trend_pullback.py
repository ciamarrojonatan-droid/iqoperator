"""
h002_trend_pullback.py - Trend Pullback to Dynamic Moving Average Equilibrium.

Hypothesis ID: H002_TREND_PULLBACK
Family: TREND_CONTINUATION
Microstructural Rationale:
In an active trend characterized by elevated ADX and aligned directional indicators,
counter-trend retracements into dynamic equilibrium (EMA 20) represent institutional
liquidity reloads, producing continuation waves over the next 1 to 2 candles.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.indicators import (
    compute_adx,
    compute_ema,
)
from iq_regime_adaptive.feature_engine.signal_router import MarketSignal
from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis


class H002TrendPullback(BaseHypothesis):
    """
    H002: Trend Pullback (EMA Alignment + Dynamic Equilibrium Retest + Rejection).
    """

    def __init__(
        self,
        ema_fast: int = 20,
        ema_slow: int = 50,
        adx_period: int = 14,
        adx_min: float = 22.0,
        di_diff_min: float = 8.0,
        default_horizon_bars: int = 2,
        default_payout_hurdle: float = 0.75,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = {
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "adx_period": adx_period,
            "adx_min": adx_min,
            "di_diff_min": di_diff_min,
        }
        if parameters:
            params.update(parameters)
        super().__init__(
            hypothesis_id="H002_TREND_PULLBACK",
            family="TREND_CONTINUATION",
            name="Trend Pullback",
            description="Exploits directional continuation from dynamic EMA equilibrium pullbacks in trending regimes.",
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
        fast_len = p["ema_fast"]
        slow_len = p["ema_slow"]
        adx_period = p["adx_period"]
        adx_min = p["adx_min"]
        di_diff_min = p["di_diff_min"]

        min_lookback = max(slow_len, adx_period * 2) + 5
        if n < min_lookback:
            return signals

        # 1. Moving Averages
        ema_f = compute_ema(close, span=fast_len)
        ema_s = compute_ema(close, span=slow_len)

        # 2. ADX and Directional Indicators
        adx, plus_di, minus_di, _ = compute_adx(high, low, close, period=adx_period)

        # Trend filter
        is_trending = (adx >= adx_min) & (abs(plus_di - minus_di) >= di_diff_min)
        uptrend = is_trending & (plus_di > minus_di) & (ema_f > ema_s)
        downtrend = is_trending & (minus_di > plus_di) & (ema_f < ema_s)

        # Retracement & Bounce
        # Bullish: Low touches or breaches EMA fast, but Close finishes above it, green candle
        call_cond = (
            uptrend
            & (low <= ema_f)
            & (close > ema_f)
            & (close >= open_p)
        )

        # Bearish: High touches or breaches EMA fast, but Close finishes below it, red candle
        put_cond = (
            downtrend
            & (high >= ema_f)
            & (close < ema_f)
            & (close <= open_p)
        )

        signals[call_cond] = MarketSignal.CALL.value
        signals[put_cond] = MarketSignal.PUT.value
        signals[call_cond & put_cond] = MarketSignal.NO_TRADE.value

        return signals
