"""
iq_regime_adaptive.backtest - Backtesting Framework for Binary Options.

Modules:
- partitioner: Chronological 50/25/25 partitioning, boundary purging, warmup embargo.
- engine: Zero-lookahead discrete binary options backtest simulation engine.
- metrics: Quantitative performance metrics (EV, Wilson Lower Bound, Effective N, Max DD).
- degradation: IS vs VAL vs OOS performance degradation and stability scoring.
"""

from iq_regime_adaptive.backtest.partitioner import (
    DataPartitioner,
    PartitionedData,
    PartitionMetadata,
    partition_dataset,
)
from iq_regime_adaptive.backtest.metrics import (
    BacktestMetrics,
    compute_effective_n,
    compute_backtest_metrics,
)
from iq_regime_adaptive.backtest.engine import (
    TradeRecord,
    BacktestResult,
    BacktestEngine,
)
from iq_regime_adaptive.backtest.degradation import (
    DegradationReport,
    compute_degradation,
)

__all__ = [
    "DataPartitioner",
    "PartitionedData",
    "PartitionMetadata",
    "partition_dataset",
    "BacktestMetrics",
    "compute_effective_n",
    "compute_backtest_metrics",
    "TradeRecord",
    "BacktestResult",
    "BacktestEngine",
    "DegradationReport",
    "compute_degradation",
]
