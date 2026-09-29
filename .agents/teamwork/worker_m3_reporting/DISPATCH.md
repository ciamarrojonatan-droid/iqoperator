## 2026-09-29T03:23:25Z
You are Worker M3 (worker_m3_reporting).
Your working directory is: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\worker_m3_reporting\

MANDATORY: Read ORIGINAL_REQUEST.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\ORIGINAL_REQUEST.md.
MANDATORY: Read PROJECT.md at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\PROJECT.md.
Read Explorer Survey IQ 3 report at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\explorer_survey_iq_3\report.md.
Read Worker M2 handoff at c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\worker_m2_backtest\handoff.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

TOKEN SAVING DIRECTIVE:
Do NOT use cat, Get-Content, or full-file reads. Use the sidecar daemon or small slice reads.

SCOPE OF MILESTONE 3:
1. `iq_regime_adaptive/reports/generator.py`:
   - Builds the Quantitative Verification Report in both JSON and Markdown formats:
     - Summary metrics: Effective N of trades (N_eff), normalized average EV, Wilson Lower Bound win rate (WLB_95%), nominal win rate, total PnL, Max Drawdown, Sharpe/Sortino ratios.
     - Automatic IS/OOS degradation calculation across all hypotheses processed (H001-H008): Delta EV = EV_IS - EV_OOS, Degradation Index DI, Delta WR, Composite Stability Score S_comp, and Stability Verdict.
     - Verification attestations: explicit check confirming ZERO martingale / irrational asymmetric allocation dependencies, fixed risk / strict Kelly allocation compliance.
   - Saves reports to `reports/research_report.md` and `reports/research_report.json`.
2. `run_research.py` (top-level executable script at project root `c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\run_research.py`):
   - Comprehensive CLI entrypoint:
     `python run_research.py [--data <path>] [--hypotheses H001,H002,...] [--payout 0.85] [--export-report <path>]`
   - By default loads `data/EURUSD_M5_iq.csv`, executes the rigid 50/25/25 chronological partitioning with boundary purging and warmup embargo.
   - Runs all 8 hypotheses H001-H008 across In-Sample (IS), Validation (VAL), and Out-of-Sample (OOS) partitions.
   - Automatically computes degradation metrics between IS and OOS for each hypothesis.
   - Generates the Quantitative Verification Report, displays an ASCII summary table to stdout, and exports Markdown and JSON reports.
3. Integration & Acceptance Tests:
   - Add `iq_regime_adaptive/tests/test_reporting.py` testing report generation, JSON schema validation, Markdown formatting, and degradation table formatting.
   - Execute the full test suite with:
     `.\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests`
   - Run `run_research.py` end-to-end using `.\.venv\Scripts\python.exe run_research.py` to confirm zero crashes and generate the authoritative research report artifact.
4. Write `handoff.md` with execution logs of `run_research.py`, test suite results, and confirmation of all acceptance criteria.
5. Send a message to orchestrator when complete.
