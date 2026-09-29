# BRIEFING — 2026-09-29T03:22:45Z

## Mission
Implement Milestone 2 (R3): Backtesting framework and 8 empirical hypotheses (H001-H008) in `iq_regime_adaptive/` with rigorous partitioning, boundary purging, statistical metrics, degradation evaluation, and full unit/integration test coverage.

## 🔒 My Identity
- Archetype: worker
- Roles: implementer, qa, specialist
- Working directory: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\worker_m2_backtest\
- Original parent: 5300d532-e3aa-4ce2-bdf4-d9b54031954a
- Milestone: Milestone 2 (R3) - Backtest & Hypotheses Engine

## 🔒 Key Constraints
- Rigid chronological data partitioning: 50% IS, 25% VAL, 25% OOS.
- Strict h-bar boundary purging: purge any trade entry at index t where t + h > K_split to prevent outcome leakage into the adjacent partition.
- Warmup embargo: skip W_warmup (default 60 bars) at partition boundaries so indicator rolling windows do not peek into adjacent partitions.
- Zero Martingale. Fixed risk and fractional Kelly allocation only.
- Strict binary options simulation at candle Close / next Open for expiry h bars.
- Genuine implementations only: NO hardcoded test results, NO dummy/facade implementations, real state and real behavior.
- Use small slice reads, avoid cat/Get-Content/full-file reads.

## Current Parent
- Conversation ID: 5300d532-e3aa-4ce2-bdf4-d9b54031954a
- Updated: 2026-09-29T03:22:45Z

## Task Summary
- **What to build**:
  - `iq_regime_adaptive/backtest/partitioner.py`
  - `iq_regime_adaptive/hypotheses/base_hypothesis.py`
  - `iq_regime_adaptive/hypotheses/h001_range_mean_reversion.py`
  - `iq_regime_adaptive/hypotheses/h002_trend_pullback.py`
  - `iq_regime_adaptive/hypotheses/h003_volatility_expansion.py`
  - `iq_regime_adaptive/hypotheses/h004_autocorrelation_reversion.py`
  - `iq_regime_adaptive/hypotheses/h005_mtf_trend_alignment.py`
  - `iq_regime_adaptive/hypotheses/h006_payout_filtered_edge.py`
  - `iq_regime_adaptive/hypotheses/h007_squeeze_breakout.py`
  - `iq_regime_adaptive/hypotheses/h008_regime_adaptive_router.py`
  - `iq_regime_adaptive/hypotheses/registry.py`
  - `iq_regime_adaptive/backtest/engine.py`
  - `iq_regime_adaptive/backtest/metrics.py`
  - `iq_regime_adaptive/backtest/degradation.py`
  - `iq_regime_adaptive/tests/test_backtest.py`
  - `iq_regime_adaptive/tests/test_hypotheses.py`
- **Success criteria**:
  - Clean unit/integration test execution: `.\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests`
  - Complete verification of boundary purging, metrics, Kelly/fixed stakes, degradation, and all 8 hypotheses.
- **Interface contracts**: `.agents\teamwork\PROJECT.md`

## Key Decisions Made
- Partitioner: Designed `DataPartitioner` and `partition_dataset` returning `(is_df, val_df, oos_df)` with explicit `trade_eligible`, `boundary_purged`, and `warmup_embargo` boolean columns and `PartitionedData` metadata.
- Hypotheses: Implemented all 8 hypotheses inheriting from `BaseHypothesis` with canonical registry and discovery factory.
- Backtest Engine: Implemented causal simulation (Open_{t+1} or Close_t entry, Close_{t+h} expiry), payoff calculation (+payout vs -1), circuit breaker kill-switch, and strict anti-martingale stake sizing.
- Metrics & Degradation: Implemented exact Wilson Lower Bound, Effective N ($N_{eff}$) with outcome autocorrelation, Delta EV, Degradation Index, and 4-component Composite Stability Score ($S_{comp} \in [0, 100]$).

## Artifact Index
- `.agents\teamwork\worker_m2_backtest\DISPATCH.md` — Assignment from orchestrator
- `.agents\teamwork\worker_m2_backtest\BRIEFING.md` — Persistent state tracking
- `.agents\teamwork\worker_m2_backtest\progress.md` — Liveness heartbeat
- `.agents\teamwork\worker_m2_backtest\handoff.md` — 5-component handoff report

## Change Tracker
- **Files created**:
  - `iq_regime_adaptive/backtest/__init__.py`
  - `iq_regime_adaptive/backtest/partitioner.py`
  - `iq_regime_adaptive/backtest/metrics.py`
  - `iq_regime_adaptive/backtest/engine.py`
  - `iq_regime_adaptive/backtest/degradation.py`
  - `iq_regime_adaptive/hypotheses/__init__.py`
  - `iq_regime_adaptive/hypotheses/base_hypothesis.py`
  - `iq_regime_adaptive/hypotheses/h001_range_mean_reversion.py`
  - `iq_regime_adaptive/hypotheses/h002_trend_pullback.py`
  - `iq_regime_adaptive/hypotheses/h003_volatility_expansion.py`
  - `iq_regime_adaptive/hypotheses/h004_autocorrelation_reversion.py`
  - `iq_regime_adaptive/hypotheses/h005_mtf_trend_alignment.py`
  - `iq_regime_adaptive/hypotheses/h006_payout_filtered_edge.py`
  - `iq_regime_adaptive/hypotheses/h007_squeeze_breakout.py`
  - `iq_regime_adaptive/hypotheses/h008_regime_adaptive_router.py`
  - `iq_regime_adaptive/hypotheses/registry.py`
  - `iq_regime_adaptive/tests/test_backtest.py`
  - `iq_regime_adaptive/tests/test_hypotheses.py`
- **Build status**: 129/129 tests passing (100% pass)
- **Pending issues**: None

## Quality Status
- **Build/test result**: PASS (129 tests in 5.756s)
- **Lint status**: Clean (all python files compile without error)
- **Tests added/modified**: 30 new unit & integration tests added (15 in test_hypotheses, 15 in test_backtest)

## Loaded Skills
- None requested specifically
