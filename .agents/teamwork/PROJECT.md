# Project: Quantitative Research Architecture (Backtest & Signal Engine) for Binary Options (IQ Option)

## Architecture
- **Objective**: Build a production-grade, mathematically sound Quantitative Research Architecture (Backtest & Signal Engine) for Binary Options (IQ Option) enforcing:
  1. Regime-Adaptive Feature Engine (Trend, Range, Expansion, Chaos with explicit NO TRADE)
  2. Expiry & Payout Conditional Pipeline (Break-even probability, EV > 0 with Wilson Lower Bound)
  3. Out-of-Sample (OOS) Stability (Rigid IS/VAL/OOS split, degradation calculation for hypotheses H001-H008)
  4. Quantitative Verification Report (effective N, normalized average EV, Wilson Lower Bound win rate), automatic IS/OOS degradation calculation, and zero martingale / irrational asymmetric allocation dependencies.
- **Package Root**: `iq_regime_adaptive/`
- **Runtime**: Python 3.11.9 at `.venv\Scripts\python.exe`.
- **Test Runner**: Python standard library `unittest` via `.\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests`.
- **Token Efficiency Invariant**: Compliance with user directive prohibiting whole-file reads; use sidecar daemon (`python -m synaptic_hypervisor.sidecar.daemon`) or localized slice reads.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | `data_loader_normalizer` | Robust CSV ingestion with auto-detection of epoch sec/msec/ISO timestamps and OHLCV validation | M1 | Survey IQ 1 |
| 2 | `volatility_indicators` | ATR, Normalized ATR (NATR), Bollinger Bandwidth (BBW, BBW_Z, percentile), and Parkinson / NRV volatility | M1 | Survey IQ 2 / R1 |
| 3 | `trend_indicators` | Wilder's ADX (14-period) with +DI / -DI directional movement indices | M1 | Survey IQ 2 / R1 |
| 4 | `market_memory_indicators` | Lag-1 return autocorrelation $\rho_1$ and Lo-MacKinlay Variance Ratio $VR(q)$ | M1 | Survey IQ 2 / R1 |
| 5 | `regime_classifier` | 5-Tier deterministic decision tree assigning Trend, Range, Expansion, Chaos | M1 | Survey IQ 2 / R1 |
| 6 | `chaos_no_trade_veto` | Strict non-bypassable NO TRADE decision when regime is Chaos or volatility shock | M1 | Survey IQ 2 / R1 |
| 7 | `strategy_setup_router` | Routes market state to setup: Mean Reversion (Range), Trend Pullback (Trend), Breakout (Expansion) | M1 | Survey IQ 2 / R1 |
| 8 | `payout_breakeven_math` | Calculates break-even win rate $P_{BE} = 1 / (1 + \text{Payout})$ and nominal EV | M1 | Survey IQ 2 / R2 |
| 9 | `wilson_lower_bound` | Closed-form Wilson Score Interval Lower Bound ($WLB_{95\%}$, $z=1.96$) penalizing small sample sizes | M1 | Survey IQ 2 / R2 |
| 10 | `ev_wlb_execution_gate` | Strict execution invariant: trade allowed iff $EV_{WLB} = WLB(1+b)-1 > 0 \iff WLB > P_{BE}$ | M1 | Survey IQ 2 / R2 |
| 11 | `capital_allocation_anti_martingale` | Regularized fractional Kelly ($f^*_{WLB}$) and fixed fractional risk with strict proof of zero martingale | M1 | Survey IQ 2 / R2 |
| 12 | `rigid_chronological_split` | 50% In-Sample (IS), 25% Validation (VAL), 25% Out-of-Sample (OOS) chronological partitioner | M2 | Survey IQ 3 / R3 |
| 13 | `boundary_purging_embargo` | Mathematical $h$-bar boundary purging ($t+h \le K_{split}$) and warmup embargo ($E_{embargo}$) | M2 | Survey IQ 3 / R3 |
| 14 | `hypotheses_h001_h008` | Concrete implementations of 8 quantitative hypotheses for binary options (H001 to H008) | M2 | Survey IQ 3 / R3 |
| 15 | `backtest_engine` | Vectorized/event-driven binary option backtester simulating entries, payouts, and outcomes without lookahead | M2 | Survey IQ 3 / R3 |
| 16 | `degradation_calculator` | Automatic calculation of $\Delta EV = EV_{IS} - EV_{OOS}$, Degradation Index $DI$, $\Delta WR$, and Stability Score | M2 | Survey IQ 3 / R3 |
| 17 | `quant_verification_report` | Generates quantitative report with effective N, normalized average EV, Wilson Lower Bound, and degradation matrix | M3 | Survey IQ 3 / Criteria |
| 18 | `e2e_research_runner` | Top-level executable pipeline script (`run_research.py`) orchestrating hypotheses execution across datasets | M3 | Survey IQ 1 / Criteria |
| 19 | `e2e_test_suite_opaque` | Opaque-box 4-tier requirement-driven test suite validating all R1, R2, R3 constraints and invariants | M3 | E2E Testing Track |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | `m1_engine_and_pipeline` | Features 1-11: R1 Regime Feature Engine (Indicators, Classifier, Chaos Veto, Router) + R2 Payout Pipeline (P_BE, Wilson Lower Bound, EV_WLB Gate, Strict Kelly/Anti-Martingale) + Unit Tests | none | DONE |
| 2 | `m2_backtest_and_hypotheses` | Features 12-16: R3 Backtest Engine (Rigid IS/VAL/OOS split, Purging/Embargo, H001-H008 Hypotheses, Degradation Calculator) + Unit Tests | M1 | IN_PROGRESS |
| 3 | `m3_reporting_and_e2e_verification` | Features 17-19: Quantitative Verification Report, Top-level Research Runner, E2E Acceptance Test Suite, Challenger Verification, and Forensic Integrity Audit | M2 | PLANNED |

