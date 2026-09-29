# BRIEFING — 2026-09-29T02:41:35Z

## Mission
Research and rigorously specify the mathematical and statistical formulations for R1 (Regime-Adaptive Feature Engine) and R2 (Expiry & Payout Conditional Pipeline with Wilson Lower Bound and EV).

## 🔒 My Identity
- Archetype: explorer
- Roles: Quantitative Researcher, Statistical Modeler
- Working directory: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_2
- Original parent: 5300d532-e3aa-4ce2-bdf4-d9b54031954a
- Milestone: Survey IQ 2 — Mathematical & Quantitative Formulations for R1 & R2

## 🔒 Key Constraints
- Read-only investigation — do NOT implement production code
- Strict zero martingale, zero irrational asymmetric compounding
- Rigorous mathematical and statistical formulations for Trend, Range, Expansion, Chaos regimes
- Rigorous Payout-conditional logic, Wilson Score Interval Lower Bound, EV, Kelly/Fractional Kelly
- Output must be in report.md and summarized in handoff.md; communication via send_message to parent
- Strict token efficiency: No cat / Get-Content or whole-file dumps; audit using small slices or sidecar daemon

## Current Parent
- Conversation ID: 5300d532-e3aa-4ce2-bdf4-d9b54031954a
- Updated: 2026-09-29T02:41:16Z

## Investigation State
- **Explored paths**: .agents/teamwork/ORIGINAL_REQUEST.md, kelly.py, strategies.py, ml_filter.py
- **Key findings**: Formulated complete mathematical specifications for R1 (ATR, BBW, NRV, Parkinson, ADX/+DI/-DI, Lag-1 autocorrelation, Lo-MacKinlay Variance Ratio test, deterministic decision tree, Chaos veto, strategy routing) and R2 (P_BE, Wilson Score Interval Lower Bound derivation, conservative EV_WLB, sample size sensitivity table, mathematical proof of martingale ruin, regularized Quarter-Kelly). Validated formulas with python.
- **Unexplored areas**: None within the survey scope for Survey IQ 2. Ready for handoff to orchestrator and implementers.

## Key Decisions Made
- Derived exact quadratic roots for Wilson Score Interval Lower Bound ($WLB$) with standard $z=1.96$ (95% confidence).
- Formulated Lo-MacKinlay heteroskedasticity-consistent Variance Ratio test ($VR(q)$) as a statistical discriminator between mean-reverting and trending regimes.
- Formulated hard Chaos veto in Tier 1 of classification to prevent negative-sum execution under fat-tailed volatility shocks.
- Enforced Quarter-Kelly ($\gamma = 0.25$) risk sizing with 2% hard bankroll ceiling and absolute mathematical prohibition of martingale.

## Artifact Index
- c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_2\DISPATCH.md — Stored dispatch directives
- c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_2\BRIEFING.md — Persistent context & identity
- c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_2\progress.md — Heartbeat and liveness tracking
- c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_2\report.md — Full quantitative research specification (R1 & R2)
- c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_2\handoff.md — 5-component self-contained handoff report
