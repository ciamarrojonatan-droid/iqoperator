"""
base_hypothesis.py - Abstract Base Class for Binary Options Hypotheses.

Defines the standard interface contract:
- generate_signals(df: pd.DataFrame, payout: float = 0.85) -> pd.Series
- metadata: hypothesis_id, family, name, description, default_horizon_bars, default_payout_hurdle, parameters
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import pandas as pd

from iq_regime_adaptive.feature_engine.signal_router import MarketSignal


class BaseHypothesis(ABC):
    """
    Abstract Base Class for empirical binary options hypotheses (H001 - H008).
    All concrete hypotheses must implement generate_signals.
    """

    def __init__(
        self,
        hypothesis_id: str,
        family: str,
        name: str,
        description: str,
        default_horizon_bars: int = 1,
        default_payout_hurdle: float = 0.80,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        self.hypothesis_id = hypothesis_id
        self.family = family
        self.name = name
        self.description = description
        self.default_horizon_bars = default_horizon_bars
        self.default_payout_hurdle = default_payout_hurdle
        self.parameters = parameters or {}

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame, payout: float = 0.85) -> pd.Series:
        """
        Generates trading signals for each candle in df.

        Args:
            df: Historical OHLCV DataFrame.
            payout: Current broker payout rate B in (0, 1].

        Returns:
            pd.Series indexed by df.index with values in ["CALL", "PUT", "NO_TRADE"].
        """
        pass

    def validate_df(self, df: pd.DataFrame) -> None:
        """Validates that df contains standard OHLCV columns."""
        required = ["open", "high", "low", "close"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"DataFrame missing required OHLC columns: {missing}")

    def get_metadata(self) -> Dict[str, Any]:
        """Returns structured dictionary of hypothesis metadata."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "family": self.family,
            "name": self.name,
            "description": self.description,
            "default_horizon_bars": self.default_horizon_bars,
            "default_payout_hurdle": self.default_payout_hurdle,
            "parameters": dict(self.parameters),
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.hypothesis_id}, horizon={self.default_horizon_bars})>"
