# Milestone 3 Handoff Report: Quantitative Verification Reporting & CLI Pipeline Orchestration

## 1. Observation
- Requirements from dispatch:
  1. `iq_regime_adaptive/reports/generator.py`:
     - Builds Quantitative Verification Report in both JSON and Markdown formats.
     - Summary metrics: Effective N of trades ($N_{eff}$), normalized average EV, Wilson Lower Bound win rate ($WLB_{95\%}$), nominal win rate, total PnL, Max Drawdown, Sharpe/Sortino ratios.
     - Automatic IS/OOS degradation calculation across all hypotheses (H001-H008): $\Delta EV = EV_{IS} - EV_{OOS}$, Degradation Index $DI$, $\Delta WR$, Composite Stability Score $S_{comp}$, and Stability Verdict.
     - Verification attestations: explicit check confirming ZERO martingale / irrational asymmetric allocation dependencies, fixed risk / strict Kelly allocation compliance.
     - Saves reports to `reports/research_report.md` and `reports/research_report.json`.
  2. `run_research.py` (top-level executable script at project root):
     - Comprehensive CLI entrypoint: `python run_research.py [--data <path>] [--hypotheses H001,H002,...] [--payout 0.85] [--export-report <path>]`
     - Loads `data/EURUSD_M5_iq.csv`, executes rigid 50/25/25 chronological partitioning with boundary purging and warmup embargo.
     - Evaluates hypotheses H001-H008 across In-Sample (IS), Validation (VAL), and Out-of-Sample (OOS) partitions.
     - Automatically computes degradation metrics between IS and OOS for each hypothesis.
     - Displays ASCII summary table to stdout and exports Markdown and JSON reports.
  3. Acceptance & Integration Tests:
     - Added `iq_regime_adaptive/tests/test_reporting.py` covering report generation, JSON schema validation, Markdown formatting, degradation matrix, and governance audit.
- Full test suite execution:
  - Command: `.\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests`
  - Output:
    ```text
    Ran 141 tests in 5.877s
    OK
    ```
