# Orchestration Plan — Quantitative Research Architecture for Binary Options

## Objective
Build a robust, production-grade Quantitative Research Architecture (Backtest & Signal Engine) for Binary Options (IQ Option) implementing:
- R1: Regime-Adaptive Feature Engine (Trend, Range, Expansion, Chaos with explicit NO TRADE)
- R2: Expiry & Payout Conditional Pipeline (Break-even probability, EV > 0 with Wilson Lower Bound)
- R3: Out-of-Sample (OOS) Stability (Rigid IS/VAL/OOS split, degradation calculation for hypotheses H001-H008)
- Acceptance Criteria: Quantitative verification report (effective N, normalized average EV, Wilson Lower Bound win rate), automatic IS/OOS degradation calculation, and zero martingale / irrational asymmetric allocation dependencies.

## Phases
1. **Phase 0: Survey & Discovery**
   - Dispatch 3 Explorers in parallel to inspect:
     - Explorer A: Workspace layout, existing repositories/modules (`iqoperator`, `iq_regime_adaptive`, python env, packages, datasets, strategies).
     - Explorer B: Quantitative formulations, statistical specifications (Wilson Lower Bound, EV, Break-even probability, Regime classifications: Trend, Range, Expansion, Chaos, ADX, volatility, autocorrelation).
     - Explorer C: Hypotheses H001-H008 specifications, IS/VAL/OOS partitioning rules, degradation calculation, and test/backtest runner architecture.
   - Aggregate findings into `PROJECT.md` (Architecture, Feature Inventory, Milestones, Interface Contracts, Code Layout).

2. **Phase 1: Milestone Decomposition & Interface Contracts**
   - Define milestones (e.g., M1: Core Regime Engine & Data Pipeline; M2: Expiry & Payout Conditional Pipeline + Risk Allocation; M3: Backtest Engine, IS/VAL/OOS Evaluation & Hypotheses H001-H008 runner; M4: E2E Integration & Verification Suite).
   - Setup E2E Testing track.

3. **Phase 2: Milestone Iteration Loops**
   - For each milestone: Explorer -> Worker -> Reviewers (2) + Challengers (2) + Forensic Auditor (1) -> Gate.
   - Strictly enforce integrity checks: Zero martingale, zero fabricated data, genuine statistical calculations.

4. **Phase 3: E2E Verification & Audit Gate**
   - Execute full backtest suite across datasets and hypotheses H001-H008.
   - Verify all acceptance criteria and generate quantitative report.
   - Final review and forensic integrity audit.

5. **Phase 4: Synthesis & Reporting**
   - Final synthesis and reporting back to caller (Sentinel).
