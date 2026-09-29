"""
signal_router.py - Regime-Adaptive Signal Router for Binary Options.

Routes market regimes to statistically aligned setups:
1. RANGE -> Mean Reversion (Bollinger/Donchian penetration + RSI exhaustion + Wick rejection)
2. TREND -> Trend Pullback (EMA alignment + Dynamic equilibrium retest + RSI recovery)
3. EXPANSION -> Volatility Breakout (Bandwidth expansion + Directional momentum bar)
4. CHAOS -> Strictly NO_TRADE (Non-bypassable safety veto)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

from iq_regime_adaptive.feature_engine.regime_classifier import (
    MarketRegime,
    RegimeOutput,
    RegimeClassifier,
)
from iq_regime_adaptive.feature_engine.indicators import (
    compute_atr,
    compute_bollinger_bands,
    compute_donchian_channels,
    compute_adx,
    compute_ema,
    compute_rsi,
    compute_stochastic,
    compute_candle_morphology,
)


class MarketSignal(str, Enum):
    CALL = "CALL"
    PUT = "PUT"
    NO_TRADE = "NO_TRADE"


# Alias for spec compliance
Signal = MarketSignal



@dataclass(frozen=True)
class SignalDecision:
    """Detailed trading signal decision routed by market regime."""
    signal: MarketSignal
    regime: MarketRegime
    setup_name: str
    expiry_bars: int
    confidence: float
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class SignalRouter:
    """
    Evaluates candle data under the current classified market regime
    and routes to the appropriate trading setup.
    """

    def __init__(self, classifier: Optional[RegimeClassifier] = None):
        self.classifier = classifier or RegimeClassifier()

    def route_signal(
        self,
        df: pd.DataFrame,
        regime_output: Optional[RegimeOutput] = None,
    ) -> SignalDecision:
        """
        Determines the trading signal for the current candle.
        Strictly enforces NO_TRADE on CHAOS.
        """
        if regime_output is None:
            regime_output = self.classifier.classify_latest(df)

        regime = regime_output.regime

        # INVARIANT 1: Strict Non-Bypassable CHAOS NO-TRADE
        if regime == MarketRegime.CHAOS or not regime_output.allow_trade:
            return SignalDecision(
                signal=MarketSignal.NO_TRADE,
                regime=MarketRegime.CHAOS,
                setup_name="NONE",
                expiry_bars=0,
                confidence=0.0,
                reason=f"CHAOS VETO: {regime_output.reason}",
                metadata={"regime_metrics": regime_output.metrics},
            )

        if len(df) < 30:
            return SignalDecision(
                signal=MarketSignal.NO_TRADE,
                regime=regime,
                setup_name="NONE",
                expiry_bars=0,
                confidence=0.0,
                reason="Insufficient candles for setup indicator calculation",
            )

        close = df["close"]
        high = df["high"]
        low = df["low"]
        open_p = df["open"]

        # Compute technical indicators
        mid_bb, upper_bb, lower_bb = compute_bollinger_bands(close, period=20, k=2.0)
        dc_up, dc_low, _ = compute_donchian_channels(high, low, period=20)
        adx, pdi, mdi, _ = compute_adx(high, low, close, period=14)
        ema_20 = compute_ema(close, span=20)
        ema_50 = compute_ema(close, span=50)
        rsi = compute_rsi(close, period=14)
        stoch_k, stoch_d = compute_stochastic(high, low, close, k_period=14, d_period=3)
        morph = compute_candle_morphology(open_p, high, low, close)
        atr_14 = compute_atr(high, low, close, period=14)

        # Current & prior bar states
        c0 = float(close.iloc[-1])
        c1 = float(close.iloc[-2])
        h0 = float(high.iloc[-1])
        l0 = float(low.iloc[-1])
        o0 = float(open_p.iloc[-1])

        ub0 = float(upper_bb.iloc[-1])
        lb0 = float(lower_bb.iloc[-1])
        ub1 = float(upper_bb.iloc[-2])
        lb1 = float(lower_bb.iloc[-2])

        dc_up1 = float(dc_up.iloc[-2])
        dc_low1 = float(dc_low.iloc[-2])

        rsi0 = float(rsi.iloc[-1])
        rsi1 = float(rsi.iloc[-2])
        stoch0 = float(stoch_k.iloc[-1])
        stoch1 = float(stoch_k.iloc[-2])

        curr_atr = float(atr_14.iloc[-1])
        pdi0 = float(pdi.iloc[-1])
        mdi0 = float(mdi.iloc[-1])
        e20 = float(ema_20.iloc[-1])
        e50 = float(ema_50.iloc[-1])

        body_ratio = float(morph["body_ratio"].iloc[-1])
        upper_wick = float(morph["upper_wick_ratio"].iloc[-1])
        lower_wick = float(morph["lower_wick_ratio"].iloc[-1])
        is_bullish = bool(morph["is_bullish"].iloc[-1])

        # ---------------------------------------------------------------------
        # SETUP 1: MEAN REVERSION (RANGE REGIME)
        # ---------------------------------------------------------------------
        if regime == MarketRegime.RANGE:
            # CALL Setup: Oversold bounce off lower band
            penetrated_lower = (c1 <= lb1) or (l0 <= lb0) or (c1 <= dc_low1)
            oversold = (rsi1 <= 32.0) or (rsi0 <= 32.0) or (stoch1 <= 20.0) or (stoch0 <= 20.0)
            bullish_rejection = is_bullish and (lower_wick >= 0.25 or (c0 > o0 and c0 > l0 + 0.5 * (h0 - l0)))

            if penetrated_lower and oversold and bullish_rejection:
                return SignalDecision(
                    signal=MarketSignal.CALL,
                    regime=MarketRegime.RANGE,
                    setup_name="RANGE_MEAN_REVERSION",
                    expiry_bars=1,
                    confidence=0.70,
                    reason=f"Lower band bounce + oversold RSI ({rsi0:.1f}) + rejection wick ({lower_wick:.2f})",
                    metadata={"rsi": rsi0, "lower_wick": lower_wick, "lb": lb0},
                )

            # PUT Setup: Overbought bounce off upper band
            penetrated_upper = (c1 >= ub1) or (h0 >= ub0) or (c1 >= dc_up1)
            overbought = (rsi1 >= 68.0) or (rsi0 >= 68.0) or (stoch1 >= 80.0) or (stoch0 >= 80.0)
            bearish_rejection = (not is_bullish) and (upper_wick >= 0.25 or (c0 < o0 and c0 < h0 - 0.5 * (h0 - l0)))

            if penetrated_upper and overbought and bearish_rejection:
                return SignalDecision(
                    signal=MarketSignal.PUT,
                    regime=MarketRegime.RANGE,
                    setup_name="RANGE_MEAN_REVERSION",
                    expiry_bars=1,
                    confidence=0.70,
                    reason=f"Upper band bounce + overbought RSI ({rsi0:.1f}) + rejection wick ({upper_wick:.2f})",
                    metadata={"rsi": rsi0, "upper_wick": upper_wick, "ub": ub0},
                )

            return SignalDecision(
                signal=MarketSignal.NO_TRADE,
                regime=MarketRegime.RANGE,
                setup_name="RANGE_MEAN_REVERSION",
                expiry_bars=0,
                confidence=0.0,
                reason="Range regime active, but no band penetration + exhaustion trigger met",
            )

        # ---------------------------------------------------------------------
        # SETUP 2: TREND PULLBACK (TREND REGIME)
        # ---------------------------------------------------------------------
        if regime == MarketRegime.TREND:
            # Bullish Trend Pullback -> CALL
            trend_bull = (pdi0 > mdi0) and (e20 > e50)
            pullback_bull_held = (l0 <= e20 + 0.3 * curr_atr) and (c0 > e20)
            rsi_bull_recovery = (35.0 <= rsi0 <= 55.0) and (rsi0 >= rsi1)

            if trend_bull and pullback_bull_held and rsi_bull_recovery:
                return SignalDecision(
                    signal=MarketSignal.CALL,
                    regime=MarketRegime.TREND,
                    setup_name="TREND_PULLBACK",
                    expiry_bars=2,
                    confidence=0.75,
                    reason=f"Bullish trend EMA held + RSI pullback recovery ({rsi0:.1f})",
                    metadata={"rsi": rsi0, "ema_20": e20, "ema_50": e50},
                )

            # Bearish Trend Pullback -> PUT
            trend_bear = (mdi0 > pdi0) and (e20 < e50)
            pullback_bear_held = (h0 >= e20 - 0.3 * curr_atr) and (c0 < e20)
            rsi_bear_recovery = (45.0 <= rsi0 <= 65.0) and (rsi0 <= rsi1)

            if trend_bear and pullback_bear_held and rsi_bear_recovery:
                return SignalDecision(
                    signal=MarketSignal.PUT,
                    regime=MarketRegime.TREND,
                    setup_name="TREND_PULLBACK",
                    expiry_bars=2,
                    confidence=0.75,
                    reason=f"Bearish trend EMA held + RSI pullback recovery ({rsi0:.1f})",
                    metadata={"rsi": rsi0, "ema_20": e20, "ema_50": e50},
                )

            return SignalDecision(
                signal=MarketSignal.NO_TRADE,
                regime=MarketRegime.TREND,
                setup_name="TREND_PULLBACK",
                expiry_bars=0,
                confidence=0.0,
                reason="Trend active, but no dynamic equilibrium pullback confirmed",
            )

        # ---------------------------------------------------------------------
        # SETUP 3: VOLATILITY BREAKOUT (EXPANSION REGIME)
        # ---------------------------------------------------------------------
        if regime == MarketRegime.EXPANSION:
            # Bullish Breakout -> CALL
            break_bull = (c0 > ub0) or (c0 > dc_up1)
            body_bull = is_bullish and (body_ratio >= 0.50)
            di_bull = (pdi0 - mdi0) >= 12.0

            if break_bull and body_bull and di_bull:
                return SignalDecision(
                    signal=MarketSignal.CALL,
                    regime=MarketRegime.EXPANSION,
                    setup_name="VOLATILITY_BREAKOUT",
                    expiry_bars=1,
                    confidence=0.72,
                    reason=f"Bullish volatility breakout (Body={body_ratio:.2f}, DI_diff={pdi0 - mdi0:.1f})",
                    metadata={"body_ratio": body_ratio, "ub": ub0},
                )

            # Bearish Breakout -> PUT
            break_bear = (c0 < lb0) or (c0 < dc_low1)
            body_bear = (not is_bullish) and (body_ratio >= 0.50)
            di_bear = (mdi0 - pdi0) >= 12.0

            if break_bear and body_bear and di_bear:
                return SignalDecision(
                    signal=MarketSignal.PUT,
                    regime=MarketRegime.EXPANSION,
                    setup_name="VOLATILITY_BREAKOUT",
                    expiry_bars=1,
                    confidence=0.72,
                    reason=f"Bearish volatility breakout (Body={body_ratio:.2f}, DI_diff={mdi0 - pdi0:.1f})",
                    metadata={"body_ratio": body_ratio, "lb": lb0},
                )

            return SignalDecision(
                signal=MarketSignal.NO_TRADE,
                regime=MarketRegime.EXPANSION,
                setup_name="VOLATILITY_BREAKOUT",
                expiry_bars=0,
                confidence=0.0,
                reason="Expansion active, but candle does not satisfy breakout body and directional spread",
            )

        # Catch-all
        return SignalDecision(
            signal=MarketSignal.NO_TRADE,
            regime=MarketRegime.CHAOS,
            setup_name="NONE",
            expiry_bars=0,
            confidence=0.0,
            reason="Unrecognized regime state",
        )


def route_signal(df: pd.DataFrame, regime_output: Optional[RegimeOutput] = None) -> SignalDecision:
    """Convenience functional interface for signal routing."""
    router = SignalRouter()
    return router.route_signal(df, regime_output=regime_output)