- Full pipeline execution:
  - Command: `.\.venv\Scripts\python.exe run_research.py`
  - Verbatim stdout:
    ```text
    ================================================================================
    IQ REGIME-ADAPTIVE: QUANTITATIVE RESEARCH & VERIFICATION ENGINE
    ================================================================================
    [1/5] Ingesting candle dataset: C:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\data\EURUSD_M5_iq.csv
          Loaded 20,000 bars | Span: 2026-06-22 10:20:00+00:00 -> 2026-09-25 20:55:00+00:00
    [2/5] Executing rigid chronological partitioning (50/25/25)...
          IS  partition: 10,000 bars (tradeable: 9,939)
          VAL partition: 5,000 bars (tradeable: 4,939)
          OOS partition: 5,000 bars (tradeable: 4,939)
    [3/5] Evaluating 8 hypotheses across IS, VAL, and OOS partitions (payout=85.0%)...
          [1/8] Running H001_RANGE_MEAN_REVERSION... Done (0.1s) | IS Trades: 21, OOS Trades: 13 | DI: +0.95 | S_comp: 35.0 (REJECTED)
          [2/8] Running H002_TREND_PULLBACK... Done (0.1s) | IS Trades: 20, OOS Trades: 20 | DI: +26.43 | S_comp: 24.8 (REJECTED)
          [3/8] Running H003_VOLATILITY_EXPANSION_BREAKOUT... Done (0.1s) | IS Trades: 20, OOS Trades: 20 | DI: +4.93 | S_comp: 24.1 (REJECTED)
          [4/8] Running H004_AUTOCORRELATION_MEAN_REVERSION... Done (0.3s) | IS Trades: 20, OOS Trades: 21 | DI: -10.57 | S_comp: 70.0 (ANTIFRAGILE)
          [5/8] Running H005_MTF_TREND_ALIGNMENT... Done (0.1s) | IS Trades: 20, OOS Trades: 10 | DI: +1.68 | S_comp: 35.0 (REJECTED)
          [6/8] Running H006_PAYOUT_FILTERED_DYNAMIC_EDGE... Done (0.1s) | IS Trades: 20, OOS Trades: 20 | DI: +3.36 | S_comp: 29.7 (REJECTED)
          [7/8] Running H007_VOLATILITY_CONTRACTION_SQUEEZE... Done (0.1s) | IS Trades: 20, OOS Trades: 20 | DI: -1.10 | S_comp: 70.0 (ANTIFRAGILE)
          [8/8] Running H008_REGIME_ADAPTIVE_ENSEMBLE_ROUTER... Done (189.4s) | IS Trades: 20, OOS Trades: 19 | DI: -4.11 | S_comp: 70.0 (ANTIFRAGILE)
    [4/5] Executing Anti-Martingale Governance Audit and compiling report...

    ================================================================================
    COMPARATIVE DEGRADATION MATRIX (IN-SAMPLE VS OUT-OF-SAMPLE)
    ================================================================================
    +--------+----------------------------+------+-------+--------+-------+--------+---------+--------+----------+--------+--------+-------------+
    | Hyp ID | Family                     | N_IS | WR_IS | EV_IS  | N_OOS | WR_OOS | WLB_OOS | EV_OOS | Delta EV | DI     | S_comp | Verdict     |
    +--------+----------------------------+------+-------+--------+-------+--------+---------+--------+----------+--------+--------+-------------+
    | H001   | STATISTICAL_MEAN_REVERSION | 21   | 50.0% | -0.075 | 13    | 46.2%  | 23.2%   | -0.146 | +0.071   | 0.95   | 35.0   | REJECTED    |
    | H002   | TREND_CONTINUATION         | 20   | 55.0% | +0.018 | 20    | 30.0%  | 14.5%   | -0.445 | +0.463   | 26.43  | 24.8   | REJECTED    |
    | H003   | MOMENTUM_BREAKOUT          | 20   | 50.0% | -0.075 | 20    | 30.0%  | 14.5%   | -0.445 | +0.370   | 4.93   | 24.1   | REJECTED    |
    | H004   | STATISTICAL_MICROSTRUCTURE | 20   | 55.0% | +0.018 | 21    | 65.0%  | 43.3%   | +0.203 | -0.185   | -10.57 | 70.0   | ANTIFRAGILE |
    | H005   | HIERARCHICAL_MULTISCALE    | 20   | 60.0% | +0.110 | 10    | 50.0%  | 23.7%   | -0.075 | +0.185   | 1.68   | 35.0   | REJECTED    |
    | H006   | PAYOUT_EV_OPTIMIZATION     | 20   | 60.0% | +0.110 | 20    | 40.0%  | 21.9%   | -0.260 | +0.370   | 3.36   | 29.7   | REJECTED    |
    | H007   | REGIME_TRANSITION_EDGE     | 20   | 45.0% | -0.168 | 20    | 55.0%  | 34.2%   | +0.018 | -0.185   | -1.10  | 70.0   | ANTIFRAGILE |
    | H008   | META_ENSEMBLE_ROUTER       | 20   | 50.0% | -0.075 | 19    | 66.7%  | 43.8%   | +0.233 | -0.308   | -4.11  | 70.0   | ANTIFRAGILE |
    +--------+----------------------------+------+-------+--------+-------+--------+---------+--------+----------+--------+--------+-------------+

    GOVERNANCE & VERIFICATION ATTESTATION:
      Anti-Martingale Audit : [VERIFIED_ZERO_MARTINGALE]
      Allocation Compliance : [FIXED_RISK_AND_STRICT_KELLY_COMPLIANT]
      Audited Trades Count  : 458
      Audit Passed          : True

    RECOMMENDED CHAMPION STRATEGY:
      Identifier     : H004_AUTOCORRELATION_MEAN_REVERSION (H004)
      Stability Score: 70.0 / 100
      OOS Win Rate   : 65.00%
      OOS EV         : +0.2025
      Verdict        : ANTIFRAGILE
      Edge Status    : CONDITIONAL

    [5/5] Exporting authoritative research reports...
          Markdown report saved: C:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\reports\research_report.md
          JSON report saved    : C:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\reports\research_report.json

    Pipeline successfully completed in 190.35 seconds.
    ================================================================================
    ```
- Generated authoritative artifacts:
  - `reports/research_report.md` (216 lines, 14,154 bytes)
  - `reports/research_report.json` (725 lines, 22,186 bytes)
- Python compilation check:
  `python -c "import py_compile, glob; [py_compile.compile(f, doraise=True) for f in glob.glob('iq_regime_adaptive/**/*.py', recursive=True)]; py_compile.compile('run_research.py', doraise=True); print('All Python files compile cleanly!')"`
  Output: `All Python files compile cleanly!`

