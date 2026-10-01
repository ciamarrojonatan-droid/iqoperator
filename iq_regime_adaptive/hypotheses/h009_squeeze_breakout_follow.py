"""
h009_squeeze_breakout_follow.py - Squeeze-Gated Donchian Breakout Follow.

Hypothesis ID: H009_SQUEEZE_BREAKOUT_FOLLOW
Family: REGIME_TRANSITION_EDGE
Microstructural Rationale:
Prolonged volatility compression stores directional potential (same precondition
as H007). Unlike H007 (fires on release bar) and donchian_fade (bets against
the break), H009 bets WITH a confirmed Donchian channel break that occurs
while volatility is still compressed: close beyond the N-bar extreme in the
direction of the break. Rationale: crypto M5 breaks persist via liquidation
cascades and momentum ignition; fading them bleeds.

Interaction is exactly ONE: compression precondition x breakout direction.
All parameters fixed a priori (no tuning). Pre-registered success criteria:
OOS WLB > breakeven AND N >= 50 on BOTH BTCUSDT_M5_3y and EURUSD_M5_iq.
Anything else = REJECTED without appeal.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import pandas as pd

from iq_regime_adaptive.feature_engine.indicators import compute_bollinger_bands
from iq_regime_adaptive.feature_engine.signal_router import MarketSignal
from iq_regime_adaptive.hypotheses.base_hypothesis import BaseHypothesis


class H009SqueezeBreakoutFollow(BaseHypothesis):
    """
    H009: Donchian breakout follow gated by Bollinger compression.
    """

    def __init__(
        self,
        donchian_n: int = 20,
        bb_period: int = 20,
        bb_mult: float = 2.0,
        squeeze_lookback: int = 100,
        squeeze_pct: float = 0.25,
        default_horizon_bars: int = 1,
        default_payout_hurdle: float = 0.75,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = {
            "donchian_n": donchian_n,
            "bb_period": bb_period,
            "bb_mult": bb_mult,
            "squeeze_lookback": squeeze_lookback,
            "squeeze_pct": squeeze_pct,
        }
        if parameters:
            params.update(parameters)
        super().__init__(
            hypothesis_id="H009_SQUEEZE_BREAKOUT_FOLLOW",
            family="REGIME_TRANSITION_EDGE",
            name="Squeeze-Gated Breakout Follow",
            description="Follows confirmed Donchian breaks occurring under volatility compression.",
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

        p = self.parameters
        dc_n = p["donchian_n"]
        bb_period = p["bb_period"]
        bb_mult = p["bb_mult"]
        sq_lb = p["squeeze_lookback"]
        sq_pct = p["squeeze_pct"]

        if n < sq_lb + dc_n + 5:
            return signals

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # 1. Compression: BB width / close below its rolling percentile.
        _, bb_upper, bb_lower = compute_bollinger_bands(close, period=bb_period, k=bb_mult)
        width = (bb_upper - bb_lower) / close.replace(0, float("nan"))
        width_rank = width.rolling(window=sq_lb, min_periods=sq_lb).rank(pct=True)
        compressed = width_rank <= sq_pct

        # 2. Donchian extremes EXCLUDING current bar (no lookahead, same as fade).
        hi = high.shift(1).rolling(window=dc_n, min_periods=dc_n).max()
        lo = low.shift(1).rolling(window=dc_n, min_periods=dc_n).min()

        # 3. Follow (inverse of fade): break up -> CALL, break down -> PUT.
        call_cond = compressed & (close > hi)
        put_cond = compressed & (close < lo)

        signals[call_cond] = MarketSignal.CALL.value
        signals[put_cond] = MarketSignal.PUT.value
        signals[call_cond & put_cond] = MarketSignal.NO_TRADE.value

        return signals
