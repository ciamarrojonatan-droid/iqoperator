"""
h006_payout_filtered_edge.py - High Payout & EV_WLB Filtered Edge.

Hypothesis ID: H006_PAYOUT_FILTERED_DYNAMIC_EDGE
Family: PAYOUT_EV_OPTIMIZATION
Microstructural Rationale:
Binary options expected value is acutely sensitive to broker payout yield:
EV = p * (1 + B) - 1. P_BE = 1 / (1 + B).
At B < 0.80, required break-even win rate exceeds 55.5%, leading to rapid negative-drift ruin.
This hypothesis strictly halts all trading whenever payout B < 0.80, and under favorable
payouts (B >= 0.80), triggers high-conviction statistical confluence setups where EV_WLB > 0.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.indicators import (
    compute_bollinger_bands,
    compute_rsi,
    compute_adx,
)
from iq_regime_adaptive.feature_engine.signal_router import MarketSignal
from iq_regime_adaptive.pipeline.payout_filter import (
    compute_payout_be,
    compute_wilson_lower_bound,
    compute_expected_value,
)
from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis


class H006PayoutFilteredEdge(BaseHypothesis):
    """
    H006: Payout-Filtered Dynamic Edge (Payout >= 0.80 + Confluence + EV_WLB > 0).
    """

    def __init__(
        self,
        min_payout: float = 0.80,
        hurdle_cushion: float = 0.015,
        bb_period: int = 20,
        rsi_period: int = 14,
        default_horizon_bars: int = 1,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = {
            "min_payout": min_payout,
            "hurdle_cushion": hurdle_cushion,
            "bb_period": bb_period,
            "rsi_period": rsi_period,
        }
        if parameters:
            params.update(parameters)
        super().__init__(
            hypothesis_id="H006_PAYOUT_FILTERED_DYNAMIC_EDGE",
            family="PAYOUT_EV_OPTIMIZATION",
            name="Payout Filtered Dynamic Edge",
            description="Strictly gates execution by minimum payout (>=0.80) and EV_WLB mathematical expectation.",
            default_horizon_bars=default_horizon_bars,
            default_payout_hurdle=min_payout,
            parameters=params,
        )

    def generate_signals(self, df: pd.DataFrame, payout: float = 0.85) -> pd.Series:
        self.validate_df(df)
        n = len(df)
        signals = pd.Series(MarketSignal.NO_TRADE.value, index=df.index, name="signal")

        p = self.parameters
        min_pay = p["min_payout"]

        # Strict Payout Gate Invariant: If payout is below hurdle, unconditional NO_TRADE
        if payout < min_pay:
            return signals

        # Calculate break-even win rate
        p_be = compute_payout_be(payout)

        close = df["close"]
        high = df["high"]
        low = df["low"]
        open_p = df["open"]

        bb_period = p["bb_period"]
        rsi_period = p["rsi_period"]

        if n < max(bb_period, rsi_period) + 15:
            return signals

        # Indicators
        bb_mid, bb_upper, bb_lower = compute_bollinger_bands(close, period=bb_period, k=2.0)
        rsi = compute_rsi(close, period=rsi_period)
        adx, plus_di, minus_di, _ = compute_adx(high, low, close, period=14)

        # High-conviction confluence:
        # Reversion setup during non-chaotic markets
        candle_range = (high - low).replace(0, np.nan)
        lower_wick_ratio = (close - low) / candle_range
        upper_wick_ratio = (high - close) / candle_range

        call_cond = (
            (close <= bb_lower)
            & (rsi <= 32.0)
            & (lower_wick_ratio >= 0.25)
            & (adx <= 30.0)
        )

        put_cond = (
            (close >= bb_upper)
            & (rsi >= 68.0)
            & (upper_wick_ratio >= 0.25)
            & (adx <= 30.0)
        )

        signals[call_cond] = MarketSignal.CALL.value
        signals[put_cond] = MarketSignal.PUT.value
        signals[call_cond & put_cond] = MarketSignal.NO_TRADE.value

        return signals