## 2. Logic Chain
1. *From Reporting Requirements & JSON Specification*:
   - Section 4.2 of `explorer_survey_iq_3/report.md` specified an exact structured JSON schema with `hypothesisId`, `payoutTested`, `breakevenHurdle`, `partitions` (`inSample`, `validation`, `outOfSample`), `degradation` (`deltaEV`, `degradationIndex`, `winRateDrop`, `stabilityScore`, `verdict`), and `governanceVerdict`.
   - `iq_regime_adaptive/reports/generator.py` was built around `HypothesisEvaluation`, `VerificationAttestation`, `ResearchReport`, and `QuantitativeReportGenerator`.
   - All partition metrics ($N$, $N_{eff}$, Nominal WR, $WLB_{95\%}$, EV, Total PnL, MaxDD, Profit Factor, Sharpe, Sortino) are extracted from `BacktestMetrics` and serialized cleanly.
2. *From Governance & Anti-Martingale Verification Attestation*:
   - `run_governance_audit` conducts both formal algorithmic verification via `verify_anti_martingale_invariant` (verifying $\partial \text{Stake} / \partial \text{LossStreak} = 0$ and monotonic balance scaling for Kelly and fixed models) and empirical ledger verification across all 458 backtest trades (verifying that after every loss, stake never increases and stake never breaches the 2% equity cap).
   - This formally and empirically guarantees zero martingale or irrational loss-chasing multiplier dependencies.
3. *From Top-Level CLI Orchestration (`run_research.py`)*:
   - Built a comprehensive entrypoint supporting `--data`, `--hypotheses`, `--payout`, `--export-report`, `--is-ratio`, `--val-ratio`, `--oos-ratio`, `--warmup`, `--risk-method`, etc.
   - Enforces 50/25/25 chronological partitioning via `DataPartitioner`, ensuring zero lookahead and zero state leakage.
   - Discovers and evaluates all requested hypotheses, evaluates IS vs OOS degradation, renders an aligned ASCII summary table to stdout, and exports both Markdown and JSON reports.
4. *From Acceptance Testing*:
   - Created `test_reporting.py` with 12 tests validating evaluation creation, JSON schema compliance, Markdown formatting, ASCII table alignment, report save/reload, governance audit passing, adversarial detection of martingale doubling, and programmatic CLI execution.
   - All 141 tests in the repository pass cleanly without errors.

## 3. Caveats
- Runtime characteristics: H001 through H007 execute across 20,000 bars in under 1 second total. H008 (Meta-Ensemble Router) evaluates a 5-tier decision tree across all bars, which requires approximately 3 minutes across IS, VAL, and OOS partitions. Users desiring faster preliminary sweeps can filter hypotheses via `--hypotheses H001,H002,H004,H006,H007`.
- Real-world market payouts: Payout defaults to 85% ($B = 0.85$, $P_{BE} = 54.05\%$). Hypotheses can be tested against other broker payout scenarios (e.g. 80%, 90%) using the `--payout` argument.

## 4. Conclusion
Milestone 3 is complete, fully functional, and verified:
- `iq_regime_adaptive/reports/generator.py` and `reports/__init__.py` provide full quantitative verification reporting in Markdown and JSON formats.
- `run_research.py` provides the authoritative top-level executable entrypoint.
- `iq_regime_adaptive/tests/test_reporting.py` provides complete test coverage.
- All 141 tests in `unittest discover iq_regime_adaptive/tests` pass with zero failures.
- `run_research.py` executed end-to-end on `data/EURUSD_M5_iq.csv`, successfully generating `reports/research_report.md` and `reports/research_report.json`.

## 5. Verification Method
To independently verify:
1. Run the entire test discovery suite:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover iq_regime_adaptive/tests
   ```
   *Expected outcome*: 141 tests run and pass cleanly (`OK`).
2. Run the reporting tests specifically:
   ```powershell
   .\.venv\Scripts\python.exe -m unittest iq_regime_adaptive.tests.test_reporting
   ```
   *Expected outcome*: 12 tests run and pass cleanly.
3. Run the research pipeline end-to-end:
   ```powershell
   .\.venv\Scripts\python.exe run_research.py --hypotheses H001,H004,H007
   ```
   *Expected outcome*: Ingests dataset, runs 50/25/25 chronological partitioning, evaluates hypotheses, displays ASCII table, audits risk governance, and writes reports to `reports/research_report.md` and `reports/research_report.json`.
4. Run full 8-hypothesis authoritative pipeline:
   ```powershell
   .\.venv\Scripts\python.exe run_research.py
   ```
   *Expected outcome*: Executes all 8 hypotheses H001-H008 across IS, VAL, and OOS partitions and generates authoritative reports with zero crashes.
