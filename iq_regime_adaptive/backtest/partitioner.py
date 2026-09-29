"""
partitioner.py - Rigid Chronological Data Partitioning & Boundary Anti-Leakage.

R3 Partitioning Architecture:
1. 3-Way Chronological Split:
   - In-Sample (IS): 50% of chronological timeline [T_0, T_IS]
   - Validation (VAL): 25% of chronological timeline [T_IS, T_VAL]
   - Out-of-Sample (OOS): 25% of chronological timeline [T_VAL, T_OOS]
   No future data is shuffled into past partitions (zero random cross-validation).

2. Strict h-Bar Boundary Purging:
   For trade expiry horizon h bars:
   A trade opened at bar t resolves at bar t + h.
   If t + h > K_split (the partition frontier), the trade outcome would leak into
   the subsequent partition.
   Purge Invariant: Drop / disallow any trade entry at bar t where t + h > K_end.

3. Warmup Embargo (W_warmup):
   Rolling indicators (EMA, ADX, ATR, RSI, Bollinger Bands) require history.
   To prevent transient distortions and cross-boundary forward leakage:
   - Trade entries are embargoed for the initial W_warmup bars (default 60) of each partition.
   - For continuous indicator continuity, read-only warmup context from the preceding
     partition may be supplied without allowing trade entries during the embargo window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PartitionMetadata:
    """Detailed metadata for a dataset partition."""
    name: str
    start_idx: int
    end_idx: int
    total_bars: int
    warmup_bars: int
    purged_bars: int
    tradeable_bars: int
    start_time: Optional[pd.Timestamp] = None
    end_time: Optional[pd.Timestamp] = None


@dataclass(frozen=True)
class PartitionedData:
    """Structured container holding partitioned DataFrames and anti-leakage masks."""
    is_df: pd.DataFrame
    val_df: pd.DataFrame
    oos_df: pd.DataFrame
    metadata: Dict[str, PartitionMetadata]
    horizon_bars: int
    warmup_bars: int

    @property
    def is_tradeable_mask(self) -> pd.Series:
        return self.is_df["trade_eligible"]

    @property
    def val_tradeable_mask(self) -> pd.Series:
        return self.val_df["trade_eligible"]

    @property
    def oos_tradeable_mask(self) -> pd.Series:
        return self.oos_df["trade_eligible"]


class DataPartitioner:
    """
    Implements rigid chronological partitioning with strict boundary purging
    and warmup embargo governance.
    """

    def __init__(
        self,
        is_ratio: float = 0.50,
        val_ratio: float = 0.25,
        oos_ratio: float = 0.25,
        horizon_bars: int = 1,
        warmup_bars: int = 60,
    ):
        if not np.isclose(is_ratio + val_ratio + oos_ratio, 1.0, atol=1e-5):
            raise ValueError(
                f"Partition ratios must sum to 1.0. Given: is={is_ratio}, val={val_ratio}, oos={oos_ratio} "
                f"(sum={is_ratio + val_ratio + oos_ratio})"
            )
        if min(is_ratio, val_ratio, oos_ratio) <= 0.0:
            raise ValueError("All partition ratios must be strictly positive.")
        if horizon_bars < 1:
            raise ValueError(f"horizon_bars must be >= 1, got {horizon_bars}")
        if warmup_bars < 0:
            raise ValueError(f"warmup_bars must be >= 0, got {warmup_bars}")

        self.is_ratio = is_ratio
        self.val_ratio = val_ratio
        self.oos_ratio = oos_ratio
        self.horizon_bars = horizon_bars
        self.warmup_bars = warmup_bars

    def partition(
        self,
        df: pd.DataFrame,
        attach_context_warmup: bool = False,
    ) -> PartitionedData:
        """
        Partitions the input DataFrame chronologically into IS, VAL, and OOS.

        Args:
            df: OHLCV DataFrame (must have datetime index or monotonic index).
            attach_context_warmup: If True, VAL and OOS partitions include trailing
                warmup bars from the prior partition (marked trade_eligible = False)
                to allow rolling indicators to initialize without lookahead.

        Returns:
            PartitionedData container with annotated DataFrames.
        """
        n = len(df)
        min_required = max(10, self.warmup_bars + self.horizon_bars + 1) * 3
        if n < min_required:
            raise ValueError(
                f"Dataset length {n} is insufficient for 3-way partitioning with "
                f"warmup_bars={self.warmup_bars} and horizon_bars={self.horizon_bars}. "
                f"Minimum required is {min_required} bars."
            )

        # Enforce chronological ordering
        if not df.index.is_monotonic_increasing:
            df = df.sort_index()

        k_is_end = int(np.floor(n * self.is_ratio))
        k_val_end = k_is_end + int(np.floor(n * self.val_ratio))
        # Ensure OOS gets remainder
        k_oos_end = n

        # Build raw chronological slices
        is_raw = df.iloc[0:k_is_end].copy()
        
        if attach_context_warmup and self.warmup_bars > 0:
            val_start = max(0, k_is_end - self.warmup_bars)
            oos_start = max(0, k_val_end - self.warmup_bars)
            val_raw = df.iloc[val_start:k_val_end].copy()
            oos_raw = df.iloc[oos_start:k_oos_end].copy()
            val_warmup_len = k_is_end - val_start
            oos_warmup_len = k_val_end - oos_start
        else:
            val_raw = df.iloc[k_is_end:k_val_end].copy()
            oos_raw = df.iloc[k_val_end:k_oos_end].copy()
            val_warmup_len = min(self.warmup_bars, len(val_raw))
            oos_warmup_len = min(self.warmup_bars, len(oos_raw))

        is_annotated, meta_is = self._annotate_partition(
            is_raw,
            name="IS",
            warmup_count=min(self.warmup_bars, len(is_raw)),
            horizon=self.horizon_bars,
            orig_start_idx=0,
            orig_end_idx=k_is_end,
        )

        val_annotated, meta_val = self._annotate_partition(
            val_raw,
            name="VAL",
            warmup_count=val_warmup_len,
            horizon=self.horizon_bars,
            orig_start_idx=k_is_end,
            orig_end_idx=k_val_end,
        )

        oos_annotated, meta_oos = self._annotate_partition(
            oos_raw,
            name="OOS",
            warmup_count=oos_warmup_len,
            horizon=self.horizon_bars,
            orig_start_idx=k_val_end,
            orig_end_idx=k_oos_end,
        )

        metadata = {
            "IS": meta_is,
            "VAL": meta_val,
            "OOS": meta_oos,
        }

        return PartitionedData(
            is_df=is_annotated,
            val_df=val_annotated,
            oos_df=oos_annotated,
            metadata=metadata,
            horizon_bars=self.horizon_bars,
            warmup_bars=self.warmup_bars,
        )

    def _annotate_partition(
        self,
        sub_df: pd.DataFrame,
        name: str,
        warmup_count: int,
        horizon: int,
        orig_start_idx: int,
        orig_end_idx: int,
    ) -> Tuple[pd.DataFrame, PartitionMetadata]:
        """
        Annotates partition with trade_eligible, warmup_embargo, and boundary_purged flags.
        """
        p_len = len(sub_df)
        trade_eligible = np.ones(p_len, dtype=bool)
        warmup_embargo = np.zeros(p_len, dtype=bool)
        boundary_purged = np.zeros(p_len, dtype=bool)

        # 1. Warmup Embargo: First warmup_count bars cannot enter trades
        if warmup_count > 0:
            warmup_embargo[:warmup_count] = True
            trade_eligible[:warmup_count] = False

        # 2. Strict Boundary Purging: Trade at index t resolving at t + horizon
        # must NOT resolve beyond the end of this partition (t + horizon >= p_len)
        purge_start = max(0, p_len - horizon)
        boundary_purged[purge_start:] = True
        trade_eligible[purge_start:] = False

        sub_df["trade_eligible"] = trade_eligible
        sub_df["warmup_embargo"] = warmup_embargo
        sub_df["boundary_purged"] = boundary_purged
        sub_df["partition"] = name

        tradeable_count = int(np.sum(trade_eligible))
        purged_count = int(np.sum(boundary_purged))
        warmup_count_effective = int(np.sum(warmup_embargo))

        start_time = sub_df.index[0] if isinstance(sub_df.index, pd.DatetimeIndex) else None
        end_time = sub_df.index[-1] if isinstance(sub_df.index, pd.DatetimeIndex) else None

        meta = PartitionMetadata(
            name=name,
            start_idx=orig_start_idx,
            end_idx=orig_end_idx,
            total_bars=p_len,
            warmup_bars=warmup_count_effective,
            purged_bars=purged_count,
            tradeable_bars=tradeable_count,
            start_time=start_time,
            end_time=end_time,
        )

        return sub_df, meta


def partition_dataset(
    df: pd.DataFrame,
    is_ratio: float = 0.50,
    val_ratio: float = 0.25,
    oos_ratio: float = 0.25,
    horizon_bars: int = 1,
    warmup_bars: int = 60,
    attach_context_warmup: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Standard interface contract function matching PROJECT.md:
    partition_dataset(df: pd.DataFrame, is_ratio=0.50, val_ratio=0.25, oos_ratio=0.25,
                      horizon_bars=1, warmup_bars=60) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]

    Enforces:
    1. Chronological ordering (sort_index).
    2. Strict h-bar boundary purging: last horizon_bars in each partition have trade_eligible = False.
    3. Warmup embargo: first warmup_bars in each partition have trade_eligible = False.

    Returns:
        Tuple of (is_df, val_df, oos_df) with 'trade_eligible' boolean column.
    """
    partitioner = DataPartitioner(
        is_ratio=is_ratio,
        val_ratio=val_ratio,
        oos_ratio=oos_ratio,
        horizon_bars=horizon_bars,
        warmup_bars=warmup_bars,
    )
    result = partitioner.partition(df, attach_context_warmup=attach_context_warmup)
    return result.is_df, result.val_df, result.oos_df
