"""
h007_squeeze_breakout.py - Volatility Contraction Squeeze Breakout.

Hypothesis ID: H007_VOLATILITY_CONTRACTION_SQUEEZE
Family: REGIME_TRANSITION_EDGE
Microstructural Rationale:
Prolonged volatility compression (Bollinger Bands contracting completely within
Keltner Channels) stores directional potential. When the squeeze fires (bands expand
outside channels), high-velocity directional flow persists for 1 to 2 candles.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.indicators import (
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
)
from iq_regime_adaptive.feature_engine.signal_router import MarketSignal
from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis


class H007SqueezeBreakout(BaseHypothesis):
    """
    H007: Volatility Contraction Pre-Breakout Squeeze (Bollinger inside Keltner -> Release).
    """

    def __init__(
        self,
        bb_period: int = 20,
        bb_mult: float = 1.5,
        kc_period: int = 20,
        kc_mult: float = 1.5,
        min_squeeze_bars: int = 3,
        default_horizon_bars: int = 2,
        default_payout_hurdle: float = 0.75,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = {
            "bb_period": bb_period,
            "bb_mult": bb_mult,
            "kc_period": kc_period,
            "kc_mult": kc_mult,
            "min_squeeze_bars": min_squeeze_bars,
        }
        if parameters:
            params.update(parameters)
        super().__init__(
            hypothesis_id="H007_VOLATILITY_CONTRACTION_SQUEEZE",
            family="REGIME_TRANSITION_EDGE",
            name="Volatility Contraction Squeeze Breakout",
            description="Trades directional impulse upon release of Bollinger-Keltner compression squeeze.",
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
        bb_mult = p["bb_mult"]
        kc_period = p["kc_period"]
        kc_mult = p["kc_mult"]
        min_sqz = p["min_squeeze_bars"]

        min_lookback = max(bb_period, kc_period) + 10
        if n < min_lookback:
            return signals

        # 1. Bollinger Bands (k=1.5)
        bb_mid, bb_upper, bb_lower = compute_bollinger_bands(close, period=bb_period, k=bb_mult)

        # 2. Keltner Channels (m=1.5)
        kc_mid = compute_ema(close, span=kc_period)
        atr_kc = compute_atr(high, low, close, period=kc_period)
        kc_upper = kc_mid + (kc_mult * atr_kc)
        kc_lower = kc_mid - (kc_mult * atr_kc)

        # 3. Squeeze state: BB is inside KC
        squeeze_active = (bb_upper < kc_upper) & (bb_lower > kc_lower)

        # Count consecutive squeeze bars prior to bar t
        squeeze_active_prev = squeeze_active.shift(1).fillna(False)
        
        # Rolling count of squeeze bars in previous window
        squeeze_count = squeeze_active.rolling(window=min_sqz, min_periods=min_sqz).sum()
        squeeze_persisted = (squeeze_count.shift(1) >= (min_sqz - 1))

        # Squeeze fires when previous was active and current is inactive
        squeeze_fired = squeeze_persisted & squeeze_active_prev & (~squeeze_active)

        # Momentum direction: close relative to KC mid
        momentum = close - kc_mid

        # CALL: Squeeze fires + positive momentum + close above upper BB
        call_cond = squeeze_fired & (momentum > 0) & (close >= bb_upper)

        # PUT: Squeeze fires + negative momentum + close below lower BB
        put_cond = squeeze_fired & (momentum < 0) & (close <= bb_lower)

        signals[call_cond] = MarketSignal.CALL.value
        signals[put_cond] = MarketSignal.PUT.value
        signals[call_cond & put_cond] = MarketSignal.NO_TRADE.value

        return signals