## Interface Contracts
### Feature Engine $\leftrightarrow$ Pipeline Router
- Function: `classify_regime(df: pd.DataFrame) -> pd.Series`
  - Input: DataFrame with OHLCV data.
  - Output: Categorical Series with values `['TREND', 'RANGE', 'EXPANSION', 'CHAOS']`.
  - Invariant: If `CHAOS`, signal routing returns `Signal.NO_TRADE` unconditionally.

### Pipeline Router $\leftrightarrow$ Execution Gate
- Function: `evaluate_trade_gate(sample_wins: int, sample_n: int, payout: float) -> TradeGateDecision`
  - Computes $P_{BE} = \frac{1}{1 + \text{payout}}$.
  - Computes $WLB = \frac{\hat{p} + \frac{z^2}{2n} - z\sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$ ($z=1.96$).
  - Computes $EV_{WLB} = WLB \cdot (1 + \text{payout}) - 1$.
  - Decision: `allowed = (EV_WLB > 0.0)`.

### Partitioning $\leftrightarrow$ Backtest Engine
- Function: `partition_dataset(df: pd.DataFrame, is_ratio=0.50, val_ratio=0.25, oos_ratio=0.25, horizon_bars=1, warmup_bars=60) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`
  - Enforces chronological ordering (`sort_index()`).
  - Purges boundary: drops indices where $t + horizon\_bars > \text{split\_index}$.
  - Embargo: skips $warmup\_bars$ at partition boundaries to eliminate state leakage.

### Degradation Evaluator $\leftrightarrow$ Report
- Function: `compute_degradation(is_metrics: Dict, oos_metrics: Dict) -> DegradationReport`
  - Computes $\Delta EV = EV_{IS} - EV_{OOS}$.
  - Computes $DI = \frac{EV_{IS} - EV_{OOS}}{\max(|EV_{IS}|, 1e-6)}$.
  - Computes Stability Score $S_{comp} \in [0, 100]$.

## Code Layout
- Package Root: `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\iq_regime_adaptive\`
  - `feature_engine/`:
    - `__init__.py`
    - `indicators.py`: Volatility, ADX, Autocorrelation, Variance Ratio calculations.
    - `regime_classifier.py`: 5-Tier Decision Tree and Chaos Veto.
    - `signal_router.py`: Routing to setups.
  - `pipeline/`:
    - `__init__.py`
    - `payout_filter.py`: $P_{BE}$, $EV$, Wilson Lower Bound, Execution Gate.
    - `risk_allocation.py`: Regularized fractional Kelly, Fixed fractional risk, Anti-martingale invariant.
    - `data_loader.py`: CSV loading, timestamp parsing, validation.
  - `hypotheses/`:
    - `__init__.py`
    - `base_hypothesis.py`: Abstract Base Class for binary options hypotheses.
    - `h001_range_mean_reversion.py`
    - `h002_trend_pullback.py`
    - `h003_volatility_expansion.py`
    - `h004_autocorrelation_reversion.py`
    - `h005_mtf_trend_alignment.py`
    - `h006_payout_filtered_edge.py`
    - `h007_squeeze_breakout.py`
    - `h008_regime_adaptive_router.py`
    - `registry.py`: Hypotheses registry mapping H001-H008.
  - `backtest/`:
    - `__init__.py`
    - `partitioner.py`: Rigid chronological IS/VAL/OOS split, purging, embargo.
    - `engine.py`: Vectorized/event-driven simulation of binary option trades.
    - `metrics.py`: Effective N, Wilson Lower Bound, normalized EV, Max Drawdown.
    - `degradation.py`: Automated IS vs OOS degradation calculator.
  - `reports/`:
    - `__init__.py`
    - `generator.py`: Quantitative verification report (Markdown and JSON).
  - `tests/`:
    - `test_feature_engine.py`
    - `test_pipeline.py`
    - `test_backtest.py`
    - `test_hypotheses.py`
    - `test_anti_martingale.py`
    - `test_e2e_acceptance.py`
  - `run_research.py`: CLI/entrypoint for running full backtest & research suite across datasets.
