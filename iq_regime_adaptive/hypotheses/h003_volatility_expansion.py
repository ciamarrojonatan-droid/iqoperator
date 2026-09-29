"""
h003_volatility_expansion.py - Volatility Expansion Breakout with Body Dominance.

Hypothesis ID: H003_VOLATILITY_EXPANSION_BREAKOUT
Family: MOMENTUM_BREAKOUT
Microstructural Rationale:
Sudden Bollinger Bandwidth expansion accompanied by range expansion and high candle
body dominance reflects aggressive liquidity sweeps and order flow imbalance,
exhibiting momentum follow-through on the subsequent candle.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.indicators import (
    compute_atr,
    compute_bollinger_bands,
    compute_bollinger_bandwidth,
    compute_donchian_channels,
)
from iq_regime_adaptive.feature_engine.signal_router import MarketSignal
from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis


class H003VolatilityExpansion(BaseHypothesis):
    """
    H003: Volatility Expansion Breakout (Bandwidth Surge + Range Expansion + Body Dominance).
    """

    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        donchian_period: int = 20,
        bbw_expansion_threshold: float = 1.25,
        body_ratio_min: float = 0.55,
        range_expansion_min: float = 1.20,
        default_horizon_bars: int = 1,
        default_payout_hurdle: float = 0.75,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = {
            "bb_period": bb_period,
            "bb_std": bb_std,
            "donchian_period": donchian_period,
            "bbw_expansion_threshold": bbw_expansion_threshold,
            "body_ratio_min": body_ratio_min,
            "range_expansion_min": range_expansion_min,
        }
        if parameters:
            params.update(parameters)
        super().__init__(
            hypothesis_id="H003_VOLATILITY_EXPANSION_BREAKOUT",
            family="MOMENTUM_BREAKOUT",
            name="Volatility Expansion Breakout",
            description="Captures directional momentum surges during sudden volatility and bandwidth expansion.",
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
        dc_period = p["donchian_period"]
        gamma_bbw = p["bbw_expansion_threshold"]
        body_min = p["body_ratio_min"]
        range_min = p["range_expansion_min"]

        min_lookback = max(bb_period, dc_period) + 20
        if n < min_lookback:
            return signals

        # 1. Bollinger Bands & Bandwidth
        bb_mid, bb_upper, bb_lower = compute_bollinger_bands(close, period=bb_period, k=bb_std)
        bbw = compute_bollinger_bandwidth(close, period=bb_period, k=bb_std)
        bbw_ma = bbw.rolling(window=20, min_periods=5).mean()
        bbw_expansion = bbw / bbw_ma.replace(0, np.nan)

        # 2. Donchian Channels (shifted by 1 bar to strictly represent past channel)
        dc_upper, dc_lower, _ = compute_donchian_channels(high, low, period=dc_period)
        dc_upper_prev = dc_upper.shift(1)
        dc_lower_prev = dc_lower.shift(1)

        # 3. ATR & Range Expansion
        atr = compute_atr(high, low, close, period=14)
        candle_range = high - low
        range_factor = candle_range / atr.replace(0, np.nan)

        # 4. Body dominance
        body_abs = (close - open_p).abs()
        body_ratio = body_abs / candle_range.replace(0, np.nan)

        # Expansion conditions
        is_expansion = (bbw_expansion >= gamma_bbw) & (range_factor >= range_min) & (body_ratio >= body_min)

        # CALL: Breakout above Donchian High and Upper BB with strong green body
        call_cond = (
            is_expansion
            & (close > dc_upper_prev)
            & (close > bb_upper)
            & (close > open_p)
        )

        # PUT: Breakout below Donchian Low and Lower BB with strong red body
        put_cond = (
            is_expansion
            & (close < dc_lower_prev)
            & (close < bb_lower)
            & (close < open_p)
        )

        signals[call_cond] = MarketSignal.CALL.value
        signals[put_cond] = MarketSignal.PUT.value
        signals[call_cond & put_cond] = MarketSignal.NO_TRADE.value

        return signals
