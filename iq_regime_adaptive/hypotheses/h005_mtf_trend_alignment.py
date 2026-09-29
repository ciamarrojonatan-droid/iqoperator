"""
h005_mtf_trend_alignment.py - Multi-Timeframe Hierarchical Trend Alignment.

Hypothesis ID: H005_MTF_TREND_ALIGNMENT
Family: HIERARCHICAL_MULTISCALE
Microstructural Rationale:
Single-timeframe signals frequently get whipsawed by higher-timeframe order flow.
By conditioning trade direction on a strictly causal higher-timeframe (macro) trend
envelope (EMA 50 / 100 alignment), micro pullbacks (RSI exhaustion + EMA 20 retest)
exhibit significantly higher conditional probability of winning.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.indicators import (
    compute_ema,
    compute_rsi,
)
from iq_regime_adaptive.feature_engine.signal_router import MarketSignal
from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis


class H005MTFTrendAlignment(BaseHypothesis):
    """
    H005: Multi-Timeframe Trend Alignment (Macro Trend Filter + Micro Pullback).
    """

    def __init__(
        self,
        macro_ema_fast: int = 50,
        macro_ema_slow: int = 100,
        micro_ema: int = 20,
        micro_rsi_period: int = 14,
        micro_rsi_oversold: float = 38.0,
        micro_rsi_overbought: float = 62.0,
        default_horizon_bars: int = 2,
        default_payout_hurdle: float = 0.75,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = {
            "macro_ema_fast": macro_ema_fast,
            "macro_ema_slow": macro_ema_slow,
            "micro_ema": micro_ema,
            "micro_rsi_period": micro_rsi_period,
            "micro_rsi_oversold": micro_rsi_oversold,
            "micro_rsi_overbought": micro_rsi_overbought,
        }
        if parameters:
            params.update(parameters)
        super().__init__(
            hypothesis_id="H005_MTF_TREND_ALIGNMENT",
            family="HIERARCHICAL_MULTISCALE",
            name="Multi-Timeframe Trend Alignment",
            description="Filters micro pullbacks through a strictly causal macro trend alignment envelope.",
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
        macro_fast_len = p["macro_ema_fast"]
        macro_slow_len = p["macro_ema_slow"]
        micro_ema_len = p["micro_ema"]
        rsi_period = p["micro_rsi_period"]
        rsi_os = p["micro_rsi_oversold"]
        rsi_ob = p["micro_rsi_overbought"]

        min_lookback = max(macro_slow_len, micro_ema_len, rsi_period) + 10
        if n < min_lookback:
            return signals

        # 1. Macro trend indicators (causal moving averages over current frequency)
        macro_ema_f = compute_ema(close, span=macro_fast_len)
        macro_ema_s = compute_ema(close, span=macro_slow_len)

        macro_bullish = (close > macro_ema_s) & (macro_ema_f > macro_ema_s)
        macro_bearish = (close < macro_ema_s) & (macro_ema_f < macro_ema_s)

        # 2. Micro trigger indicators
        micro_ema = compute_ema(close, span=micro_ema_len)
        rsi = compute_rsi(close, period=rsi_period)

        # Micro pullback triggers:
        # Bullish: Macro bull + Micro RSI oversold/pullback + price bouncing near/below micro EMA
        call_cond = (
            macro_bullish
            & (rsi <= rsi_os)
            & (low <= micro_ema)
            & (close >= open_p)
        )

        # Bearish: Macro bear + Micro RSI overbought/pullback + price bouncing near/above micro EMA
        put_cond = (
            macro_bearish
            & (rsi >= rsi_ob)
            & (high >= micro_ema)
            & (close <= open_p)
        )

        signals[call_cond] = MarketSignal.CALL.value
        signals[put_cond] = MarketSignal.PUT.value
        signals[call_cond & put_cond] = MarketSignal.NO_TRADE.value

        return signals
